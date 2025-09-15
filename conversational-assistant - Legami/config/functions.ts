// Functions mapping to tool calls
// Define one function per tool call - each tool call should have a matching function
// Parameters for a tool call are passed as an object to the corresponding function

export const search_redis = async (params: {
  query_text: string
  k?: number
  min_price?: number
  max_price?: number
  include_details?: boolean
  expanded?: boolean
  sort_by?: 'relevance' | 'price_asc' | 'price_desc'
}) => {
  const response = await fetch('/api/tools/gift_finder/search_redis', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  })
  const result = await response.json()
  return result
}

export const get_product = async (params: { code?: string; id?: string }) => {
  const qs = new URLSearchParams()
  if (params.code) qs.set('code', params.code)
  if (params.id) qs.set('id', params.id)
  const response = await fetch(
    `/api/tools/gift_finder/get_product?${qs.toString()}`,
    {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    }
  )
  const result = await response.json()
  return result
}

export const add_to_cart = ({ items }: { items: any }) => {
  return { message: `Added these items to cart: ${JSON.stringify(items)}` }
}

export const functionsMap = {
  search_redis,
  get_product,
  add_to_cart
  // Add more functions here as you define them
}
