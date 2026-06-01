import { HeatmapGrid }     from '@/components/HeatmapGrid'
import { WhatIfSimulator } from '@/components/WhatIfSimulator'

export default function Explorador() {
  return (
    <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">🔍 Explorador de patrones</h1>
        <p className="text-gray-400 text-sm mt-1">
          Visualiza cómo varía la demanda a lo largo del año y simula escenarios de temperatura
        </p>
      </div>

      <HeatmapGrid />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <WhatIfSimulator />

        {/* Info contextual */}
        <div className="bg-gray-900 rounded-2xl p-5 shadow-lg space-y-4">
          <h3 className="text-white font-semibold">📖 Cómo leer el heatmap</h3>
          <div className="space-y-3 text-sm text-gray-300">
            <div className="flex gap-3">
              <span className="text-2xl">🔵</span>
              <div><strong className="text-white">Azul oscuro</strong> — madrugada en invierno. Demanda mínima (~16.000 MW)</div>
            </div>
            <div className="flex gap-3">
              <span className="text-2xl">🟡</span>
              <div><strong className="text-white">Amarillo</strong> — mañanas de días laborables. Ramp-up de actividad industrial y comercial</div>
            </div>
            <div className="flex gap-3">
              <span className="text-2xl">🔴</span>
              <div><strong className="text-white">Rojo</strong> — tardes de verano (AC) y noches de invierno (calefacción). Picos de demanda</div>
            </div>
          </div>

          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-white font-semibold mb-2">💡 Curva en U de temperatura</h3>
            <p className="text-sm text-gray-400">
              La demanda eléctrica no es lineal con la temperatura. En la zona de confort (~18–22°C)
              la gente usa poco AC ni calefacción. Por debajo de 18°C sube la calefacción;
              por encima de 22°C, el aire acondicionado. Usa el slider para explorarlo.
            </p>
          </div>
        </div>
      </div>
    </main>
  )
}
