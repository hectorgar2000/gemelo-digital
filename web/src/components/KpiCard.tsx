'use client'

interface KpiCardProps {
  label: string
  value: number | null
  unit: string
  icon: string
  color: string
  decimals?: number
}

export function KpiCard({ label, value, unit, icon, color, decimals = 1 }: KpiCardProps) {
  return (
    <div className={`rounded-2xl p-5 text-white shadow-lg ${color}`}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm font-medium opacity-80">{label}</span>
        <span className="text-2xl">{icon}</span>
      </div>
      <div className="text-3xl font-bold">
        {value !== null ? value.toFixed(decimals) : '—'}
        <span className="text-lg font-normal ml-1 opacity-80">{unit}</span>
      </div>
    </div>
  )
}
