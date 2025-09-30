from rest_framework import authentication, exceptions
from django.contrib.auth.models import AnonymousUser
from firebase_admin import auth as firebase_auth
import logging
from .models import User

logger = logging.getLogger(__name__)


class FirebaseAuthentication(authentication.BaseAuthentication):
    """Custom Firebase authentication class"""
    
    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header:
            return None
            
        try:
            # Extract token from Bearer header
            auth_type, token = auth_header.split(' ')
            if auth_type.lower() != 'bearer':
                return None
                
            # Verify Firebase token
            decoded_token = firebase_auth.verify_id_token(token)
            firebase_uid = decoded_token['uid']
            
            # Get or create user
            try:
                user = User.objects.get(firebase_uid=firebase_uid)
            except User.DoesNotExist:
                raise exceptions.AuthenticationFailed('User not found')
            
            return (user, decoded_token)
            
        except Exception as e:
            logger.error(f"Firebase authentication error: {e}")
            raise exceptions.AuthenticationFailed('Invalid token')


class AnonymousTokenAuthentication(authentication.BaseAuthentication):
    """Custom authentication for anonymous users using session tokens"""
    
    def authenticate(self, request):
        # Check for anonymous token in header or session
        anon_token = request.META.get('HTTP_X_ANONYMOUS_TOKEN') or \
                    request.session.get('anonymous_token')
        
        if not anon_token:
            return None
            
        try:
            # Find user by anonymous token (stored in preferences)
            user = User.objects.get(
                is_anonymous=True,
                preferences__anonymous_token=anon_token
            )
            
            # Check if expired
            if user.anonymous_expires_at and user.anonymous_expires_at < timezone.now():
                raise exceptions.AuthenticationFailed('Anonymous session expired')
                
            return (user, None)
            
        except User.DoesNotExist:
            return None