import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 60

const RANGE_HOURS: Record<string, number> = {
  '-24h': 24, '-7d': 168, '-30d': 720, '-365d': 8760,
}
const WINDOW_MINUTES: Record<string, number> = {
  '30m': 30, '3h': 180, '12h': 720, '1d': 1440,
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const rangeKey  = searchParams.get('range')  || '-7d'
  const windowKey = searchParams.get('window') || '1h'

  const hours   = RANGE_HOURS[rangeKey]   ?? 168
  const minutes = WINDOW_MINUTES[windowKey] ?? 60

  const since = new Date(Date.now() - hours * 3600 * 1000).toISOString()
  const sb    = getSupabase()

  const [wRows, eRows] = await Promise.all([
    sb.from('weather').select('ts,temperature_c').gte('ts', since).order('ts') as unknown as Promise<{ data: { ts: string; temperature_c: number | null }[] | null }>,
    sb.from('energy').select('ts,demand_mw').gte('ts', since).order('ts') as unknown as Promise<{ data: { ts: string; demand_mw: number }[] | null }>,
  ])

  // Agregar en ventanas de `minutes`
  function bucket(isoTs: string) {
    const ms = Math.floor(new Date(isoTs).getTime() / (minutes * 60000)) * (minutes * 60000)
    return new Date(ms).toISOString()
  }

  const tempMap: Record<string, number[]> = {}
  for (const r of wRows.data ?? []) {
    const b = bucket(r.ts)
    if (!tempMap[b]) tempMap[b] = []
    if (r.temperature_c != null) tempMap[b].push(r.temperature_c)
  }

  const demandMap: Record<string, number[]> = {}
  for (const r of eRows.data ?? []) {
    const b = bucket(r.ts)
    if (!demandMap[b]) demandMap[b] = []
    if (r.demand_mw != null) demandMap[b].push(r.demand_mw)
  }

  const allBuckets = [...new Set([...Object.keys(tempMap), ...Object.keys(demandMap)])].sort()

  const data = allBuckets.map(b => ({
    time:        b,
    temperature: tempMap[b]?.length   ? Math.max(...tempMap[b])   : null,
    demand:      demandMap[b]?.length ? Math.max(...demandMap[b]) : null,
  }))

  return NextResponse.json(data)
}
