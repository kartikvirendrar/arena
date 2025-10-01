from django.urls import path, include
from ai_model.view import AIModelViewSet, ModelLeaderboardView, ModelStatsView
from rest_framework.routers import DefaultRouter

app_name = 'ai_model'

router = DefaultRouter()
router.register(r'models', AIModelViewSet, basename='model')

urlpatterns = [
    # Model management
    path('', include(router.urls)),
    
    # Additional endpoints
    path('leaderboard/', ModelLeaderboardView.as_view(), name='leaderboard'),
    path('models/<uuid:model_id>/stats/', ModelStatsView.as_view(), name='model-stats'),
]

# URL patterns will be:
# GET /api/models/ - List all models
# POST /api/models/ - Create new model (admin only)
# GET /api/models/{id}/ - Get model details
# PATCH /api/models/{id}/ - Update model (admin only)
# DELETE /api/models/{id}/ - Delete model (admin only)
# GET /api/models/providers/ - Get available providers
# GET /api/models/capabilities/ - Get available capabilities
# POST /api/models/{id}/test/ - Test a model
# GET /api/models/{id}/validate/ - Validate model configuration
# POST /api/models/compare/ - Compare two models
# GET /api/leaderboard/ - Get model leaderboard
# GET /api/models/{id}/stats/ - Get model statistics