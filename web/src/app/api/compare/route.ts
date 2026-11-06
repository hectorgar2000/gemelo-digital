import { NextRequest, NextResponse } from 'next/server'
import { callRpc } from '@/lib/supabase'

// Lee searchParams → siempre dinámico; revalidate sería ignorado por Next.js
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
  // Validar: solo años enteros razonables, sin duplicados y como máximo 5
  // (cada año es una llamada RPC; sin límite un cliente podría forzar cientos).
  const currentYear = new Date().getFullYear()
  const years = [...new Set(
    (new URL(req.url).searchParams.get('years') ?? `${currentYear - 1},${currentYear}`)
      .split(',')
      .map(Number)
      .filter(y => Number.isInteger(y) && y >= 2010 && y <= currentYear)
  )].slice(0, 5)

  const results: Record<number, { week: number; demand: number }[]> = {}

  await Promise.all(years.map(async year => {
    const { data } = await callRpc<{ week: number; demand: number }>('get_weekly_demand', { p_year: year })
    results[year] = data ?? []
  }))

  return NextResponse.json(results)
}
