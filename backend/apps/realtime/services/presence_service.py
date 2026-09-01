import redis.asyncio as redis


class PresenceService:

    def __init__(self):
        self.redis = redis.Redis(
            host="127.0.0.1",
            port=6379,
            decode_responses=True,
        )

    def get_user_key(self, user_id):
        return f"presence:user:{user_id}"

    async def add_connection(
        self,
        user_id,
        connection_id,
    ):
        key = self.get_user_key(user_id)

        await self.redis.sadd(
            key,
            connection_id,
        )

        # Return number of active connections
        return await self.redis.scard(key)

    async def remove_connection(
        self,
        user_id,
        connection_id,
    ):
        key = self.get_user_key(user_id)

        await self.redis.srem(
            key,
            connection_id,
        )

        connection_count = await self.redis.scard(
            key
        )

        # Remove empty Redis key
        if connection_count == 0:
            await self.redis.delete(key)

        return connection_count

    async def is_online(self, user_id):

        key = self.get_user_key(user_id)

        return await self.redis.exists(key)