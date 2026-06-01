import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const years = (new URL(req.url).searchParams.get('years') ?? '2024,2025')
    .split(',').map(Number)
  const sb = getSupabase()

  const results: Record<number, { week: number; demand: number }[]> = {}

  await Promise.all(years.map(async year => {
    const { data } = await (sb.rpc as Function)('get_weekly_demand', { p_year: year })
    results[year] = (data as { week: number; demand: number }[] ?? [])
  }))

  return NextResponse.json(results)
}
