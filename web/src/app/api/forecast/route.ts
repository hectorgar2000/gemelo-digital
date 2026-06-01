import { NextResponse } from 'next/server'
import { getSupabase, type ForecastRow } from '@/lib/supabase'

export const revalidate = 300

export async function GET() {
  const sb    = getSupabase()
  const since = new Date(Date.now() - 4 * 3600 * 1000).toISOString()
  const until = new Date(Date.now() + 26 * 3600 * 1000).toISOString()

  const { data } = await sb
    .from('forecast')
    .select('ts,demand_mw,demand_mw_upper,demand_mw_lower')
    .gte('ts', since)
    .lte('ts', until)
    .order('ts') as unknown as { data: ForecastRow[] | null }

  return NextResponse.json(
    (data ?? []).map(r => ({
      time:  r.ts,
      pred:  r.demand_mw,
      upper: r.demand_mw_upper,
      lower: r.demand_mw_lower,
    }))
  )
}
