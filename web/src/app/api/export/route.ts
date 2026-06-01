import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

const RANGE_HOURS: Record<string, number> = {
  '-7d': 168, '-30d': 720, '-365d': 8760,
}

export async function GET(req: NextRequest) {
  const rangeKey = new URL(req.url).searchParams.get('range') ?? '-30d'
  const hours    = RANGE_HOURS[rangeKey] ?? 720
  const since    = new Date(Date.now() - hours * 3600 * 1000).toISOString()
  const sb       = getSupabase()

  type WRow = { ts: string; temperature_c: number | null; solar_radiation_wm2: number | null; humidity_pct: number | null; wind_speed_kmh: number | null }
  type ERow = { ts: string; demand_mw: number }
  type ARow = { ts: string; is_anomaly: number }

  const [wRes, eRes, aRes] = await Promise.all([
    sb.from('weather').select('ts,temperature_c,solar_radiation_wm2,humidity_pct,wind_speed_kmh').gte('ts', since).order('ts') as unknown as Promise<{ data: WRow[] | null }>,
    sb.from('energy').select('ts,demand_mw').gte('ts', since).order('ts') as unknown as Promise<{ data: ERow[] | null }>,
    sb.from('anomalies').select('ts,is_anomaly').gte('ts', since).order('ts') as unknown as Promise<{ data: ARow[] | null }>,
  ])

  const demandMap: Record<string, number> = {}
  for (const r of eRes.data ?? []) demandMap[r.ts] = r.demand_mw

  const anomalyMap: Record<string, number> = {}
  for (const r of aRes.data ?? []) anomalyMap[r.ts] = r.is_anomaly

  const header = 'timestamp,temperatura_c,radiacion_wm2,humedad_pct,viento_kmh,demanda_mw,anomalia\n'
  const lines  = (wRes.data ?? []).map(r => [
    r.ts,
    r.temperature_c       ?? '',
    r.solar_radiation_wm2 ?? '',
    r.humidity_pct        ?? '',
    r.wind_speed_kmh      ?? '',
    demandMap[r.ts]       ?? '',
    anomalyMap[r.ts]      ?? '',
  ].join(','))

  return new NextResponse(header + lines.join('\n'), {
    headers: {
      'Content-Type':        'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="gemelo_digital_${rangeKey.replace('-','')}.csv"`,
    },
  })
}
