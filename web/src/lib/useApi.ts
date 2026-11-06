'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Hook de carga de datos para los componentes del dashboard.
 *
 * - Cancela la petición anterior (AbortController) cuando cambia `key`, así una
 *   respuesta lenta de un rango antiguo nunca sobrescribe la del rango nuevo.
 * - `loading` se deriva comparando la clave pedida con la última resuelta, en
 *   lugar de hacer setState síncrono dentro del effect (regla
 *   react-hooks/set-state-in-effect del React Compiler).
 * - Mantiene los datos anteriores mientras carga la siguiente petición.
 *
 * @param key      Identifica la petición: al cambiar, se vuelve a pedir.
 * @param fetcher  Función que obtiene los datos; debe respetar `signal`.
 * @param initial  Valor inicial de `data` antes de la primera respuesta.
 */
export function useApi<T>(
  key: string,
  fetcher: (signal: AbortSignal) => Promise<T>,
  initial: T,
) {
  const [nonce, setNonce] = useState(0)
  const reqKey = `${key}#${nonce}`

  const [state, setState] = useState<{
    key: string | null
    data: T
    error: boolean
    updatedAt: Date | null
  }>({ key: null, data: initial, error: false, updatedAt: null })

  // Guardar el fetcher más reciente sin que su identidad dispare re-peticiones
  const fetcherRef = useRef(fetcher)
  useEffect(() => { fetcherRef.current = fetcher })

  useEffect(() => {
    const ctrl = new AbortController()
    fetcherRef.current(ctrl.signal)
      .then(data => setState({ key: reqKey, data, error: false, updatedAt: new Date() }))
      .catch(() => {
        if (ctrl.signal.aborted) return
        setState(s => ({ ...s, key: reqKey, error: true }))
      })
    return () => ctrl.abort()
  }, [reqKey])

  const reload = useCallback(() => setNonce(n => n + 1), [])

  return {
    data:      state.data,
    loading:   state.key !== reqKey,
    error:     state.key === reqKey && state.error,
    updatedAt: state.updatedAt,
    /** true hasta que llega la primera respuesta (con éxito o error) */
    firstLoad: state.key === null,
    reload,
  }
}

/** fetch + comprobación de status + JSON, respetando AbortSignal. */
export async function fetchJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const r = await fetch(url, { signal })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
  return r.json() as Promise<T>
}
