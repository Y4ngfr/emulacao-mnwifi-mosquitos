import argparse
import json
import math
import os
import random

ARQUIVO_SAIDA = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "definicao_rede.json"
)

ENDERECO_BASE = (100.0, 100.0, 15.0)
SERVIDOR_IP = "11.0.0.10/16"
CIENTISTAS_IPS = ["11.0.1.20/24", "11.0.1.21/24", "11.0.1.22/24"]


def _coordenada(x, y, z):
    return f"{x:.2f},{y:.2f},{z:.2f}"


def _posicoes_aps(n_aps, dist_aps):
    posicoes = []
    for i in range(n_aps):
        linha = i // 5
        coluna = i % 5
        posicoes.append(
            (
                ENDERECO_BASE[0] + coluna * dist_aps,
                ENDERECO_BASE[1] + linha * dist_aps,
                ENDERECO_BASE[2],
            )
        )
    return posicoes


def _sensores_por_ap(n_sensores, n_aps):
    base, resto = divmod(n_sensores, n_aps)
    return [base + (1 if i < resto else 0) for i in range(n_aps)]


def _ip_sensor(cluster, posicao):
    if posicao < 255 * 246:
        sensor_high = posicao // 246
        sensor_low = (posicao % 246) + 10
    else:
        sensor_high = 255
        sensor_low = (posicao - (255 * 246)) + 10

    return f"10.{cluster}.{sensor_high}.{sensor_low}/16"


def gerar_estrela(
    n_sensores=15,
    n_aps=1,
    raio=150.0,
    raio_min=150.0,
    dist_aps=250.0,
    seed=42,
):
    gerador = random.Random(seed)

    posicoes_aps = _posicoes_aps(n_aps, dist_aps)
    sensores_por_ap = _sensores_por_ap(n_sensores, n_aps)

    pontos_de_acesso = {}
    sensores = {}
    sensor_id = 0

    for cluster, (posicao_ap, quantidade) in enumerate(
        zip(posicoes_aps, sensores_por_ap)
    ):
        nome_ap = f"ap{cluster}"
        pontos_de_acesso[nome_ap] = {
            "id": cluster,
            "coordenada": _coordenada(*posicao_ap),
        }

        for posicao_no_cluster in range(quantidade):
            u = gerador.random()
            r = math.sqrt(raio_min**2 + u * (raio**2 - raio_min**2))
            theta = gerador.uniform(0, 2 * math.pi)

            x = posicao_ap[0] + r * math.cos(theta)
            y = posicao_ap[1] + r * math.sin(theta)

            nome_sensor = f"sensor_{sensor_id}"
            sensores[nome_sensor] = {
                "id": sensor_id,
                "ip": _ip_sensor(cluster, posicao_no_cluster),
                "coordenada": _coordenada(x, y, posicao_ap[2]),
            }
            sensor_id += 1

    cientistas = {}
    for i, ip in enumerate(CIENTISTAS_IPS):
        cientistas[f"cient_{i}"] = {
            "id": i,
            "ip": ip,
            "coordenada": _coordenada(0.0, -50.0 * (i + 1), 0.0),
        }

    servidor = {
        "servidor_0": {
            "id": 0,
            "ip": SERVIDOR_IP,
            "coordenada": _coordenada(0.0, 0.0, 0.0),
        }
    }

    return {
        "sensores": sensores,
        "pontos de acesso": pontos_de_acesso,
        "cientistas": cientistas,
        "servidor": servidor,
    }


GERADORES = {
    "estrela": gerar_estrela,
}


def gerar_rede(n_sensores, n_aps, raio_max, raio_min, dist_aps, seed=100):

    rede = GERADORES["estrela"](
        n_sensores=n_sensores,
        n_aps=n_aps,
        raio=raio_max,
        raio_min=raio_min,
        dist_aps=dist_aps,
        seed=seed,
    )

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as arquivo:
        json.dump(rede, arquivo, indent=4, ensure_ascii=False)

    print(f"Rede gerada em {ARQUIVO_SAIDA}")


# def main():
#     parser = argparse.ArgumentParser(description="Gerar definição de rede em JSON")
#     parser.add_argument(
#         "--tipo",
#         choices=sorted(GERADORES),
#         default="estrela",
#         help="Tipo de configuração de rede",
#     )
#     parser.add_argument(
#         "--n-sensores", type=int, default=15, help="Número total de sensores"
#     )
#     parser.add_argument(
#         "--n-aps", type=int, default=1, help="Número total de access points"
#     )
#     parser.add_argument(
#         "--raio", type=float, default=150.0, help="Raio máximo em relação ao AP (m)"
#     )
#     parser.add_argument(
#         "--raio-min", type=float, default=150.0, help="Raio mínimo em relação ao AP (m)"
#     )
#     parser.add_argument(
#         "--dist-aps", type=float, default=250.0, help="Distância entre APs (m)"
#     )
#     parser.add_argument("--seed", type=int, default=42, help="Semente aleatória")
#     parser.add_argument(
#         "--saida", default=ARQUIVO_SAIDA, help="Arquivo JSON de saída"
#     )

#     args = parser.parse_args()

#     if args.n_sensores < 0:
#         parser.error("--n-sensores deve ser >= 0")
#     if args.n_aps <= 0:
#         parser.error("--n-aps deve ser > 0")
#     if args.raio_min < 0 or args.raio < args.raio_min:
#         parser.error("--raio deve ser >= --raio-min >= 0")

#     rede = GERADORES[args.tipo](
#         n_sensores=args.n_sensores,
#         n_aps=args.n_aps,
#         raio=args.raio,
#         raio_min=args.raio_min,
#         dist_aps=args.dist_aps,
#         seed=args.seed,
#     )

#     with open(args.saida, "w", encoding="utf-8") as arquivo:
#         json.dump(rede, arquivo, indent=4, ensure_ascii=False)

#     print(f"Rede gerada em {args.saida}")


# if __name__ == "__main__":
    # main()
