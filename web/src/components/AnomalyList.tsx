'use client'

import { useEffect, useState, useCallback } from 'react'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'
import { ErrorState, Skeleton } from '@/components/ui'

type Anomaly = { time: string; nivel: string; zscore: number | null }

const NIVEL_CONFIG = {
  alta:  { bg: 'bg-red-900/40',    border: 'border-red-500',    dot: 'bg-red-500',    label: 'Alta' },
  media: { bg: 'bg-orange-900/40', border: 'border-orange-500', dot: 'bg-orange-400', label: 'Media' },
}

function AnomalySkeleton() {
  return (
    <div className="space-y-2">
      {[0, 1, 2, 3].map(i => (
        <Skeleton key={i} className="h-14" />
      ))}
</div>
  )
}

export function AnomalyList() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [range,     setRange]     = useState('-30d')
  const [loading,   setLoading]   = useState(true)
  const [error,     setError]     = useState(false)

  const fetchData = useCallback(() => {
    setLoading(true)
    setError(false)
    fetch(`/api/anomalies?range=${range}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(d => { setAnomalies(d); setLoading(false) })
      .catch(() => { setError(true); setLoading(false) })
  }, [range])

  useEffect(() => { fetchData() }, [fetchData])

  const alta  = anomalies.filter(a => a.nivel === 'alta').length
  const media = anomalies.filter(a => a.nivel === 'media').length

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-white font-semibold text-lg">🚨 Anomalías detectadas</h2>
          {!loading && !error && (
            <p className="text-gray-400 text-xs mt-1">
              <span className="text-red-400 font-medium">{alta} alta</span>
              {' · '}
              <span className="text-orange-400 font-medium">{media} media</span>
              {' confianza'}
            </p>
          )}
        </div>
        <select
          value={range}
          onChange={e => setRange(e.target.value)}
          className="bg-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1 border border-gray-600"
        >
          <option value="-7d">7 días</option>
          <option value="-30d">30 días</option>
          <option value="-90d">3 meses</option>
          <option value="-365d">1 año</option>
        </select>
      </div>

      {loading ? (
        <AnomalySkeleton />
      ) : error ? (
        <ErrorState onRetry={fetchData} />
      ) : anomalies.length === 0 ? (
        <div className="flex-1 flex items-center justify-center text-gray-500 text-sm">
          ✅ Sin anomalías en el período seleccionado
        </div>
      ) : (
        <div className="space-y-2 overflow-y-auto max-h-72 pr-1">
          {anomalies.map((a, i) => {
            const cfg = NIVEL_CONFIG[a.nivel as keyof typeof NIVEL_CONFIG]
            if (!cfg) return null
            return (
              <div key={i} className={`flex items-center gap-3 rounded-xl px-4 py-2.5 border ${cfg.bg} ${cfg.border}`}>
                <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${cfg.dot}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-medium">
                    {format(parseISO(a.time), "EEEE dd MMM, HH:mm", { locale: es })}
                  </div>
                  <div className="text-gray-400 text-xs">
                    Confianza {cfg.label.toLowerCase()}
                    {a.zscore !== null ? ` · Z-score ${a.zscore.toFixed(2)}` : ''}
                  </div>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                  a.nivel === 'alta' ? 'bg-red-600 text-white' : 'bg-orange-600 text-white'
                }`}>
                  {cfg.label}
                </span>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
