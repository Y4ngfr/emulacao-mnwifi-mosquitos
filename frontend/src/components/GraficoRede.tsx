import { Activity, Clock3, PackageCheck, TriangleAlert } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatarInteiro, formatarNumero } from '../lib/format'
import type { AmostraRede, Metricas } from '../types'

interface GraficoRedeProps {
  historico: AmostraRede[]
  metricas: Metricas
}

export function GraficoRede({ historico, metricas }: GraficoRedeProps) {
  const latenciaMs =
    metricas.latencia_media_pacote_s === null
      ? null
      : metricas.latencia_media_pacote_s * 1000
  const vazaoKbps =
    metricas.throughput_agregado_bps === null
      ? null
      : metricas.throughput_agregado_bps / 1000

  const indicadores = [
    {
      titulo: 'Vazão agregada',
      valor: formatarNumero(vazaoKbps, 1, ' kbps'),
      icone: Activity,
      cor: 'text-emerald-300',
    },
    {
      titulo: 'Latência média/pacote',
      valor: formatarNumero(latenciaMs, 2, ' ms'),
      icone: Clock3,
      cor: 'text-cyan-300',
    },
    {
      titulo: 'Pacotes recebidos',
      valor: formatarInteiro(metricas.pacotes_recebidos),
      icone: PackageCheck,
      cor: 'text-sky-300',
    },
    {
      titulo: 'Pacotes perdidos',
      valor: formatarInteiro(metricas.pacotes_perdidos),
      icone: TriangleAlert,
      cor: 'text-amber-300',
    },
  ]

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 shadow-xl shadow-black/10">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-200">Métricas de rede</h2>
          <p className="text-xs text-slate-500">totais globais no servidor por pacote RTP</p>
        </div>
        <span className="rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-1 text-[10px] uppercase tracking-wider text-slate-400">
          {historico.length} amostras
        </span>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {indicadores.map((indicador) => {
          const Icone = indicador.icone
          return (
            <div
              key={indicador.titulo}
              className="flex items-center gap-3 rounded-xl border border-slate-800 bg-slate-950/50 p-3"
            >
              <Icone className={`h-4 w-4 shrink-0 ${indicador.cor}`} />
              <div className="min-w-0">
                <p className="text-[11px] text-slate-500">{indicador.titulo}</p>
                <p className={`mt-0.5 text-sm font-semibold ${indicador.cor}`}>
                  {indicador.valor}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="mt-4 h-64">
        {historico.length === 0 ? (
          <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-800 text-xs text-slate-500">
            Aguardando amostras de rede...
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={historico} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="rotulo"
                stroke="#64748b"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                minTickGap={40}
              />
              <YAxis
                yAxisId="latencia"
                stroke="#22d3ee"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={44}
                domain={[0, 'auto']}
              />
              <YAxis
                yAxisId="vazao"
                orientation="right"
                stroke="#34d399"
                tick={{ fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={52}
                domain={[0, 'auto']}
              />
              <Tooltip
                contentStyle={{
                  background: '#020617',
                  border: '1px solid #1e293b',
                  borderRadius: 12,
                  fontSize: 11,
                }}
                labelStyle={{ color: '#cbd5e1' }}
                formatter={(valor, nome) => {
                  const numero = Number(valor)
                  if (!Number.isFinite(numero)) return ['—', nome]
                  return [
                    nome === 'Latência/pacote'
                      ? `${numero.toLocaleString('pt-BR', {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })} ms`
                      : `${numero.toLocaleString('pt-BR', {
                          minimumFractionDigits: 1,
                          maximumFractionDigits: 1,
                        })} kbps`,
                    nome,
                  ]
                }}
              />
              <Line
                yAxisId="latencia"
                type="monotone"
                dataKey="latencia_pacote_ms"
                name="Latência/pacote"
                stroke="#22d3ee"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
              <Line
                yAxisId="vazao"
                type="monotone"
                dataKey="throughput_agregado_kbps"
                name="Vazão agregada"
                stroke="#34d399"
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  )
}
