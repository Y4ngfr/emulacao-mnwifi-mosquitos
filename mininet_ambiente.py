import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from time import monotonic, sleep, monotonic_ns
import cenario as c
import argparse
import gerar_rede
import agregar_metricas
import metricas_hardware
import matplotlib
matplotlib.use('TkAgg')

from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP 
from mn_wifi.cli import CLI
from mn_wifi.link import wmediumd
from mn_wifi.wmediumdConnector import interference
from mininet.log import setLogLevel, info

from definicao_bytes import FINALIZAR_EXPERIMENTO, TOPICO_FINALIZAR_EXPERIMENTO

DIR_BASE = os.path.dirname(os.path.abspath(__file__))
CAMINHO_REDE = os.path.join(DIR_BASE, "definicao_rede.json")
CAMINHO_AMBIENTE = os.path.join(DIR_BASE, "cenario_ambiente.json")
CAMINHO_SENSOR = os.path.join(DIR_BASE, "sensor.py")
CAMINHO_SERVIDOR = os.path.join(DIR_BASE, "servidor.py")
DIR_LOGS = os.path.join(DIR_BASE, "logs")
DIR_RESULTADOS = os.path.join(DIR_BASE, "resultados")
CAMINHO_MOSQUITTO_CONF = os.path.join(DIR_BASE, "mosquitto.conf")
CAMINHO_DONE_SERVIDOR = os.path.join(
    DIR_RESULTADOS, "servidor_inferencia.done"
)

RAIO_MIN = 15
RAIO_MAX = 30
DISTANCIA_APS = 150
TENTATIVAS_PING = 3
MAX_WORKERS_PING = 16

