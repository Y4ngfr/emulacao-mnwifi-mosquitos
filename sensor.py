import argparse
import json
import math
import os
import random
import socket
import struct
import subprocess
import threading
import time
from collections import deque

import numpy as np
import paho.mqtt.client as mqtt

import definicao_bytes as bytes
import modelo_leve
import util_rtp as rtp
from metricas import MetricasSensor

BROKERIP = None
MQTT_PORTA = 1883
TENTATIVAS_MQTT = 3
TIMEOUT_MQTT_S = 30.0
BACKOFF_MQTT_S = 2.0
TOPICO_STREAM = "stream"
TOPICO_SINAL = "sinal"
DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Dataset-processado")
DIR_BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_AMBIENTE = os.path.join(DIR_BASE, "cenario_ambiente.json")

SSRC = None
CLUSTER = 0
PAYLOAD_TYPE = 96
RTP_PORTA = 9001
INTERVALO_CAPTURA_S = 2 * modelo_leve.WINDOW_SIZE / modelo_leve.SR
TAXA_AMOSTRAGEM_RTP = 8000
AMOSTRAS_POR_BLOCO_RTP = 160

_CACHE = None
_INFERENCIA = None

# variavel global trheading safe. Inicialmente com estado inicial de flag = false.
pronto = threading.Event() 
iniciar_experimento = threading.Event()
subscricao_controle = threading.Event()

def on_publish(client, userdata, mid, reason_code, properties):
    pronto.set()    # flag passa a ser true


def on_message(client, userdata, msg):
    if (
        msg.topic == bytes.TOPICO_INICIAR_EXPERIMENTO
        and msg.payload == bytes.INICIAR_EXPERIMENTO
    ):
        iniciar_experimento.set()

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    subscricao_controle.set()

def iniciar_conexao_mqtt(sensor_id):
    cliente_pub = None

    for tentativa in range(1, TENTATIVAS_MQTT + 1):
        try:
            pronto.clear()
            subscricao_controle.clear()

            cliente_pub = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=f"sensor_{sensor_id}",
            )
            cliente_pub.on_publish = on_publish
            cliente_pub.on_message = on_message
            cliente_pub.on_subscribe = on_subscribe
            cliente_pub.connect(BROKERIP, MQTT_PORTA)
            cliente_pub.loop_start()
            cliente_pub.publish(
                TOPICO_SINAL, bytes.ESTABELECENDO_CONEXAO, qos=1
            )

            if not pronto.wait(timeout=TIMEOUT_MQTT_S):
                raise TimeoutError("confirmacao de publish")

            cliente_pub.subscribe(bytes.TOPICO_INICIAR_EXPERIMENTO, qos=1)
            if not subscricao_controle.wait(timeout=TIMEOUT_MQTT_S):
                raise TimeoutError("confirmacao de subscribe")

            return cliente_pub, True
        except Exception as erro:
            print(f"Tentativa {tentativa}/{TENTATIVAS_MQTT} MQTT falhou: {erro}")
            if cliente_pub is not None:
                try:
                    cliente_pub.loop_stop()
                    cliente_pub.disconnect()
                except Exception:
                    pass
            if tentativa < TENTATIVAS_MQTT:
                time.sleep(BACKOFF_MQTT_S)

    return cliente_pub, False


def carregar_dataset(dataset_dir=DATASET_DIR):
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    with open(os.path.join(dataset_dir, "meta.json")) as f:
        meta = json.load(f)

    window = int(meta["window"])
    _CACHE = {}
    for classe, info in meta["classes"].items():
        if int(info["janelas"]) <= 0:
            continue
        classe_dir = os.path.join(dataset_dir, classe)
        nomes = sorted(n for n in os.listdir(classe_dir) if n.endswith(".npy"))
        _CACHE[int(classe)] = [
            np.load(
                os.path.join(classe_dir, nome),
                mmap_mode="r",
                allow_pickle=False,
            )
            for nome in nomes
        ]

    return _CACHE


def carregar_inferencia(backend="numpy"):
    global _INFERENCIA
    if _INFERENCIA is None:
        _INFERENCIA = modelo_leve.criar_inferencia(backend=backend)
    return _INFERENCIA


def capturar_amostra_de_audio(densidade):
    dataset = carregar_dataset()
    classes_mosquito = [classe for classe in (0, 1, 2) if classe in dataset]
    classes_fundo = [classe for classe in (3,) if classe in dataset]

    if not classes_mosquito:
        classes_mosquito = sorted(dataset)
    if not classes_fundo:
        classes_fundo = [classe for classe in sorted(dataset) if classe not in classes_mosquito]
    if not classes_fundo:
        classes_fundo = sorted(dataset)

    p_presenca = 1.0 - math.exp(-max(0.0, densidade))
    if random.random() < p_presenca and classes_mosquito:
        classe = random.choices(
            classes_mosquito,
            weights=[len(dataset[classe]) for classe in classes_mosquito],
            k=1,
        )[0]
    else:
        classe = random.choice(classes_fundo)

    janelas = dataset[classe]
    indice_a = random.randrange(len(janelas))
    indice_b = random.randrange(len(janelas)) # 2.4 s
    audio = np.concatenate([janelas[indice_a], janelas[indice_b]])
    return audio, classe, indice_a, indice_b


