'use client'

import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine,
} from 'recharts'
import { format, parseISO } from 'date-fns'

type FPoint = { time: string; pred: number | null; upper: number | null; lower: number | null }
type DPoint = { time: string; demand: number | null }

export function ForecastChart() {
  const [forecast, setForecast] = useState<FPoint[]>([])
  const [real,     setReal]     = useState<DPoint[]>([])
  const [loading,  setLoading]  = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/forecast').then(r => r.json()),
      fetch('/api/series?range=-48h&window=1h').then(r => r.json()),
    ]).then(([fc, sr]) => {
      setForecast(fc)
      setReal(sr)
      setLoading(false)
    })
  }, [])

  // Mezclar real + forecast en un único array por tiempo.
  // La API forecast empieza 4h atrás, solapando con la ventana real.
  // Usar un Map keyed por timestamp evita duplicados: si un instante
  // tiene ambos, se fusionan en un solo punto (real + pred en el mismo objeto).
  const now = new Date().toISOString()
  type MPoint = { time: string; real: number | null; pred: number | null; upper: number | null; lower: number | null }
  const mergeMap = new Map<string, MPoint>()

  real.forEach((r: DPoint) => {
    mergeMap.set(r.time, { time: r.time, real: r.demand, pred: null, upper: null, lower: null })
  })
  forecast.forEach((f: FPoint) => {
    const existing = mergeMap.get(f.time)
    if (existing) {
      existing.pred  = f.pred
      existing.upper = f.upper
      existing.lower = f.lower
    } else {
      mergeMap.set(f.time, { time: f.time, real: null, pred: f.pred, upper: f.upper, lower: f.lower })
    }
  })

  const merged = Array.from(mergeMap.values()).sort((a, b) => a.time.localeCompare(b.time))

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-white font-semibold text-lg">🔮 Predicción Prophet — 24h</h2>
          <p className="text-gray-400 text-xs mt-1">Últimas 48h reales + próximas 24h estimadas</p>
        </div>
        {forecast.length > 0 && (
          <div className="text-right">
            <div className="text-orange-400 font-bold text-xl">
              {Math.max(...forecast.filter(f => f.pred).map(f => f.pred!)).toLocaleString('es-ES', { maximumFractionDigits: 0 })} MW
            </div>
            <div className="text-gray-400 text-xs">Pico previsto</div>
          </div>
        )}
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-gray-500">Cargando...</div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <ComposedChart data={merged} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="time"
                   tickFormatter={v => format(parseISO(v), 'dd/MM HH:mm')}
                   stroke="#9CA3AF" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 11 }}
                   tickFormatter={v => `${(v/1000).toFixed(0)}k`} unit="MW" />
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
              labelFormatter={v => format(parseISO(v), "dd/MM/yyyy HH:mm")}
              formatter={(v, name) => [`${Number(v).toLocaleString('es-ES', { maximumFractionDigits: 0 })} MW`, String(name)]}
            />
            <Legend wrapperStyle={{ color: '#D1D5DB', fontSize: 12 }} />
            <ReferenceLine x={now} stroke="#F59E0B" strokeDasharray="4 2"
                           label={{ value: 'Ahora', fill: '#F59E0B', fontSize: 11 }} />
            <Line dataKey="real" name="Real" stroke="#60A5FA" strokeWidth={2} dot={false} connectNulls={true} />
            <Area dataKey="upper" name="IC superior" stroke="transparent" fill="#F97316" fillOpacity={0.15} dot={false} />
            <Area dataKey="lower" name="IC inferior" stroke="transparent" fill="#1F2937" fillOpacity={1} dot={false} />
            <Line dataKey="pred" name="Predicción" stroke="#F97316" strokeWidth={2}
                  strokeDasharray="6 3" dot={false} connectNulls={false} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
