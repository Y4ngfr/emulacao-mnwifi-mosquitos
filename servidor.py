import argparse
import csv
import datetime
import json
import os
import socket
import struct
import subprocess
import threading
import time
import wave

import numpy as np
import paho.mqtt.client as mqtt

from definicao_bytes import (
    ESTABELECENDO_CONEXAO,
    FINALIZAR_EXPERIMENTO,
    INICIANDO_MONITORAMENTO,
    INICIAR_EXPERIMENTO,
    TOPICO_FINALIZAR_EXPERIMENTO,
    TOPICO_INICIAR_EXPERIMENTO,
    TOPICO_SOLICITAR_EXPERIMENTO,
)
from util_rtp import RTP_EXT_PROFILE

BROKERIP = None
MQTT_PORTA = 1883
TOPICO_SINAL = "sinal"
RTP_PORTA = 9001

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DIR_AUDIOS = os.path.join(DIR_BASE, "audios_recebidos")
DIR_RESULTADOS = os.path.join(DIR_BASE, "resultados")
DIR_METRICAS_STREAMS = os.path.join(DIR_BASE, "logs", "metricas_streams")
DIR_METRICAS_REDE = os.path.join(DIR_BASE, "logs", "metricas_rede")
INTERVALO_SNAPSHOT_REDE_S = 1.0
GRACE_FINALIZACAO_S = 1.0
CAMINHO_MODELO = os.path.join(DIR_BASE, "modelos", "model_float16.tflite")
CAMINHO_CSV = os.path.join(DIR_RESULTADOS, "servidor_inferencia.csv")
CAMINHO_DONE = os.path.join(DIR_RESULTADOS, "servidor_inferencia.done")
CAMINHO_AMBIENTE = os.path.join(DIR_BASE, "cenario_ambiente.json")

AMOSTRAS_ALVO = 19968
TAMANHO_BLOCO_ADPCM = 1024
TAXA_AMOSTRAGEM = 8000
INICIO_SERVIDOR = time.time()
CAMINHO_LOG_REDE = os.path.join(
    DIR_METRICAS_REDE, f"rede_{int(INICIO_SERVIDOR * 1000)}.log"
)

buffers_rtp = {}
estados_stream = {}
classes_por_audio = {}
audio_recebidos = 0
metricas_rede = {
    "primeiro_recv_ns": None,
    "ultimo_recv_ns": None,
    "bytes_totais": 0,
    "pacotes_recebidos": 0,
    "pacotes_perdidos": 0,
    "soma_latencia_ns": 0,
}
_audios_pendentes = []
_streams_pendentes = []
_buffer_bloqueio = threading.Lock()
_finalizando = False
_finalizando_bloqueio = threading.Lock()
_inferencia = None
_inferencia_bloqueio = threading.Lock()
_metricas_rede_bloqueio = threading.Lock()
_ultimo_snapshot_rede_ns = 0


