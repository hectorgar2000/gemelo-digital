import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

// C2: force-dynamic — el CSV debe ser siempre fresco, nunca cacheado
export const dynamic = 'force-dynamic'

const RANGE_HOURS: Record<string, number> = {
  '-7d': 168, '-30d': 720, '-365d': 8760,
}

// C4: normaliza cualquier formato ISO a 'YYYY-MM-DDTHH:MM' para el join
function tsKey(ts: string): string {
  return new Date(ts).toISOString().slice(0, 16)
}

export async function GET(req: NextRequest) {
  const rawRange = new URL(req.url).searchParams.get('range') ?? '-30d'
  const rangeKey = Object.hasOwn(RANGE_HOURS, rawRange) ? rawRange : '-30d'
  const hours    = RANGE_HOURS[rangeKey]
  const since    = new Date(Date.now() - hours * 3600 * 1000).toISOString()
  const sb       = getSupabase()

  type WRow = { ts: string; temperature_c: number | null; solar_radiation_wm2: number | null; humidity_pct: number | null; wind_speed_kmh: number | null }
  type ERow = { ts: string; demand_mw: number }
  type ARow = { ts: string; is_anomaly: number }

  // PostgREST aplica max_rows=1000 en el servidor aunque se pida .range(0, 9999),
  // así que el export de 1 año (8760 h) quedaba truncado a ~41 días.
  // Paginamos en bloques de 1000 hasta agotar los datos.
  async function fetchAll<T>(table: string, columns: string): Promise<T[]> {
    const PAGE = 1000
    const MAX_PAGES = 12   // 12.000 filas: 1 año + margen
    const rows: T[] = []
    for (let page = 0; page < MAX_PAGES; page++) {
      const { data, error } = await sb
        .from(table)
        .select(columns)
        .gte('ts', since)
        .order('ts')
        .range(page * PAGE, (page + 1) * PAGE - 1)
      if (error) throw new Error(`${table}: ${error.message}`)
      const batch = (data ?? []) as unknown as T[]
      rows.push(...batch)
      if (batch.length < PAGE) break
    }
    return rows
  }

  let wRows: WRow[], eRows: ERow[], aRows: ARow[]
  try {
    ;[wRows, eRows, aRows] = await Promise.all([
      fetchAll<WRow>('weather',   'ts,temperature_c,solar_radiation_wm2,humidity_pct,wind_speed_kmh'),
      fetchAll<ERow>('energy',    'ts,demand_mw'),
      fetchAll<ARow>('anomalies', 'ts,is_anomaly'),
    ])
  } catch (err) {
    return NextResponse.json({ error: (err as Error).message }, { status: 500 })
  }

  // C4: mapas por timestamp normalizado (YYYY-MM-DDTHH:MM) para join robusto
  const demandMap: Record<string, number>  = {}
  for (const r of eRows) demandMap[tsKey(r.ts)] = r.demand_mw

  const anomalyMap: Record<string, number> = {}
  for (const r of aRows) anomalyMap[tsKey(r.ts)] = r.is_anomaly

  const header = 'timestamp,temperatura_c,radiacion_wm2,humedad_pct,viento_kmh,demanda_mw,anomalia\n'
  const lines  = wRows.map(r => [
    r.ts,
    r.temperature_c       ?? '',
    r.solar_radiation_wm2 ?? '',
    r.humidity_pct        ?? '',
    r.wind_speed_kmh      ?? '',
    demandMap[tsKey(r.ts)]  ?? '',
    anomalyMap[tsKey(r.ts)] ?? '',
  ].join(','))

  return new NextResponse(header + lines.join('\n'), {
    headers: {
      'Content-Type':        'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="gemelo_digital_${rangeKey.replace('-', '')}.csv"`,
    },
  })
}
