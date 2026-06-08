import { NextRequest, NextResponse } from 'next/server'
import { getSupabase } from '@/lib/supabase'

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

  // Serie temporal principal via función SQL
  const { data, error } = await (sb.rpc as Function)('get_series', {
    p_hours:          hours,
    p_bucket_minutes: minutes,
  }).range(0, 19999)

  if (error) return NextResponse.json({ error: error.message }, { status: 500 })

  // F3: detectar si hay datos sintéticos en el rango (HEAD-only, sin body)
  // source='synthetic' significa que la API REE no estaba disponible y se usó fallback
  const { count: synthCount } = await sb
    .from('energy')
    .select('*', { count: 'exact', head: true })
    .gte('ts', since)
    .eq('source', 'synthetic') as { count: number | null }

  const hasSynthetic = (synthCount ?? 0) > 0

  return NextResponse.json(
    (data as { ts: string; temperature: number | null; demand: number | null }[]).map(r => ({
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
