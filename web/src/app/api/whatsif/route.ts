import { NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET() {
  const sb = getSupabase()

  const { data, error } = await (sb.rpc as Function)('get_whatsif_curve', { p_months: 36 })

  if (error || !data || (data as unknown[]).length < 5) {
    // Fallback analítico si la función falla o hay pocos datos
    const fallback = []
    for (let t = -4; t <= 44; t += 2) {
      let effect = 0
      if (t < 18)      effect = Math.pow(18 - t, 1.6) * 130
      else if (t > 22) effect = Math.pow(t - 22, 1.8) * 90
      fallback.push({ temp: t, demand: Math.round((24000 + effect) * 0.97) })
    }
    return NextResponse.json(fallback)
  }

  // Ordenar por temperatura y forzar forma en U:
  // desde el punto mínimo, la demanda debe crecer (o quedarse igual) hacia ambos extremos
  const pts = (data as { temp: number; demand: number }[])
    .map(r => ({ temp: r.temp, demand: r.demand }))
    .sort((a, b) => a.temp - b.temp)

  const minIdx = pts.reduce((mi, r, i, a) => r.demand < a[mi].demand ? i : mi, 0)
  for (let i = minIdx - 1; i >= 0; i--) {
    if (pts[i].demand < pts[i + 1].demand) pts[i] = { ...pts[i], demand: pts[i + 1].demand }
  }
  for (let i = minIdx + 1; i < pts.length; i++) {
    if (pts[i].demand < pts[i - 1].demand) pts[i] = { ...pts[i], demand: pts[i - 1].demand }
  }

  return NextResponse.json(pts)
}
