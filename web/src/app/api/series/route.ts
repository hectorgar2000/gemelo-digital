import { NextRequest, NextResponse } from 'next/server'
import { callRpc, getSupabase } from '@/lib/supabase'

// Lee searchParams → siempre dinámico; revalidate sería ignorado por Next.js
export const dynamic = 'force-dynamic'

const RANGE_HOURS: Record<string, number> = {
  '-24h': 24, '-48h': 48, '-7d': 168, '-30d': 720, '-365d': 8760,
}
const WINDOW_MINUTES: Record<string, number> = {
  '30m': 30, '1h': 60, '3h': 180, '12h': 720, '1d': 1440,
}

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url)
  const rangeKey  = searchParams.get('range')  || '-7d'
  const windowKey = searchParams.get('window') || '1h'

  const hours   = RANGE_HOURS[rangeKey]    ?? 168
  const minutes = WINDOW_MINUTES[windowKey] ?? 60
  const since   = new Date(Date.now() - hours * 3600 * 1000).toISOString()

  const sb = getSupabase()

  type SeriesRow = { ts: string; temperature: number | null; demand: number | null }

  // Serie temporal (función SQL) + detección de datos sintéticos en paralelo.
  // F3: source='synthetic' significa que la API REE no estaba disponible y se
  // usó el fallback; el HEAD con count no descarga filas.
  const [series, synth] = await Promise.all([
    callRpc<SeriesRow>('get_series', { p_hours: hours, p_bucket_minutes: minutes }, [0, 19999]),
    sb.from('energy')
      .select('*', { count: 'exact', head: true })
      .gte('ts', since)
      .eq('source', 'synthetic') as unknown as Promise<{ count: number | null }>,
  ])

  const { data, error } = series
  if (error) return NextResponse.json({ error: error.message }, { status: 500 })
  const synthCount = synth.count

  const hasSynthetic = (synthCount ?? 0) > 0

  return NextResponse.json(
    (data ?? []).map(r => ({
      time:        r.ts,
      temperature: r.temperature,
      demand:      r.demand,
    })),
    {
      headers: {
        // El cliente lee este header para mostrar el badge de advertencia
        'X-Has-Synthetic': hasSynthetic ? '1' : '0',
      },
    }
  )
}
