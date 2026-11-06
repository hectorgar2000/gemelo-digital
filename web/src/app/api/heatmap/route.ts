import { NextRequest, NextResponse } from 'next/server'
import { callRpc } from '@/lib/supabase'

// Lee searchParams → siempre dinámico; revalidate sería ignorado por Next.js
export const dynamic = 'force-dynamic'

type Cell = { week: number; hour: number; demand: number }

export async function GET(req: NextRequest) {
  const currentYear = new Date().getFullYear()
  const rawYear = Number(new URL(req.url).searchParams.get('year') ?? currentYear - 1)
  if (!Number.isInteger(rawYear) || rawYear < 2010 || rawYear > currentYear) {
    return NextResponse.json({ error: 'Parámetro year inválido' }, { status: 400 })
  }
  const year = rawYear

  // supabase-js llama al RPC via POST — la paginación por .range() no funciona
  // en el cliente JS para llamadas POST a RPC (sí en Python). En su lugar
  // dividimos por rango de semanas: cada mitad devuelve <= 648 filas (< 1000).
  const [r1, r2] = await Promise.all([
    callRpc<Cell>('get_heatmap', { p_year: year, p_week_start: 1,  p_week_end: 26 }),
    callRpc<Cell>('get_heatmap', { p_year: year, p_week_start: 27, p_week_end: 53 }),
  ])

  const error = r1.error ?? r2.error
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  const data = [...(r1.data ?? []), ...(r2.data ?? [])]

  return NextResponse.json(
    data.map(r => ({ week: r.week, hour: r.hour, demand: r.demand }))
  )
}
