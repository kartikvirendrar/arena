from django.urls import path, include
from rest_framework.routers import DefaultRouter
from message.views import MessageViewSet

app_name = 'message'

router = DefaultRouter()
router.register(r'messages', MessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]

# URL patterns will be:
# GET /api/messages/ - List messages
# POST /api/messages/ - Create message
# GET /api/messages/{id}/ - Get message details
# PATCH /api/messages/{id}/ - Update message
# DELETE /api/messages/{id}/ - Delete message
# POST /api/messages/stream/ - Stream message response
# GET /api/messages/{id}/tree/ - Get message tree
# POST /api/messages/{id}/branch/ - Create branch
# POST /api/messages/{id}/regenerate/ - Regenerate message
# GET /api/messages/conversation_path/ - Get path between messages