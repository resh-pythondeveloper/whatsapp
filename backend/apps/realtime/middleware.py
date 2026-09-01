from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth import get_user_model

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


User = get_user_model()


@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


class JWTAuthMiddleware:

    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):

        query_string = parse_qs(
            scope["query_string"].decode()
        )

        token = query_string.get("token")

        if not token:
            scope["user"] = AnonymousUser()

            return await self.inner(
                scope,
                receive,
                send
            )

        try:
            access_token = AccessToken(
                token[0]
            )

            user_id = access_token["user_id"]

            scope["user"] = await get_user(
                user_id
            )

        except TokenError:
            scope["user"] = AnonymousUser()

        return await self.inner(
            scope,
            receive,
            send
        )


def JWTAuthMiddlewareStack(inner):

    return JWTAuthMiddleware(inner)