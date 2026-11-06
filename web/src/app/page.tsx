'use client'

import { useEffect } from 'react'
import { useApi, fetchJson } from '@/lib/useApi'
import { KpiCard }       from '@/components/KpiCard'
import { DemandChart }   from '@/components/DemandChart'
import { ForecastChart } from '@/components/ForecastChart'
import { AnomalyList }   from '@/components/AnomalyList'
import { ErrorState }    from '@/components/ui'

type KPI = {
  temperature_c?:       number
  humidity_pct?:        number
  wind_speed_kmh?:      number
  solar_radiation_wm2?: number
  demand_mw?:           number
}

export default function Dashboard() {
  const {
    data: kpi, error: kpiError, firstLoad: kpiLoading, updatedAt: updated, reload: fetchKpi,
  } = useApi<KPI>('kpi', signal => fetchJson<KPI>('/api/kpi', signal), {})

  // Refresco automático cada minuto (mantiene los KPIs anteriores mientras carga)
  useEffect(() => {
    const id = setInterval(fetchKpi, 60_000)
    return () => clearInterval(id)
  }, [fetchKpi])

  return (
    <main className="max-w-7xl mx-auto px-6 py-6 space-y-6">

      {/* Título de página + indicador de actualización */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">⚡ Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">Madrid · Demanda peninsular española</p>
        </div>
        {updated && (
          <div className="text-right text-xs text-gray-500">
            <div>Actualizado: {updated.toLocaleTimeString('es-ES')}</div>
            <button onClick={fetchKpi} className="mt-1 text-blue-400 hover:text-blue-300 transition-colors">
              ↻ Refrescar
            </button>
          </div>
        )}
      </div>

      {/* KPIs */}
      {kpiError ? (
        <div className="bg-gray-900 rounded-2xl p-4">
          <ErrorState message="Error al cargar los KPIs" onRetry={fetchKpi} />
        </div>
      ) : (
        <section className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <KpiCard loading={kpiLoading} label="Demanda actual"  value={kpi.demand_mw           ?? null} unit="MW"   icon="⚡" color="bg-gradient-to-br from-blue-600   to-blue-800"   decimals={0} />
          <KpiCard loading={kpiLoading} label="Temperatura"     value={kpi.temperature_c       ?? null} unit="°C"   icon="🌡️" color="bg-gradient-to-br from-red-600    to-orange-700"  decimals={1} />
          <KpiCard loading={kpiLoading} label="Radiación solar" value={kpi.solar_radiation_wm2 ?? null} unit="W/m²" icon="☀️" color="bg-gradient-to-br from-yellow-500 to-orange-600"  decimals={0} />
          <KpiCard loading={kpiLoading} label="Humedad"         value={kpi.humidity_pct        ?? null} unit="%"    icon="💧" color="bg-gradient-to-br from-cyan-600   to-teal-700"    decimals={0} />
          <KpiCard loading={kpiLoading} label="Viento"          value={kpi.wind_speed_kmh      ?? null} unit="km/h" icon="🌬️" color="bg-gradient-to-br from-slate-600  to-slate-800"   decimals={1} />
        </section>
      )}

      {/* Gráfico demanda + temperatura */}
      <DemandChart />

      {/* Forecast + Anomalías */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ForecastChart />
        <AnomalyList />
      </div>

      <footer className="text-center text-gray-600 text-xs py-4 border-t border-gray-800">
        Datos: Open-Meteo ERA5 · REE API pública · Modelo Prophet · Supabase / PostgreSQL
      </footer>
    </main>
  )
}
