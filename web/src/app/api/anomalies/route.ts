import { NextRequest, NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 300

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const range = searchParams.get('range') || '-30d'

  const flux = `
    from(bucket: "${bucket}")
      |> range(start: ${range})
      |> filter(fn: (r) => r._measurement == "anomalies" and r._field == "is_anomaly" and r._value == 1)
      |> pivot(rowKey: ["_time", "nivel"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 100)
  `

  const rows = await queryInflux<{
    _time: string
    nivel: string
    is_anomaly: number
  }>(flux)

  const zFlux = `
    from(bucket: "${bucket}")
      |> range(start: ${range})
      |> filter(fn: (r) => r._measurement == "anomalies" and r._field == "z_score" and r.nivel != "normal")
      |> sort(columns: ["_time"], desc: true)
      |> limit(n: 100)
  `

  const zRows = await queryInflux<{ _time: string; _value: number; nivel: string }>(zFlux)
  const zByTime: Record<string, number> = {}
  for (const r of zRows) zByTime[r._time] = r._value

  return NextResponse.json(rows.map(r => ({
    time:  r._time,
    nivel: r.nivel,
    zscore: zByTime[r._time] ?? null,
  })))
}
