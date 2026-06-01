import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET(req: NextRequest) {
  const year = Number(new URL(req.url).searchParams.get('year') ?? new Date().getFullYear() - 1)
  const sb   = getSupabase()

  // PostgREST max_rows=1000 por defecto. Un año completo tiene 52x24=1248 filas.
  // Paginamos en 2 requests paralelos para superar el límite sin tocar la config de Supabase.
  const [r1, r2] = await Promise.all([
    (sb.rpc as Function)('get_heatmap', { p_year: year }).range(0, 999),
    (sb.rpc as Function)('get_heatmap', { p_year: year }).range(1000, 1499),
  ])

  const error = r1.error ?? r2.error
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  const data = [...(r1.data ?? []), ...(r2.data ?? [])] as { week: number; hour: number; demand: number }[]

  return NextResponse.json(
    data.map(r => ({ week: r.week, hour: r.hour, demand: r.demand }))
  )
}
