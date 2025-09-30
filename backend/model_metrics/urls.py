from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ModelMetricViewSet, LeaderboardView, CategoryLeaderboardView,
    ModelPerformanceView, ModelComparisonView, MetricAggregationView,
    ProviderMetricsView, CategoryDominanceView, ModelRankingsView
)

app_name = 'model_metrics'

router = DefaultRouter()
router.register(r'metrics', ModelMetricViewSet, basename='metric')

urlpatterns = [
    path('', include(router.urls)),
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('leaderboard/categories/', CategoryLeaderboardView.as_view(), name='category-leaderboard'),
    path('models/<uuid:model_id>/performance/', ModelPerformanceView.as_view(), name='model-performance'),
    path('models/<uuid:model_id>/rankings/', ModelRankingsView.as_view(), name='model-rankings'),
    path('compare/', ModelComparisonView.as_view(), name='model-comparison'),
    path('aggregate/', MetricAggregationView.as_view(), name='metric-aggregation'),
    path('providers/', ProviderMetricsView.as_view(), name='provider-metrics'),
    path('dominance/', CategoryDominanceView.as_view(), name='category-dominance'),
]

# URL patterns will be:
# GET /api/metrics/ - List all metrics
# GET /api/metrics/{id}/ - Get specific metric
# GET /api/leaderboard/ - Get main leaderboard
# GET /api/leaderboard/categories/ - Get leaderboards for all categories
# GET /api/models/{model_id}/performance/ - Get detailed model performance
# GET /api/models/{model_id}/rankings/ - Get model rankings and percentiles
# GET /api/compare/ - Compare two models
# POST /api/aggregate/ - Get aggregated metrics
# GET /api/providers/ - Get metrics by provider
# GET /api/dominance/ - Get category dominance analysis