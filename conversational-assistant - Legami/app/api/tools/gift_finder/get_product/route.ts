import { getRedisClient, envRedis } from '@/lib/redis'

// Fetch only JSON product details. No HASH lookup.
export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const code = url.searchParams.get('code') || undefined
    const id = url.searchParams.get('id') || undefined

    if (!code && !id) {
      return new Response(
        JSON.stringify({ error: 'Missing code or id' }),
        { status: 400 }
      )
    }

    const redis = await getRedisClient()
    const jsonKey = `${envRedis.JSON_PREFIX}${id || code}`

    let product: any = null
    try {
      const jraw = await redis.sendCommand(['JSON.GET', jsonKey])
      const jtext = typeof jraw === 'string' ? jraw : jraw?.toString?.()
      product = jtext ? JSON.parse(jtext) : null
    } catch (e) {
      // ignore parse/command errors and return not found
    }

    const codeOut = (product && (product.code || product.id)) || code || id || null

    return new Response(
      JSON.stringify({ found: !!product, code: codeOut, product }),
      { status: 200 }
    )
  } catch (error) {
    console.error('get_product error', error)
    return new Response(
      JSON.stringify({ error: 'Failed to fetch product' }),
      { status: 500 }
    )
  }
}
