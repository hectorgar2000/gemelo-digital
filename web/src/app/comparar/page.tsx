'use client'

import { YearCompare } from '@/components/YearCompare'

// Rangos disponibles para exportar CSV
const EXPORT_RANGES = [
  { label: '7 días',  value: '-7d'   },
  { label: '30 días', value: '-30d'  },
  { label: '1 año',   value: '-365d' },
]

export default function Comparar() {
  return (
    <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">📊 Comparador interanual</h1>
          <p className="text-gray-400 text-sm mt-1">
            Superpone la demanda semanal de distintos años para identificar tendencias y estacionalidad
          </p>
        </div>
        {/* Export CSV */}
        <div className="flex flex-col gap-2 items-end">
          <span className="text-gray-500 text-xs">Exportar datos</span>
          {EXPORT_RANGES.map(r => (
            <a
              key={r.value}
              href={`/api/export?range=${r.value}`}
              download
              className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-gray-200 text-sm rounded-lg transition-colors flex items-center gap-2"
            >
              ⬇ CSV {r.label}
            </a>
          ))}
        </div>
      </div>

      <YearCompare />

      {/* Datos curiosos */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { icon: '📈', title: '¿Qué buscar?', text: 'Semanas 26–35 (verano) suelen ser las de mayor demanda. Compara 2021 vs 2022 para ver el impacto de las olas de calor.' },
          { icon: '❄️', title: 'Demanda de invierno', text: 'Semanas 1–8 y 45–52 muestran la curva invernal. En años fríos la demanda sube notablemente por calefacción eléctrica.' },
          { icon: '📉', title: 'Pandemia', text: 'El año 2020 (semanas 10–20) muestra una caída brusca de demanda industrial con el confinamiento.' },
        ].map(({ icon, title, text }) => (
          <div key={title} className="bg-gray-900 rounded-2xl p-4">
            <div className="text-2xl mb-2">{icon}</div>
            <h3 className="text-white font-medium mb-1">{title}</h3>
            <p className="text-gray-400 text-sm">{text}</p>
          </div>
        ))}
      </div>
    </main>
  )
}
