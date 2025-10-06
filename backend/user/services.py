from django.conf import settings
from django.utils import timezone
from typing import Optional, Dict
import logging
import pyrebase
import uuid
from rest_framework_simplejwt.tokens import RefreshToken
from user.models import User
from chat_session.models import ChatSession

logger = logging.getLogger(__name__)

# Initialize Pyrebase
firebase_config = settings.FIREBASE_CONFIG

firebase = pyrebase.initialize_app(firebase_config)
firebase_auth = firebase.auth()


class UserService:
    @staticmethod
    def get_tokens_for_user(user: User) -> Dict[str, str]:
        """Generate JWT tokens for a user"""
        refresh = RefreshToken.for_user(user)
        
        # Add custom claims
        refresh['user_id'] = str(user.id)
        refresh['email'] = user.email
        refresh['is_anonymous'] = user.is_anonymous
        refresh['auth_provider'] = user.auth_provider
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'token_type': 'Bearer',
            'expires_in': settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME').total_seconds()
        }
    
    @staticmethod
    def verify_google_token_with_pyrebase(id_token: str) -> Optional[Dict]:
        """Verify Google ID token using Pyrebase"""
        try:
            # Verify the token with Firebase
            user_info = firebase_auth.get_account_info(id_token)
            if user_info and 'users' in user_info and len(user_info['users']) > 0:
                return user_info['users'][0]
            return None
        except Exception as e:
            logger.error(f"Error verifying Google token with Pyrebase: {e}")
            return None
    
    @staticmethod
    def get_or_create_google_user(google_user_info: dict) -> User:
        """Get or create user from Google auth info"""
        email = google_user_info.get('email')
        uid = google_user_info.get('localId')  # Pyrebase uses localId
        display_name = google_user_info.get('displayName', email.split('@')[0] if email else 'User')
        
        try:
            user = User.objects.get(firebase_uid=uid)
            # Update user info if changed
            if user.email != email:
                user.email = email
            if user.display_name != display_name:
                user.display_name = display_name
            user.save()
        except User.DoesNotExist:
            user = User.objects.create(
                firebase_uid=uid,
                email=email,
                display_name=display_name,
                auth_provider='google',
                is_anonymous=False
            )
        
        return user
    
    @staticmethod
    def create_anonymous_user(display_name: Optional[str] = None) -> User:
        """Create an anonymous user"""
        
        if not display_name:
            display_name = f"Anonymous_{str(uuid.uuid4())[:8]}"
            
        user = User.objects.create(
            display_name=display_name,
            auth_provider='anonymous',
            is_anonymous=True
        )
        
        # Generate anonymous token
        anon_token = str(uuid.uuid4())
        user.preferences['anonymous_token'] = anon_token
        user.save()
        
        return user
    
    @staticmethod
    def update_user_preferences(user: User, preferences: Dict) -> User:
        """Update user preferences"""
        if not user.preferences:
            user.preferences = {}
        
        user.preferences.update(preferences)
        user.save()
        return user
    
    @staticmethod
    def merge_anonymous_to_authenticated(
        anonymous_user: User, 
        authenticated_user: User
    ) -> User:
        """Merge anonymous user data to authenticated user"""
        # Transfer chat sessions
        ChatSession.objects.filter(user=anonymous_user).update(
            user=authenticated_user
        )
        
        # Merge preferences
        if anonymous_user.preferences:
            authenticated_user.preferences = {
                **authenticated_user.preferences,
                **anonymous_user.preferences
            }
            authenticated_user.save()
        
        # Delete anonymous user
        anonymous_user.delete()
        
        return authenticated_user