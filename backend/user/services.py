from django.conf import settings
from django.utils import timezone
from firebase_admin import auth as firebase_auth
from typing import Optional, Dict
import logging
from user.models import User
from chat_session.models import ChatSession
import uuid

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def get_or_create_google_user(firebase_user: dict) -> User:
        """Get or create user from Firebase Google auth"""
        try:
            user = User.objects.get(firebase_uid=firebase_user['uid'])
            # Update user info if changed
            if user.email != firebase_user.get('email'):
                user.email = firebase_user.get('email')
            if user.display_name != firebase_user.get('name'):
                user.display_name = firebase_user.get('name', firebase_user.get('email', '').split('@')[0])
            user.save()
        except User.DoesNotExist:
            user = User.objects.create(
                firebase_uid=firebase_user['uid'],
                email=firebase_user.get('email'),
                display_name=firebase_user.get('name', firebase_user.get('email', '').split('@')[0]),
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
        
        return user
    
    @staticmethod
    def verify_firebase_token(id_token: str) -> Optional[dict]:
        """Verify Firebase ID token"""
        try:
            decoded_token = firebase_auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            logger.error(f"Firebase token verification failed: {e}")
            return None
    
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