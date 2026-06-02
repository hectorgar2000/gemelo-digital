import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const year = Number(new URL(req.url).searchParams.get('year') ?? new Date().getFullYear() - 1)
  const sb   = getSupabase()

  // supabase-js llama al RPC via POST — la paginación por .range() no funciona
  // en el cliente JS para llamadas POST a RPC (sí en Python). En su lugar
  // dividimos por rango de semanas: cada mitad devuelve <= 648 filas (< 1000).
  const [r1, r2] = await Promise.all([
    (sb.rpc as Function)('get_heatmap', { p_year: year, p_week_start: 1,  p_week_end: 26 }),
    (sb.rpc as Function)('get_heatmap', { p_year: year, p_week_start: 27, p_week_end: 53 }),
  ])

  const error = r1.error ?? r2.error
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  const data = [...(r1.data ?? []), ...(r2.data ?? [])] as { week: number; hour: number; demand: number }[]

  return NextResponse.json(
    data.map(r => ({ week: r.week, hour: r.hour, demand: r.demand }))
  )
}
