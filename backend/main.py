import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, Response

RAIZ = Path(__file__).resolve().parent.parent
CAMINHO_CENARIO = RAIZ / "cenario_ambiente.json"
CAMINHO_DEFINICAO = RAIZ / "definicao_rede.json"
PASTA_LOGS = RAIZ / "logs"
CAMINHO_SERVIDOR = PASTA_LOGS / "servidor.log"
PASTA_AUDIOS = RAIZ / "audios_recebidos"
PASTA_METRICAS_SENSORES = PASTA_LOGS / "metricas_sensores"
PASTA_METRICAS_STREAMS = PASTA_LOGS / "metricas_streams"
PASTA_METRICAS_REDE = PASTA_LOGS / "metricas_rede"

NUMERO = re.compile(r"-?\d+(?:\.\d+)?")

MARCADORES_EVENTO = (
    "servidor_pronto",
    "aguardando_experimento",
    "comando de inicio",
    "comando de início",
    "mosquito detectado",
    "p_mosquito=",
    "áudio salvo",
    "audio salvo",
    "áudio enviado",
    "conexão mqtt estabelecida",
    "timeout",
    "encerrando",
)

app = FastAPI(title="Monitoramento do experimento")

_INICIO_OBSERVADO: Optional[float] = None


class CacheEstado:
    def __init__(self) -> None:
        self.chave: Optional[Tuple[Any, ...]] = None
        self.valor: Optional[Dict[str, Any]] = None

    def obter(self, agora: float) -> Dict[str, Any]:
        chave = _assinatura(agora)
        if self.valor is None or chave != self.chave:
            self.valor = _montar_estado(agora)
            self.chave = chave
        return self.valor


_cache = CacheEstado()


@app.get("/api/estado")
def obter_estado(response: Response) -> Dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    return _cache.obter(time.time())


def _assinatura(agora: float) -> Tuple[Any, ...]:
    caminhos = [CAMINHO_CENARIO, CAMINHO_DEFINICAO, CAMINHO_SERVIDOR]
    caminhos.extend(sorted(PASTA_LOGS.glob("sensor_*.log")))
    caminhos.extend(sorted(PASTA_METRICAS_SENSORES.glob("sensor_*.log")))
    caminhos.extend(sorted(PASTA_METRICAS_STREAMS.glob("*.log")))
    caminhos.extend(sorted(PASTA_METRICAS_REDE.glob("rede_*.log")))
    for padrao in ("*.wav", "*.adpcm"):
        caminhos.extend(sorted(PASTA_AUDIOS.glob(padrao)))

    itens: List[Tuple[str, int, int]] = []
    for caminho in caminhos:
        try:
            estatistica = caminho.stat()
        except OSError:
            continue
        itens.append((str(caminho), estatistica.st_mtime_ns, estatistica.st_size))

    return (int(agora), tuple(itens))


def _carregar_json(caminho: Path) -> Dict[str, Any]:
    try:
        with caminho.open("r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def _ler_texto(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _mtime(caminho: Path) -> Optional[float]:
    try:
        return caminho.stat().st_mtime
    except OSError:
        return None


def _iso(timestamp: Optional[float]) -> Optional[str]:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp).astimezone().isoformat()


def _numero(valor: Any) -> Optional[float]:
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        numero = float(valor)
    elif isinstance(valor, str):
        try:
            numero = float(valor.strip().replace(",", "."))
        except ValueError:
            return None
    else:
        return None
    return numero if math.isfinite(numero) else None


def _inteiro(valor: Any) -> Optional[int]:
    numero = _numero(valor)
    return None if numero is None else int(numero)


def _media(valores: List[float]) -> Optional[float]:
    if not valores:
        return None
    return sum(valores) / len(valores)


