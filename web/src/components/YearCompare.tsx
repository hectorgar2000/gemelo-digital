'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  ResponsiveContainer, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { ChartSkeleton, ErrorState } from '@/components/ui'

const COLORS = ['#60A5FA', '#F87171', '#34D399', '#FBBF24', '#A78BFA']

// Años disponibles: desde 2016 hasta el año actual (se actualiza automáticamente)
const CURRENT_YEAR = new Date().getFullYear()
const ALL_YEARS = Array.from({ length: CURRENT_YEAR - 2015 }, (_, i) => 2016 + i)

type YearData = Record<number, { week: number; demand: number }[]>

export function YearCompare() {
  const [selected, setSelected] = useState<number[]>([CURRENT_YEAR - 2, CURRENT_YEAR - 1, CURRENT_YEAR])
  const [data,     setData]     = useState<YearData>({})
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(false)

  const fetchData = useCallback(() => {
    if (!selected.length) return
    setLoading(true)
    setError(false)
    fetch(`/api/compare?years=${selected.join(',')}`)
      .then(r => { if (!r.ok) throw new Error(); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(() => { setError(true); setLoading(false) })
  }, [selected])

  useEffect(() => { fetchData() }, [fetchData])

  // Combinar en un array de {week, [year]: demand}
  const merged: Record<number, Record<string, number>> = {}
  for (const year of selected) {
    for (const { week, demand } of data[year] ?? []) {
      if (!merged[week]) merged[week] = { week }
      merged[week][String(year)] = demand
    }
  }
  const chartData = Object.values(merged).sort((a, b) => a.week - b.week)

  function toggleYear(y: number) {
    setSelected(prev => {
      if (prev.includes(y))   return prev.filter(x => x !== y)
      if (prev.length >= 5)   return prev
      return [...prev, y]
    })
  }

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg">
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-white font-semibold text-lg">📅 Comparador interanual</h2>
          <p className="text-gray-400 text-xs mt-1">Demanda media semanal — selecciona hasta 5 años</p>
        </div>
      </div>

      {/* Selector de años */}
      <div className="flex flex-wrap gap-2 mb-5">
        {ALL_YEARS.map((y, i) => {
          const active = selected.includes(y)
          const color  = active ? COLORS[selected.indexOf(y)] : undefined
          return (
            <button
              key={y}
              onClick={() => toggleYear(y)}
              className={`px-3 py-1 rounded-lg text-sm font-medium transition-all border ${
                active
                  ? 'text-white border-transparent'
                  : 'text-gray-500 border-gray-700 hover:border-gray-500 hover:text-gray-300'
              }`}
              style={active ? { backgroundColor: color, borderColor: color } : {}}
            >
              {y}
            </button>
          )
        })}
      </div>

      {loading ? (
        <ChartSkeleton height={280} />
      ) : error ? (
        <ErrorState onRetry={fetchData} />
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis dataKey="week" stroke="#9CA3AF" tick={{ fontSize: 11 }}
                   label={{ value: 'Semana del año', position: 'insideBottom', fill: '#6B7280', fontSize: 11, dy: 10 }} />
            <YAxis stroke="#9CA3AF" tick={{ fontSize: 11 }}
                   tickFormatter={v => `${(v/1000).toFixed(0)}k`} unit="MW" />
            <Tooltip
              contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
              labelFormatter={w => `Semana ${w}`}
              formatter={(v, name) => [
                `${Number(v).toLocaleString('es-ES', { maximumFractionDigits: 0 })} MW`, String(name)
              ]}
            />
            <Legend wrapperStyle={{ color: '#D1D5DB', fontSize: 12 }} />
            {selected.map((y, i) => (
              <Line
                key={y} type="monotone" dataKey={String(y)} name={String(y)}
                stroke={COLORS[i]} strokeWidth={2} dot={false} connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
