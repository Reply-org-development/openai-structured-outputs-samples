"use client"
import { useEffect, useState } from 'react'
import { Search, Sun, Waves } from 'lucide-react'

type BgMode = 'plain' | 'pattern' | 'gradient'

const modes: { key: BgMode; label: string }[] = [
  { key: 'plain', label: 'Bianco' },
  { key: 'pattern', label: 'Pattern' },
  { key: 'gradient', label: 'Gradiente' }
]

export default function Header() {
  const [mode, setMode] = useState<BgMode>('pattern')

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

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border/70 backdrop-blur bg-background/75">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4 md:px-8">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground font-semibold tracking-widest">
            LG
          </div>
          <span className="text-sm font-medium text-zinc-700">Assistant</span>
        </div>
        <div className="relative mx-2 hidden flex-1 items-center md:flex">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-4 text-zinc-400" />
          <input
            type="text"
            placeholder="Cerca prodotti, categorie…"
            className="w-full rounded-full border border-border bg-white py-2 pl-9 pr-4 text-sm outline-none ring-0 placeholder:text-zinc-400 focus:border-zinc-300 focus:shadow-sm"
          />
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