def _metricas_sensores_log() -> Dict[int, Dict[str, float]]:
    chaves = (
        "audios_enviados",
        "mosquitos_identificados",
        "acertos",
        "erros",
        "falsos_positivos",
        "falsos_negativos",
        "taxa_acerto",
        "inferencias_nao_mosquito",
    )
    resultado: Dict[int, Dict[str, float]] = {}

    for caminho in sorted(PASTA_METRICAS_SENSORES.glob("sensor_*.log")):
        dados = _carregar_json(caminho)
        sensor_id = _inteiro(dados.get("sensor_id"))
        if sensor_id is None:
            continue

        valores: Dict[str, float] = {}
        for chave in chaves:
            numero = _numero(dados.get(chave))
            if numero is not None:
                valores[chave] = numero
        resultado[sensor_id] = valores

    return resultado


def _metricas_streams_log() -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]]]:
    latencias: List[float] = []
    throughputs: List[float] = []
    perdidos_total = 0
    por_sensor: Dict[int, Dict[str, Any]] = {}

    for caminho in sorted(PASTA_METRICAS_STREAMS.glob("*.log")):
        dados = _carregar_json(caminho)
        latencia = _numero(dados.get("latencia_s"))
        throughput = _numero(dados.get("throughput_bps"))
        perdidos = _inteiro(dados.get("pacotes_perdidos")) or 0
        sensor_id = _inteiro(dados.get("sensor_id"))
        if latencia is None or throughput is None:
            continue

        latencias.append(latencia)
        throughputs.append(throughput)
        perdidos_total += perdidos

        if sensor_id is not None:
            grupo = por_sensor.setdefault(
                sensor_id,
                {"latencias": [], "throughputs": [], "pacotes_perdidos": 0},
            )
            grupo["latencias"].append(latencia)
            grupo["throughputs"].append(throughput)
            grupo["pacotes_perdidos"] += perdidos

    resumo: Dict[str, Any] = {
        "latencia_media_s": _media(latencias),
        "throughput_medio_bps": _media(throughputs),
        "pacotes_perdidos": perdidos_total,
    }

    for sensor_id, grupo in por_sensor.items():
        por_sensor[sensor_id] = {
            "latencia_media_s": _media(grupo["latencias"]),
            "throughput_medio_bps": _media(grupo["throughputs"]),
            "pacotes_perdidos": grupo["pacotes_perdidos"],
        }

    return resumo, por_sensor


def _metricas_rede_log() -> Dict[str, Any]:
    vazio: Dict[str, Any] = {
        "throughput_bps": None,
        "latencia_media_pacote_s": None,
        "pacotes_recebidos": 0,
        "pacotes_perdidos": 0,
        "audio_recebidos": 0,
    }
    caminhos = sorted(
        PASTA_METRICAS_REDE.glob("rede_*.log"),
        key=lambda caminho: _mtime(caminho) or 0,
    )
    if not caminhos:
        return vazio

    ultimo = None
    for linha in _ler_texto(caminhos[-1]).splitlines():
        if not linha.strip():
            continue
        try:
            dados = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(dados, dict):
            ultimo = dados
    if ultimo is None:
        return vazio

    return {
        "throughput_bps": _numero(ultimo.get("throughput_bps")),
        "latencia_media_pacote_s": _numero(ultimo.get("latencia_media_pacote_s")),
        "pacotes_recebidos": _inteiro(ultimo.get("pacotes_recebidos")) or 0,
        "pacotes_perdidos": _inteiro(ultimo.get("pacotes_perdidos")) or 0,
        "audio_recebidos": _inteiro(ultimo.get("audio_recebidos")) or 0,
    }


def _coordenada(valor: Any) -> Optional[List[float]]:
    numeros: List[float] = []

    if isinstance(valor, str):
        candidatos = NUMERO.findall(valor)
    elif isinstance(valor, dict):
        candidatos = [valor.get(eixo) for eixo in ("x", "y", "z")]
    elif isinstance(valor, (list, tuple)):
        candidatos = list(valor[:3])
    else:
        candidatos = []

    for candidato in candidatos:
        numero = _numero(candidato)
        if numero is not None:
            numeros.append(numero)

    if len(numeros) < 3:
        return None
    return [round(numero, 2) for numero in numeros[:3]]


def _cluster_do_ip(ip: str) -> int:
    partes = ip.split("/")[0].split(".")
    if len(partes) >= 2:
        try:
            return int(partes[1])
        except ValueError:
            pass
    return 0


