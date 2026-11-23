import { SlidersHorizontal } from 'lucide-react'
import { formatarNumero } from '../lib/format'
import type { ClusterEstado } from '../types'

interface ScenarioPanelProps {
  clusters: Record<string, ClusterEstado>
}

export function ScenarioPanel({ clusters }: ScenarioPanelProps) {
  const entradas = Object.entries(clusters).sort(([a], [b]) => Number(a) - Number(b))

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10">
      <div className="mb-4 flex items-center gap-2">
        <SlidersHorizontal className="h-4 w-4 text-cyan-300" />
        <h2 className="text-sm font-semibold text-slate-200">Estado do cenário por cluster</h2>
      </div>

      {entradas.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-500">
          Nenhum estado de cenário disponível.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="pb-2 pr-3">Cluster</th>
                <th className="pb-2 pr-3">Densidade</th>
                <th className="pb-2 pr-3">Ruído</th>
                <th className="pb-2">Tx</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {entradas.map(([chave, cluster]) => (
                <tr key={chave} className="text-slate-300">
                  <td className="py-2 pr-3 font-medium text-slate-100">cluster_{chave}</td>
                  <td className="py-2 pr-3">{formatarNumero(cluster.densidade_mosquitos, 2)}</td>
                  <td className="py-2 pr-3">{formatarNumero(cluster.ruido_audio, 1, ' dB')}</td>
                  <td className="py-2">{formatarNumero(cluster.qualidade_transmissao, 1, ' dBm')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
