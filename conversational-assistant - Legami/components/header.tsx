"use client"
import { useEffect, useRef, useState } from 'react'
import { Search, Sun, Waves } from 'lucide-react'
import { search_redis } from '@/config/functions'
import { viewProductDetails } from '@/config/user-actions'

type BgMode = 'plain' | 'pattern' | 'gradient'

const modes: { key: BgMode; label: string }[] = [
  { key: 'plain', label: 'Bianco' },
  { key: 'pattern', label: 'Pattern' },
  { key: 'gradient', label: 'Gradiente' }
]

export default function Header() {
  const [mode, setMode] = useState<BgMode>('pattern')
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<any[]>([])
  const [activeIndex, setActiveIndex] = useState<number>(-1)
  const containerRef = useRef<HTMLDivElement | null>(null)
  const debounceRef = useRef<NodeJS.Timeout | null>(null)

  const DEFAULT_IMAGE_URL =
    'https://www.legami.com/dw/image/v2/BDSQ_PRD/on/demandware.static/-/Sites-legami-master-catalog/default/dwf6da9456/images_legami/zoom/AG2616062_1.jpg?sw=1200&sh=1200'

  const parseBool = (v?: string | number | boolean) =>
    ['true', '1', 'yes', 'on'].includes(String(v ?? '').trim().toLowerCase())
  const LIVE_SEARCH = parseBool(process.env.NEXT_PUBLIC_SEARCH_LIVE as any)
  const DEBOUNCE_MS = Number(process.env.NEXT_PUBLIC_SEARCH_DEBOUNCE_MS || 300)
  const MIN_CHARS = Number(process.env.NEXT_PUBLIC_SEARCH_MIN_CHARS || 2)

  const runSearch = async (q: string) => {
    const qTrim = q.trim()
    if (!qTrim || qTrim.length < MIN_CHARS) {
      setResults([])
      setOpen(false)
      setActiveIndex(-1)
      return
    }
    setLoading(true)
    try {
      const res = await search_redis({
        query_text: qTrim,
        include_details: true
      })
      const items = (res?.items || [])
        .slice()
        .sort((a: any, b: any) => (b?.similarity ?? 0) - (a?.similarity ?? 0))
      setResults(items)
      setOpen(!!items.length)
      setActiveIndex(items.length ? 0 : -1)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    const saved = (localStorage.getItem('bg-mode') as BgMode) || 'pattern'
    setMode(saved)
  }, [])

  useEffect(() => {
    const cls = {
      plain: 'bg-plain',
      pattern: 'bg-legami',
      gradient: 'bg-gradient-legami'
    }[mode]
    const targets = document.body.classList
    targets.remove('bg-plain', 'bg-legami', 'bg-gradient-legami')
    targets.add(cls)
    localStorage.setItem('bg-mode', mode)
  }, [mode])

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/70 backdrop-blur bg-background/75">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 md:px-8">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground font-semibold tracking-widest">
            LG
          </div>
          <span className="text-sm font-medium text-zinc-700">Assistant</span>
        </div>
        <div ref={containerRef} className="relative mx-2 hidden flex-1 items-center md:flex">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-4 text-zinc-400" />
          <form
            onSubmit={async e => {
              e.preventDefault()
              if (LIVE_SEARCH) {
                // In live mode, Enter selects the active result
                const item = results[activeIndex]
                if (item) {
                  setOpen(false)
                  setQuery('')
                  setResults([])
                  viewProductDetails(item.code)
                } else {
                  await runSearch(query)
                }
              } else {
                await runSearch(query)
              }
            }}
            className="w-full"
          >
            <input
              type="text"
              value={query}
              onChange={e => {
                const val = e.target.value
                setQuery(val)
                if (!val) {
                  setResults([])
                  setOpen(false)
                  setActiveIndex(-1)
                  return
                }
                if (LIVE_SEARCH) {
                  if (debounceRef.current) clearTimeout(debounceRef.current)
                  debounceRef.current = setTimeout(() => {
                    if (val.trim().length >= MIN_CHARS) {
                      runSearch(val)
                    } else {
                      setResults([])
                      setOpen(false)
                      setActiveIndex(-1)
                    }
                  }, DEBOUNCE_MS)
                }
              }}
              onFocus={() => {
                if (results.length) setOpen(true)
              }}
              onKeyDown={async e => {
                if (!open && results.length) setOpen(true)
                if (e.key === 'ArrowDown') {
                  e.preventDefault()
                  setActiveIndex(prev =>
                    results.length ? (prev + 1 + results.length) % results.length : -1
                  )
                } else if (e.key === 'ArrowUp') {
                  e.preventDefault()
                  setActiveIndex(prev =>
                    results.length ? (prev - 1 + results.length) % results.length : -1
                  )
                } else if (e.key === 'Enter') {
                  // handled by onSubmit
                } else if (e.key === 'Escape') {
                  setOpen(false)
                }
              }}
              placeholder="Cerca prodotti, categorie…"
              className="w-full rounded-full border border-border bg-white py-2 pl-9 pr-10 text-sm outline-none ring-0 placeholder:text-zinc-400 focus:border-zinc-300 focus:shadow-sm"
            />
          </form>
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1">
              <span
                className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                style={{ animationDelay: '0ms' }}
              />
              <span
                className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                style={{ animationDelay: '150ms' }}
              />
              <span
                className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                style={{ animationDelay: '300ms' }}
              />
            </div>
          )}
          {open && (
            <div className="absolute left-0 right-0 top-10 z-50 rounded-xl border border-zinc-200 bg-white shadow-lg">
              <div className="max-h-96 overflow-y-auto p-2">
                {loading ? (
                  <div className="p-2">
                    <div className="flex items-center gap-2 p-2 text-xs text-zinc-500">
                      <div className="flex items-center gap-1">
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                          style={{ animationDelay: '0ms' }}
                        />
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                          style={{ animationDelay: '150ms' }}
                        />
                        <span
                          className="h-1.5 w-1.5 rounded-full bg-[#e30613] animate-pulse"
                          style={{ animationDelay: '300ms' }}
                        />
                      </div>
                      Ricerca…
                    </div>
                    <div className="space-y-2 animate-pulse">
                      {[0, 1, 2].map(i => (
                        <div
                          key={i}
                          className="flex w-full items-center gap-3 rounded-lg p-2"
                        >
                          <div className="h-12 w-12 rounded bg-zinc-200" />
                          <div className="flex-1 space-y-2">
                            <div className="h-3 w-2/3 rounded bg-zinc-200" />
                            <div className="h-3 w-1/2 rounded bg-zinc-100" />
                          </div>
                          <div className="h-4 w-16 rounded bg-zinc-200" />
                        </div>
                      ))}
                    </div>
                  </div>
                ) : results.length ? (
                  results.map((item, idx) => (
                    <button
                      key={item.code}
                      onMouseEnter={() => setActiveIndex(idx)}
                      onClick={() => {
                        setOpen(false)
                        setQuery('')
                        setResults([])
                        viewProductDetails(item.code)
                      }}
                      className={`flex w-full items-center gap-3 rounded-lg p-2 text-left hover:bg-zinc-50 ${
                        activeIndex === idx ? 'bg-zinc-50 ring-1 ring-zinc-200' : ''
                      }`}
                    >
                      <img
                        alt={item.title}
                        src={
                          item?.product?.primary_image || item?.primary_image
                            ? `/imgs/${item.product?.primary_image || item.primary_image}`
                            : DEFAULT_IMAGE_URL
                        }
                        className="h-12 w-12 rounded object-cover"
                      />
                      <div className="flex-1">
                        <div className="text-sm font-medium text-stone-800 line-clamp-1">
                          {item.title}
                        </div>
                        <div className="text-xs text-stone-500 line-clamp-1">
                          {item.product?.description || item.product?.desc || ''}
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-0.5">
                        {typeof item.price === 'number' && (
                          <div className="text-sm font-semibold text-stone-900">
                            {new Intl.NumberFormat('it-IT', {
                              style: 'currency',
                              currency: 'EUR'
                            }).format(item.price)}
                          </div>
                        )}
                        {typeof item.similarity === 'number' && (
                          <div className="text-[11px] font-medium text-emerald-600">
                            {Math.round(Math.max(0, Math.min(1, item.similarity)) * 100)}% match
                          </div>
                        )}
                      </div>
                    </button>
                  ))
                ) : (
                  <div className="p-4 text-sm text-zinc-500">Nessun risultato</div>
                )}
              </div>
            </div>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <div className="hidden items-center gap-1 rounded-full border border-border bg-white p-1 text-xs md:flex">
            {modes.map(m => (
              <button
                key={m.key}
                className={`rounded-full px-3 py-1 transition-colors ${
                  mode === m.key ? 'bg-primary text-white' : 'hover:bg-zinc-100'
                }`}
                onClick={() => setMode(m.key)}
              >
                {m.label}
              </button>
            ))}
          </div>
          <Sun className="size-5 text-zinc-500" />
          <Waves className="size-5 text-primary" />
        </div>
      </div>
    </header>
  )
}
