import OpenAI from 'openai'
import { getRedisClient, envRedis } from '@/lib/redis'

// Sanitize text for embedding
const sanitize = (t: any, max = 12000) => {
  let s = t == null ? '' : String(t)
  s = s.replace(/\x00/g, ' ').replace(/\s+/g, ' ').trim()
  if (!s) s = '.'
  if (s.length > max) s = s.slice(0, max)
  return s
}

const toFloat32Buffer = (arr: number[]) => {
  const f32 = new Float32Array(arr)
  return Buffer.from(f32.buffer)
}

export async function POST(req: Request) {
  try {
    const body = await req.json()
    const {
      query_text,
      k = 8,
      min_price,
      max_price,
      include_details = true,
      expanded,
      sort_by
    } = body || {}

    if (!query_text || typeof query_text !== 'string') {
      return new Response(JSON.stringify({ error: 'Missing query_text' }), {
        status: 400
      })
    }

    const q = sanitize(query_text)
    const redis = await getRedisClient()

    // Build price-only filter
    const parts: string[] = []
    if (min_price != null || max_price != null) {
      const lo = min_price != null ? String(min_price) : '-inf'
      const hi = max_price != null ? String(max_price) : '+inf'
      parts.push(`(@price:[${lo} ${hi}]|@prezzo:[${lo} ${hi}])`)
    }
    const filterExpr = parts.length ? parts.join(' ') : '*'

    // Always semantic KNN
    const openai = new OpenAI()
    const embDim = Number(process.env.EMBED_DIM || '1024')
    const expandedQuery = expanded ? `${q} alternative simili correlati` : q
    const emb = await openai.embeddings.create({
      model: process.env.EMBED_MODEL || 'text-embedding-3-large',
      input: [expandedQuery],
      dimensions: embDim
    })
    const vec = toFloat32Buffer(emb.data[0].embedding as unknown as number[])

    // Oversample if sorting by price
    // Default ordering: by price ascending unless explicitly 'price_desc'
    const order: 'price_asc' | 'price_desc' =
      sort_by === 'price_desc' ? 'price_desc' : 'price_asc'

    // Enforce a hard cap of 5 results
    const kLimit = Math.min(5, Number(k) || 5)
    const kQuery = Math.min(50, Math.max(kLimit, kLimit * 3))

    const returnFields = [
      'code',
      'title',
      'brand',
      'category',
      'keywords',
      'price',
      'prezzo',
      'score'
    ]

    const argsWithDialect: (string | Buffer)[] = [
      'FT.SEARCH',
      envRedis.INDEX_NAME,
      `(${filterExpr})=>[KNN ${kQuery} @embedding $vec AS score]`,
      'PARAMS',
      '2',
      'vec',
      vec,
      'SORTBY',
      'score',
      'LIMIT',
      '0',
      String(kQuery),
      'RETURN',
      String(returnFields.length),
      ...returnFields,
      'DIALECT',
      '2'
    ]
    const argsNoDialect = argsWithDialect.slice(0, -2)

    let raw: any[]
    try {
      raw = (await redis.sendCommand(argsWithDialect)) as any[]
    } catch (e) {
      raw = (await redis.sendCommand(argsNoDialect)) as any[]
    }

    const items: any[] = []
    for (let i = 1; i < raw.length; i += 2) {
      const doc = raw[i + 1] as Array<string | Buffer>
      const obj: Record<string, any> = {}
      for (let j = 0; j < doc.length; j += 2) {
        const f = String(doc[j])
        const v = doc[j + 1]
        obj[f] = typeof v === 'string' ? v : v?.toString?.() ?? ''
      }
      const code = obj.code
      const row: any = {
        code,
        title: obj.title,
        brand: obj.brand ?? null,
        category: obj.category ?? null,
        keywords: obj.keywords ?? null,
        price:
          obj.price != null
            ? Number(obj.price)
            : obj.prezzo != null
              ? Number(obj.prezzo)
              : undefined,
        score: obj.score ? Number(obj.score) : undefined
      }
      if (include_details && code) {
        try {
          const jsonKey = `${envRedis.JSON_PREFIX}${code}`
          const jraw = await redis.sendCommand(['JSON.GET', jsonKey])
          const jtext = typeof jraw === 'string' ? jraw : jraw?.toString?.()
          if (jtext) {
            const j = JSON.parse(jtext)
            row.product = j
          }
        } catch {}
      }
      items.push(row)
    }

    const dir = order === 'price_asc' ? 1 : -1
    const out = items
      .slice()
      .sort((a, b) => {
        const pa = typeof a.price === 'number' ? a.price : Number.POSITIVE_INFINITY
        const pb = typeof b.price === 'number' ? b.price : Number.POSITIVE_INFINITY
        if (pa === pb) return (a.score ?? 0) - (b.score ?? 0)
        return dir * (pa - pb)
      })
      .slice(0, kLimit)

    return new Response(
      JSON.stringify({
        count: out.length,
        k: kLimit,
        filters: { min_price, max_price },
        sort_by: order,
        mode_used: 'semantic',
        items: out
      }),
      { status: 200 }
    )
  } catch (error: any) {
    console.error('search_redis error', error)
    const message = error?.message || String(error)
    return new Response(
      JSON.stringify({ error: 'Failed to query Redis', details: message }),
      { status: 500 }
    )
  }
}
