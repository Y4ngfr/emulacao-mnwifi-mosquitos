DENSIDADE_BAIXA = 0.5
DENSIDADE_MEDIA = 2.0
DENSIDADE_ALTA = 5.0
DENSIDADE_EXTREMA = 10.0

RUIDO_NULO = 30.0
RUIDO_BAIXO = 20.0
RUIDO_MEDIO = 10.0
RUIDO_MEDIO_ALTO = 15.0
RUIDO_ALTO = 5.0

TRANSMISSAO_BAIXA = 6.0
TRANSMISSAO_MEDIA_BAIXA = 9.0
TRANSMISSAO_MEDIA = 12.0
TRANSMISSAO_MEDIA_ALTA = 15.0
TRANSMISSAO_ALTA = 20.0

NUM_ESTAGIOS = 5

CENARIOS_ESTAGIADOS = {
    2: {
        "fator": "densidade_mosquitos",
        "valores": [DENSIDADE_BAIXA, 1.0, DENSIDADE_MEDIA, DENSIDADE_ALTA, DENSIDADE_EXTREMA],
        "fixos": {
            "ruido_audio": RUIDO_NULO,
            "qualidade_transmissao": TRANSMISSAO_ALTA,
        },
    },
    3: {
        "fator": "ruido_audio",
        "valores": [RUIDO_NULO, RUIDO_BAIXO, RUIDO_MEDIO_ALTO, RUIDO_MEDIO, RUIDO_ALTO],
        "fixos": {
            "densidade_mosquitos": DENSIDADE_MEDIA,
            "qualidade_transmissao": TRANSMISSAO_ALTA,
        },
    },
    4: {
        "fator": "qualidade_transmissao",
        "valores": [
            TRANSMISSAO_ALTA,
            TRANSMISSAO_MEDIA_ALTA,
            TRANSMISSAO_MEDIA,
            TRANSMISSAO_MEDIA_BAIXA,
            TRANSMISSAO_BAIXA,
        ],
        "fixos": {
            "densidade_mosquitos": DENSIDADE_MEDIA,
            "ruido_audio": RUIDO_BAIXO,
        },
    },
    5: {
        "fator": "densidade_mosquitos",
        "valores": [DENSIDADE_BAIXA],
        "fixos": {
            "ruido_audio": RUIDO_NULO,
            "qualidade_transmissao": TRANSMISSAO_ALTA,
        },
    },
    6: {
        "fator": "densidade_mosquitos",
        "valores": [DENSIDADE_MEDIA],
        "fixos": {
            "ruido_audio": RUIDO_NULO,
            "qualidade_transmissao": TRANSMISSAO_ALTA,
        },
    },
    7: {
        "fator": "densidade_mosquitos",
        "valores": [DENSIDADE_ALTA],
        "fixos": {
            "ruido_audio": RUIDO_NULO,
            "qualidade_transmissao": TRANSMISSAO_ALTA,
        },
    },
}

ATRIBUTOS_FATOR = {
    "densidade_mosquitos": "densidade",
    "ruido_audio": "ruido",
    "qualidade_transmissao": "transmissao",
}

