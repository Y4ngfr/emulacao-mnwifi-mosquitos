import csv
import datetime
import os
import threading
import time

CAMINHO_CSV = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "resultados",
    "metricas_hardware.csv",
)

COLUNAS = [
    "timestamp",
    "timestamp_epoch",
    "run_id",
    "cenario",
    "n_APs",
    "sensores_por_AP",
    "n_sensores",
    "repeticao",
    "seed",
    "duracao",
    "warmup",
    "cpu_percent",
    "memoria_mb",
]

CANDIDATOS_MEMORIA = [
    "/sys/fs/cgroup/memory.current",
    "/sys/fs/cgroup/memory/memory.usage_in_bytes",
]


def _ler_valor_chave(caminho, chave):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            for linha in arquivo:
                partes = linha.split()
                if len(partes) >= 2 and partes[0] == chave:
                    return partes[1]
    except OSError:
        return None
    return None


def _ler_numero(caminho):
    try:
        with open(caminho, encoding="utf-8") as arquivo:
            return arquivo.read().strip()
    except OSError:
        return None


def descobrir_cpu_stat():
    for caminho in ("/sys/fs/cgroup/cpu.stat", "/sys/fs/cgroup/cpu/cpu.stat"):
        if os.path.isfile(caminho):
            return caminho
    return None


def descobrir_memoria():
    for caminho in CANDIDATOS_MEMORIA:
        if os.path.isfile(caminho):
            return caminho
    try:
        for raiz, diretorios, arquivos in os.walk("/sys/fs/cgroup"):
            diretorios[:] = [
                diretorio
                for diretorio in diretorios
                if raiz.count(os.sep) < 5
            ]
            for nome in arquivos:
                if nome in ("memory.current", "memory.usage_in_bytes"):
                    return os.path.join(raiz, nome)
    except OSError:
        return None
    return None


def descobrir_n_cpus():
    caminhos = (
        "/sys/fs/cgroup/cpuset.cpus.effective",
        "/sys/fs/cgroup/cpuset/cpuset.cpus",
    )
    for caminho in caminhos:
        conteudo = _ler_numero(caminho)
        if not conteudo:
            continue
        total = 0
        try:
            for parte in conteudo.split(","):
                if "-" in parte:
                    inicio, fim = parte.split("-", 1)
                    total += int(fim) - int(inicio) + 1
                elif parte:
                    total += 1
        except ValueError:
            continue
        if total:
            return total
    return os.cpu_count() or 1


class ColetorHardware:
    def __init__(self, config, intervalo=1.0, caminho_csv=None):
        self.config = dict(config)
        self.intervalo = float(intervalo)
        self.caminho_csv = caminho_csv or CAMINHO_CSV
        self._parar = threading.Event()
        self._thread = None
        self._cpu_stat = descobrir_cpu_stat()
        self._memoria = descobrir_memoria()
        self._n_cpus = descobrir_n_cpus()
        self._ultimo_usage_usec = None
        self._ultimo_tempo = None
        if self._memoria is None:
            print(
                "AVISO: memoria do container nao disponivel no cgroup",
                flush=True,
            )

    def iniciar(self):
        if self._thread is not None:
            return
        os.makedirs(os.path.dirname(self.caminho_csv), exist_ok=True)
        self._escrever_cabecalho()
        self._ultimo_usage_usec = self._usage_usec()
        self._ultimo_tempo = time.monotonic()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def parar(self):
        self._parar.set()
        if self._thread is not None:
            self._thread.join(timeout=self.intervalo + 1.0)
            self._thread = None

    def _escrever_cabecalho(self):
        if os.path.isfile(self.caminho_csv) and os.path.getsize(self.caminho_csv) > 0:
            return
        with open(self.caminho_csv, "w", newline="", encoding="utf-8") as arquivo:
            csv.DictWriter(arquivo, fieldnames=COLUNAS).writeheader()

    def _usage_usec(self):
        if not self._cpu_stat:
            return None
        valor = _ler_valor_chave(self._cpu_stat, "usage_usec")
        if valor is None:
            return None
        try:
            return int(valor)
        except ValueError:
            return None

    def _memoria_mb(self):
        if not self._memoria:
            return ""
        valor = _ler_numero(self._memoria)
        if valor is None:
            return ""
        try:
            return round(int(valor) / (1024 * 1024), 2)
        except ValueError:
            return ""

    def _cpu_percent(self):
        atual = self._usage_usec()
        agora = time.monotonic()
        if atual is None or self._ultimo_usage_usec is None:
            self._ultimo_usage_usec = atual
            self._ultimo_tempo = agora
            return ""
        delta_usec = atual - self._ultimo_usage_usec
        delta_s = agora - self._ultimo_tempo
        self._ultimo_usage_usec = atual
        self._ultimo_tempo = agora
        if delta_s <= 0:
            return ""
        return round(delta_usec / (delta_s * 1e6 * self._n_cpus) * 100, 2)

    def _loop(self):
        while not self._parar.wait(self.intervalo):
            agora_epoch = time.time()
            registro = {
                "timestamp": datetime.datetime.fromtimestamp(
                    agora_epoch
                ).astimezone().isoformat(timespec="milliseconds"),
                "timestamp_epoch": round(agora_epoch, 6),
                "run_id": self.config.get("run_id", ""),
                "cenario": self.config.get("cenario", ""),
                "n_APs": self.config.get("n_APs", ""),
                "sensores_por_AP": self.config.get("sensores_por_AP", ""),
                "n_sensores": self.config.get("n_sensores", ""),
                "repeticao": self.config.get("repeticao", ""),
                "seed": self.config.get("seed", ""),
                "duracao": self.config.get("duracao", ""),
                "warmup": self.config.get("warmup", ""),
                "cpu_percent": self._cpu_percent(),
                "memoria_mb": self._memoria_mb(),
            }
            with open(self.caminho_csv, "a", newline="", encoding="utf-8") as arquivo:
                csv.DictWriter(arquivo, fieldnames=COLUNAS).writerow(registro)
