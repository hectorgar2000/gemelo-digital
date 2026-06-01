'use client'

import { useEffect, useState } from 'react'

type Cell = { week: number; hour: number; demand: number }

const MONTHS = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
// Semana ISO aproximada en que empieza cada mes (año no bisiesto)
const MONTH_WEEKS = [1, 5, 9, 14, 18, 22, 27, 31, 36, 40, 45, 49]

function demandColor(demand: number, min: number, max: number) {
  if (!demand) return '#1F2937'
  const t = (demand - min) / (max - min)
  if (t < 0.25) return `hsl(220, 80%, ${20 + t * 80}%)`
  if (t < 0.6)  return `hsl(${220 - (t - 0.25) * 400}, 80%, 50%)`
  return `hsl(${10 - (t - 0.6) * 20}, 90%, ${55 - (t - 0.6) * 20}%)`
}

export function HeatmapGrid() {
  const currentYear = new Date().getFullYear()
  const [year,   setYear]   = useState(currentYear - 1)
  const [cells,  setCells]  = useState<Cell[]>([])
  const [loading, setLoading] = useState(true)
  const [tooltip, setTooltip] = useState<{ week: number; hour: number; demand: number } | null>(null)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/heatmap?year=${year}`)
      .then(r => r.json())
      .then(d => { setCells(d); setLoading(false) })
  }, [year])

  const demands = cells.map(c => c.demand).filter(Boolean)
  // Percentil p5-p95 para que picos puntuales de invierno/verano no desplacen toda la escala
  const sorted  = [...demands].sort((a, b) => a - b)
  const min = sorted[Math.floor(sorted.length * 0.05)] ?? 0
  const max = sorted[Math.floor(sorted.length * 0.95)] ?? 1

  // Build lookup: grid[hour][week] = demand
  const grid: Record<number, Record<number, number>> = {}
  for (let h = 0; h < 24; h++) grid[h] = {}
  for (const c of cells) grid[c.hour][c.week] = c.demand

  const years = Array.from({ length: 10 }, (_, i) => currentYear - i)

  return (
    <div className="bg-gray-900 rounded-2xl p-5 shadow-lg">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-white font-semibold text-lg">🗓️ Patrón de demanda — Hora × Semana</h2>
          <p className="text-gray-400 text-xs mt-1">
            Cada celda = demanda media (MW). Azul=bajo · Amarillo=medio · Rojo=alto
          </p>
        </div>
        <select
          value={year}
          onChange={e => setYear(Number(e.target.value))}
          className="bg-gray-700 text-gray-200 text-sm rounded-lg px-3 py-1.5 border border-gray-600"
        >
          {years.map(y => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="h-64 flex items-center justify-center text-gray-500">Calculando heatmap...</div>
      ) : (
        <div className="overflow-x-auto">
          {/* Meses en el eje X — posición absoluta por semana de inicio */}
          <div className="relative h-5 mb-1 ml-8">
            {MONTHS.map((m, i) => (
              <span
                key={m}
                className="absolute text-gray-500 text-xs"
                style={{ left: `${((MONTH_WEEKS[i] - 1) / 53) * 100}%` }}
              >
                {m}
              </span>
            ))}
          </div>

          {/* Grid: filas = horas, columnas = semanas */}
          <div className="relative">
            {Array.from({ length: 24 }, (_, hour) => (
              <div key={hour} className="flex items-center mb-px">
                <div className="text-gray-500 text-xs w-8 text-right pr-1.5 flex-shrink-0">
                  {hour % 4 === 0 ? `${hour}h` : ''}
                </div>
                {Array.from({ length: 53 }, (_, wi) => {
                  const week = wi + 1
                  const demand = grid[hour]?.[week]
                  return (
                    <div
                      key={week}
                      className="flex-1 rounded-sm cursor-pointer transition-opacity hover:opacity-80"
                      style={{
                        height: 11,
                        backgroundColor: demand ? demandColor(demand, min, max) : '#111827',
                        margin: '0 0.5px',
                      }}
                      onMouseEnter={() => setTooltip({ week, hour, demand })}
                      onMouseLeave={() => setTooltip(null)}
                    />
                  )
                })}
              </div>
            ))}
          </div>

          {/* Leyenda */}
          <div className="flex items-center gap-2 mt-3 justify-end">
            <span className="text-gray-500 text-xs">Menos</span>
            {[0, 0.25, 0.5, 0.75, 1].map(t => (
              <div key={t} className="w-5 h-3 rounded-sm" style={{ backgroundColor: demandColor(min + t * (max - min), min, max) }} />
            ))}
            <span className="text-gray-500 text-xs">Más</span>
          </div>

          {/* Tooltip flotante */}
          {tooltip && (
            <div className="mt-2 text-center text-sm text-gray-300 bg-gray-800 rounded-lg py-2 px-4 inline-block">
              Semana {tooltip.week} · {tooltip.hour}:00h →{' '}
              <span className="text-white font-semibold">
                {tooltip.demand?.toLocaleString('es-ES')} MW
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
