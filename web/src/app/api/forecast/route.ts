import { NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 300

export async function GET() {
  const flux = `
    from(bucket: "${bucket}")
      |> range(start: -4h, stop: 26h)
      |> filter(fn: (r) => r._measurement == "forecast" and
          (r._field == "demand_mw" or r._field == "demand_mw_upper" or r._field == "demand_mw_lower"))
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
  `

  const rows = await queryInflux<{
    _time: string
    demand_mw?: number
    demand_mw_upper?: number
    demand_mw_lower?: number
  }>(flux)

  return NextResponse.json(rows.map(r => ({
    time:  r._time,
    pred:  r.demand_mw       ?? null,
    upper: r.demand_mw_upper ?? null,
    lower: r.demand_mw_lower ?? null,
  })))
}