class Mininet_T:
    def __init__(self, n_sensores, n_APs, tempo, warmup, id_cenario):
        self.net = Mininet_wifi(
            link=wmediumd,
            wmediumd_mode=interference,
            accessPoint=OVSKernelAP,
            mode="g",   # 802.11g
            channel=3,
            autoAssociation=False,
            allAutoAssociation=False
        )

        self.n_sensores = n_sensores
        self.n_APs = n_APs
        self.n_clusters = n_APs
        self.tempo = tempo
        self.warmup = warmup
        self.id_cenario = id_cenario
        self.definicao_rede = None
        self.resultado_conectividade = {
            "gw_icmp_ok": 0,
            "gw_icmp_falhas": 0,
            "gw_icmp_tentativas": 0,
            "gw_icmp_sensores": "",
        }

    def construir_nos(self):
        with open(CAMINHO_REDE, encoding="utf-8") as arquivo:
            arquivo_definicao_rede = json.load(arquivo)

        self.definicao_rede = arquivo_definicao_rede

        info("Criando Servidor Central\n")
        for nome, dados in self.definicao_rede["servidor"].items():
            self.net.addHost(nome, ip=dados["ip"])

        info("Criando Cientistas\n")
        for nome, dados in self.definicao_rede["cientistas"].items():
            self.net.addHost(nome, ip=dados["ip"])

        info("*** Criando Access Points (Clusters)\n")
        for nome, dados in self.definicao_rede["pontos de acesso"].items():
            self.net.addAccessPoint(
                nome,
                ssid=f"cluster_{dados['id']}",
                mode='g',
                channel=self.net.channel,
                position=dados["coordenada"]
            )

        info("*** Criando Sensores\n")
        for nome, dados in self.definicao_rede["sensores"].items():
            cluster = int(dados["ip"].split(".")[1])

            self.net.addStation(
                nome,
                ssid=f"cluster_{cluster}",
                mode='g',
                channel=self.net.channel,
                ip=dados["ip"],
                position=dados["coordenada"]
            )

        self.net.setPropagationModel(model="logNormalShadowing")

    @staticmethod
    def _hostapd_cli(ap, comando):
        intf = ap.wintfs[0].name
        return ap.cmd(
            f"hostapd_cli -p /var/run/hostapd -i {intf} {comando} 2>&1"
        )

    def _estado_hostapd(self, ap):
        saida = self._hostapd_cli(ap, "status")

        for linha in saida.splitlines():
            if linha.startswith("state="):
                return linha.split("=", 1)[1].strip()

        if (
            "Failed to connect" in saida
            or "No such file" in saida
            or "command not found" in saida
        ):
            return "OFFLINE"

        return saida.strip() or "UNKNOWN"

    def aguardar_hostapd(self, timeout=30.0, intervalo=0.2):
        estados = {}

        for ap in self.net.aps:
            inicio = monotonic()
            estado = self._estado_hostapd(ap)

            while estado != "ENABLED" and monotonic() - inicio < timeout:
                sleep(intervalo)
                estado = self._estado_hostapd(ap)

            estados[ap.name] = estado

            if estado == "ENABLED":
                info(f"*** hostapd {ap.name} ({ap.wintfs[0].name}) pronto\n")
            else:
                info(
                    f"*** hostapd {ap.name} ({ap.wintfs[0].name}) "
                    f"nao ficou pronto: {estado}\n"
                )

        self.hostapd_status = estados
        return estados

    @staticmethod
    def _associar_sensor(sta, ap, timeout=20.0):
        intf = sta.wintfs[0].name
        ssid = ap.params["ssid"]

        sta.cmd(
            "sh -c 'iw dev %s disconnect 2>/dev/null; "
            "timeout %d iw dev %s connect -w %s 2>/dev/null'"
            % (intf, int(timeout), intf, ssid)
        )

        return "Connected to" in sta.cmd("iw dev %s link" % intf)

    def associar_wifi(self, timeout_hostapd=30.0, timeout_associacao=20.0):
        info("*** Aguardando hostapd...\n")
        estados = self.aguardar_hostapd(timeout=timeout_hostapd)

        aps_prontos = {
            ap.params["ssid"]: ap
            for ap in self.net.aps
            if estados.get(ap.name) == "ENABLED"
        }

        pendentes = []

        for sta in self.net.stations:
            ssid = sta.params.get("ssid")
            ap = aps_prontos.get(ssid)

            if ap is None:
                info(
                    f"*** {sta.name}: AP com ssid={ssid!r} nao esta pronto\n"
                )
                pendentes.append(sta.name)
                continue

            associado = False
            for tentativa in range(1, 6):
                if self._associar_sensor(sta, ap, timeout=timeout_associacao):
                    associado = True
                    break
                if tentativa < 5:
                    sleep(1)

            if associado:
                info(f"*** {sta.name} associado a {ap.name} ({ssid})\n")
            else:
                info(
                    f"*** {sta.name} FALHOU a associacao em "
                    f"{ap.name} ({ssid})\n"
                )
                pendentes.append(sta.name)

        if pendentes:
            info("*** %d sensores FALHARAM a associacao\n" % len(pendentes))

        return pendentes

    def add_backhaul_links(self):
        info("*** Configurando Backhaul (Ethernet)\n")

        self.net.addHost('gw', ip=None)
        self.net.addSwitch('sw', dpid='0000000000000001')

        nome_servidor = next(iter(self.definicao_rede["servidor"]))
        servidor = self.net[nome_servidor]

        for nome_ap in self.definicao_rede["pontos de acesso"]:
            self.net.addLink(self.net['gw'], self.net[nome_ap])

        self.net.addLink(servidor, self.net['gw'])
        self.net.addLink(servidor, self.net['sw'])

        for nome_cientista in self.definicao_rede["cientistas"]:
            self.net.addLink(self.net['sw'], self.net[nome_cientista])

    def configurar_rede(self):
        gw = self.net['gw']
        nome_servidor = next(iter(self.definicao_rede["servidor"]))
        servidor = self.net[nome_servidor]
        nomes_aps = list(self.definicao_rede["pontos de acesso"])
        n_aps = len(nomes_aps)

        gw.cmd('sysctl -w net.ipv4.ip_forward=1')

        for i in range(n_aps):
            gw.cmd(f'ip addr add 10.{i}.0.1/16 dev gw-eth{i}')
            gw.cmd(f'ip neigh flush dev gw-eth{i}')
            info(f"rede gw gw-eth{i} -> 10.{i}.0.1/16 \n")

        gw.cmd(f'ip addr add 11.0.0.2/16 dev gw-eth{n_aps}')
        gw.cmd(f'ip neigh flush dev gw-eth{n_aps}')
        gw.cmd('ip route add default via 11.0.0.10')

        for i in range(n_aps):
            servidor.cmd(f'ip route add 10.{i}.0.0/16 via 11.0.0.2')

        for nome_ap in nomes_aps:
            ap = self.net[nome_ap]
            bridge = ap.name
            radio = f'{ap.name}-wlan1'

            ap.cmd(
                f'ovs-vsctl --if-exists del-port {bridge} '
                f'{radio.replace("wlan1", "wlan2")}'
            )
            if radio not in ap.cmd(f'ovs-vsctl list-ports {bridge}'):
                ap.cmd(f'ovs-vsctl add-port {bridge} {radio}')
                ap.cmd(f'ip link set {radio} up')
            ap.cmd(f'ip link set {bridge} up')
            ap.cmd(
                f'ovs-ofctl add-flow {bridge} "priority=0,actions=NORMAL"'
            )

        for nome_sensor, dados in self.definicao_rede["sensores"].items():
            cluster = int(dados["ip"].split(".")[1])
            sta = self.net[nome_sensor]
            intf = sta.wintfs[0].name
            sta.cmd(f'ip route add default via 10.{cluster}.0.1 dev {intf}')

        servidor.cmd(f'ip addr add 11.0.1.1/24 dev {servidor.name}-eth1')
        servidor.cmd(f'ip link set {servidor.name}-eth1 up')

        self.net['sw'].cmd('ovs-ofctl add-flow sw priority=0,actions=NORMAL')

        for nome_cientista in self.definicao_rede["cientistas"]:
            self.net[nome_cientista].cmd('ip route add default via 11.0.1.1')

    def _ping_com_retentativas(self, nome_sensor, alvo, tentativas=TENTATIVAS_PING):
        sta = self.net[nome_sensor]
        for tentativa in range(1, tentativas + 1):
            saida = sta.cmd(
                f"ping -c 1 -W 1 {alvo} >/dev/null 2>&1 && echo ok"
            )
            if "ok" in saida:
                return True, tentativa
        return False, tentativas

    def _verificar_conectividade_sensor(self, nome_sensor, dados, ip_servidor):
        cluster = int(dados["ip"].split(".")[1])
        gateway = f"10.{cluster}.0.1"
        servidor_ok, servidor_tentativas = self._ping_com_retentativas(
            nome_sensor, ip_servidor
        )
        gateway_ok, gateway_tentativas = self._ping_com_retentativas(
            nome_sensor, gateway
        )
        return {
            "sensor": nome_sensor,
            "gateway": gateway,
            "servidor": ip_servidor,
            "servidor_ok": servidor_ok,
            "servidor_tentativas": servidor_tentativas,
            "gateway_ok": gateway_ok,
            "gateway_tentativas": gateway_tentativas,
        }

    def aguardar_conectividade(self, timeout=60.0):
        _, ip_servidor = self._nome_e_ip_servidor()
        sensores = self.definicao_rede["sensores"]
        inicio = monotonic()
        ultimos = {}
        pendentes = {}

        while monotonic() - inicio < timeout:
            pendentes = {}

            with ThreadPoolExecutor(
                max_workers=min(MAX_WORKERS_PING, len(sensores) or 1)
            ) as executor:
                futuros = {
                    executor.submit(
                        self._verificar_conectividade_sensor,
                        nome_sensor,
                        dados,
                        ip_servidor,
                    ): nome_sensor
                    for nome_sensor, dados in sensores.items()
                }
                for futuro in as_completed(futuros):
                    nome_sensor = futuros[futuro]
                    resultado = futuro.result()
                    ultimos[nome_sensor] = resultado
                    if not resultado["servidor_ok"]:
                        pendentes[nome_sensor] = [ip_servidor]

            gateway_com_falha = sorted(
                nome
                for nome, resultado in ultimos.items()
                if not resultado["gateway_ok"] and nome not in pendentes
            )
            self.resultado_conectividade = {
                "gw_icmp_ok": len(ultimos) - len(gateway_com_falha),
                "gw_icmp_falhas": len(gateway_com_falha),
                "gw_icmp_tentativas": sum(
                    resultado["gateway_tentativas"]
                    for resultado in ultimos.values()
                ),
                "gw_icmp_sensores": ",".join(gateway_com_falha),
            }

            if not pendentes:
                if gateway_com_falha:
                    info(
                        f"*** aviso: {len(gateway_com_falha)} sensores sem resposta ICMP "
                        "do gateway; servidor OK\n"
                    )
                    info("*** " + ", ".join(gateway_com_falha) + "\n")
                return

            info(
                f"*** {len(pendentes)} sensores sem resposta do servidor; "
                "tentando novamente\n"
            )
            sleep(0.5)

        detalhes = []
        for nome_sensor in sorted(pendentes):
            resultado = ultimos.get(nome_sensor, {})
            sta = self.net[nome_sensor]
            intf = sta.wintfs[0].name
            detalhes.append(
                f"{nome_sensor} alvos={', '.join(pendentes[nome_sensor])}\n"
                f"servidor_ok={resultado.get('servidor_ok')} "
                f"gateway_ok={resultado.get('gateway_ok')}\n"
                f"iw link: {sta.cmd(f'iw dev {intf} link')}\n"
                f"ip addr: {sta.cmd(f'ip addr show {intf}')}\n"
                f"ip route: {sta.cmd('ip route show')}\n"
                f"arp: {sta.cmd('arp -n')}"
            )

        for ap in self.net.aps:
            status = self._hostapd_cli(ap, "status")
            resumo = [
                linha
                for linha in status.splitlines()
                if linha.startswith(("state=", "ssid[", "num_sta[", "channel="))
            ]
            detalhes.append(f"{ap.name} hostapd: " + " | ".join(resumo))

        gw = self.net["gw"]
        clusters = sorted(
            {
                int(self.definicao_rede["sensores"][nome]["ip"].split(".")[1])
                for nome in pendentes
            }
        )
        for cluster in clusters:
            detalhes.append(
                f"gw-eth{cluster} neigh: "
                f"{gw.cmd(f'ip neigh show dev gw-eth{cluster}')}\n"
                f"gw-eth{cluster} icmp capturado: "
                f"{gw.cmd(f'timeout 2 tcpdump -n -i gw-eth{cluster} icmp -c 10 2>&1')}"
            )

        raise RuntimeError(
            "Sensores sem conectividade:\n" + "\n\n".join(detalhes)
        )

    def _nome_e_ip_servidor(self):
        nome_servidor = next(iter(self.definicao_rede["servidor"]))
        ip_servidor = self.definicao_rede["servidor"][nome_servidor]["ip"].split("/")[0]
        return nome_servidor, ip_servidor

    @staticmethod
    def _porta_aberta(host, porta, udp=False):
        opcao = "-lun" if udp else "-ltn"
        saida = host.cmd(f"ss {opcao} 2>/dev/null")
        return f":{porta}" in saida

    def _aguardar_porta(self, host, porta, timeout=15.0, udp=False):
        inicio = monotonic()

        while monotonic() - inicio < timeout:
            if self._porta_aberta(host, porta, udp=udp):
                return True
            sleep(0.2)

        return False

    def carregar_dataset(self):
        caminho = os.path.join(DIR_BASE, "Dataset-processado")

        for raiz, _, arquivos in os.walk(caminho):
            for nome in arquivos:
                if not nome.endswith(".npy"):
                    continue

                with open(os.path.join(raiz, nome), "rb") as arquivo:
                    while arquivo.read(1024 * 1024):
                        pass

    @staticmethod
    def _log_contem(caminho, marcador):
        if not os.path.exists(caminho):
            return False

        with open(caminho, encoding="utf-8", errors="replace") as arquivo:
            return marcador in arquivo.read()

    def _aguardar_marcador_log(self, caminho, marcador, timeout=60.0):
        inicio = monotonic()

        while monotonic() - inicio < timeout:
            if self._log_contem(caminho, marcador):
                return True
            sleep(0.2)

        return False

    def _aguardar_sensores_prontos(self, timeout=240.0):
        inicio = monotonic()
        pendentes = []

        while monotonic() - inicio < timeout:
            pendentes = []

            for nome_sensor, dados in self.definicao_rede["sensores"].items():
                log_sensor = os.path.join(
                    DIR_LOGS, f"sensor_{dados['id']}.log"
                )
                if not self._log_contem(
                    log_sensor, "AGUARDANDO_EXPERIMENTO"
                ):
                    pendentes.append(nome_sensor)

            if not pendentes:
                return

            sleep(0.2)

        raise RuntimeError(
            "Sensores nao ficaram prontos: " + ", ".join(pendentes)
        )

    def iniciar_servicos(self):
        os.makedirs(DIR_LOGS, exist_ok=True)

        nome_servidor, ip_servidor = self._nome_e_ip_servidor()
        servidor = self.net[nome_servidor]

        log_mosquitto = os.path.join(DIR_LOGS, "mosquitto.log")
        log_servidor = os.path.join(DIR_LOGS, "servidor.log")

        with open(CAMINHO_MOSQUITTO_CONF, "w", encoding="utf-8") as arquivo:
            arquivo.write(
                "listener 1883 0.0.0.0\n"
                "allow_anonymous true\n"
                "persistence false\n"
            )

        info(f"*** Iniciando Mosquitto em {nome_servidor} ({ip_servidor})\n")
        servidor.cmd(
            f"pkill -f '[m]osquitto -c {CAMINHO_MOSQUITTO_CONF}' 2>/dev/null"
        )
        servidor.cmd(
            f"mosquitto -c {CAMINHO_MOSQUITTO_CONF} "
            f"> {log_mosquitto} 2>&1 &"
        )

        if not self._aguardar_porta(servidor, 1883):
            raise RuntimeError(
                f"Mosquitto nao abriu a porta 1883 em {nome_servidor}; "
                f"veja {log_mosquitto}"
            )

        info(f"*** Iniciando servidor.py em {nome_servidor}\n")
        servidor.cmd(
            f"python3 -u {CAMINHO_SERVIDOR} --servidor-ip {ip_servidor} "
            f"> {log_servidor} 2>&1 &"
        )

        if not self._aguardar_porta(servidor, 9001, udp=True):
            raise RuntimeError(
                f"servidor.py nao abriu a porta 9001 em {nome_servidor}; "
                f"veja {log_servidor}"
            )

        if not self._aguardar_marcador_log(log_servidor, "SERVIDOR_PRONTO"):
            raise RuntimeError(
                f"servidor.py nao ficou pronto em {nome_servidor}; "
                f"veja {log_servidor}"
            )

        for nome_sensor, dados in self.definicao_rede["sensores"].items():
            sta = self.net[nome_sensor]
            sensor_id = dados["id"]
            cluster = int(dados["ip"].split(".")[1])
            log_sensor = os.path.join(DIR_LOGS, f"sensor_{sensor_id}.log")

            sta.cmd(
                f"python3 -u {CAMINHO_SENSOR} --sensor-id {sensor_id} "
                f"--cluster {cluster} --servidor-ip {ip_servidor} "
                f"> {log_sensor} 2>&1 &"
            )
            info(f"*** sensor.py iniciado em {nome_sensor}\n")

        self._aguardar_sensores_prontos()

    def executar_experimento(self):
        nome_servidor, _ = self._nome_e_ip_servidor()
        servidor = self.net[nome_servidor]

        servidor.cmd(
            "python3 -c 'import paho.mqtt.publish as p; "
            "p.single(\"experimento/solicitar\", payload=bytes([0x02]), "
            "qos=1, hostname=\"127.0.0.1\")'"
        )

    def finalizar_experimento(self, timeout=900.0):
        nome_servidor, _ = self._nome_e_ip_servidor()
        servidor = self.net[nome_servidor]

        if os.path.exists(CAMINHO_DONE_SERVIDOR):
            os.remove(CAMINHO_DONE_SERVIDOR)

        info("*** Parando sensores\n")
        for sta in self.net.stations:
            sta.cmd("pkill -f '[s]ensor.py' 2>/dev/null")
        sleep(1.0)

        carga = ", ".join(f"0x{b:02x}" for b in FINALIZAR_EXPERIMENTO)
        info("*** Solicitando finalizacao do servidor\n")
        servidor.cmd(
            "python3 -c 'import paho.mqtt.publish as p; "
            f"p.single(\"{TOPICO_FINALIZAR_EXPERIMENTO}\", payload=bytes([{carga}]), "
            "qos=1, hostname=\"127.0.0.1\")'"
        )

        t0 = monotonic()
        while monotonic() - t0 < timeout:
            if os.path.exists(CAMINHO_DONE_SERVIDOR):
                info("*** Finalizacao do servidor concluida\n")
                return True
            sleep(0.5)

        info("*** AVISO: finalizacao do servidor nao confirmada\n")
        return False

    def encerrar_servicos(self):
        if not hasattr(self, "definicao_rede"):
            return

        nome_servidor, _ = self._nome_e_ip_servidor()
        servidor = self.net[nome_servidor]

        info("*** Encerrando sensores\n")
        for sta in self.net.stations:
            sta.cmd("pkill -f '[s]ensor.py' 2>/dev/null")

        info("*** Encerrando servidor.py\n")
        servidor.cmd("pkill -f '[s]ervidor.py' 2>/dev/null")

        info("*** Encerrando Mosquitto\n")
        servidor.cmd(
            f"pkill -f '[m]osquitto -c {CAMINHO_MOSQUITTO_CONF}' 2>/dev/null"
        )

    def atualizar_ambiente(self, cenario):
        """
        Atualização do arquivo cenario_ambiente.json com escrita atômica
        """
        estado = cenario.get_dict()
        caminho_temporario = f"{CAMINHO_AMBIENTE}.{os.getpid()}.tmp"
        try:
            with open(caminho_temporario, "w", encoding="utf-8") as arquivo:
                json.dump(estado, arquivo, indent=4, ensure_ascii=False)
                arquivo.flush()
                os.fsync(arquivo.fileno())

            os.replace(caminho_temporario, CAMINHO_AMBIENTE)
        finally:
            if os.path.exists(caminho_temporario):
                os.remove(caminho_temporario)

    def aplicar_qualidade_transmissao(self, cenario):
        if cenario.id_cenario not in c.CENARIOS_ESTAGIADOS:
            return

        estado = cenario.get_dict()
        for chave_cluster, dados_cluster in estado["clusters"].items():
            txpower = float(dados_cluster["qualidade_transmissao"])
            for nome_sensor, dados_sensor in self.definicao_rede["sensores"].items():
                cluster = int(dados_sensor["ip"].split(".")[1])
                if cluster != int(chave_cluster):
                    continue
                sta = self.net[nome_sensor]
                interface = sta.wintfs[0].name
                saida = sta.cmd(
                    f"iw dev {interface} set txpower fixed "
                    f"{int(round(txpower * 100))} 2>&1"
                )
                if saida.strip():
                    info(
                        f"*** txpower {nome_sensor}={txpower:.0f}dBm: "
                        f"{saida.strip()}\n"
                    )

