from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/session/(?P<session_id>[^/]+)/$', consumers.ChatSessionConsumer.as_asgi()),
]