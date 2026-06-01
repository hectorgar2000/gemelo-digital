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

  const hours   = RANGE_HOURS[rangeKey]    ?? 168
  const minutes = WINDOW_MINUTES[windowKey] ?? 60

  const sb = getSupabase()

  const { data, error } = await (sb.rpc('get_series', {
    p_hours:          hours,
    p_bucket_minutes: minutes,
  }) as any).range(0, 19999)

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json(
    (data as { ts: string; temperature: number | null; demand: number | null }[]).map(r => ({
      time:        r.ts,
      temperature: r.temperature,
      demand:      r.demand,
    }))
  )
}
