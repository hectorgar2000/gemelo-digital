import { NextRequest, NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 60

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const range  = searchParams.get('range')  || '-7d'
  const window = searchParams.get('window') || '1h'

  // Usamos join explícito en lugar de pivot para evitar que los tags distintos
  // (location=madrid vs source=ree_real) impidan fusionar las filas.
  const flux = `
    weather = from(bucket: "${bucket}")
      |> range(start: ${range})
      |> filter(fn: (r) => r._measurement == "weather" and r._field == "temperature_c")
      |> aggregateWindow(every: ${window}, fn: max, createEmpty: false)
      |> keep(columns: ["_time", "_value"])
      |> rename(columns: {_value: "temperature_c"})

    energy = from(bucket: "${bucket}")
      |> range(start: ${range})
      |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
      |> aggregateWindow(every: ${window}, fn: max, createEmpty: false)
      |> keep(columns: ["_time", "_value"])
      |> rename(columns: {_value: "demand_mw"})

    join(tables: {w: weather, e: energy}, on: ["_time"])
      |> sort(columns: ["_time"])
  `

  const rows = await queryInflux<{
    _time: string
    temperature_c?: number
    demand_mw?: number
  }>(flux)

  const data = rows.map(r => ({
    time:        r._time,
    temperature: r.temperature_c ?? null,
    demand:      r.demand_mw     ?? null,
  }))

  return NextResponse.json(data)
}
