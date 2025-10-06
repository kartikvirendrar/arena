from rest_framework import authentication, exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from user.models import User
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class FirebaseAuthentication(JWTAuthentication):
    """Extended JWT authentication to handle our custom User model"""
    
    def get_user(self, validated_token):
        try:
            user_id = validated_token.get('user_id')
            user = User.objects.get(id=user_id, is_active=True)
            
            # Check if anonymous user is expired
            if user.is_anonymous and user.anonymous_expires_at:
                if user.anonymous_expires_at < timezone.now():
                    raise exceptions.AuthenticationFailed('Anonymous session expired')
            
            return user
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('User not found')


class AnonymousTokenAuthentication(authentication.BaseAuthentication):
    """Fallback authentication for anonymous users using session tokens"""
    
    def authenticate(self, request):
        # Check for anonymous token in header
        anon_token = request.META.get('HTTP_X_ANONYMOUS_TOKEN')
        
        if not anon_token:
            return None
            
        try:
            # Find user by anonymous token
            user = User.objects.get(
                is_anonymous=True,
                preferences__anonymous_token=anon_token,
                is_active=True
            )
            
            # Check if expired
            if user.anonymous_expires_at and user.anonymous_expires_at < timezone.now():
                raise exceptions.AuthenticationFailed('Anonymous session expired')
                
            return (user, None)
            
        except User.DoesNotExist:
            return None