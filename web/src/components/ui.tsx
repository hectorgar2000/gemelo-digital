'use client'

/** Bloque animado genérico para skeletons */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse bg-gray-800 rounded-lg ${className}`} />
}

/**
 * Skeleton que imita la forma de un gráfico:
 * fondo pulsante + leyenda simulada debajo
 */
export function ChartSkeleton({ height = 280 }: { height?: number }) {
  return (
    <div className="animate-pulse space-y-3">
      {/* Área del gráfico */}
      <div className="bg-gray-800 rounded-xl" style={{ height }} />
      {/* Leyenda simulada */}
      <div className="flex justify-center gap-6">
        <div className="h-2 w-16 bg-gray-800 rounded" />
        <div className="h-2 w-16 bg-gray-800 rounded" />
      </div>
    </div>
  )
}

/**
 * Estado de error con botón de reintento.
 * Usar dentro del área de contenido del componente (sustituye al skeleton/datos).
 */
export function ErrorState({
  message = 'Error al cargar los datos',
  onRetry,
}: {
  message?: string
  onRetry: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 py-10 text-gray-500">
      <span className="text-3xl">⚠️</span>
      <p className="text-sm">{message}</p>
      <button
        onClick={onRetry}
        className="mt-1 px-3 py-1 text-xs bg-gray-800 hover:bg-gray-700 text-blue-400 hover:text-blue-300 rounded-lg transition-colors"
      >
        ↻ Reintentar
      </button>
    </div>
  )
}
