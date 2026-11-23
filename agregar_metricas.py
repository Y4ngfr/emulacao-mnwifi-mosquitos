import csv
import json
import os

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_METRICAS_SENSORES = os.path.join(DIR_BASE, "logs", "metricas_sensores")
CAMINHO_SAIDA = os.path.join(DIR_BASE, "resultados", "metricas_sensores.csv")
DIR_STREAMS = os.path.join(DIR_BASE, "logs", "metricas_streams")
CAMINHO_STREAMS = os.path.join(DIR_BASE, "resultados", "metricas_streams.csv")
DIR_REDE = os.path.join(DIR_BASE, "logs", "metricas_rede")
CAMINHO_REDE = os.path.join(DIR_BASE, "resultados", "metricas_rede.csv")
CAMINHO_EXPLORATORIA = os.path.join(DIR_BASE, "resultados", "metricas_exploratoria.csv")

METADADOS = [
    "cenario_id",
    "estagio",
    "indice_estagio",
    "fator_variado",
    "valor_fator",
    "densidade_mosquitos",
    "ruido_audio",
    "qualidade_transmissao",
    "n_clusters",
    "n_sensores",
    "gw_icmp_ok",
    "gw_icmp_falhas",
    "gw_icmp_tentativas",
    "gw_icmp_sensores",
]

COLUNAS = [
    "sensor_id",
    "cluster",
    "audios_enviados",
    "mosquitos_identificados",
    "acertos",
    "erros",
    "falsos_positivos",
    "falsos_negativos",
    "taxa_acerto",
    "inferencias_nao_mosquito",
] + METADADOS

COLUNAS_CONSOLIDADAS = ["run_id"] + COLUNAS

COLUNAS_STREAMS = [
    "run_id",
    "sensor_id",
    "timestamp",
    "latencia_s",
    "throughput_bps",
    "pacotes_recebidos",
    "pacotes_perdidos",
] + METADADOS

COLUNAS_REDE = [
    "throughput_bps",
    "latencia_media_pacote_s",
    "pacotes_recebidos",
    "pacotes_perdidos",
    "audio_recebidos",
] + METADADOS

COLUNAS_REDE_CONSOLIDADAS = ["run_id"] + COLUNAS_REDE

COLUNAS_EXPLORATORIA = [
    "run_id",
    "cenario_id",
    "estagio",
    "fator_variado",
    "valor_fator",
    "densidade_mosquitos",
    "ruido_audio",
    "qualidade_transmissao",
    "n_clusters",
    "n_sensores",
    "gw_icmp_ok",
    "gw_icmp_falhas",
    "gw_icmp_tentativas",
    "gw_icmp_sensores",
    "inferencias",
    "inferencias_nao_mosquito",
    "mosquitos_identificados",
    "acertos",
    "erros",
    "falsos_positivos",
    "falsos_negativos",
    "acuracia",
    "precisao",
    "recall",
    "f1",
    "audios_enviados",
    "audio_recebidos",
    "streams_completas",
    "taxa_entrega",
    "throughput_bps",
    "latencia_media_pacote_s",
    "pacotes_recebidos",
    "pacotes_perdidos",
]

CONTADORES_SENSOR = [
    "inferencias",
    "inferencias_nao_mosquito",
    "mosquitos_identificados",
    "acertos",
    "erros",
    "falsos_positivos",
    "falsos_negativos",
    "audios_enviados",
]


