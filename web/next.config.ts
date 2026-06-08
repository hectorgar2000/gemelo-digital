import type { NextConfig } from 'next'

/**
 * Cabeceras de seguridad HTTP aplicadas a todas las rutas.
 * Bloquean los vectores de ataque más comunes: clickjacking,
 * MIME sniffing, XSS via scripts externos, y iframes no autorizados.
 */
const SECURITY_HEADERS = [
  // Deshabilitar detección de tipo MIME (evita MIME-sniffing attacks)
  { key: 'X-Content-Type-Options', value: 'nosniff' },

  // Bloquear carga de la app en iframes de otros orígenes (clickjacking)
  { key: 'X-Frame-Options', value: 'SAMEORIGIN' },

  // Activar DNS prefetch para mejorar rendimiento
  { key: 'X-DNS-Prefetch-Control', value: 'on' },

  // Política de referrer: enviar origin solo en requests del mismo sitio
  { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },

  // Deshabilitar acceso a cámara, micrófono y geolocalización
  { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },

  // HSTS: forzar HTTPS durante 2 años (solo activo en producción con HTTPS)
  {
    key: 'Strict-Transport-Security',
    value: 'max-age=63072000; includeSubDomains; preload',
  },

  // Content Security Policy
  // - script-src 'unsafe-eval': necesario para webpack HMR en dev y chunks en prod
  // - style-src 'unsafe-inline': Tailwind CSS genera estilos inline
  // - connect-src *.supabase.co: API REST y WebSocket de Supabase
  // - font-src 'self': next/font self-hostea las fuentes de Google (no CDN)
  {
    key: 'Content-Security-Policy',
    value: [
      "default-src 'self'",
      "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self'",
      "connect-src 'self' https://*.supabase.co wss://*.supabase.co",
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
      "upgrade-insecure-requests",
    ].join('; '),
  },
]

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: '/(.*)',  // todas las rutas
        headers: SECURITY_HEADERS,
      },
    ]
  },
}

export default nextConfig
