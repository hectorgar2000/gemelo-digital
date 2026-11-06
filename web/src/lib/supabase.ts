import { createClient } from '@supabase/supabase-js'

// Tipos de las tablas
export type WeatherRow   = { ts: string; temperature_c: number | null; humidity_pct: number | null; wind_speed_kmh: number | null; cloud_cover_pct: number | null; solar_radiation_wm2: number | null }
export type EnergyRow    = { ts: string; demand_mw: number; source: string }
export type ForecastRow  = { ts: string; demand_mw: number | null; demand_mw_upper: number | null; demand_mw_lower: number | null; model: string }
export type AnomalyRow   = { ts: string; residual_mw: number | null; z_score: number | null; iforest_score: number | null; is_anomaly: number; nivel: string }

const url = process.env.SUPABASE_URL!

// S1 (seguridad): usar la clave anon para las API routes (solo lectura, RLS habilitado).
// La clave anon solo puede hacer SELECT (políticas en supabase/rls.sql).
// Si SUPABASE_ANON_KEY no está configurada aún, cae al service key como fallback.
//
// Pasos para activar el modo seguro:
//   1. Aplica supabase/rls.sql en el SQL Editor de Supabase
//   2. Añade SUPABASE_ANON_KEY a web/.env.local y a las variables de Vercel
//      (obtenla en Supabase → Project Settings → API → anon public)
//   3. Una vez configurada, los scripts Python siguen usando SUPABASE_SERVICE_KEY
const key = process.env.SUPABASE_ANON_KEY ?? process.env.SUPABASE_SERVICE_KEY!

let _client: ReturnType<typeof createClient> | null = null

export function getSupabase() {
  if (!_client) _client = createClient(url, key)
  return _client
}

/** Helper: ejecuta una query Supabase y devuelve los datos tipados */
export async function sbQuery<T>(
  query: ReturnType<ReturnType<typeof createClient>['from']>['select']
): Promise<T[]> {
  const result = await (query as unknown as Promise<{ data: T[] | null }>)
  return result.data ?? []
}

// ---------------------------------------------------------------------------
// RPC tipado para las funciones SQL propias (supabase/functions.sql)
// ---------------------------------------------------------------------------
// Sin un tipo `Database` generado, supabase-js tipa rpc() con args `undefined`
// y obligaba a usar `(sb.rpc as Function)(...)`, que desactiva el type-checking.
// Este helper concentra el cast en un único sitio y devuelve un resultado tipado.

export type RpcResult<T> = { data: T[] | null; error: { message: string } | null }

type RpcBuilder = PromiseLike<RpcResult<unknown>> & {
  range: (from: number, to: number) => PromiseLike<RpcResult<unknown>>
}
type LooseRpc = (fn: string, args?: Record<string, unknown>) => RpcBuilder

export async function callRpc<T>(
  fn: string,
  args: Record<string, unknown>,
  range?: [number, number],
): Promise<RpcResult<T>> {
  const sb  = getSupabase()
  const rpc = sb.rpc.bind(sb) as unknown as LooseRpc
  const q   = rpc(fn, args)
  return (await (range ? q.range(range[0], range[1]) : q)) as RpcResult<T>
}