def _metadados_ambiente():
    metadados = {
        "cenario_id": None,
        "estagio": None,
        "indice_estagio": None,
        "fator_variado": None,
        "valor_fator": None,
        "densidade_mosquitos": None,
        "ruido_audio": None,
        "qualidade_transmissao": None,
        "n_clusters": None,
        "n_sensores": None,
        "gw_icmp_ok": None,
        "gw_icmp_falhas": None,
        "gw_icmp_tentativas": None,
        "gw_icmp_sensores": "",
    }
    try:
        with open(CAMINHO_AMBIENTE, encoding="utf-8") as arquivo:
            ambiente = json.load(arquivo)
    except (OSError, ValueError):
        return metadados

    clusters = ambiente.get("clusters", {})
    cluster = clusters.get("0")
    if not isinstance(cluster, dict) and clusters:
        cluster = next(iter(clusters.values()))
    if not isinstance(cluster, dict):
        cluster = {}

    def numero(valor):
        try:
            return None if valor is None else float(valor)
        except (TypeError, ValueError):
            return None

    def inteiro(valor):
        try:
            return None if valor is None else int(valor)
        except (TypeError, ValueError):
            return None

    metadados.update(
        {
            "cenario_id": inteiro(
                ambiente.get("cenario_id", ambiente.get("id_cenario"))
            ),
            "estagio": inteiro(ambiente.get("estagio")),
            "indice_estagio": inteiro(ambiente.get("indice_estagio")),
            "fator_variado": ambiente.get("fator_variado"),
            "valor_fator": numero(ambiente.get("valor_fator")),
            "densidade_mosquitos": numero(cluster.get("densidade_mosquitos")),
            "ruido_audio": numero(cluster.get("ruido_audio")),
            "qualidade_transmissao": numero(cluster.get("qualidade_transmissao")),
            "n_clusters": inteiro(ambiente.get("n_clusters", len(clusters))),
            "n_sensores": inteiro(ambiente.get("n_sensores")),
            "gw_icmp_ok": inteiro(ambiente.get("gw_icmp_ok")),
            "gw_icmp_falhas": inteiro(ambiente.get("gw_icmp_falhas")),
            "gw_icmp_tentativas": inteiro(ambiente.get("gw_icmp_tentativas")),
            "gw_icmp_sensores": ambiente.get("gw_icmp_sensores", ""),
        }
    )
    return metadados


def cabecalho_adpcm(tamanho_dados):
    tamanho_fmt = 18
    fmt = struct.pack(
        "<HHIIHHH",
        0x0011,
        1,
        TAXA_AMOSTRAGEM,
        4000,
        TAMANHO_BLOCO_ADPCM,
        4,
        0,
    )
    riff = b"RIFF" + struct.pack(
        "<I", 4 + 8 + tamanho_fmt + 8 + tamanho_dados
    ) + b"WAVE"
    return (
        riff
        + b"fmt "
        + struct.pack("<I", tamanho_fmt)
        + fmt
        + b"data"
        + struct.pack("<I", tamanho_dados)
    )


def decodificar_adpcm(adpcm_bytes):
    cabecalho = cabecalho_adpcm(len(adpcm_bytes))
    processo = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "wav", "-i", "pipe:0",
            "-f", "s16le", "-ac", "1", "-ar", str(TAXA_AMOSTRAGEM), "pipe:1",
        ],
        input=cabecalho + adpcm_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    amostras = np.frombuffer(processo.stdout, dtype="<i2")
    if amostras.size < AMOSTRAS_ALVO:
        amostras = np.pad(amostras, (0, AMOSTRAS_ALVO - amostras.size))
    return amostras[:AMOSTRAS_ALVO].astype("<i2")


