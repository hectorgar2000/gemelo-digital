import { InfluxDB } from '@influxdata/influxdb-client'

const url    = process.env.INFLUX_URL!
const token  = process.env.INFLUX_TOKEN!
const org    = process.env.INFLUX_ORG!
export const bucket = process.env.INFLUX_BUCKET!

let client: InfluxDB | null = null

export function getQueryApi() {
  if (!client) client = new InfluxDB({ url, token })
  return client.getQueryApi(org)
}

/** Ejecuta una query Flux y devuelve array de objetos */
export async function queryInflux<T = Record<string, unknown>>(
  flux: string
): Promise<T[]> {
  const api = getQueryApi()
  const rows: T[] = []
  await new Promise<void>((resolve, reject) => {
    api.queryRows(flux, {
      next(row, meta) { rows.push(meta.toObject(row) as T) },
      error: reject,
      complete: resolve,
    })
  })
  return rows
}
