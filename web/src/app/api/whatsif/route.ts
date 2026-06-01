import { NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

export const revalidate = 3600

export async function GET() {
  const sb    = getSupabase()
  const since = new Date(Date.now() - 3 * 365 * 24 * 3600 * 1000).toISOString()

  const [wRes, eRes] = await Promise.all([
    sb.from('weather').select('ts,temperature_c').gte('ts', since).order('ts') as unknown as Promise<{ data: { ts: string; temperature_c: number | null }[] | null }>,
    sb.from('energy').select('ts,demand_mw').gte('ts', since).order('ts') as unknown as Promise<{ data: { ts: string; demand_mw: number }[] | null }>,
  ])

  // Construir lookup ts→demand
  const demandByTs: Record<string, number> = {}
  for (const r of eRes.data ?? []) {
    demandByTs[r.ts.slice(0, 16)] = r.demand_mw
  }

  // Agrupar demanda por banda de temperatura (cada 2°C)
  const acc: Record<number, { sum: number; n: number }> = {}
  for (const r of wRes.data ?? []) {
    const key = r.ts.slice(0, 16)
    const demand = demandByTs[key]
    if (demand == null || r.temperature_c == null) continue
    const band = Math.floor(r.temperature_c / 2) * 2
    if (!acc[band]) acc[band] = { sum: 0, n: 0 }
    acc[band].sum += demand
    acc[band].n   += 1
  }

  const curve = Object.entries(acc)
    .filter(([, { n }]) => n > 5)
    .map(([t, { sum, n }]) => ({ temp: Number(t), demand: Math.round(sum / n) }))
    .sort((a, b) => a.temp - b.temp)

  // Fallback analítico si no hay datos suficientes
  if (curve.length < 10) {
    const fallback = []
    for (let t = -4; t <= 44; t += 2) {
      let effect = 0
      if (t < 18)      effect = Math.pow(18 - t, 1.6) * 130
      else if (t > 22) effect = Math.pow(t - 22, 1.8) * 90
      fallback.push({ temp: t, demand: Math.round((24000 + effect) * 0.97) })
    }
    return NextResponse.json(fallback)
  }

  return NextResponse.json(curve)
}
