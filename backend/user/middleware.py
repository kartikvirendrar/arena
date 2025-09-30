from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from user.models import User
from user.services import UserService


class WebSocketAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections using tokens
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Try to authenticate user from query string token
        query_string = scope.get('query_string', b'').decode()
        
        if 'token=' in query_string:
            token = query_string.split('token=')[-1].split('&')[0]
            scope['user'] = await self.get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()
        
        return await self.app(scope, receive, send)
    
    @database_sync_to_async
    def get_user_from_token(self, token):
        try:
            # First try Firebase token
            firebase_user = UserService.verify_firebase_token(token)
            
            if firebase_user:
                return User.objects.get(firebase_uid=firebase_user['uid'])
            
            # Then try anonymous token
            user = User.objects.filter(
                is_anonymous=True,
                preferences__anonymous_token=token
            ).first()
            
            return user or AnonymousUser()
            
        except Exception:
            return AnonymousUser()