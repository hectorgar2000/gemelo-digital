import { NextRequest, NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const range = searchParams.get('range') ?? '-30d'

  const flux = `
    from(bucket: "${bucket}")
      |> range(start: ${range})
      |> filter(fn: (r) =>
          (r._measurement == "weather" and
           (r._field == "temperature_c" or r._field == "solar_radiation_wm2" or
            r._field == "humidity_pct"  or r._field == "wind_speed_kmh")) or
          (r._measurement == "energy"  and r._field == "demand_mw") or
          (r._measurement == "anomalies" and r._field == "is_anomaly"))
      |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"])
  `

  const rows = await queryInflux<{
    _time: string
    temperature_c?: number
    solar_radiation_wm2?: number
    humidity_pct?: number
    wind_speed_kmh?: number
    demand_mw?: number
    is_anomaly?: number
  }>(flux)

  const header = 'timestamp,temperatura_c,radiacion_wm2,humedad_pct,viento_kmh,demanda_mw,anomalia\n'
  const lines = rows.map(r =>
    [
      r._time,
      r.temperature_c       ?? '',
      r.solar_radiation_wm2 ?? '',
      r.humidity_pct        ?? '',
      r.wind_speed_kmh      ?? '',
      r.demand_mw           ?? '',
      r.is_anomaly          ?? '',
    ].join(',')
  )

  return new NextResponse(header + lines.join('\n'), {
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="gemelo_digital_${range.replace('-','')}.csv"`,
    },
  })
}
