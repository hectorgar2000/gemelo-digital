import { NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

type Pt = { temp: number; demand: number }

// ---------------------------------------------------------------------------
// Helpers — cada uno con responsabilidad única y CC ≤ 3
// ---------------------------------------------------------------------------

/** Curva analítica en U para cuando no hay datos históricos suficientes. */
function buildFallbackCurve(): Pt[] {
  return Array.from({ length: 25 }, (_, i) => {
    const t = -4 + i * 2
    const effect =
      t < 18 ? Math.pow(18 - t, 1.6) * 130
      : t > 22 ? Math.pow(t - 22, 1.8) * 90
      : 0
    return { temp: t, demand: Math.round((24_000 + effect) * 0.97) }
  })
}

/**
 * Garantiza forma en U: desde el mínimo, la demanda crece hacia ambos extremos.
 * Evita que ruido estadístico en los bordes invierta la curva.
 */
function enforceUShape(pts: Pt[]): Pt[] {
  const result = pts.slice()
  const minIdx = result.reduce((mi, r, i, a) => (r.demand < a[mi].demand ? i : mi), 0)

  for (let i = minIdx - 1; i >= 0; i--) {
    if (result[i].demand < result[i + 1].demand)
      result[i] = { ...result[i], demand: result[i + 1].demand }
  }
  for (let i = minIdx + 1; i < result.length; i++) {
    if (result[i].demand < result[i - 1].demand)
      result[i] = { ...result[i], demand: result[i - 1].demand }
  }
  return result
}

// ---------------------------------------------------------------------------
// Handler
// ---------------------------------------------------------------------------

export async function GET() {
  const sb = getSupabase()
  const { data, error } = await (sb.rpc as Function)('get_whatsif_curve', { p_months: 36 })

  const hasEnoughData = !error && Array.isArray(data) && data.length >= 5
  if (!hasEnoughData) return NextResponse.json(buildFallbackCurve())

  const pts = (data as Pt[])
    .map(r => ({ temp: r.temp, demand: r.demand }))
    .sort((a, b) => a.temp - b.temp)

  return NextResponse.json(enforceUShape(pts))
}