def escrever_wav(caminho, amostras):
    with wave.open(caminho, "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA_AMOSTRAGEM)
        arquivo.writeframes(np.asarray(amostras, dtype="<i2").tobytes())


def ler_wav(caminho):
    with wave.open(caminho, "rb") as arquivo:
        dados = arquivo.readframes(arquivo.getnframes())
    return np.frombuffer(dados, dtype="<i2").astype(np.float32) / 32768.0


def sensor_id_do_audio(caminho):
    partes = os.path.basename(caminho).split("_")
    try:
        return int(partes[1]) - 1
    except (IndexError, ValueError):
        return ""


def carregar_inferencia():
    global _inferencia
    if _inferencia is None:
        with _inferencia_bloqueio:
            if _inferencia is None:
                import modelo_leve

                _inferencia = modelo_leve.criar_inferencia(
                    caminho_modelo=CAMINHO_MODELO
                )
    return _inferencia


def remover_audios_processados(caminhos):
    removidos = 0
    for caminho in caminhos:
        try:
            os.remove(caminho)
            removidos += 1
        except OSError:
            continue
        classes_por_audio.pop(caminho, None)
    print(f"Áudios processados removidos: {removidos}", flush=True)


def processar_inferencia_final():
    if os.path.exists(CAMINHO_DONE):
        os.remove(CAMINHO_DONE)

    print("Inferência final do servidor iniciada", flush=True)
    os.makedirs(DIR_RESULTADOS, exist_ok=True)
    inferencia = carregar_inferencia()

    caminhos = []
    if os.path.isdir(DIR_AUDIOS):
        for nome in sorted(os.listdir(DIR_AUDIOS)):
            if not nome.endswith(".wav"):
                continue
            caminho = os.path.join(DIR_AUDIOS, nome)
            try:
                if os.path.getmtime(caminho) >= INICIO_SERVIDOR:
                    caminhos.append(caminho)
            except OSError:
                continue

    with open(CAMINHO_CSV, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if os.path.getsize(CAMINHO_CSV) == 0:
            escritor.writerow([
                "timestamp",
                "sensor_id",
                "audio",
                "classe_verdadeira",
                "classe_prevista",
            ])

        for caminho in caminhos:
            resultado = inferencia.prever_classes(ler_wav(caminho))
            escritor.writerow([
                datetime.datetime.now().isoformat(timespec="seconds"),
                sensor_id_do_audio(caminho),
                os.path.basename(caminho),
                classes_por_audio.get(caminho, ""),
                resultado["classe_prevista"],
            ])
            arquivo.flush()

    remover_audios_processados(caminhos)
    salvar_snapshot_rede()

    with open(CAMINHO_DONE, "w", encoding="utf-8") as arquivo:
        arquivo.write(datetime.datetime.now().isoformat(timespec="seconds"))

    print(
        "Inferência final concluída: {} áudios -> {}".format(
            len(caminhos), CAMINHO_CSV
        )
    )


def registrar_skip_inferencia():
    os.makedirs(DIR_RESULTADOS, exist_ok=True)
    with open(CAMINHO_CSV, "a", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        if os.path.getsize(CAMINHO_CSV) == 0:
            escritor.writerow([
                "timestamp",
                "sensor_id",
                "audio",
                "classe_verdadeira",
                "classe_prevista",
            ])
        escritor.writerow([
            datetime.datetime.now().isoformat(timespec="seconds"),
            "",
            "SKIP_DECODIFICACAO_CLASSIFICACAO",
            "",
            "skip",
        ])


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"Conectado ao Mosquitto: {reason_code}")
    client.subscribe([
        (TOPICO_SINAL, 1),
        (TOPICO_SOLICITAR_EXPERIMENTO, 1),
        (TOPICO_FINALIZAR_EXPERIMENTO, 1),
    ])


def on_subscribe(client, userdata, mid, reason_code_list, properties):
    print("SERVIDOR_PRONTO")


def on_message(client, userdata, msg):
    if msg.payload in (ESTABELECENDO_CONEXAO, INICIANDO_MONITORAMENTO):
        return
    if (
        msg.topic == TOPICO_SOLICITAR_EXPERIMENTO
        and msg.payload == INICIAR_EXPERIMENTO
    ):
        client.publish(TOPICO_INICIAR_EXPERIMENTO, INICIAR_EXPERIMENTO, qos=1)
        print("Comando de inicio enviado aos sensores")
    elif (
        msg.topic == TOPICO_FINALIZAR_EXPERIMENTO
        and msg.payload == FINALIZAR_EXPERIMENTO
    ):
        threading.Thread(target=finalizar_servidor, daemon=True).start()
    else:
        print(f"Sinal desconhecido em {msg.topic}: {msg.payload!r}")


def registrar_audio(ssrc, pacotes, classe_verdadeira):
    global audio_recebidos

    if not pacotes:
        return time.time()

    agora = time.time()
    with _metricas_rede_bloqueio:
        audio_recebidos += 1
    return agora


def preparar_metrica_stream(ssrc, estado, agora):
    duracao_recepcao_s = (
        estado["ultimo_recv_ns"] - estado["primeiro_recv_ns"]
    ) / 1e9
    dados = {
        "timestamp": datetime.datetime.fromtimestamp(agora).isoformat(timespec="seconds"),
        "timestamp_epoch": agora,
        "sensor_id": ssrc - 1,
        "latencia_s": (
            estado["ultimo_recv_ns"] - estado["primeiro_send_ns"]
        ) / 1e9,
        "throughput_bps": (
            estado["bytes_totais"] * 8 / duracao_recepcao_s
            if duracao_recepcao_s > 0
            else 0.0
        ),
        "pacotes_recebidos": estado["pacotes_recebidos"],
        "pacotes_perdidos": estado["pacotes_perdidos"],
    }
    dados.update(_metadados_ambiente())
    with _buffer_bloqueio:
        _streams_pendentes.append((ssrc, agora, dados))
    return dados


def gravar_audio(ssrc, adpcm, classe_verdadeira, agora):
    nome = os.path.join(
        DIR_AUDIOS, f"audio_{ssrc}_{int(agora * 1000)}.wav"
    )
    escrever_wav(nome, decodificar_adpcm(adpcm))
    classes_por_audio[nome] = int(classe_verdadeira)
    return nome


def gravar_metricas_stream(ssrc, agora, dados):
    nome = os.path.join(
        DIR_METRICAS_STREAMS,
        f"stream_{ssrc}_{int(agora * 1000)}.log",
    )
    with open(nome, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, indent=2)
    os.utime(nome, (agora, agora))


def descarregar_buffer():
    with _buffer_bloqueio:
        _audios_pendentes.clear()
        streams = list(_streams_pendentes)
        _streams_pendentes.clear()

    if streams:
        os.makedirs(DIR_METRICAS_STREAMS, exist_ok=True)
        for ssrc, agora, dados in streams:
            gravar_metricas_stream(ssrc, agora, dados)

    print(
        f"Flush de streams concluído: {len(streams)} streams",
        flush=True,
    )


def finalizar_servidor():
    global _finalizando
    with _finalizando_bloqueio:
        if _finalizando:
            return
        _finalizando = True

    print("Comando de finalização recebido", flush=True)
    time.sleep(GRACE_FINALIZACAO_S)
    print("SKIP: decodificação e classificação no servidor", flush=True)
    classes_por_audio.clear()
    descarregar_buffer()
    salvar_snapshot_rede()
    registrar_skip_inferencia()

    with open(CAMINHO_DONE, "w", encoding="utf-8") as arquivo:
        arquivo.write(datetime.datetime.now().isoformat(timespec="seconds"))

    print(
        "Finalização do servidor concluída (skip de decodificação/classificação)",
        flush=True,
    )


def atualizar_metricas_rede(bytes_pacote, latencia_ns, recv_ns, perdidos=0):
    with _metricas_rede_bloqueio:
        if metricas_rede["primeiro_recv_ns"] is None:
            metricas_rede["primeiro_recv_ns"] = recv_ns
        metricas_rede["ultimo_recv_ns"] = recv_ns
        metricas_rede["bytes_totais"] += bytes_pacote
        metricas_rede["pacotes_recebidos"] += 1
        metricas_rede["pacotes_perdidos"] += perdidos
        metricas_rede["soma_latencia_ns"] += latencia_ns


def salvar_snapshot_rede():
    with _metricas_rede_bloqueio:
        primeiro = metricas_rede["primeiro_recv_ns"]
        ultimo = metricas_rede["ultimo_recv_ns"]
        duracao_s = (ultimo - primeiro) / 1e9 if primeiro is not None and ultimo > primeiro else 0.0
        bytes_totais = metricas_rede["bytes_totais"]
        recebidos = metricas_rede["pacotes_recebidos"]
        soma_latencia_ns = metricas_rede["soma_latencia_ns"]
        agora = time.time()
        dados = {
            "timestamp": datetime.datetime.fromtimestamp(agora).isoformat(
                timespec="seconds"
            ),
            "timestamp_epoch": agora,
            "bytes_totais": bytes_totais,
            "duracao_recepcao_s": round(duracao_s, 6),
            "throughput_bps": (
                round(bytes_totais * 8 / duracao_s, 2) if duracao_s > 0 else 0.0
            ),
            "latencia_media_pacote_s": (
                round(soma_latencia_ns / recebidos / 1e9, 9)
                if recebidos > 0
                else 0.0
            ),
            "soma_latencia_ns": soma_latencia_ns,
            "pacotes_recebidos": recebidos,
            "pacotes_perdidos": metricas_rede["pacotes_perdidos"],
            "audio_recebidos": audio_recebidos,
        }
    dados.update(_metadados_ambiente())

    os.makedirs(DIR_METRICAS_REDE, exist_ok=True)
    with open(CAMINHO_LOG_REDE, "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")


def salvar_snapshot_periodico(now_ns):
    global _ultimo_snapshot_rede_ns
    if now_ns - _ultimo_snapshot_rede_ns >= INTERVALO_SNAPSHOT_REDE_S * 1e9:
        salvar_snapshot_rede()
        _ultimo_snapshot_rede_ns = now_ns


def receber_rtp():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", RTP_PORTA))
    print(f"Receptor RTP em 0.0.0.0:{RTP_PORTA}...")

    while True:
        data, _ = sock.recvfrom(2048)
        recv_ns = time.monotonic_ns()
        if len(data) < 12:
            continue

        seq, ts, ssrc = struct.unpack("!HII", data[2:12])
        marker = (data[1] >> 7) & 0x1

        send_mono_ns = None
        classe_verdadeira = -1
        offset = 12
        if data[0] & 0x10:
            if len(data) < 16:
                continue
            perfil, extensao_palavras = struct.unpack("!HH", data[12:16])
            offset = 16 + extensao_palavras * 4
            if (
                perfil == RTP_EXT_PROFILE
                and extensao_palavras >= 2
                and len(data) >= 24
            ):
                send_mono_ns = struct.unpack("!Q", data[16:24])[0]
            if (
                perfil == RTP_EXT_PROFILE
                and extensao_palavras >= 3
                and len(data) >= 28
            ):
                classe_verdadeira = struct.unpack("!I", data[24:28])[0]

        if offset > len(data) or send_mono_ns is None:
            continue

        payload = data[offset:]

        buffers_rtp.setdefault(ssrc, {})[seq] = payload

        estado = estados_stream.get(ssrc)
        perdidos_pacote = 0
        if estado is None:
            estado = {
                "primeiro_send_ns": send_mono_ns,
                "primeiro_recv_ns": recv_ns,
                "ultimo_recv_ns": recv_ns,
                "ultimo_seq": seq,
                "bytes_totais": len(data),
                "pacotes_recebidos": 1,
                "pacotes_perdidos": seq,
                "classe_verdadeira": classe_verdadeira,
            }
            estados_stream[ssrc] = estado
        else:
            if seq != estado["ultimo_seq"]:
                perdidos = (seq - estado["ultimo_seq"] - 1) & 0xFFFF
                if perdidos < 0x8000:
                    estado["pacotes_perdidos"] += perdidos
                    perdidos_pacote = perdidos
                estado["ultimo_seq"] = seq
                estado["bytes_totais"] += len(data)
                estado["pacotes_recebidos"] += 1
            if classe_verdadeira >= 0:
                estado["classe_verdadeira"] = classe_verdadeira
        estado["ultimo_recv_ns"] = recv_ns

        atualizar_metricas_rede(
            len(data),
            recv_ns - send_mono_ns,
            recv_ns,
            perdidos_pacote,
        )
        salvar_snapshot_periodico(recv_ns)

        if marker:
            agora = registrar_audio(
                ssrc,
                buffers_rtp.pop(ssrc, {}),
                estado.get("classe_verdadeira", -1),
            )
            estado = estados_stream.pop(ssrc, None)
            if estado is not None:
                preparar_metrica_stream(ssrc, estado, agora)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor")
    parser.add_argument(
        "--servidor-ip", required=True, help="IP do servidor"
    )
    args = parser.parse_args()

    BROKERIP = args.servidor_ip

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="broker")
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    cliente.on_subscribe = on_subscribe
    cliente.connect(BROKERIP, MQTT_PORTA)
    cliente.loop_start()

    try:
        receber_rtp()
    except KeyboardInterrupt:
        print("\nEncerrando broker...")
    finally:
        cliente.loop_stop()
        cliente.disconnect()
