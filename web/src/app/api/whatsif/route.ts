import { NextResponse } from 'next/server'
import { queryInflux, bucket } from '@/lib/influx'

export const revalidate = 3600

// Devuelve la curva real demanda-media vs temperatura (bandas de 2°C)
// usada por el simulador what-if
export async function GET() {
  const flux = `
    import "math"

    joined = () => {
      weather = from(bucket: "${bucket}")
        |> range(start: -3y)
        |> filter(fn: (r) => r._measurement == "weather" and r._field == "temperature_c")
        |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)
        |> map(fn: (r) => ({_time: r._time, temp: r._value}))

      energy = from(bucket: "${bucket}")
        |> range(start: -3y)
        |> filter(fn: (r) => r._measurement == "energy" and r._field == "demand_mw")
        |> aggregateWindow(every: 1h, fn: mean, createEmpty: false)

      return join(tables: {w: weather, e: energy}, on: ["_time"])
    }

    joined()
      |> map(fn: (r) => ({
          _value:  r._value,
          tempBand: math.floor(x: r.temp / 2.0) * 2,
        }))
      |> group(columns: ["tempBand"])
      |> mean()
      |> group()
      |> sort(columns: ["tempBand"])
  `

  try {
    const rows = await queryInflux<{ tempBand: number; _value: number }>(flux)
    return NextResponse.json(
      rows.map(r => ({ temp: r.tempBand, demand: Math.round(r._value) }))
    )
  } catch {
    // Fallback: curva analítica basada en el modelo sintético conocido
    const curve = []
    for (let t = -4; t <= 44; t += 2) {
      let effect = 0
      if (t < 18) effect = Math.pow(18 - t, 1.6) * 130
      else if (t > 22) effect = Math.pow(t - 22, 1.8) * 90
      const demand = Math.round((24000 + effect) * 0.97) // factor horario medio
      curve.push({ temp: t, demand })
    }
    return NextResponse.json(curve)
  }
}