def _numero(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _inteiro(valor):
    if valor is None or valor == "":
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _metadados(dados):
    resultado = {}
    for chave in METADADOS:
        if chave == "fator_variado":
            resultado[chave] = dados.get(chave)
        else:
            resultado[chave] = _numero(dados.get(chave))
    return resultado


def _carregar_jsonl(caminho):
    registros = []
    try:
        with open(caminho, encoding="utf-8") as entrada:
            for linha in entrada:
                if not linha.strip():
                    continue
                try:
                    dados = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(dados, dict):
                    registros.append(dados)
    except OSError:
        return []
    return registros


def _epoch(dados):
    valor = _numero(dados.get("timestamp_epoch"))
    if valor is not None:
        return valor
    texto = dados.get("timestamp")
    if not isinstance(texto, str):
        return 0.0
    try:
        import datetime

        return datetime.datetime.fromisoformat(texto).timestamp()
    except ValueError:
        return 0.0


def _contadores_sensor(dados):
    acertos = _inteiro(dados.get("acertos")) or 0
    erros = _inteiro(dados.get("erros")) or 0
    return {
        "inferencias": acertos + erros,
        "inferencias_nao_mosquito": _inteiro(dados.get("inferencias_nao_mosquito")) or 0,
        "mosquitos_identificados": _inteiro(dados.get("mosquitos_identificados")) or 0,
        "acertos": acertos,
        "erros": erros,
        "falsos_positivos": _inteiro(dados.get("falsos_positivos")) or 0,
        "falsos_negativos": _inteiro(dados.get("falsos_negativos")) or 0,
        "audios_enviados": _inteiro(dados.get("audios_enviados")) or 0,
    }


def _linha_metrica_sensor(dados, sensor_id):
    linha = {
        "sensor_id": sensor_id,
        "cluster": _inteiro(dados.get("cluster")) or 0,
        "audios_enviados": _inteiro(dados.get("audios_enviados")) or 0,
        "mosquitos_identificados": _inteiro(dados.get("mosquitos_identificados")) or 0,
        "acertos": _inteiro(dados.get("acertos")) or 0,
        "erros": _inteiro(dados.get("erros")) or 0,
        "falsos_positivos": _inteiro(dados.get("falsos_positivos")) or 0,
        "falsos_negativos": _inteiro(dados.get("falsos_negativos")) or 0,
        "taxa_acerto": round(_numero(dados.get("taxa_acerto")) or 0.0, 4),
        "inferencias_nao_mosquito": _inteiro(dados.get("inferencias_nao_mosquito")) or 0,
    }
    linha.update(_metadados(dados))
    return linha


def agregar_metricas_sensores(definicao_rede, caminho_saida=CAMINHO_SAIDA):
    if not definicao_rede or "sensores" not in definicao_rede:
        return

    ids = sorted(int(dados["id"]) for dados in definicao_rede["sensores"].values())
    linhas = []

    for sensor_id in ids:
        caminho = os.path.join(CAMINHO_METRICAS_SENSORES, f"sensor_{sensor_id}.log")
        try:
            with open(caminho, encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            linha = _linha_metrica_sensor(dados, sensor_id)
        except (OSError, ValueError, TypeError, KeyError):
            linha = {coluna: "" for coluna in COLUNAS}
            linha["sensor_id"] = sensor_id

        linhas.append(linha)

    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(linhas)


def consolidar_resultados(itens, caminho_saida=CAMINHO_SAIDA):
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=COLUNAS_CONSOLIDADAS, extrasaction="ignore"
        )
        escritor.writeheader()

        for run_id, caminho_entrada in itens:
            try:
                with open(caminho_entrada, newline="", encoding="utf-8") as entrada:
                    for linha in csv.DictReader(entrada):
                        escritor.writerow({"run_id": run_id, **linha})
            except (OSError, csv.Error):
                continue


def consolidar_streams(itens, caminho_saida=CAMINHO_STREAMS):
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=COLUNAS_STREAMS, extrasaction="ignore"
        )
        escritor.writeheader()

        for run_id, caminhos_entrada in itens:
            for caminho_entrada in caminhos_entrada:
                try:
                    with open(caminho_entrada, encoding="utf-8") as entrada:
                        dados = json.load(entrada)
                    linha = {
                        "run_id": run_id,
                        "sensor_id": _inteiro(dados.get("sensor_id")),
                        "timestamp": dados.get("timestamp"),
                        "latencia_s": round(_numero(dados.get("latencia_s")) or 0.0, 6),
                        "throughput_bps": round(_numero(dados.get("throughput_bps")) or 0.0, 2),
                        "pacotes_recebidos": _inteiro(dados.get("pacotes_recebidos")) or 0,
                        "pacotes_perdidos": _inteiro(dados.get("pacotes_perdidos")) or 0,
                    }
                    linha.update(_metadados(dados))
                    escritor.writerow(linha)
                except (OSError, ValueError, TypeError, KeyError):
                    continue


def _ultimo_snapshot_rede(caminho_entrada=None):
    if caminho_entrada is None:
        if not os.path.isdir(DIR_REDE):
            return None
        candidatos = []
        for nome in os.listdir(DIR_REDE):
            if not nome.endswith(".log"):
                continue
            caminho = os.path.join(DIR_REDE, nome)
            try:
                candidatos.append((os.path.getmtime(caminho), caminho))
            except OSError:
                continue
        if not candidatos:
            return None
        caminho_entrada = max(candidatos)[1]

    ultimo = None
    for dados in _carregar_jsonl(caminho_entrada):
        ultimo = dados
    return ultimo


