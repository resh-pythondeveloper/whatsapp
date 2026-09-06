import redis.asyncio as redis
import os

class TypingService:

    TYPING_TIMEOUT = 5

    def __init__(self):

        self.redis = redis.from_url(
            os.getenv(
                "REDIS_URL",
                "redis://127.0.0.1:6379"
            ),
            decode_responses=True,
        )

    def get_typing_key(
        self,
        conversation_id,
        user_id,
    ):

        return (
            f"typing:{conversation_id}:{user_id}"
        )

    async def start_typing(
        self,
        conversation_id,
        user_id,
    ):

        key = self.get_typing_key(
            conversation_id,
            user_id,
        )

        # Check existing typing state
        already_typing = await self.redis.exists(
            key
        )

        # Refresh TTL
        await self.redis.set(
            key,
            "1",
            ex=self.TYPING_TIMEOUT,
        )

        # True means state changed:
        # NOT TYPING → TYPING
        return not bool(already_typing)

    async def stop_typing(
        self,
        conversation_id,
        user_id,
    ):

        key = self.get_typing_key(
            conversation_id,
            user_id,
        )

        deleted = await self.redis.delete(
            key
        )

        # True means:
        # TYPING → NOT TYPING
        return bool(deleted)

    async def is_typing(
        self,
        conversation_id,
        user_id,
    ):

        key = self.get_typing_key(
            conversation_id,
            user_id,
        )

        return bool(
            await self.redis.exists(key)
        )