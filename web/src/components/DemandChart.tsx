'use client'

import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { format, parseISO } from 'date-fns'
import { es } from 'date-fns/locale'

const RANGES = [
  { label: '24h',  range: '-24h',  window: '30m' },
  { label: '7d',   range: '-7d',   window: '3h'  },
  { label: '30d',  range: '-30d',  window: '12h' },
  { label: '1 año', range: '-365d', window: '1d'  },
]

type Point = { time: string; temperature: number | null; demand: number | null }

function fmtTime(iso: string, range: string) {
  const d = parseISO(iso)
  if (range === '-24h') return format(d, 'HH:mm')
  if (range === '-7d')  return format(d, 'dd/MM HH:mm')
  return format(d, 'dd MMM', { locale: es })
}

function CustomTooltip({
  active, payload, label, range,
}: {
  active?: boolean
  payload?: { dataKey: string; value: number | null }[]
  label?: string
  range: string
}) {
  if (!active || !payload?.length || !label) return null

  const demand = payload.find(p => p.dataKey === 'demand')?.value
  const temp   = payload.find(p => p.dataKey === 'temperature')?.value

  return (
    <div className="rounded-lg px-3 py-2 text-sm shadow-lg"
         style={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}>
      <p className="text-gray-300 font-medium mb-1">{fmtTime(label, range)}</p>
      {demand != null && (
        <p className="text-blue-400">
          ⚡ {Number(demand).toLocaleString('es-ES', { maximumFractionDigits: 0 })} MW
        </p>
      )}
      {temp != null && (
        <p className="text-red-400">
          🌡️ {Number(temp).toFixed(1)} °C
        </p>
      )}
    </div>
  )
}

export function DemandChart() {
  const [range, setRange] = useState(RANGES[0])
  const [data,  setData]  = useState<Point[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/series?range=${range.range}&window=${range.window}`)
      .then(r => r.json())
      .then(d => { setData(d); setLoading(false) })
  }, [range])

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-white font-semibold text-lg">⚡ Demanda y Temperatura</h2>
        <div className="flex gap-2">
          {RANGES.map(r => (
            <button
              key={r.label}
              onClick={() => setRange(r)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                r.label === range.label
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-gray-500">Cargando...</div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={data} margin={{ top: 5, right: 30, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="time"
              tickFormatter={v => fmtTime(v, range.range)}
              stroke="#9CA3AF"
              tick={{ fontSize: 11 }}
              interval="preserveStartEnd"
            />
            <YAxis yAxisId="left"  stroke="#60A5FA" tick={{ fontSize: 11 }}
                   tickFormatter={v => `${(v/1000).toFixed(0)}k`} label={{ value: 'MW', angle: -90, position: 'insideLeft', fill: '#60A5FA', fontSize: 12 }} />
            <YAxis yAxisId="right" orientation="right" stroke="#F87171"
                   tick={{ fontSize: 11 }} unit="°C"
                   label={{ value: '°C', angle: 90, position: 'insideRight', fill: '#F87171', fontSize: 12 }} />
            <Tooltip content={<CustomTooltip range={range.range} />} />
            <Legend wrapperStyle={{ color: '#D1D5DB', fontSize: 12 }} />
            <Area yAxisId="left" type="monotone" dataKey="demand" name="Demanda"
                  stroke="#3B82F6" fill="#1D4ED8" fillOpacity={0.15} strokeWidth={2} dot={false}
                  connectNulls={true} />
            <Line yAxisId="right" type="monotone" dataKey="temperature" name="Temperatura"
                  stroke="#EF4444" strokeWidth={2} dot={false} connectNulls={true} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
