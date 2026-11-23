import argparse
import json
import os
import subprocess
import sys
import time

import agregar_metricas

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
DIRETORIO_RESULTADOS = os.path.join(DIR_BASE, "resultados")
CAMINHO_CHECKPOINT = os.path.join(DIRETORIO_RESULTADOS, "runs_concluidos.json")

NOME_EXPERIMENTO = "densidade_fixa_360"
SENSORES_POR_AP = [1, 5, 10, 15]
APS = [1, 3, 6]
CENARIOS = [5, 6, 7]
REPETICOES = 5
DURACAO = 360
WARMUP = 0
SEED_BASE = 100
MAX_SENSORES = 100


def gerar_runs():
    runs = []
    for cenario in CENARIOS:
        for repeticao in range(1, REPETICOES + 1):
            for n_aps in APS:
                for sensores_por_ap in SENSORES_POR_AP:
                    seed = SEED_BASE + repeticao - 1
                    n_sensores = sensores_por_ap * n_aps
                    if n_sensores > MAX_SENSORES:
                        continue
                    run_id = (
                        f"{NOME_EXPERIMENTO}_s{n_sensores:02d}"
                        f"_spa{sensores_por_ap:02d}_ap{n_aps:02d}"
                        f"_c{cenario:02d}_r{repeticao:02d}_seed{seed}"
                    )
                    runs.append(
                        {
                            "run_id": run_id,
                            "n_sensores": n_sensores,
                            "sensores_por_ap": sensores_por_ap,
                            "n_aps": n_aps,
                            "cenario": cenario,
                            "repeticao": repeticao,
                            "duracao": DURACAO,
                            "warmup": WARMUP,
                            "seed": seed,
                        }
                    )
    return runs


