import { createClient, RedisClientType } from 'redis'

let client: RedisClientType | null = null

export const getRedisClient = async (): Promise<RedisClientType> => {
  if (client) return client
  const url = process.env.REDIS_URL || 'redis://localhost:6379'
  client = createClient({ url })
  client.on('error', err => {
    console.error('Redis Client Error', err)
  })
  if (!client.isOpen) await client.connect()
  return client
}

export const envRedis = {
  INDEX_NAME: process.env.INDEX_NAME || 'idx:products',
  JSON_PREFIX: process.env.JSON_PREFIX || 'prod:',
  VEC_PREFIX: process.env.VEC_PREFIX || 'vec:'
}

