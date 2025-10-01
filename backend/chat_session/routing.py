from django.urls import re_path
from chat_session.consumers import ChatSessionConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/session/(?P<session_id>[^/]+)/$', ChatSessionConsumer.as_asgi()),
]