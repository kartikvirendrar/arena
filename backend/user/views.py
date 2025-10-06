from datetime import timedelta
from rest_framework import viewsets, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.utils import timezone
from django.db import transaction
import logging

from .models import User
from .serializers import (
    UserSerializer, UserCreateSerializer, UserPreferencesSerializer,
    AnonymousAuthSerializer, GoogleAuthSerializer
)
from .services import UserService
from .authentication import AnonymousTokenAuthentication, FirebaseAuthentication
from .permissions import IsOwnerOrReadOnly
from django.db.models import Count
from message.models import Message
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for user management"""
    queryset = User.objects.filter(is_active=True)
    authentication_classes = [FirebaseAuthentication, AnonymousTokenAuthentication]
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action == 'update_preferences':
            return UserPreferencesSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_preferences(self, request):
        """Update user preferences"""
        serializer = UserPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = UserService.update_user_preferences(
            request.user, 
            serializer.validated_data
        )
        
        return Response(UserSerializer(user).data)


class GoogleAuthView(views.APIView):
    """Handle Google authentication"""
    permission_classes = [AllowAny]
    serializer_class = GoogleAuthSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verify Google token with Pyrebase
        google_user_info = UserService.verify_google_token_with_pyrebase(
            serializer.validated_data['id_token']
        )
        
        if not google_user_info:
            return Response(
                {"error": "Invalid Google token"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create user
        with transaction.atomic():
            user = UserService.get_or_create_google_user(google_user_info)
            
            # Check if there's an anonymous session to merge
            anon_token = request.META.get('HTTP_X_ANONYMOUS_TOKEN')
            if anon_token:
                try:
                    anon_user = User.objects.get(
                        is_anonymous=True,
                        preferences__anonymous_token=anon_token
                    )
                    user = UserService.merge_anonymous_to_authenticated(
                        anon_user, user
                    )
                except User.DoesNotExist:
                    pass
        
        # Generate JWT tokens
        tokens = UserService.get_tokens_for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens
        })


class AnonymousAuthView(views.APIView):
    """Handle anonymous authentication"""
    permission_classes = [AllowAny]
    serializer_class = AnonymousAuthSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create anonymous user
        user = UserService.create_anonymous_user(
            display_name=serializer.validated_data.get('display_name')
        )
        
        # Generate JWT tokens
        tokens = UserService.get_tokens_for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'tokens': tokens,
            'anonymous_token': user.preferences.get('anonymous_token'),
            'expires_at': user.anonymous_expires_at
        })


class RefreshTokenView(TokenObtainPairView):
    """Custom token refresh view"""
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # You can add custom logic here
            logger.info(f"Token refreshed for user")
        return response
        
class UserStatsView(views.APIView):
    """Get user statistics"""
    authentication_classes = [FirebaseAuthentication, AnonymousTokenAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Get user stats
        stats = {
            'total_sessions': user.chat_sessions.count(),
            'total_messages': Message.objects.filter(
                session__user=user,
                role='user'
            ).count(),
            'favorite_models': self._get_favorite_models(user),
            'activity_streak': self._calculate_activity_streak(user),
            'member_since': user.created_at,
            'feedback_given': user.feedbacks.count(),
            'session_breakdown': self._get_session_breakdown(user)
        }
        
        return Response(stats)
    
    def _get_favorite_models(self, user):
        """Get user's most used models"""
        
        favorite_models = Message.objects.filter(
            session__user=user,
            role='assistant',
            model__isnull=False
        ).values(
            'model__id',
            'model__display_name',
            'model__provider'
        ).annotate(
            usage_count=Count('id')
        ).order_by('-usage_count')[:5]
        
        return list(favorite_models)
    
    def _calculate_activity_streak(self, user):
        """Calculate user's activity streak in days"""
        
        # Get all unique days user was active
        active_days = user.chat_sessions.annotate(
            day=TruncDate('created_at')
        ).values('day').distinct().order_by('-day')
        
        if not active_days:
            return 0
        
        streak = 1
        current_date = active_days[0]['day']
        
        for i in range(1, len(active_days)):
            if active_days[i]['day'] == current_date - timedelta(days=1):
                streak += 1
                current_date = active_days[i]['day']
            else:
                break
        
        return streak
    
    def _get_session_breakdown(self, user):
        """Get breakdown of sessions by mode"""
        
        breakdown = user.chat_sessions.values('mode').annotate(
            count=Count('id')
        ).order_by('mode')
        
        return {item['mode']: item['count'] for item in breakdown}