import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const years = (new URL(req.url).searchParams.get('years') ?? '2024,2025')
    .split(',').map(Number)
  const sb = getSupabase()

  const results: Record<number, { week: number; demand: number }[]> = {}

  await Promise.all(years.map(async year => {
    const { data } = await sb
      .from('energy')
      .select('ts,demand_mw')
      .gte('ts', `${year}-01-01T00:00:00Z`)
      .lte('ts', `${year}-12-31T23:59:59Z`)
      .order('ts')
      .limit(10000) as { data: { ts: string; demand_mw: number }[] | null }

    // Media semanal
    const acc: Record<number, { sum: number; n: number }> = {}
    for (const r of data ?? []) {
      const d     = new Date(r.ts)
      const start = new Date(Date.UTC(d.getUTCFullYear(), 0, 1))
      const week  = Math.ceil(((d.getTime() - start.getTime()) / 86400000 + start.getUTCDay() + 1) / 7)
      if (!acc[week]) acc[week] = { sum: 0, n: 0 }
      acc[week].sum += r.demand_mw
      acc[week].n   += 1
    }

    results[year] = Object.entries(acc)
      .map(([w, { sum, n }]) => ({ week: Number(w), demand: Math.round(sum / n) }))
      .sort((a, b) => a.week - b.week)
  }))

  return NextResponse.json(results)
}
