import json

import redis


class MessageCacheService:

    CACHE_TIMEOUT = 60 * 5  # 5 minutes

    def __init__(self):

        self.redis = redis.Redis(
            host="127.0.0.1",
            port=6379,
            decode_responses=True,
        )

    def get_cache_key(
        self,
        conversation_id,
        cursor=None,
    ):

        return (
            f"messages:"
            f"{conversation_id}:"
            f"{cursor or 'first'}"
        )

    def get_messages(
        self,
        conversation_id,
        cursor=None,
    ):

        key = self.get_cache_key(
            conversation_id,
            cursor,
        )

        data = self.redis.get(key)

        if not data:
            return None

        return json.loads(data)

    def set_messages(
        self,
        conversation_id,
        data,
        cursor=None,
    ):

        key = self.get_cache_key(
            conversation_id,
            cursor,
        )

        self.redis.set(
            key,
            json.dumps(data),
            ex=self.CACHE_TIMEOUT,
        )

    def delete_conversation_cache(
        self,
        conversation_id,
    ):

        pattern = (
            f"messages:"
            f"{conversation_id}:*"
        )

        keys = list(
            self.redis.scan_iter(
                match=pattern
            )
        )

        if keys:
            self.redis.delete(*keys)