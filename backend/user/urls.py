from django.urls import path, include
from rest_framework.routers import DefaultRouter
from user.views import (
    UserViewSet,
    GoogleAuthView,
    AnonymousAuthView,
    UserStatsView
)

app_name = 'user'

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    # Authentication endpoints
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('auth/anonymous/', AnonymousAuthView.as_view(), name='anonymous-auth'),
    
    # User stats
    path('users/stats/', UserStatsView.as_view(), name='user-stats'),
    
    # Include router URLs
    path('', include(router.urls)),
]

# The URLs will be:
# POST /api/auth/google/ - Google authentication
# POST /api/auth/anonymous/ - Anonymous authentication
# GET /api/users/ - List users (admin only)
# POST /api/users/ - Create user
# GET /api/users/{id}/ - Get user details
# PATCH /api/users/{id}/ - Update user
# DELETE /api/users/{id}/ - Delete user
# GET /api/users/me/ - Get current user
# PATCH /api/users/update_preferences/ - Update preferences
# POST /api/users/delete_account/ - Soft delete account
# GET /api/users/stats/ - Get user statistics