// List of tools available to the assistant
// No need to include the top-level wrapper object as it is added in lib/tools/tools.ts
// More information on function calling: https://platform.openai.com/docs/guides/function-calling

export const toolsList = [
  {
    name: 'search_redis',
    description:
      'Semantic KNN search on Redis vector index with optional filters. Returns top products; can include product JSON details.',
    parameters: {
      query_text: { type: 'string', description: 'User intent/query text' },
      k: { type: 'integer', description: 'Top K results (1..50)' },
      min_price: { type: 'number', description: 'Min price filter' },
      max_price: { type: 'number', description: 'Max price filter' },
      include_details: {
        type: 'boolean',
        description: 'If true, attach product JSON details.'
      },
      sort_by: {
        type: 'string',
        description: 'Result ordering: relevance (default), price_asc, price_desc',
        enum: ['relevance', 'price_asc', 'price_desc']
      },
      expanded: {
        type: 'boolean',
        description: 'If true, perform an expanded, broader search.'
      }
    }
  },
  {
    name: 'get_product',
    description:
      'Fetch a product JSON payload from Redis by product code/id (JSON only).',
    parameters: {
      code: { type: 'string', description: 'Product code used in HASH key' },
      id: { type: 'string', description: 'Product id used in JSON key' }
    }
  },
  {
    name: 'add_to_cart',
    description:
      'Add items to cart when the user has confirmed their interest.',
    parameters: {
      items: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            productId: {
              type: 'string',
              description: 'ID of the product to add to the cart'
            },
            quantity: {
              type: 'integer',
              description: 'Quantity of the product to add to the cart'
            }
          },
          required: ['productId', 'quantity'],
          additionalProperties: false
        }
      }
    }
  }
]
