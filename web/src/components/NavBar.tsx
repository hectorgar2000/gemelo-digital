'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const LINKS = [
  { href: '/',          label: '⚡ Dashboard'  },
  { href: '/explorador', label: '🔍 Explorador' },
  { href: '/comparar',   label: '📊 Comparar'   },
]

export function NavBar() {
  const path = usePathname()
  return (
    <nav className="border-b border-gray-800 bg-gray-950 px-6 py-3 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto flex items-center gap-8">
        <span className="font-bold text-white tracking-tight">Gemelo Digital</span>
        <div className="flex gap-1">
          {LINKS.map(l => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                path === l.href
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`}
            >
              {l.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  )
}
