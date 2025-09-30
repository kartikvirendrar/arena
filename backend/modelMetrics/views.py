from rest_framework import viewsets, views, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import datetime, timedelta

from apps.ai_model.models import AIModel, ModelMetric
from .serializers import (
    ModelMetricSerializer, LeaderboardSerializer, CategoryLeaderboardSerializer,
    ModelPerformanceSerializer, MetricAggregationSerializer,
    ModelComparisonMetricsSerializer
)
from .services import ModelMetricsService, ModelComparisonService
from .aggregators import MetricsAggregator
from .calculators import MetricsCalculator


class ModelMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for model metrics"""
    queryset = ModelMetric.objects.all()
    serializer_class = ModelMetricSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by model
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(model_id=model_id)
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by period
        period = self.request.query_params.get('period')
        if period:
            queryset = queryset.filter(period=period)
        
        # Get latest only
        latest_only = self.request.query_params.get('latest_only', 'true').lower() == 'true'
        if latest_only:
            # Get latest metric for each model/category/period combination
            queryset = queryset.order_by(
                'model', 'category', 'period', '-calculated_at'
            ).distinct('model', 'category', 'period')
        
        return queryset.order_by('-calculated_at')


class LeaderboardView(views.APIView):
    """Main leaderboard view"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        category = request.query_params.get('category', 'overall')
        period = request.query_params.get('period', 'all_time')
        limit = int(request.query_params.get('limit', 20))
        
        leaderboard = ModelMetricsService.get_leaderboard(
            category=category,
            period=period,
            limit=limit
        )
        
        serializer = LeaderboardSerializer(leaderboard, many=True)
        
        return Response({
            'category': category,
            'period': period,
            'last_updated': timezone.now(),
            'entries': serializer.data
        })


class CategoryLeaderboardView(views.APIView):
    """Get leaderboards for all categories"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        categories = [
            {'name': 'overall', 'display_name': 'Overall', 'description': 'Overall performance across all tasks'},
            {'name': 'code', 'display_name': 'Code Generation', 'description': 'Programming and code-related tasks'},
            {'name': 'creative', 'display_name': 'Creative Writing', 'description': 'Creative and storytelling tasks'},
            {'name': 'reasoning', 'display_name': 'Reasoning', 'description': 'Logic and problem-solving tasks'},
            {'name': 'conversation', 'display_name': 'Conversation', 'description': 'Natural conversation ability'},
        ]
        
        period = request.query_params.get('period', 'all_time')
        limit = int(request.query_params.get('limit', 10))
        
        results = []
        
        for cat_info in categories:
            leaderboard = ModelMetricsService.get_leaderboard(
                category=cat_info['name'],
                period=period,
                limit=limit
            )
            
            results.append({
                'category': cat_info['name'],
                'display_name': cat_info['display_name'],
                'description': cat_info['description'],
                'last_updated': timezone.now(),
                'entries': LeaderboardSerializer(leaderboard, many=True).data
            })
        
        return Response(results)


class ModelPerformanceView(views.APIView):
    """Detailed model performance analysis"""
    permission_classes = [AllowAny]
    
    def get(self, request, model_id):
        model = get_object_or_404(AIModel, id=model_id)
        
        # Time range parameter
        days = int(request.query_params.get('days', 30))
        time_range = timedelta(days=days)
        
        analysis = ModelMetricsService.get_model_performance_analysis(
            model=model,
            time_range=time_range
        )
        
        serializer = ModelPerformanceSerializer(analysis)
        return Response(serializer.data)


class ModelComparisonView(views.APIView):
    """Compare two models"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        model_a_id = request.query_params.get('model_a')
        model_b_id = request.query_params.get('model_b')
        
        if not model_a_id or not model_b_id:
            return Response(
                {'error': 'Both model_a and model_b parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        model_a = get_object_or_404(AIModel, id=model_a_id)
        model_b = get_object_or_404(AIModel, id=model_b_id)
        
        categories = request.query_params.getlist('categories')
        
        comparison = ModelComparisonService.compare_models(
            model_a=model_a,
            model_b=model_b,
            categories=categories if categories else None
        )
        
        serializer = ModelComparisonMetricsSerializer(comparison)
        return Response(serializer.data)


class MetricAggregationView(views.APIView):
    """Aggregate metrics across models"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = MetricAggregationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Get models
        model_ids = serializer.validated_data.get('models', [])
        if model_ids:
            models = AIModel.objects.filter(id__in=model_ids)
        else:
            models = AIModel.objects.filter(is_active=True)
        
        # Time range
        start_date = serializer.validated_data.get('start_date', timezone.now() - timedelta(days=30))
        end_date = serializer.validated_data.get('end_date', timezone.now())
        
        # Generate time series
        df = MetricsAggregator.generate_time_series_metrics(
            models=list(models),
            start_date=start_date,
            end_date=end_date,
            granularity='daily'
        )
        
        # Convert to response format
        response_data = {
            'period': {
                'start': start_date,
                'end': end_date
            },
            'models': [m.display_name for m in models],
            'data': df.to_dict('records') if not df.empty else []
        }
        
        return Response(response_data)


class ProviderMetricsView(views.APIView):
    """Get aggregated metrics by provider"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        providers = AIModel.objects.filter(
            is_active=True
        ).values_list('provider', flat=True).distinct()
        
        results = []
        
        for provider in providers:
            metrics = MetricsAggregator.aggregate_provider_metrics(provider)
            results.append(metrics)
        
        # Sort by average ELO
        results.sort(key=lambda x: x['average_elo'], reverse=True)
        
        return Response(results)


class CategoryDominanceView(views.APIView):
    """Get category dominance analysis"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        dominance = MetricsAggregator.calculate_category_dominance()
        return Response(dominance)


class ModelRankingsView(views.APIView):
    """Get model rankings with percentiles"""
    permission_classes = [AllowAny]
    
    def get(self, request, model_id):
        model = get_object_or_404(AIModel, id=model_id)
        
        rankings = {
            'model': model.display_name,
            'percentiles': {},
            'rankings': {}
        }
        
        categories = ['overall', 'code', 'creative', 'reasoning']
        
        for category in categories:
            # Get percentile rank
            percentile = MetricsCalculator.calculate_percentile_rank(
                model=model,
                category=category
            )
            
            rankings['percentiles'][category] = percentile
            
            # Get actual rank
            leaderboard = ModelMetricsService.get_leaderboard(
                category=category,
                period='all_time',
                limit=100
            )
            
            rank = None
            for idx, entry in enumerate(leaderboard):
                if entry['model'].id == model.id:
                    rank = idx + 1
                    break
            
            rankings['rankings'][category] = rank
        
        return Response(rankings)