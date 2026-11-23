import { Activity, FileAudio, PackageCheck, Radio } from 'lucide-react'
import { formatarInteiro, formatarPercentual } from '../lib/format'
import type { Estado } from '../types'

interface StatusCardsProps {
  estado: Estado
}

export function StatusCards({ estado }: StatusCardsProps) {
  const { metricas } = estado
  const cartoes = [
    {
      titulo: 'Sensores prontos',
      valor: `${formatarInteiro(metricas.sensores_prontos)}/${formatarInteiro(metricas.sensores_total)}`,
      detalhe: 'Handshake MQTT concluído',
      icone: Radio,
      cor: 'bg-cyan-500/10 text-cyan-300',
    },
    {
      titulo: 'Detectando',
      valor: formatarInteiro(metricas.deteccoes),
      detalhe: 'Janelas classificadas como mosquito',
      icone: Activity,
      cor: 'bg-emerald-500/10 text-emerald-300',
    },
    {
      titulo: 'Taxa de entrega',
      valor: formatarPercentual(metricas.taxa_entrega, 1),
      detalhe: `${formatarInteiro(metricas.audio_recebidos)}/${formatarInteiro(metricas.audios_enviados)} áudios`,
      icone: PackageCheck,
      cor: 'bg-violet-500/10 text-violet-300',
    },
    {
      titulo: 'Áudios recebidos',
      valor: formatarInteiro(metricas.audio_recebidos),
      detalhe: `${formatarInteiro(metricas.streams)} streams RTP ativas`,
      icone: FileAudio,
      cor: 'bg-amber-500/10 text-amber-300',
    },
  ]

  return (
    <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {cartoes.map((cartao) => {
        const Icone = cartao.icone
        return (
          <article
            key={cartao.titulo}
            className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
                {cartao.titulo}
              </span>
              <span className={`rounded-lg p-2 ${cartao.cor}`}>
                <Icone className="h-4 w-4" />
              </span>
            </div>
            <p className="mt-3 text-2xl font-semibold text-slate-50">{cartao.valor}</p>
            <p className="mt-1 text-xs text-slate-500">{cartao.detalhe}</p>
          </article>
        )
      })}
    </section>
  )
}
