import { NextRequest, NextResponse } from 'next/server'

/**
 * Rate limiting por IP para las API routes.
 *
 * Límites:
 *   - 60 requests / minuto por IP → uso normal del dashboard
 *   - 10 requests / minuto para /api/export → previene abuso de descarga
 *
 * Nota sobre serverless: en Vercel cada worker instance mantiene su propio
 * Map en memoria. El límite se aplica por worker, no globalmente. Para rate
 * limiting global se necesitaría Vercel KV / Upstash. Esto es best-effort
 * y efectivo contra ráfagas rápidas desde una misma IP.
 */

const WINDOW_MS      = 60_000   // ventana de 1 minuto
const MAX_DEFAULT    = 60       // requests / min para rutas normales
const MAX_EXPORT     = 10       // requests / min para /api/export (CSV pesado)

type Entry = { count: number; reset: number }
const store = new Map<string, Entry>()

function getEntry(key: string, max: number): { entry: Entry; allowed: boolean } {
  const now  = Date.now()
  const prev = store.get(key)

  if (!prev || now > prev.reset) {
    const entry = { count: 1, reset: now + WINDOW_MS }
    store.set(key, entry)
    return { entry, allowed: true }
  }

  prev.count++
  return { entry: prev, allowed: prev.count <= max }
}

// Limpiar entradas expiradas cada 5 minutos para evitar memory leak
let lastCleanup = Date.now()
function maybeCleanup() {
  const now = Date.now()
  if (now - lastCleanup < 5 * 60_000) return
  lastCleanup = now
  for (const [k, v] of store.entries()) {
    if (now > v.reset) store.delete(k)
  }
}

export function middleware(req: NextRequest) {
  // Solo aplicar a las API routes
  if (!req.nextUrl.pathname.startsWith('/api')) return NextResponse.next()

  maybeCleanup()

  // IP: x-forwarded-for en Vercel, ::1 en localhost
  const ip   = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim() ?? '127.0.0.1'
  const path = req.nextUrl.pathname

  // Límite diferenciado para el endpoint de export (CSV costoso)
  const isExport = path === '/api/export'
  const max      = isExport ? MAX_EXPORT : MAX_DEFAULT
  const key      = `${ip}:${isExport ? 'export' : 'api'}`

  const { entry, allowed } = getEntry(key, max)
  const remaining = Math.max(0, max - entry.count)
  const retryAfter = Math.ceil((entry.reset - Date.now()) / 1000)

  if (!allowed) {
    return NextResponse.json(
      { error: 'Demasiadas peticiones. Espera un momento e inténtalo de nuevo.' },
      {
        status: 429,
        headers: {
          'Retry-After':          String(retryAfter),
          'X-RateLimit-Limit':    String(max),
          'X-RateLimit-Remaining':'0',
          'X-RateLimit-Reset':    String(Math.ceil(entry.reset / 1000)),
        },
      }
    )
  }

  // Añadir headers informativos a las respuestas permitidas
  const res = NextResponse.next()
  res.headers.set('X-RateLimit-Limit',     String(max))
  res.headers.set('X-RateLimit-Remaining', String(remaining))
  return res
}

export const config = {
  matcher: '/api/:path*',
}