def _linha_rede(dados):
    linha = {
        "throughput_bps": round(_numero(dados.get("throughput_bps")) or 0.0, 2),
        "latencia_media_pacote_s": round(
            _numero(dados.get("latencia_media_pacote_s")) or 0.0, 9
        ),
        "pacotes_recebidos": _inteiro(dados.get("pacotes_recebidos")) or 0,
        "pacotes_perdidos": _inteiro(dados.get("pacotes_perdidos")) or 0,
        "audio_recebidos": _inteiro(dados.get("audio_recebidos")) or 0,
    }
    linha.update(_metadados(dados))
    return linha


def agregar_metricas_rede(caminho_entrada=None, caminho_saida=CAMINHO_REDE):
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS_REDE)
        escritor.writeheader()

        dados = _ultimo_snapshot_rede(caminho_entrada)
        if dados is None:
            return
        try:
            escritor.writerow(_linha_rede(dados))
        except (ValueError, TypeError, KeyError):
            return


def consolidar_rede(itens, caminho_saida=CAMINHO_REDE):
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=COLUNAS_REDE_CONSOLIDADAS, extrasaction="ignore"
        )
        escritor.writeheader()

        for run_id, caminho_entrada in itens:
            if not caminho_entrada:
                continue
            dados = _ultimo_snapshot_rede(caminho_entrada)
            if dados is None:
                continue
            try:
                escritor.writerow({"run_id": run_id, **_linha_rede(dados)})
            except (ValueError, TypeError, KeyError):
                continue


def _deltas_sensores_por_estagio(caminhos):
    por_estagio = {}
    for caminho in caminhos:
        registros = sorted(_carregar_jsonl(caminho), key=_epoch)
        ultimos = {}
        for registro in registros:
            estagio = _inteiro(registro.get("estagio")) or 1
            ultimos[estagio] = registro
        if not ultimos:
            continue

        anterior = {chave: 0 for chave in CONTADORES_SENSOR}
        for estagio in sorted(ultimos):
            registro = ultimos[estagio]
            atual = _contadores_sensor(registro)
            delta = {
                chave: max(0, atual.get(chave, 0) - anterior.get(chave, 0))
                for chave in CONTADORES_SENSOR
            }
            destino = por_estagio.setdefault(
                estagio,
                {"contadores": {chave: 0 for chave in CONTADORES_SENSOR}, "metadados": {}},
            )
            for chave, valor in delta.items():
                destino["contadores"][chave] += valor
            if not destino["metadados"]:
                destino["metadados"] = _metadados(registro)
            anterior = atual
    return por_estagio


def _estagios_rede(caminho):
    snapshots = sorted(_carregar_jsonl(caminho), key=_epoch)
    if not snapshots:
        return {}

    grupos = {}
    for snapshot in snapshots:
        estagio = _inteiro(snapshot.get("estagio")) or 1
        grupos.setdefault(estagio, []).append(snapshot)

    resultado = {}
    anterior = None
    for estagio in sorted(grupos):
        grupo = grupos[estagio]
        inicio = anterior or grupo[0]
        fim = grupo[-1]
        duracao = _epoch(fim) - _epoch(inicio)
        if duracao <= 0:
            duracao = _numero(fim.get("duracao_estagio_s")) or 0.0

        bytes_delta = (_numero(fim.get("bytes_totais")) or 0.0) - (
            _numero(inicio.get("bytes_totais")) or 0.0
        )
        pacotes_delta = (_inteiro(fim.get("pacotes_recebidos")) or 0) - (
            _inteiro(inicio.get("pacotes_recebidos")) or 0
        )
        perdas_delta = (_inteiro(fim.get("pacotes_perdidos")) or 0) - (
            _inteiro(inicio.get("pacotes_perdidos")) or 0
        )
        audio_delta = (_inteiro(fim.get("audio_recebidos")) or 0) - (
            _inteiro(inicio.get("audio_recebidos")) or 0
        )
        latencia_ns_delta = (_numero(fim.get("soma_latencia_ns")) or 0.0) - (
            _numero(inicio.get("soma_latencia_ns")) or 0.0
        )

        linha = {
            "throughput_bps": round(bytes_delta * 8 / duracao, 2) if duracao > 0 else 0.0,
            "latencia_media_pacote_s": (
                round(latencia_ns_delta / pacotes_delta / 1e9, 9)
                if pacotes_delta > 0
                else 0.0
            ),
            "pacotes_recebidos": max(0, pacotes_delta),
            "pacotes_perdidos": max(0, perdas_delta),
            "audio_recebidos": max(0, audio_delta),
        }
        linha.update(_metadados(fim))
        resultado[estagio] = linha
        anterior = fim
    return resultado


