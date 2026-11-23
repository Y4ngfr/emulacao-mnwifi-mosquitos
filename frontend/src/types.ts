export type FaseExperimento =
  | 'parado'
  | 'iniciando'
  | 'pronto'
  | 'executando'
  | 'finalizado'
  | 'erro'
  | string

export type NivelEvento = 'info' | 'sucesso' | 'aviso' | 'erro' | string

export interface Experimento {
  fase: FaseExperimento
  tempo_decorrido_s: number | null
  duracao_s: number | null
  cenario_id: number | null
}

export interface ClusterEstado {
  densidade_mosquitos: number | null
  ruido_audio: number | null
  qualidade_transmissao: number | null
}

export interface SensorEstado {
  id: number
  nome: string
  cluster: number
  ip: string | null
  coordenada: [number, number, number] | null
  pronto: boolean
  monitorando: boolean
  detectando: boolean
  latencia_media_s: number | null
  pacotes_perdidos: number
  ultimo_evento: string | null
  ultima_atualizacao: string | null
}

export interface Metricas {
  sensores_prontos: number
  sensores_total: number
  deteccoes: number
  streams: number
  deteccoes_cumulativas: number
  audios_enviados: number
  audio_recebidos: number
  taxa_entrega: number | null
  throughput_agregado_bps: number | null
  latencia_media_pacote_s: number | null
  pacotes_recebidos: number
  pacotes_perdidos: number
}

export interface Evento {
  tempo: string
  origem: string
  mensagem: string
  nivel: NivelEvento
}

export interface Estado {
  timestamp: string
  experimento: Experimento
  clusters: Record<string, ClusterEstado>
  sensores: SensorEstado[]
  metricas: Metricas
  eventos: Evento[]
}

export interface AmostraRede {
  indice: number
  rotulo: string
  latencia_pacote_ms: number | null
  throughput_agregado_kbps: number | null
  deteccoes: number
  audios_enviados: number
  audios_recebidos: number
  pacotes_perdidos: number
}

export interface AmostraProbabilidade {
  indice: number
  rotulo: string
  p_medio: number | null
  porSensor: Record<string, number | null>
}