class Cenario:
    def __init__(self, n_clusters, tempo_experimento, id_cenario, n_sensores=None):
        self.densidade = []
        self.ruido = []
        self.transmissao = []
        self.eventos = []
        self.id_cenario = id_cenario
        self.n_clusters = n_clusters
        self.n_sensores = n_sensores
        self.tempo_experimento = tempo_experimento
        self.tempo_s = 0

        self.config_estagios = CENARIOS_ESTAGIADOS.get(id_cenario)
        self.fator_variado = (
            self.config_estagios["fator"] if self.config_estagios else None
        )
        self.num_estagios = (
            len(self.config_estagios["valores"]) if self.config_estagios else 0
        )
        self.duracao_estagio_s = (
            max(1, int(tempo_experimento) // self.num_estagios)
            if self.config_estagios
            else 0
        )
        self.estado_atual = -1 if self.config_estagios else 0
        self.resultado_conectividade = {
            "gw_icmp_ok": 0,
            "gw_icmp_falhas": 0,
            "gw_icmp_tentativas": 0,
            "gw_icmp_sensores": "",
        }

        for i in range(n_clusters):
            self.densidade.append(DENSIDADE_BAIXA)
            self.ruido.append(RUIDO_NULO)
            self.transmissao.append(TRANSMISSAO_ALTA)

    def verificar_evento(self, tempo):
        if self.config_estagios:
            indice = min(
                self.num_estagios - 1,
                max(0, int(tempo) // self.duracao_estagio_s),
            )
            return self._aplicar_estagio(indice)

        verif = False

        if self.id_cenario == 1:
            verif = self.cenario_1(tempo)
        elif self.id_cenario == 2:
            verif = self.cenario_2(tempo)
        elif self.id_cenario == 3:
            verif = self.cenario_3(tempo)

        return verif

    def _aplicar_estagio(self, indice):
        if indice == self.estado_atual:
            return False

        self.estado_atual = indice
        self.tempo_s = indice * self.duracao_estagio_s
        valor = self.config_estagios["valores"][indice]
        fixos = self.config_estagios["fixos"]
        atributo = ATRIBUTOS_FATOR[self.fator_variado]

        for i in range(self.n_clusters):
            self.densidade[i] = fixos.get("densidade_mosquitos", self.densidade[i])
            self.ruido[i] = fixos.get("ruido_audio", self.ruido[i])
            self.transmissao[i] = fixos.get(
                "qualidade_transmissao", self.transmissao[i]
            )
            getattr(self, atributo)[i] = valor

        return True

    def cenario_1(self, tempo):
        if tempo >= 0 and self.estado_atual == 0:
            for i in range(self.n_clusters):
                self.densidade[i] = DENSIDADE_BAIXA
                self.ruido[i] = RUIDO_NULO
                self.transmissao[i] = TRANSMISSAO_ALTA
            self.estado_atual += 1

        elif tempo >= self.tempo_experimento // 3 and self.estado_atual == 1:
            for i in range(self.n_clusters):
                self.densidade[i] = DENSIDADE_MEDIA
                self.ruido[i] = RUIDO_BAIXO
                self.transmissao[i] = TRANSMISSAO_ALTA
            self.estado_atual += 1

        elif tempo >= 2 * self.tempo_experimento // 3 and self.estado_atual == 2:
            for i in range(self.n_clusters):
                self.densidade[i] = DENSIDADE_ALTA
                self.ruido[i] = RUIDO_MEDIO
                self.transmissao[i] = TRANSMISSAO_ALTA
            self.estado_atual += 1

        else:
            return False

        self.tempo_s = tempo
        return True

    def cenario_2(self, tempo):
        return False

    def cenario_3(self, tempo):
        return False

    def get_dict(self):
        estado = {"clusters": {}}
        for i in range(self.n_clusters):
            estado["clusters"][i] = {
                "densidade_mosquitos": self.densidade[i],
                "ruido_audio": self.ruido[i],
                "qualidade_transmissao": self.transmissao[i],
            }

        estado["cenario_id"] = self.id_cenario
        estado["id_cenario"] = self.id_cenario
        estado["n_clusters"] = self.n_clusters
        estado["n_sensores"] = self.n_sensores
        estado["duracao_s"] = self.tempo_experimento
        estado["estagio"] = max(0, self.estado_atual) + 1
        estado["indice_estagio"] = max(0, self.estado_atual)
        estado["num_estagios"] = self.num_estagios
        estado["duracao_estagio_s"] = self.duracao_estagio_s
        estado["tempo_s"] = self.tempo_s
        estado["fator_variado"] = self.fator_variado
        estado["gw_icmp_ok"] = self.resultado_conectividade.get("gw_icmp_ok", 0)
        estado["gw_icmp_falhas"] = self.resultado_conectividade.get("gw_icmp_falhas", 0)
        estado["gw_icmp_tentativas"] = self.resultado_conectividade.get(
            "gw_icmp_tentativas", 0
        )
        estado["gw_icmp_sensores"] = self.resultado_conectividade.get(
            "gw_icmp_sensores", ""
        )
        estado["valor_fator"] = (
            self.config_estagios["valores"][self.estado_atual]
            if self.config_estagios and self.estado_atual >= 0
            else None
        )
        return estado
