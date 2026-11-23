import type { ClusterEstado, Estado, Evento, Metricas, SensorEstado } from '../types'

const CAMINHO_ESTADO = '/api/estado'

type Objeto = Record<string, unknown>

export async function buscarEstado(sinal: AbortSignal): Promise<Estado> {
  const resposta = await fetch(CAMINHO_ESTADO, {
    signal: sinal,
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  })

  if (!resposta.ok) {
    throw new Error(`Falha ao consultar a API: HTTP ${resposta.status}`)
  }

  return normalizarEstado(await resposta.json())
}

export function normalizarEstado(dados: unknown): Estado {
  const bruto = objeto(dados)
  const experimentoBruto = objeto(bruto.experimento)

  const sensores: SensorEstado[] = lista(bruto.sensores).map((item, indice) => {
    const sensor = objeto(item)
    const id = numero(sensor.id) ?? indice

    return {
      id,
      nome: texto(sensor.nome ?? sensor.id, `sensor_${id}`),
      cluster: numero(sensor.cluster ?? sensor.grupo) ?? 0,
      ip: sensor.ip === undefined || sensor.ip === null ? null : texto(sensor.ip),
      coordenada: coordenada(sensor.coordenada ?? sensor.posicao),
      pronto: booleano(sensor.pronto ?? sensor.ready),
      monitorando: booleano(sensor.monitorando ?? sensor.ativo),
      detectando: booleano(sensor.detectando ?? sensor.detectado),
      latencia_media_s: numero(
        sensor.latencia_media_s ?? sensor.latencia ?? sensor.latencia_media,
      ),
      pacotes_perdidos: numero(sensor.pacotes_perdidos) ?? 0,
      ultimo_evento:
        sensor.ultimo_evento === undefined || sensor.ultimo_evento === null
          ? null
          : texto(sensor.ultimo_evento ?? sensor.evento),
      ultima_atualizacao:
        sensor.ultima_atualizacao === undefined && sensor.atualizado_em === undefined
          ? null
          : texto(sensor.ultima_atualizacao ?? sensor.atualizado_em),
    }
  })

  const clusters: Record<string, ClusterEstado> = {}
  for (const [chave, item] of Object.entries(objeto(bruto.clusters))) {
    const cluster = objeto(item)
    clusters[chave] = {
      densidade_mosquitos: numero(cluster.densidade_mosquitos ?? cluster.densidade),
      ruido_audio: numero(cluster.ruido_audio ?? cluster.ruido),
      qualidade_transmissao: numero(
        cluster.qualidade_transmissao ?? cluster.txpower ?? cluster.qualidade,
      ),
    }
  }

  const metricasBrutas = objeto(bruto.metricas)
  const metricas: Metricas = {
    sensores_prontos:
      numero(metricasBrutas.sensores_prontos) ?? sensores.filter((sensor) => sensor.pronto).length,
    sensores_total: numero(metricasBrutas.sensores_total) ?? sensores.length,
    deteccoes:
      numero(metricasBrutas.deteccoes) ?? sensores.filter((sensor) => sensor.detectando).length,
    streams:
      numero(metricasBrutas.streams) ?? sensores.filter((sensor) => sensor.monitorando).length,
    deteccoes_cumulativas: numero(metricasBrutas.deteccoes_cumulativas) ?? 0,
    audios_enviados: numero(metricasBrutas.audios_enviados) ?? 0,
    audio_recebidos:
      numero(metricasBrutas.audio_recebidos ?? metricasBrutas.audios_recebidos) ?? 0,
    taxa_entrega: numero(metricasBrutas.taxa_entrega),
    throughput_agregado_bps: numero(metricasBrutas.throughput_agregado_bps),
    latencia_media_pacote_s: numero(metricasBrutas.latencia_media_pacote_s),
    pacotes_recebidos: numero(metricasBrutas.pacotes_recebidos) ?? 0,
    pacotes_perdidos: numero(metricasBrutas.pacotes_perdidos) ?? 0,
  }

  const eventos: Evento[] = lista(bruto.eventos).map((item) => {
    const evento = objeto(item)
    return {
      tempo: texto(evento.tempo ?? evento.timestamp, ''),
      origem: texto(evento.origem ?? evento.sensor, 'sistema'),
      mensagem: texto(evento.mensagem ?? evento.texto, ''),
      nivel: texto(evento.nivel ?? evento.tipo, 'info'),
    }
  })

  return {
    timestamp: texto(bruto.timestamp, new Date().toISOString()),
    experimento: {
      fase: texto(experimentoBruto.fase ?? experimentoBruto.estado, 'aguardando'),
      tempo_decorrido_s: numero(
        experimentoBruto.tempo_decorrido_s ?? experimentoBruto.tempo_decorrido,
      ),
      duracao_s: numero(experimentoBruto.duracao_s ?? experimentoBruto.duracao),
      cenario_id: numero(experimentoBruto.cenario_id ?? experimentoBruto.cenario),
    },
    clusters,
    sensores,
    metricas,
    eventos,
  }
}

function objeto(valor: unknown): Objeto {
  if (typeof valor !== 'object' || valor === null || Array.isArray(valor)) return {}
  return valor as Objeto
}

function lista(valor: unknown): unknown[] {
  return Array.isArray(valor) ? valor : []
}

function texto(valor: unknown, padrao = ''): string {
  if (valor === undefined || valor === null) return padrao
  if (typeof valor === 'string') return valor
  if (typeof valor === 'number' || typeof valor === 'boolean') return String(valor)
  return padrao
}

function numero(valor: unknown): number | null {
  if (typeof valor === 'number') return Number.isFinite(valor) ? valor : null
  if (typeof valor !== 'string') return null
  const convertido = Number(valor.trim().replace(',', '.'))
  return Number.isFinite(convertido) ? convertido : null
}

function booleano(valor: unknown): boolean {
  if (typeof valor === 'boolean') return valor
  if (typeof valor === 'number') return valor !== 0
  if (typeof valor === 'string') {
    const normalizado = valor.trim().toLowerCase()
    return normalizado === 'true' || normalizado === '1' || normalizado === 'sim' || normalizado === 'yes'
  }
  return false
}

function coordenada(valor: unknown): [number, number, number] | null {
  if (Array.isArray(valor) && valor.length >= 3) {
    const x = numero(valor[0])
    const y = numero(valor[1])
    const z = numero(valor[2])
    return x !== null && y !== null && z !== null ? [x, y, z] : null
  }

  const objetoCoordenada = objeto(valor)
  const x = numero(objetoCoordenada.x)
  const y = numero(objetoCoordenada.y)
  const z = numero(objetoCoordenada.z)
  return x !== null && y !== null && z !== null ? [x, y, z] : null
}
