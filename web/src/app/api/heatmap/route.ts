import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const year = Number(new URL(req.url).searchParams.get('year') ?? new Date().getFullYear() - 1)
  const sb   = getSupabase()

  const { data, error } = await (sb.rpc('get_heatmap', { p_year: year }) as any).range(0, 1499)

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  return NextResponse.json(
    (data as { week: number; hour: number; demand: number }[]).map(r => ({
      week:   r.week,
      hour:   r.hour,
      demand: r.demand,
    }))
  )
}
