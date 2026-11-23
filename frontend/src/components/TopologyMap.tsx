import { Network } from 'lucide-react'
import type { SensorEstado } from '../types'

interface TopologyMapProps {
  sensores: SensorEstado[]
}

interface Ponto {
  id: number
  nome: string
  cluster: number
  x: number
  y: number
  detectando: boolean
  monitorando: boolean
  pronto: boolean
}

export function TopologyMap({ sensores }: TopologyMapProps) {
  const pontos: Ponto[] = sensores.flatMap((sensor) => {
    if (!sensor.coordenada) return []
    const [x, y] = sensor.coordenada
    return [
      {
        id: sensor.id,
        nome: sensor.nome,
        cluster: sensor.cluster,
        x,
        y,
        detectando: sensor.detectando,
        monitorando: sensor.monitorando,
        pronto: sensor.pronto,
      },
    ]
  })

  if (pontos.length === 0) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-4 flex items-center gap-2">
          <Network className="h-4 w-4 text-cyan-300" />
          <h2 className="text-sm font-semibold text-slate-200">Topologia</h2>
        </div>
        <div className="flex h-[300px] items-center justify-center rounded-lg border border-dashed border-slate-700 text-sm text-slate-500">
          Coordenadas indisponíveis para desenhar a rede.
        </div>
      </section>
    )
  }

  const minX = Math.min(...pontos.map((ponto) => ponto.x))
  const maxX = Math.max(...pontos.map((ponto) => ponto.x))
  const minY = Math.min(...pontos.map((ponto) => ponto.y))
  const maxY = Math.max(...pontos.map((ponto) => ponto.y))
  const largura = Math.max(maxX - minX, 1)
  const altura = Math.max(maxY - minY, 1)
  const xSvg = (x: number) => 56 + ((x - minX) / largura) * 788
  const ySvg = (y: number) => 306 - ((y - minY) / altura) * 244

  const centros = new Map<number, { x: number; y: number; total: number }>()
  for (const ponto of pontos) {
    const centro = centros.get(ponto.cluster) ?? { x: 0, y: 0, total: 0 }
    centro.x += xSvg(ponto.x)
    centro.y += ySvg(ponto.y)
    centro.total += 1
    centros.set(ponto.cluster, centro)
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg shadow-black/10">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Network className="h-4 w-4 text-cyan-300" />
        <h2 className="text-sm font-semibold text-slate-200">Topologia da rede</h2>
        <div className="ml-auto flex flex-wrap items-center gap-3 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rotate-45 rounded-[2px] bg-amber-400" /> AP
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> detectando
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-cyan-400" /> ativo
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-slate-500" /> inativo
          </span>
        </div>
      </div>

      <svg viewBox="0 0 900 360" className="h-auto w-full rounded-xl bg-slate-950/70">
        <defs>
          <pattern id="malha" width="36" height="36" patternUnits="userSpaceOnUse">
            <path d="M 36 0 L 0 0 0 36" fill="none" stroke="#0f172a" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width="900" height="360" fill="url(#malha)" />

        {pontos.map((ponto) => {
          const centro = centros.get(ponto.cluster)
          if (!centro) return null
          return (
            <line
              key={`linha-${ponto.id}`}
              x1={centro.x / centro.total}
              y1={centro.y / centro.total}
              x2={xSvg(ponto.x)}
              y2={ySvg(ponto.y)}
              stroke="#1e293b"
              strokeWidth={1}
            />
          )
        })}

        {Array.from(centros.entries()).map(([cluster, centro]) => {
          const cx = centro.x / centro.total
          const cy = centro.y / centro.total
          return (
            <g key={`ap-${cluster}`}>
              <rect
                x={cx - 7}
                y={cy - 7}
                width={14}
                height={14}
                rx={2}
                transform={`rotate(45 ${cx} ${cy})`}
                fill="#fbbf24"
                stroke="#020617"
                strokeWidth={2}
              />
              <text x={cx} y={cy + 24} textAnchor="middle" fill="#94a3b8" fontSize={11}>
                AP {cluster}
              </text>
            </g>
          )
        })}

        {pontos.map((ponto) => {
          const cor = ponto.detectando
            ? '#34d399'
            : ponto.monitorando
              ? '#22d3ee'
              : ponto.pronto
                ? '#64748b'
                : '#ef4444'

          return (
            <circle
              key={`sensor-${ponto.id}`}
              cx={xSvg(ponto.x)}
              cy={ySvg(ponto.y)}
              r={6}
              fill={cor}
              stroke="#020617"
              strokeWidth={2}
            >
              <title>{`${ponto.nome} · cluster_${ponto.cluster}`}</title>
            </circle>
          )
        })}
      </svg>
    </section>
  )
}
