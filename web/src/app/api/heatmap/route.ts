import { NextRequest, NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const year = new URL(req.url).searchParams.get('year') ?? '2025'

  // Devuelve media de demanda por (semana del año, hora del día)
  // resultado: array de { week, hour, demand }
  const flux = `
    import "date"
    import "math"

    from(bucket: "${bucket}")
      |> range(start: ${year}-01-01T00:00:00Z, stop: ${year}-12-31T23:59:59Z)
      |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
      |> map(fn: (r) => ({
          _value: r._value,
          _time:  r._time,
          hour:   date.hour(t: r._time),
          week:   date.week(t: r._time),
        }))
      |> group(columns: ["week", "hour"])
      |> mean()
      |> group()
  `

  const rows = await queryInflux<{
    week: number; hour: number; _value: number
  }>(flux)

  return NextResponse.json(
    rows.map(r => ({ week: r.week, hour: r.hour, demand: Math.round(r._value) }))
  )
}