def _id_por_nome(nome: str) -> int:
    encontrado = re.search(r"(\d+)$", nome)
    return int(encontrado.group(1)) if encontrado else 0


def _sensores_definicao() -> List[Dict[str, Any]]:
    dados = _carregar_json(CAMINHO_DEFINICAO)
    brutos = dados.get("sensores")
    if not isinstance(brutos, dict):
        brutos = {}

    metadados: List[Dict[str, Any]] = []
    for nome, item in brutos.items():
        if not isinstance(item, dict):
            continue

        sensor_id = _inteiro(item.get("id"))
        if sensor_id is None:
            sensor_id = _id_por_nome(str(nome))

        ip = str(item.get("ip") or "")
        metadados.append(
            {
                "id": sensor_id,
                "nome": str(nome),
                "ip": ip or None,
                "coordenada": _coordenada(item.get("coordenada")),
                "cluster": _cluster_do_ip(ip),
            }
        )

    return sorted(metadados, key=lambda sensor: sensor["id"])


def _caminho_log_sensor(sensor_id: int) -> Path:
    return PASTA_LOGS / f"sensor_{sensor_id}.log"


def _ultimo_evento(linhas: List[str]) -> Optional[str]:
    for linha in reversed(linhas):
        minuscula = linha.lower()
        if any(marcador in minuscula for marcador in MARCADORES_EVENTO):
            return linha
    return linhas[-1] if linhas else None


