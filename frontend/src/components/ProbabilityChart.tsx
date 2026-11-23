import { useMemo } from 'react'
import { Activity } from 'lucide-react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { AmostraProbabilidade } from '../types'

interface ProbabilityChartProps {
  historico: AmostraProbabilidade[]
}

const CORES = ['#22d3ee', '#a78bfa', '#34d399', '#fbbf24', '#fb7185']

export function ProbabilityChart({ historico }: ProbabilityChartProps) {
  const ids = useMemo(() => {
    const ultima = historico[historico.length - 1]
    if (!ultima) return []

    return Object.entries(ultima.porSensor)
      .filter((entry): entry is [string, number] => typeof entry[1] === 'number')
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([id]) => Number(id))
  }, [historico])

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10">
      <div className="mb-4 flex items-center gap-2">
        <Activity className="h-4 w-4 text-cyan-300" />
        <h2 className="text-sm font-semibold text-slate-200">Probabilidade de mosquito</h2>
        <span className="ml-auto text-xs text-slate-500">últimas {historico.length} leituras</span>
      </div>

      {historico.length === 0 ? (
        <div className="flex h-[260px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-sm text-slate-500">
          Aguardando leituras de probabilidade...
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={historico} margin={{ top: 8, right: 12, bottom: 4, left: -12 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
            <XAxis dataKey="rotulo" stroke="#64748b" tick={{ fontSize: 11 }} minTickGap={40} />
            <YAxis
              domain={[0, 1]}
              stroke="#64748b"
              tick={{ fontSize: 11 }}
              tickFormatter={(valor: number) => `${Math.round(valor * 100)}%`}
            />
            <Tooltip
              contentStyle={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 12,
                fontSize: 12,
              }}
              labelStyle={{ color: '#cbd5e1' }}
              formatter={(valor) => {
                if (typeof valor === 'number') return `${(valor * 100).toFixed(1)}%`
                return String(valor)
              }}
            />
            <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
            <Line
              type="monotone"
              dataKey="p_medio"
              name="Média"
              stroke="#e2e8f0"
              strokeWidth={2}
              dot={false}
              connectNulls
              isAnimationActive={false}
            />
            {ids.map((id, indice) => (
              <Line
                key={id}
                type="monotone"
                dataKey={(ponto: AmostraProbabilidade) => ponto.porSensor[String(id)]}
                name={`sensor_${id}`}
                stroke={CORES[indice % CORES.length]}
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </section>
  )
}
