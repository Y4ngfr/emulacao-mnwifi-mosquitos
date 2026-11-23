import datetime
import json
import os
import time

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_LOG_RESULTADOS = os.path.join(DIR_BASE, "logs/metricas_sensores/")
CAMINHO_AMBIENTE = os.path.join(DIR_BASE, "cenario_ambiente.json")
CAMINHO_DEFINICAO_REDE = os.path.join(DIR_BASE, "definicao_rede.json")


def _numero(valor):
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _inteiro(valor):
    if valor is None:
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _metadados_ambiente(cluster_id=0):
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
    cluster = clusters.get(str(cluster_id))
    if not isinstance(cluster, dict):
        cluster = clusters.get("0")
    if not isinstance(cluster, dict) and clusters:
        cluster = next(iter(clusters.values()))
    if not isinstance(cluster, dict):
        cluster = {}

    metadados.update(
        {
            "cenario_id": _inteiro(ambiente.get("cenario_id", ambiente.get("id_cenario"))),
            "estagio": _inteiro(ambiente.get("estagio")),
            "indice_estagio": _inteiro(ambiente.get("indice_estagio")),
            "fator_variado": ambiente.get("fator_variado"),
            "valor_fator": _numero(ambiente.get("valor_fator")),
            "densidade_mosquitos": _numero(cluster.get("densidade_mosquitos")),
            "ruido_audio": _numero(cluster.get("ruido_audio")),
            "qualidade_transmissao": _numero(cluster.get("qualidade_transmissao")),
            "n_clusters": _inteiro(ambiente.get("n_clusters", len(clusters))),
            "gw_icmp_ok": _inteiro(ambiente.get("gw_icmp_ok")),
            "gw_icmp_falhas": _inteiro(ambiente.get("gw_icmp_falhas")),
            "gw_icmp_tentativas": _inteiro(ambiente.get("gw_icmp_tentativas")),
            "gw_icmp_sensores": ambiente.get("gw_icmp_sensores", ""),
        }
    )

    try:
        with open(CAMINHO_DEFINICAO_REDE, encoding="utf-8") as arquivo:
            definicao = json.load(arquivo)
        metadados["n_sensores"] = len(definicao.get("sensores", {}))
    except (OSError, ValueError, TypeError):
        pass

    return metadados


class MetricasSensor:
    def __init__(self, sensor_id, cluster=0):
        self.sensor_id = sensor_id
        self.cluster = cluster
        self.arquivo = os.path.join(CAMINHO_LOG_RESULTADOS, f"sensor_{sensor_id}.log")
        self.arquivo_historico = os.path.join(
            CAMINHO_LOG_RESULTADOS, f"sensor_{sensor_id}_historico.log"
        )

        self.audios_enviados = 0
        self.mosquitos_identificados = 0
        self.acertos = 0
        self.erros = 0
        self.falsos_positivos = 0
        self.falsos_negativos = 0
        self.inferencias_nao_mosquito = 0

        os.makedirs(CAMINHO_LOG_RESULTADOS, exist_ok=True)

    def registrar_inferencia(self, resultado, classe_verdadeira):
        detectou = resultado["p_mosquito"] >= resultado["p_nao_mosquito"]
        eh_mosquito_verdadeiro = classe_verdadeira in (0, 1, 2)

        if detectou == eh_mosquito_verdadeiro:
            self.acertos += 1
        else:
            self.erros += 1
            if detectou and not eh_mosquito_verdadeiro:
                self.falsos_positivos += 1
            elif not detectou and eh_mosquito_verdadeiro:
                self.falsos_negativos += 1

        if detectou:
            self.mosquitos_identificados += 1
        else:
            self.inferencias_nao_mosquito += 1

    def registrar_envio_audio(self):
        self.audios_enviados += 1

    def _dados(self):
        agora = time.time()
        dados = {
            "timestamp": datetime.datetime.fromtimestamp(agora).isoformat(timespec="seconds"),
            "timestamp_epoch": agora,
            "sensor_id": self.sensor_id,
            "cluster": self.cluster,
            "audios_enviados": self.audios_enviados,
            "mosquitos_identificados": self.mosquitos_identificados,
            "acertos": self.acertos,
            "erros": self.erros,
            "falsos_positivos": self.falsos_positivos,
            "falsos_negativos": self.falsos_negativos,
            "taxa_acerto": (
                self.acertos / (self.acertos + self.erros)
                if (self.acertos + self.erros) > 0
                else 0.0
            ),
            "inferencias_nao_mosquito": self.inferencias_nao_mosquito,
        }
        dados.update(_metadados_ambiente(self.cluster))
        return dados

    def salvar(self):
        dados = self._dados()
        with open(self.arquivo, "w", encoding="utf-8") as arquivo:
            json.dump(dados, arquivo, indent=2)
        with open(self.arquivo_historico, "a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")
