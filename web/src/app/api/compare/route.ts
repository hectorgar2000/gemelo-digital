import { NextRequest, NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const years = (searchParams.get('years') ?? '2024,2025').split(',').map(Number)

  const results: Record<number, { week: number; demand: number }[]> = {}

  await Promise.all(years.map(async (year) => {
    const flux = `
      import "date"
      from(bucket: "${bucket}")
        |> range(start: ${year}-01-01T00:00:00Z, stop: ${year}-12-31T23:59:59Z)
        |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
        |> aggregateWindow(every: 7d, fn: mean, createEmpty: false)
        |> map(fn: (r) => ({ _value: r._value, week: date.week(t: r._time) }))
        |> group()
        |> sort(columns: ["week"])
    `
    const rows = await queryInflux<{ week: number; _value: number }>(flux)
    results[year] = rows.map(r => ({ week: r.week, demand: Math.round(r._value) }))
  }))

  return NextResponse.json(results)
}
