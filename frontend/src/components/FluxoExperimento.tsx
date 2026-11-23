import { formatarInteiro, formatarPercentual } from '../lib/format'
import type { Metricas } from '../types'

interface FluxoExperimentoProps {
  metricas: Metricas
}

function razao(parte: number, total: number): number | null {
  return total > 0 ? parte / total : null
}

export function FluxoExperimento({ metricas }: FluxoExperimentoProps) {
  const etapas = [
    {
      titulo: 'Detecções',
      descricao: 'inferências positivas no sensor',
      valor: metricas.deteccoes_cumulativas,
      detalhe: 'total acumulado',
    },
    {
      titulo: 'Áudios enviados',
      descricao: 'streams RTP iniciados',
      valor: metricas.audios_enviados,
      detalhe: `${formatarPercentual(
        razao(metricas.audios_enviados, metricas.deteccoes_cumulativas),
      )} das detecções`,
    },
    {
      titulo: 'Áudios recebidos',
      descricao: 'áudios prontos no servidor',
      valor: metricas.audio_recebidos,
      detalhe: `${formatarPercentual(
        razao(metricas.audio_recebidos, metricas.audios_enviados),
      )} dos enviados`,
    },
  ]

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl shadow-black/10">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Fluxo do experimento</h2>
          <p className="text-xs text-slate-500">detecção → envio → recebimento</p>
        </div>
        <span className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-[10px] uppercase tracking-wider text-cyan-300">
          acumulado
        </span>
      </header>

      <div className="grid gap-6 sm:grid-cols-3">
        {etapas.map((etapa, indice) => (
          <div key={etapa.titulo} className="relative">
            <div className="h-full rounded-xl border border-slate-800 bg-slate-950/50 p-3">
              <p className="text-[10px] uppercase tracking-wider text-slate-500">
                etapa {indice + 1}
              </p>
              <p className="mt-1 text-xs font-medium text-slate-300">{etapa.titulo}</p>
              <p className="mt-2 text-2xl font-semibold text-white">
                {formatarInteiro(etapa.valor)}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">{etapa.descricao}</p>
              <p className="mt-2 text-xs font-medium text-cyan-300">{etapa.detalhe}</p>
            </div>
            {indice < etapas.length - 1 && (
              <span className="absolute -right-4 top-1/2 hidden -translate-y-1/2 text-slate-600 sm:block">
                →
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
