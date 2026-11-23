import { useEffect, useState } from 'react'
import { Activity } from 'lucide-react'
import { EventLog } from './components/EventLog'
import { FluxoExperimento } from './components/FluxoExperimento'
import { GraficoRede } from './components/GraficoRede'
import { Header } from './components/Header'
import { ScenarioPanel } from './components/ScenarioPanel'
import { SensorTable } from './components/SensorTable'
import { StatusCards } from './components/StatusCards'
import { TopologyMap } from './components/TopologyMap'
import { useEstado } from './hooks/useEstado'
import type { AmostraRede } from './types'

export default function App() {
  const { estado, erro, carregando, atualizadoEm } = useEstado()
  const [historico, setHistorico] = useState<AmostraRede[]>([])

  useEffect(() => {
    if (!estado) return

    setHistorico((anterior) => {
      const amostra: AmostraRede = {
        indice: anterior.length === 0 ? 0 : anterior[anterior.length - 1].indice + 1,
        rotulo: new Date().toLocaleTimeString('pt-BR'),
        latencia_pacote_ms:
          estado.metricas.latencia_media_pacote_s === null
            ? null
            : estado.metricas.latencia_media_pacote_s * 1000,
        throughput_agregado_kbps:
          estado.metricas.throughput_agregado_bps === null
            ? null
            : estado.metricas.throughput_agregado_bps / 1000,
        deteccoes: estado.metricas.deteccoes_cumulativas,
        audios_enviados: estado.metricas.audios_enviados,
        audios_recebidos: estado.metricas.audio_recebidos,
        pacotes_perdidos: estado.metricas.pacotes_perdidos,
      }

      return [...anterior, amostra].slice(-180)
    })
  }, [estado])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-[1600px] flex-col gap-4 p-4 lg:p-6">
        <Header
          estado={estado}
          erro={erro}
          carregando={carregando}
          atualizadoEm={atualizadoEm}
        />

        {!estado ? (
          <div className="flex min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center">
            <Activity className="h-8 w-8 animate-pulse text-cyan-300" />
            <p className="text-lg font-semibold text-slate-200">
              {erro ? 'Não foi possível carregar o estado' : 'Conectando ao monitoramento'}
            </p>
            <p className="max-w-xl text-sm text-slate-500">
              {erro ??
                'Aguardando o endpoint /api/estado retornar os dados do experimento.'}
            </p>
          </div>
        ) : (
          <>
            <StatusCards estado={estado} />

            <div className="grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
              <div className="flex min-w-0 flex-col gap-4">
                <FluxoExperimento metricas={estado.metricas} />
                <GraficoRede historico={historico} metricas={estado.metricas} />
                <TopologyMap sensores={estado.sensores} />
              </div>
              <div className="flex min-w-0 flex-col gap-4">
                <ScenarioPanel clusters={estado.clusters} />
                <EventLog eventos={estado.eventos} />
              </div>
            </div>

            <SensorTable sensores={estado.sensores} />
          </>
        )}
      </div>
    </div>
  )
}