def inferir_leve(audio):
    inferencia = carregar_inferencia()
    resultado = inferencia.prever(audio)
    return resultado


def adicionar_ruido_gaussiano(sinal, snr_db):
    sinal = np.asarray(sinal, dtype=np.float32)
    if snr_db is None or not math.isfinite(float(snr_db)):
        return sinal

    p_sinal = float(np.mean(sinal ** 2))
    if p_sinal <= 0.0:
        return sinal

    ruido = np.random.normal(0.0, 1.0, size=sinal.shape).astype(np.float32)
    p_ruido = float(np.mean(ruido ** 2))
    if p_ruido <= 0.0:
        return sinal

    fator = math.sqrt(p_sinal / (p_ruido * (10.0 ** (float(snr_db) / 10.0))))
    sinal_com_ruido = sinal + (ruido * fator)
    pico = float(np.max(np.abs(sinal_com_ruido)))
    if pico > 1.0:
        sinal_com_ruido = sinal_com_ruido / pico

    return sinal_com_ruido.astype(np.float32)


def comprimir_adpcm(audio, taxa_amostragem=8000):
    pcm = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    comando = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "f32le", "-ar", str(taxa_amostragem), "-ac", "1", "-i", "pipe:0",
        "-map", "0:a", "-c:a", "adpcm_ima_wav", "-f", "data", "pipe:1",
    ]
    processo = subprocess.run(
        comando,
        input=pcm.tobytes(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    return processo.stdout


def monitorar(densidade, ruido):
    audio, classe, indice_a, indice_b = capturar_amostra_de_audio(densidade)
    audio = adicionar_ruido_gaussiano(audio, ruido)
    return audio, inferir_leve(audio), classe


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensor de audio")
    parser.add_argument(
        "--sensor-id", type=int, required=True, help="ID do sensor"
    )
    parser.add_argument(
        "--cluster", type=int, default=0, help="Cluster/AP do sensor"
    )
    parser.add_argument(
        "--servidor-ip", required=True, help="IP do servidor"
    )
    args = parser.parse_args()

    BROKERIP = args.servidor_ip
    SSRC = args.sensor_id + 1
    CLUSTER = args.cluster

    cliente_pub, resultado = iniciar_conexao_mqtt(args.sensor_id)

    if resultado == False:
        print("Timeout - Conexão MQTT ou assinatura não estabelecida")
        exit(1)

    # Criando socket udp para comunicação RTP
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    carregar_dataset()

    print("AGUARDANDO_EXPERIMENTO")
    iniciar_experimento.wait()

    metricas = MetricasSensor(args.sensor_id, cluster=args.cluster)
    metricas.salvar()

    cliente_pub.publish(TOPICO_SINAL, bytes.INICIANDO_MONITORAMENTO, qos=1)


    fila_envio = deque()
    iterador_rtp = None
    classe_stream = None
    proxima_captura = time.monotonic()
    proximo_pacote = None
    densidade = 0.0
    ruido = 0.0
    ultima_leitura_ambiente = 0.0

    while True:
        agora = time.monotonic()
        if agora - ultima_leitura_ambiente >= 1.0:
            ultima_leitura_ambiente = agora
            try:
                with open(CAMINHO_AMBIENTE, encoding="utf-8") as arquivo:
                    ambiente = json.load(arquivo)
                clusters = ambiente.get("clusters", {})
                chave = str(CLUSTER) if str(CLUSTER) in clusters else "0"
                cluster = clusters[chave]
                densidade = float(cluster["densidade_mosquitos"])
                ruido = float(cluster["ruido_audio"])
            except (OSError, ValueError, KeyError, TypeError):
                pass

        if iterador_rtp is not None and agora >= proximo_pacote:
            try:
                pacote, duracao = next(iterador_rtp)
                udp_sock.sendto(pacote, (BROKERIP, RTP_PORTA))
                proximo_pacote = time.monotonic() + duracao
            except StopIteration:
                metricas.registrar_envio_audio()
                metricas.salvar()
                iterador_rtp = None
                classe_stream = None
                proximo_pacote = None

        if agora >= proxima_captura:
            audio, resultado, classe = monitorar(densidade, ruido)
            metricas.registrar_inferencia(resultado, classe)
            metricas.salvar()

            if resultado["p_mosquito"] >= resultado["p_nao_mosquito"]:
                fila_envio.append((audio, classe))

            proxima_captura = time.monotonic() + INTERVALO_CAPTURA_S

        if iterador_rtp is None and fila_envio:
            audio, classe_stream = fila_envio.popleft()
            audio_adpcm = comprimir_adpcm(audio)
            iterador_rtp = rtp.iterar_pacotes_rtp(
                adpcm_bytes=audio_adpcm,
                taxa_amostragem=TAXA_AMOSTRAGEM_RTP,
                ssrc=SSRC,
                payload_type=PAYLOAD_TYPE,
                amostras_por_bloco=AMOSTRAS_POR_BLOCO_RTP,
                classe_verdadeira=classe_stream,
            )
            proximo_pacote = time.monotonic()

        proximos = [proxima_captura]
        if iterador_rtp is not None:
            proximos.append(proximo_pacote)
        time.sleep(max(0.0, min(proximos) - time.monotonic()))