def _streams_por_estagio(caminhos):
    contagens = {}
    for caminho in caminhos:
        try:
            with open(caminho, encoding="utf-8") as entrada:
                dados = json.load(entrada)
        except (OSError, ValueError):
            continue
        estagio = _inteiro(dados.get("estagio")) or 1
        contagens[estagio] = contagens.get(estagio, 0) + 1
    return contagens


def _metricas_classificacao(contadores):
    acertos = contadores.get("acertos", 0)
    erros = contadores.get("erros", 0)
    falsos_positivos = contadores.get("falsos_positivos", 0)
    falsos_negativos = contadores.get("falsos_negativos", 0)
    detectados = contadores.get("mosquitos_identificados", 0)
    nao_detectados = contadores.get("inferencias_nao_mosquito", 0)

    verdadeiros_positivos = max(0, detectados - falsos_positivos)
    verdadeiros_negativos = max(0, nao_detectados - falsos_negativos)
    total = acertos + erros

    precisao = (
        verdadeiros_positivos / (verdadeiros_positivos + falsos_positivos)
        if (verdadeiros_positivos + falsos_positivos) > 0
        else 0.0
    )
    recall = (
        verdadeiros_positivos / (verdadeiros_positivos + falsos_negativos)
        if (verdadeiros_positivos + falsos_negativos) > 0
        else 0.0
    )
    f1 = (
        2 * precisao * recall / (precisao + recall)
        if (precisao + recall) > 0
        else 0.0
    )

    return {
        "acuracia": round(acertos / total, 4) if total > 0 else 0.0,
        "precisao": round(precisao, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def agregar_metricas_exploratoria(itens, caminho_saida=CAMINHO_EXPLORATORIA):
    os.makedirs(os.path.dirname(caminho_saida), exist_ok=True)
    with open(caminho_saida, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=COLUNAS_EXPLORATORIA, extrasaction="ignore"
        )
        escritor.writeheader()

        for item in itens:
            run_id, caminhos_sensores, caminhos_streams, caminho_rede = item
            sensores = _deltas_sensores_por_estagio(caminhos_sensores)
            rede = _estagios_rede(caminho_rede)
            streams = _streams_por_estagio(caminhos_streams)
            estagios = sorted(set(sensores) | set(rede) | set(streams))

            for estagio in estagios:
                dados_sensor = sensores.get(estagio, {})
                contadores = dados_sensor.get(
                    "contadores", {chave: 0 for chave in CONTADORES_SENSOR}
                )
                metadados = dados_sensor.get("metadados") or rede.get(estagio, {})
                dados_rede = rede.get(estagio, {})

                linha = {"run_id": run_id}
                linha.update({chave: metadados.get(chave) for chave in METADADOS})
                linha["estagio"] = estagio
                linha.update({chave: contadores.get(chave, 0) for chave in CONTADORES_SENSOR})
                linha.update(
                    {
                        "throughput_bps": dados_rede.get("throughput_bps", 0.0),
                        "latencia_media_pacote_s": dados_rede.get(
                            "latencia_media_pacote_s", 0.0
                        ),
                        "pacotes_recebidos": dados_rede.get("pacotes_recebidos", 0),
                        "pacotes_perdidos": dados_rede.get("pacotes_perdidos", 0),
                    }
                )
                audio_recebidos = dados_rede.get("audio_recebidos")
                if audio_recebidos is None:
                    audio_recebidos = streams.get(estagio, 0)
                linha["audio_recebidos"] = audio_recebidos
                linha["streams_completas"] = streams.get(estagio, 0)
                audios_enviados = contadores.get("audios_enviados", 0)
                linha["taxa_entrega"] = (
                    round(audio_recebidos / audios_enviados, 4)
                    if audios_enviados > 0
                    else 0.0
                )
                linha.update(_metricas_classificacao(contadores))
                escritor.writerow(linha)
