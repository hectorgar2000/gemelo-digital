import { NextResponse } from 'next/server'
import { getSupabase, type WeatherRow, type EnergyRow } from '@/lib/supabase'

export const revalidate = 60

export async function GET() {
  const sb = getSupabase()

  const [weather, energy] = await Promise.all([
    sb.from('weather')
      .select('temperature_c,humidity_pct,wind_speed_kmh,solar_radiation_wm2')
      .order('ts', { ascending: false })
      .limit(1)
      .single() as unknown as Promise<{ data: WeatherRow | null }>,
    sb.from('energy')
      .select('demand_mw')
      .order('ts', { ascending: false })
      .limit(1)
      .single() as unknown as Promise<{ data: EnergyRow | null }>,
  ])

  return NextResponse.json({
    temperature_c:       weather.data?.temperature_c       ?? null,
    humidity_pct:        weather.data?.humidity_pct        ?? null,
    wind_speed_kmh:      weather.data?.wind_speed_kmh      ?? null,
    solar_radiation_wm2: weather.data?.solar_radiation_wm2 ?? null,
    demand_mw:           energy.data?.demand_mw            ?? null,
  })
}