def _estado_sensor(
    metadado: Dict[str, Any],
    rede_sensor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    caminho = _caminho_log_sensor(metadado["id"])
    texto = _ler_texto(caminho)
    minusculo = texto.lower()
    linhas = [linha.strip() for linha in texto.splitlines() if linha.strip()]
    recentes = "\n".join(linhas[-20:]).lower()
    rede = rede_sensor or {}

    atualizado = _mtime(caminho)
    return {
        "id": metadado["id"],
        "nome": metadado["nome"],
        "cluster": metadado["cluster"],
        "ip": metadado["ip"],
        "coordenada": metadado["coordenada"],
        "pronto": "aguardando_experimento" in minusculo,
        "monitorando": (
            "comando de inicio recebido" in minusculo
            or "comando de início recebido" in minusculo
        ),
        "detectando": "mosquito detectado" in recentes,
        "latencia_media_s": rede.get("latencia_media_s"),
        "pacotes_perdidos": rede.get("pacotes_perdidos", 0),
        "ultimo_evento": _ultimo_evento(linhas),
        "ultima_atualizacao": _iso(atualizado),
    }


def _nivel_evento(linha: str) -> str:
    minuscula = linha.lower()
    if any(palavra in minuscula for palavra in ("timeout", "erro", "falha", "traceback")):
        return "erro"
    if any(
        palavra in minuscula
        for palavra in ("detectado", "servidor_pronto", "pronto", "salvo", "estabelecida")
    ):
        return "sucesso"
    if "aguardando" in minuscula:
        return "aviso"
    return "info"


def _eventos_log(caminho: Path, origem: str) -> List[Dict[str, Any]]:
    texto = _ler_texto(caminho)
    if not texto:
        return []

    referencia = _iso(_mtime(caminho)) or datetime.now().astimezone().isoformat()
    eventos: List[Dict[str, Any]] = []

    for linha in texto.splitlines():
        mensagem = linha.strip()
        if not mensagem:
            continue

        minuscula = mensagem.lower()
        if any(marcador in minuscula for marcador in MARCADORES_EVENTO):
            eventos.append(
                {
                    "tempo": referencia,
                    "origem": origem,
                    "mensagem": mensagem,
                    "nivel": _nivel_evento(mensagem),
                }
            )

    return eventos


def _clusters(ambiente: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    brutos = ambiente.get("clusters")
    if not isinstance(brutos, dict):
        brutos = {}

    clusters: Dict[str, Dict[str, Any]] = {}
    for chave, item in brutos.items():
        cluster = item if isinstance(item, dict) else {}
        clusters[str(chave)] = {
            "densidade_mosquitos": _numero(
                cluster.get("densidade_mosquitos", cluster.get("densidade"))
            ),
            "ruido_audio": _numero(cluster.get("ruido_audio", cluster.get("ruido"))),
            "qualidade_transmissao": _numero(
                cluster.get(
                    "qualidade_transmissao",
                    cluster.get("txpower", cluster.get("qualidade")),
                )
            ),
        }

    return clusters


def _primeiro_numero(dados: Dict[str, Any], chaves: Tuple[str, ...]) -> Optional[float]:
    for chave in chaves:
        valor = _numero(dados.get(chave))
        if valor is not None:
            return valor
    return None


def _montar_estado(agora: float) -> Dict[str, Any]:
    global _INICIO_OBSERVADO

    ambiente = _carregar_json(CAMINHO_CENARIO)
    texto_servidor = _ler_texto(CAMINHO_SERVIDOR)
    minusculo_servidor = texto_servidor.lower()

    servidor_pronto = "servidor_pronto" in minusculo_servidor
    experimento_iniciado = "comando de inicio enviado aos sensores" in minusculo_servidor
    duracao_s = _primeiro_numero(ambiente, ("duracao_s", "tempo_experimento", "duracao"))
    cenario_id = _primeiro_numero(ambiente, ("cenario_id", "id_cenario"))

    if experimento_iniciado:
        if _INICIO_OBSERVADO is None:
            _INICIO_OBSERVADO = agora
        decorrido_s = max(0.0, agora - _INICIO_OBSERVADO)
        fase = "executando"
        if duracao_s is not None and decorrido_s >= duracao_s:
            fase = "finalizado"
    else:
        _INICIO_OBSERVADO = None
        decorrido_s = None
        fase = "pronto" if servidor_pronto else "iniciando"

    metricas_sensores = _metricas_sensores_log()
    _, rede_por_sensor = _metricas_streams_log()
    rede_global = _metricas_rede_log()
    sensores = [
        _estado_sensor(metadado, rede_por_sensor.get(metadado["id"], {}))
        for metadado in _sensores_definicao()
    ]

    deteccoes_cumulativas = sum(
        int(valores.get("mosquitos_identificados", 0))
        for valores in metricas_sensores.values()
    )
    audios_enviados = sum(
        int(valores.get("audios_enviados", 0))
        for valores in metricas_sensores.values()
    )
    audio_recebidos = rede_global.get("audio_recebidos")
    if audio_recebidos is None:
        audio_recebidos = sum(
            len(list(PASTA_AUDIOS.glob(padrao)))
            for padrao in ("*.wav", "*.adpcm")
        )
    taxa_entrega = audio_recebidos / audios_enviados if audios_enviados > 0 else None

    eventos = _eventos_log(CAMINHO_SERVIDOR, "servidor")
    for sensor in sensores:
        eventos.extend(
            _eventos_log(
                _caminho_log_sensor(sensor["id"]),
                sensor["nome"],
            )
        )
    eventos = sorted(eventos, key=lambda evento: evento["tempo"], reverse=True)[:40]

    return {
        "timestamp": datetime.fromtimestamp(agora).astimezone().isoformat(),
        "experimento": {
            "fase": fase,
            "tempo_decorrido_s": decorrido_s,
            "duracao_s": duracao_s,
            "cenario_id": None if cenario_id is None else int(cenario_id),
        },
        "clusters": _clusters(ambiente),
        "sensores": sensores,
        "metricas": {
            "sensores_prontos": sum(1 for sensor in sensores if sensor["pronto"]),
            "sensores_total": len(sensores),
            "deteccoes": sum(1 for sensor in sensores if sensor["detectando"]),
            "streams": sum(1 for sensor in sensores if sensor["monitorando"]),
            "deteccoes_cumulativas": deteccoes_cumulativas,
            "audios_enviados": audios_enviados,
            "audio_recebidos": audio_recebidos,
            "taxa_entrega": taxa_entrega,
            "throughput_agregado_bps": rede_global["throughput_bps"],
            "latencia_media_pacote_s": rede_global["latencia_media_pacote_s"],
            "pacotes_recebidos": rede_global["pacotes_recebidos"],
            "pacotes_perdidos": rede_global["pacotes_perdidos"],
        },
        "eventos": eventos,
    }
