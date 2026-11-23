import { useEffect, useState } from 'react'
import { buscarEstado } from '../api/estado'
import type { Estado } from '../types'

const INTERVALO_MS = 1000

export interface RetornoUseEstado {
  estado: Estado | null
  erro: string | null
  carregando: boolean
  atualizadoEm: number | null
}

export function useEstado(): RetornoUseEstado {
  const [estado, setEstado] = useState<Estado | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [carregando, setCarregando] = useState(true)
  const [atualizadoEm, setAtualizadoEm] = useState<number | null>(null)

  useEffect(() => {
    let ativo = true
    let controlador: AbortController | null = null

    async function atualizar() {
      controlador?.abort()
      controlador = new AbortController()

      try {
        const proximoEstado = await buscarEstado(controlador.signal)
        if (!ativo) return
        setEstado(proximoEstado)
        setErro(null)
        setAtualizadoEm(Date.now())
      } catch (erroAtual) {
        if (!ativo) return
        if (erroAtual instanceof DOMException && erroAtual.name === 'AbortError') return
        setErro(
          erroAtual instanceof Error ? erroAtual.message : 'Não foi possível consultar o estado.',
        )
      } finally {
        if (ativo) setCarregando(false)
      }
    }

    void atualizar()
    const intervalo = window.setInterval(() => void atualizar(), INTERVALO_MS)

    return () => {
      ativo = false
      window.clearInterval(intervalo)
      controlador?.abort()
    }
  }, [])

  return { estado, erro, carregando, atualizadoEm }
}
