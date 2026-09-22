"""WebSocket URL routing for retrospectives."""
from django.urls import re_path
from .consumers import RetrospectiveConsumer

websocket_urlpatterns = [
    re_path(r"^ws/retro/(?P<cycle_id>[^/]+)/$", RetrospectiveConsumer.as_asgi()),
]
