import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 300

const RANGE_HOURS: Record<string, number> = {
  '-7d': 168, '-30d': 720, '-90d': 2160, '-365d': 8760,
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const rangeKey = searchParams.get('range') || '-30d'
  const hours    = RANGE_HOURS[rangeKey] ?? 720
  const since    = new Date(Date.now() - hours * 3600 * 1000).toISOString()
  const sb       = getSupabase()

  const { data } = await sb
    .from('anomalies')
    .select('ts,nivel,z_score')
    .gte('ts', since)
    .neq('nivel', 'normal')
    .order('ts', { ascending: false })
    .limit(100) as { data: { ts: string; nivel: string; z_score: number | null }[] | null }

  return NextResponse.json(
    (data ?? []).map(r => ({
      time:   r.ts,
      nivel:  r.nivel,
      zscore: r.z_score,
    }))
  )
}
