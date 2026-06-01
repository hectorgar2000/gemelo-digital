import { NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 60   // caché 60 s

export async function GET() {
  const fields = [
    { key: 'temperature_c',       measurement: 'weather' },
    { key: 'humidity_pct',        measurement: 'weather' },
    { key: 'wind_speed_kmh',      measurement: 'weather' },
    { key: 'solar_radiation_wm2', measurement: 'weather' },
    { key: 'demand_mw',           measurement: 'energy'  },
  ]

  // La API REE publica puede tener un retraso de hasta 2h en los datos horarios,
  // por eso usamos -6h para asegurar que siempre encontramos el último dato de demanda.
  const flux = `
    from(bucket: "${bucket}")
      |> range(start: -6h)
      |> filter(fn: (r) =>
          (r._measurement == "weather" or r._measurement == "energy") and
          (r._field == "temperature_c" or r._field == "humidity_pct" or
           r._field == "wind_speed_kmh" or r._field == "solar_radiation_wm2" or
           r._field == "demand_mw"))
      |> group(columns: ["_field"])
      |> last()
  `

  const rows = await queryInflux<{ _field: string; _value: number; _time: string }>(flux)
  const kpi: Record<string, number> = {}
  for (const r of rows) kpi[r._field] = r._value

  return NextResponse.json(kpi)
}
