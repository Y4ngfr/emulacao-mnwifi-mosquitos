import { formatarMs } from '../lib/format'
import type { SensorEstado } from '../types'

interface SensorTableProps {
  sensores: SensorEstado[]
}

function statusDoSensor(sensor: SensorEstado): { texto: string; classes: string } {
  if (sensor.detectando) {
    return { texto: 'detectando', classes: 'bg-emerald-500/10 text-emerald-300' }
  }
  if (sensor.monitorando) {
    return { texto: 'monitorando', classes: 'bg-cyan-500/10 text-cyan-300' }
  }
  if (sensor.pronto) {
    return { texto: 'pronto', classes: 'bg-slate-700/40 text-slate-300' }
  }
  return { texto: 'offline', classes: 'bg-red-500/10 text-red-300' }
}

export function SensorTable({ sensores }: SensorTableProps) {
  const ordenados = [...sensores].sort((a, b) => a.id - b.id)
  const latencias = ordenados
    .map((sensor) => sensor.latencia_media_s)
    .filter((valor): valor is number => valor !== null && Number.isFinite(valor))
  const maxLatencia = latencias.length > 0 ? Math.max(...latencias) : 0

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-slate-200">Sensores</h2>
        <span className="text-xs text-slate-500">{ordenados.length} no cenário</span>
      </div>

      {ordenados.length === 0 ? (
        <p className="rounded-lg border border-dashed border-slate-700 p-4 text-sm text-slate-500">
          Nenhum sensor encontrado.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="pb-2 pr-3">Sensor</th>
                <th className="pb-2 pr-3">Cluster</th>
                <th className="pb-2 pr-3">Status</th>
                <th className="pb-2 pr-3">Latência média</th>
                <th className="pb-2 pr-3">IP</th>
                <th className="pb-2">Último evento</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {ordenados.map((sensor) => {
                const status = statusDoSensor(sensor)
                const largura = Math.max(
                  0,
                  Math.min(
                    100,
                    maxLatencia > 0 ? ((sensor.latencia_media_s ?? 0) / maxLatencia) * 100 : 0,
                  ),
                )

                return (
                  <tr key={sensor.id} className="align-middle text-slate-300">
                    <td className="py-2.5 pr-3 font-medium text-slate-100">{sensor.nome}</td>
                    <td className="py-2.5 pr-3">cluster_{sensor.cluster}</td>
                    <td className="py-2.5 pr-3">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${status.classes}`}
                      >
                        {status.texto}
                      </span>
                    </td>
                    <td className="py-2.5 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-800">
                          <div
                            className="h-full rounded-full bg-cyan-400"
                            style={{ width: `${largura}%` }}
                          />
                        </div>
                        <span className="w-20 tabular-nums">
                          {formatarMs(sensor.latencia_media_s, 0)}
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 pr-3 font-mono text-xs text-slate-400">
                      {sensor.ip ?? '—'}
                    </td>
                    <td className="max-w-[320px] truncate py-2.5 text-xs text-slate-400">
                      {sensor.ultimo_evento ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
