export function formatarNumero(valor: number | null, casas = 2, sufixo = ''): string {
  if (valor === null || !Number.isFinite(valor)) return '—'
  return `${valor.toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })}${sufixo}`
}

export function formatarInteiro(valor: number | null): string {
  if (valor === null || !Number.isFinite(valor)) return '—'
  return Math.round(valor).toLocaleString('pt-BR')
}

export function formatarPercentual(valor: number | null, casas = 0): string {
  if (valor === null || !Number.isFinite(valor)) return '—'
  return `${(valor * 100).toLocaleString('pt-BR', {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })}%`
}

export function formatarMs(segundos: number | null, casas = 0): string {
  if (segundos === null || !Number.isFinite(segundos)) return '—'
  return formatarNumero(segundos * 1000, casas, ' ms')
}

export function formatarDuracao(segundos: number | null): string {
  if (segundos === null || !Number.isFinite(segundos)) return '—'

  const total = Math.max(0, Math.floor(segundos))
  const horas = Math.floor(total / 3600)
  const minutos = Math.floor((total % 3600) / 60)
  const restante = total % 60
  const partes = [minutos, restante].map((parte) => String(parte).padStart(2, '0'))

  return horas > 0 ? `${horas}:${partes.join(':')}` : partes.join(':')
}

export function formatarHorario(valor: string | null): string {
  if (!valor) return '—'

  const data = new Date(valor)
  if (Number.isNaN(data.getTime())) return valor
  return data.toLocaleTimeString('pt-BR')
}

export function classeFase(fase: string): string {
  const normalizada = fase.trim().toLowerCase()

  if (normalizada.includes('erro') || normalizada.includes('falha')) {
    return 'border-red-500/30 bg-red-500/10 text-red-300'
  }
  if (normalizada.includes('execut')) {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
  }
  if (normalizada.includes('pront')) {
    return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300'
  }
  if (normalizada.includes('inici')) {
    return 'border-amber-500/30 bg-amber-500/10 text-amber-300'
  }
  return 'border-slate-600/40 bg-slate-700/30 text-slate-300'
}

export function classeEvento(nivel: string): string {
  const normalizado = nivel.trim().toLowerCase()

  if (normalizado.includes('erro')) return 'bg-red-500/10 text-red-300'
  if (normalizado.includes('aviso')) return 'bg-amber-500/10 text-amber-300'
  if (normalizado.includes('sucess')) return 'bg-emerald-500/10 text-emerald-300'
  return 'bg-slate-700/40 text-slate-300'
}
