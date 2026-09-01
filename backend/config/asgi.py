import os

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter

from apps.realtime.routing import websocket_urlpatterns
from apps.realtime.middleware import JWTAuthMiddlewareStack


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,

        "websocket": JWTAuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        ),
    }
)