def executar_run(run, indice, total):
    prefixo = f"[run {indice:02d}/{total:02d}] "
    caminho_csv = os.path.join(
        DIRETORIO_RESULTADOS, run["run_id"], "metricas_sensores.csv"
    )
    comando = [
        sys.executable,
        "-u",
        os.path.join(DIR_BASE, "mininet_ambiente.py"),
        "--n_sensores", str(run["n_sensores"]),
        "--n_aps", str(run["n_aps"]),
        "--duracao", str(run["duracao"]),
        "--warmup", str(run["warmup"]),
        "--cenario", str(run["cenario"]),
        "--seed", str(run["seed"]),
        "--run_id", str(run["run_id"]),
        "--sensores_por_ap", str(run["sensores_por_ap"]),
        "--repeticao", str(run["repeticao"]),
        "--sem-cli",
        "--saida-metricas", caminho_csv,
    ]

    print(
        f"{prefixo}INICIO {run['run_id']} "
        f"sensores={run['n_sensores']} por_ap={run['sensores_por_ap']} "
        f"aps={run['n_aps']} cenario={run['cenario']} seed={run['seed']}",
        flush=True,
    )

    processo = subprocess.Popen(
        comando,
        cwd=DIR_BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    for linha in processo.stdout:
        print(f"{prefixo}{linha}", end="", flush=True)

    codigo = processo.wait()
    if codigo != 0:
        raise RuntimeError(f"{prefixo}FALHA: {run['run_id']} terminou com código {codigo}")

    print(f"{prefixo}CONCLUÍDO {run['run_id']}", flush=True)
    return caminho_csv


def _coletar_por_mtime(diretorio, sufixo, inicio, fim, todos=False):
    if not os.path.isdir(diretorio):
        return [] if todos else None

    candidatos = []
    for nome in os.listdir(diretorio):
        if not nome.endswith(sufixo):
            continue
        caminho = os.path.join(diretorio, nome)
        try:
            mtime = os.path.getmtime(caminho)
        except OSError:
            continue
        if inicio <= mtime <= fim:
            candidatos.append((mtime, caminho))
    candidatos = sorted(candidatos)

    if todos:
        return [caminho for _, caminho in candidatos]
    return max(candidatos)[1] if candidatos else None


def coletar_sensores(inicio, fim):
    return _coletar_por_mtime(
        agregar_metricas.CAMINHO_METRICAS_SENSORES,
        "_historico.log",
        inicio,
        fim,
        todos=True,
    )


def coletar_streams(inicio, fim):
    return _coletar_por_mtime(
        agregar_metricas.DIR_STREAMS,
        ".log",
        inicio,
        fim,
        todos=True,
    )


def coletar_rede(inicio, fim):
    return _coletar_por_mtime(
        agregar_metricas.DIR_REDE,
        ".log",
        inicio,
        fim,
    )


def _carregar_checkpoint():
    if not os.path.isfile(CAMINHO_CHECKPOINT):
        return {}
    try:
        with open(CAMINHO_CHECKPOINT, encoding="utf-8") as arquivo:
            dados = json.load(arquivo)
    except (OSError, ValueError):
        return {}
    if not isinstance(dados, dict):
        return {}

    concluidos = {}
    for run_id, item in dados.items():
        if not isinstance(item, dict):
            continue
        caminho_csv = item.get("csv")
        if not isinstance(caminho_csv, str) or not os.path.isfile(caminho_csv):
            continue
        item.setdefault("run_id", run_id)
        item.setdefault("sensores", [])
        item.setdefault("streams", [])
        concluidos[run_id] = item
    return concluidos


def _salvar_checkpoint(concluidos):
    os.makedirs(DIRETORIO_RESULTADOS, exist_ok=True)
    temporario = f"{CAMINHO_CHECKPOINT}.{os.getpid()}.tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(concluidos, arquivo, indent=2, ensure_ascii=False)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, CAMINHO_CHECKPOINT)
    finally:
        if os.path.exists(temporario):
            os.remove(temporario)


def _semear_checkpoint(concluidos, runs, indice_limite):
    limite_anterior = 0.0
    for indice, run in enumerate(runs, start=1):
        if indice >= indice_limite:
            break
        run_id = run["run_id"]
        if run_id in concluidos:
            continue
        caminho_csv = os.path.join(
            DIRETORIO_RESULTADOS, run_id, "metricas_sensores.csv"
        )
        if not os.path.isfile(caminho_csv):
            continue
        try:
            fim = os.path.getmtime(caminho_csv) + 1
        except OSError:
            continue
        inicio = max(limite_anterior, fim - run["duracao"] - 180)
        concluidos[run_id] = {
            "run_id": run_id,
            "csv": caminho_csv,
            "sensores": coletar_sensores(inicio, fim),
            "streams": coletar_streams(inicio, fim),
            "rede": coletar_rede(inicio, fim),
        }
        limite_anterior = fim


def consolidar(concluidos, runs, verbose=False):
    itens = [
        concluidos[run["run_id"]]
        for run in runs
        if run["run_id"] in concluidos
    ]

    agregar_metricas.consolidar_resultados(
        [(item["run_id"], item["csv"]) for item in itens],
        os.path.join(DIRETORIO_RESULTADOS, "metricas_sensores.csv"),
    )
    agregar_metricas.consolidar_streams(
        [(item["run_id"], item["streams"]) for item in itens]
    )
    agregar_metricas.consolidar_rede(
        [(item["run_id"], item["rede"]) for item in itens]
    )
    agregar_metricas.agregar_metricas_exploratoria(
        [
            (item["run_id"], item["sensores"], item["streams"], item["rede"])
            for item in itens
        ]
    )

    if verbose:
        print(
            f"CSVs atualizados com {len(itens)} runs: "
            f"{agregar_metricas.CAMINHO_SAIDA}, "
            f"{agregar_metricas.CAMINHO_STREAMS}, "
            f"{agregar_metricas.CAMINHO_REDE}, "
            f"{agregar_metricas.CAMINHO_EXPLORATORIA}",
            flush=True,
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Ignora o checkpoint e reexecuta todos os runs",
    )
    parser.add_argument(
        "--iniciar-indice",
        type=int,
        default=1,
        help="Semeia runs anteriores e começa a execução no índice informado",
    )
    args = parser.parse_args()

    runs = gerar_runs()
    total = len(runs)
    if not 1 <= args.iniciar_indice <= total:
        raise SystemExit(f"--iniciar-indice deve estar entre 1 e {total}")
    ids = {run["run_id"] for run in runs}
    concluidos = {} if args.forcar else _carregar_checkpoint()
    concluidos = {
        run_id: item for run_id, item in concluidos.items() if run_id in ids
    }

    if args.iniciar_indice > 1:
        _semear_checkpoint(concluidos, runs, args.iniciar_indice)
        _salvar_checkpoint(concluidos)

    try:
        for indice, run in enumerate(runs, start=1):
            prefixo = f"[run {indice:02d}/{total:02d}] "
            run_id = run["run_id"]

            if indice < args.iniciar_indice:
                print(f"{prefixo}PULADO {run_id} (fora do intervalo)", flush=True)
                continue

            if run_id in concluidos:
                print(f"{prefixo}PULADO {run_id} (checkpoint)", flush=True)
                continue

            inicio = time.time()
            caminho_csv = executar_run(run, indice, total)
            fim = time.time()

            concluidos[run_id] = {
                "run_id": run_id,
                "csv": caminho_csv,
                "sensores": coletar_sensores(inicio, fim),
                "streams": coletar_streams(inicio, fim),
                "rede": coletar_rede(inicio, fim),
            }
            _salvar_checkpoint(concluidos)
            consolidar(concluidos, runs)
            print(f"{prefixo}CHECKPOINT e CSVs atualizados", flush=True)
    except RuntimeError as erro:
        consolidar(concluidos, runs, verbose=True)
        raise SystemExit(str(erro))
    except KeyboardInterrupt:
        consolidar(concluidos, runs, verbose=True)
        raise SystemExit("Execução interrompida; checkpoint e CSVs atualizados.")

    consolidar(concluidos, runs, verbose=True)


if __name__ == "__main__":
    main()
