import { createClient } from '@supabase/supabase-js'

// Tipos de las tablas
export type WeatherRow   = { ts: string; temperature_c: number | null; humidity_pct: number | null; wind_speed_kmh: number | null; cloud_cover_pct: number | null; solar_radiation_wm2: number | null }
export type EnergyRow    = { ts: string; demand_mw: number; source: string }
export type ForecastRow  = { ts: string; demand_mw: number | null; demand_mw_upper: number | null; demand_mw_lower: number | null; model: string }
export type AnomalyRow   = { ts: string; residual_mw: number | null; z_score: number | null; iforest_score: number | null; is_anomaly: number; nivel: string }

const url = process.env.SUPABASE_URL!
const key = process.env.SUPABASE_SERVICE_KEY!

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
