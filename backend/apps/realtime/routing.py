from django.urls import path

from .consumers import ChatConsumer,PresenceConsumer


websocket_urlpatterns = [
    path(
        "ws/chat/<uuid:conversation_id>/",
        ChatConsumer.as_asgi(),
    ),
    path(
        "ws/presence/",
        PresenceConsumer.as_asgi(),
    ),
]