def executar_ambiente(n_sensores, n_APs, duracao, warmup, id_cenario, seed=100, sem_cli=False, saida_metricas=None, run_id=None, sensores_por_ap=None, repeticao=1):
    setLogLevel("info")

    if saida_metricas is None:
        saida_metricas = agregar_metricas.CAMINHO_SAIDA

    gerar_rede.gerar_rede(n_sensores, n_APs, RAIO_MAX, RAIO_MIN, DISTANCIA_APS, seed)

    sistema = Mininet_T(n_sensores, n_APs, duracao, warmup, id_cenario)

    print("Construindo nos...")
    sistema.construir_nos()
    print("Nos criados\n")

    print("Configurando backhaul...")
    sistema.add_backhaul_links()
    print("Backhaul configurado\n")

    print("Construindo topologia...")
    sistema.net.configureNodes()
    sistema.net.build()
    print("Topologia construida\n")


    sistema.net.plotGraph(
        min_x=-100, min_y=-100, max_x=500, max_y=500
    )

    print("Iniciando rede...")
    sistema.net.start()
    print("Rede concluida\n")

    try:
        print("Associando sensores...")
        pendentes = sistema.associar_wifi(timeout_hostapd=30.0,timeout_associacao=20.0)

        if pendentes:
            raise SystemExit("ERRO: sensores sem associacao Wi-Fi: " + ", ".join(pendentes))

        print("Associacao concluida\n")


        print("Configurando rotas...")
        sistema.configurar_rede()
        print("Rotas configuradas\n")

        print("Aguardando conectividade...")
        sistema.aguardar_conectividade()
        print("Conectividade pronta\n")

        print("Carregando Dataset...")
        sistema.carregar_dataset()
        print("Dataset Carregado\n")

        print("Configurando ambiente do cenário...")
        cenario = c.Cenario(
            sistema.n_clusters, sistema.tempo, sistema.id_cenario, sistema.n_sensores
        )
        cenario.verificar_evento(0)
        cenario.resultado_conectividade = sistema.resultado_conectividade
        print("Cenário iniciado\n")
        sistema.atualizar_ambiente(cenario)
        sistema.aplicar_qualidade_transmissao(cenario)

        print("Iniciando Serviços...")
        sistema.iniciar_servicos()
        print("Serviços iniciados\n")

        configuracao_hardware = {
            "run_id": run_id or "avulso",
            "cenario": id_cenario,
            "n_APs": n_APs,
            "sensores_por_AP": (
                sensores_por_ap
                if sensores_por_ap is not None
                else n_sensores // n_APs
            ),
            "n_sensores": n_sensores,
            "repeticao": repeticao,
            "seed": seed,
            "duracao": duracao,
            "warmup": warmup,
        }
        coletor_hardware = metricas_hardware.ColetorHardware(
            configuracao_hardware,
            intervalo=1.0,
        )

        print("Iniciando Experimento...")
        coletor_hardware.iniciar()
        try:
            sistema.executar_experimento()

            print(f"Duração Total do Experimento: {sistema.tempo}s")
            t0 = monotonic()
            while monotonic() - t0 < sistema.tempo:
                sleep(1)
                print(f"Tempo do experimento: {int(monotonic() - t0)}")
        finally:
            coletor_hardware.parar()

        print("Experimento Concluído\n")
        print("Servidor finalizando (decodificação/classificação ignoradas)...\n", flush=True)
        sistema.finalizar_experimento()
        agregar_metricas.agregar_metricas_sensores(sistema.definicao_rede, saida_metricas)
        agregar_metricas.agregar_metricas_rede()
        if not sem_cli:
            CLI(sistema.net)
    finally:
        sistema.encerrar_servicos()
        sistema.net.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Executar Topologia")
    parser.add_argument("--n_sensores", type=int, default=15, help="Define o número de sensores totais")
    parser.add_argument("--n_aps", type=int, default=3, help="Define o número de pontos de acesso totais")
    parser.add_argument("--duracao", type=int, default=300, help="Duração do experimento em segundos (tempo de coleta)")
    parser.add_argument("--warmup", type=int, default=0, help="Estabilização em segundos com o sistema completo rodando; os primeiros N s são descartados na análise (default 0)")
    parser.add_argument("--cenario", type=int, default=0, help="Escolha entre os cenários definidos")
    parser.add_argument("--seed", type=int, default=100, help="Semente aleatória da topologia")
    parser.add_argument("--run_id", default=None, help="Identificador da run")
    parser.add_argument("--sensores_por_ap", type=int, default=None, help="Sensores por AP da run")
    parser.add_argument("--repeticao", type=int, default=1, help="Repetição da configuração")
    parser.add_argument("--sem-cli", action="store_true", help="Não abrir CLI ao final")
    parser.add_argument("--saida-metricas", default=None, help="Arquivo CSV de métricas da run")
    args = parser.parse_args()

    executar_ambiente(
        n_sensores=args.n_sensores,
        n_APs=args.n_aps,
        duracao=args.duracao,
        warmup=args.warmup,
        id_cenario=args.cenario,
        seed=args.seed,
        sem_cli=args.sem_cli,
        saida_metricas=args.saida_metricas,
        run_id=args.run_id,
        sensores_por_ap=args.sensores_por_ap,
        repeticao=args.repeticao,
    )
