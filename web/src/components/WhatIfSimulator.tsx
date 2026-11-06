'use client'

import { useState } from 'react'
import { useApi, fetchJson } from '@/lib/useApi'

/** Etiqueta del efecto térmico según la temperatura seleccionada. */
function thermalLabel(temp: number): string {
  if (temp < 15) return '❄️ Efecto calefacción eléctrica'
  if (temp > 28) return '🥵 Efecto aire acondicionado'
  return '✅ Zona de confort térmico — demanda mínima'
}
import {
  ResponsiveContainer, ComposedChart, Line, ReferenceLine,
  XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import { Skeleton, ErrorState } from '@/components/ui'

type Curve = { temp: number; demand: number }

function WhatIfSkeleton() {
  return (
    <div className="animate-pulse space-y-5">
      {/* Slider falso */}
      <div className="space-y-2">
        <div className="flex justify-between">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-6 w-12" />
        </div>
        <Skeleton className="h-2 w-full rounded-full" />
      </div>
      {/* Resultado falso */}
      <Skeleton className="h-24 w-full rounded-xl" />
      {/* Gráfico falso */}
      <Skeleton className="h-40 w-full rounded-xl" />
    </div>
  )
}

export function WhatIfSimulator() {
  const [temp, setTemp] = useState(20)
  const { data: curve, loading, error, reload: fetchData } = useApi<Curve[]>(
    'whatsif',
    signal => fetchJson<Curve[]>('/api/whatsif', signal),
    [],
  )

  const bandTemp  = Math.floor(temp / 2) * 2
  const predicted = curve.find(c => c.temp === bandTemp)?.demand ?? null

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg">
      <h2 className="text-white font-semibold text-lg mb-1">🎛️ Simulador What-If</h2>
      <p className="text-gray-400 text-xs mb-5">¿Cuánta demanda esperar según la temperatura?</p>

      {loading ? (
        <WhatIfSkeleton />
      ) : error ? (
        <ErrorState onRetry={fetchData} />
      ) : (
        <>
          {/* Slider */}
          <div className="mb-6">
            <div className="flex justify-between text-sm text-gray-400 mb-2">
              <span>Temperatura</span>
              <span className="text-white font-bold text-xl">{temp} °C</span>
            </div>
            <input
              type="range" min={-4} max={44} value={temp}
              onChange={e => setTemp(Number(e.target.value))}
              className="w-full h-2 rounded-lg appearance-none cursor-pointer bg-gradient-to-r from-blue-500 via-green-400 to-red-500"
            />
            <div className="flex justify-between text-xs text-gray-600 mt-1">
              <span>−4°C</span><span>20°C</span><span>44°C</span>
            </div>
          </div>

          {/* Resultado */}
          <div className="bg-gray-800 rounded-xl p-4 mb-5 text-center">
            <div className="text-gray-400 text-sm mb-1">
              Demanda estimada a {temp}°C
              {temp !== bandTemp && (
                <span className="text-gray-600 ml-1">(banda {bandTemp}–{bandTemp + 2}°C)</span>
              )}
            </div>
            <div className="text-4xl font-bold text-blue-400">
              {predicted !== null ? predicted.toLocaleString('es-ES') : '—'}
              <span className="text-xl font-normal text-gray-400 ml-2">MW</span>
            </div>
            <div className="text-xs text-gray-500 mt-2">
              {thermalLabel(temp)}
            </div>
          </div>

          {/* Curva U */}
          <ResponsiveContainer width="100%" height={160}>
            <ComposedChart data={curve} margin={{ top: 5, right: 10, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="temp" stroke="#9CA3AF" tick={{ fontSize: 10 }} unit="°C" />
              <YAxis stroke="#9CA3AF" tick={{ fontSize: 10 }}
                     tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151', borderRadius: 8 }}
                formatter={(v) => [`${Number(v).toLocaleString('es-ES')} MW`, 'Demanda media']}
                labelFormatter={v => `${v}°C`}
              />
              <ReferenceLine x={bandTemp} stroke="#60A5FA" strokeDasharray="4 2" />
              <Line dataKey="demand" stroke="#60A5FA" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
