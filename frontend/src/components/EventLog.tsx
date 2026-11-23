import { ScrollText } from 'lucide-react'
import { classeEvento, formatarHorario } from '../lib/format'
import type { Evento } from '../types'

interface EventLogProps {
  eventos: Evento[]
}

export function EventLog({ eventos }: EventLogProps) {
  const recentes = [...eventos].slice(-14).reverse()

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10">
      <div className="mb-4 flex items-center gap-2">
        <ScrollText className="h-4 w-4 text-cyan-300" />
        <h2 className="text-sm font-semibold text-slate-200">Eventos recentes</h2>
        <span className="ml-auto text-xs text-slate-500">{eventos.length} no total</span>
      </div>

      {recentes.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-500">
          Nenhum evento registrado.
        </p>
      ) : (
        <ol className="max-h-[320px] space-y-2 overflow-y-auto pr-1">
          {recentes.map((evento, indice) => (
            <li
              key={`${evento.tempo}-${evento.origem}-${indice}`}
              className="flex gap-3 rounded-lg border border-slate-800/80 bg-slate-950/40 p-2.5"
            >
              <span
                className={`h-fit rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase ${classeEvento(evento.nivel)}`}
              >
                {evento.nivel}
              </span>
              <div className="min-w-0">
                <p className="truncate text-xs text-slate-300">{evento.mensagem}</p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  {evento.origem} · {formatarHorario(evento.tempo)}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
