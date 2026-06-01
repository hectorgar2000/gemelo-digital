import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const year = new URL(req.url).searchParams.get('year') ?? String(new Date().getFullYear() - 1)
  const sb   = getSupabase()

  const { data } = await sb
    .from('energy')
    .select('ts,demand_mw')
    .gte('ts', `${year}-01-01T00:00:00Z`)
    .lte('ts', `${year}-12-31T23:59:59Z`)
    .order('ts') as unknown as { data: { ts: string; demand_mw: number }[] | null }

  // Agrupar por semana ISO × hora del día
  const acc: Record<string, { sum: number; n: number }> = {}

  for (const r of data ?? []) {
    const d    = new Date(r.ts)
    const hour = d.getUTCHours()

    // Semana ISO aproximada (1-53)
    const start = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
    const week  = Math.ceil(((d.getTime() - start.getTime()) / 86400000 + start.getUTCDay() + 1) / 7)

    const key = `${week}_${hour}`
    if (!acc[key]) acc[key] = { sum: 0, n: 0 }
    acc[key].sum += r.demand_mw
    acc[key].n   += 1
  }

  const result = Object.entries(acc).map(([key, { sum, n }]) => {
    const [w, h] = key.split('_').map(Number)
    return { week: w, hour: h, demand: Math.round(sum / n) }
  })

  return NextResponse.json(result)
}
