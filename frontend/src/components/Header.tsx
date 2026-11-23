import { Activity, CircleAlert, Clock3, RadioTower } from 'lucide-react'
import { classeFase, formatarDuracao, formatarHorario } from '../lib/format'
import type { Estado } from '../types'

interface HeaderProps {
  estado: Estado | null
  erro: string | null
  carregando: boolean
  atualizadoEm: number | null
}

export function Header({ estado, erro, carregando, atualizadoEm }: HeaderProps) {
  const fase = estado?.experimento.fase ?? 'aguardando'
  const tempo = estado?.experimento.tempo_decorrido_s ?? null
  const cenarioId = estado?.experimento.cenario_id ?? null
  const referencia = atualizadoEm
    ? new Date(atualizadoEm).toLocaleTimeString('pt-BR')
    : formatarHorario(estado?.timestamp ?? null)

  return (
    <header className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-2xl shadow-black/20 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-start gap-3">
        <div className="rounded-xl bg-cyan-500/10 p-3 text-cyan-300">
          <RadioTower className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-50 sm:text-2xl">
            Monitoramento do experimento
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Sensores MQTT/RTP em Mininet-WiFi · atualização a cada 1 s
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 font-medium ${classeFase(fase)}`}
        >
          <Activity className="h-3.5 w-3.5" />
          {fase}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/50 px-3 py-1.5 text-slate-300">
          <Clock3 className="h-3.5 w-3.5" />
          {formatarDuracao(tempo)}
        </span>
        <span className="rounded-full border border-slate-700 bg-slate-800/50 px-3 py-1.5 text-slate-300">
          Cenário {cenarioId ?? '—'}
        </span>
        {erro ? (
          <span
            title={erro}
            className="inline-flex items-center gap-1.5 rounded-full border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-red-300"
          >
            <CircleAlert className="h-3.5 w-3.5" />
            API indisponível
          </span>
        ) : (
          <span className="rounded-full border border-slate-700 bg-slate-800/50 px-3 py-1.5 text-slate-400">
            {carregando ? 'Conectando...' : `Atualizado ${referencia}`}
          </span>
        )}
      </div>
    </header>
  )
}
