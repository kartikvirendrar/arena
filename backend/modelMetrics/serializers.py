from rest_framework import serializers
from apps.ai_model.models import ModelMetric, AIModel
from apps.ai_model.serializers import AIModelListSerializer


class ModelMetricSerializer(serializers.ModelSerializer):
    """Full model metric serializer"""
    model = AIModelListSerializer(read_only=True)
    win_rate = serializers.SerializerMethodField()
    rank = serializers.SerializerMethodField()
    trend = serializers.SerializerMethodField()
    
    class Meta:
        model = ModelMetric
        fields = [
            'id', 'model', 'category', 'total_comparisons',
            'wins', 'losses', 'ties', 'average_rating',
            'elo_rating', 'period', 'calculated_at',
            'win_rate', 'rank', 'trend'
        ]
    
    def get_win_rate(self, obj):
        if obj.total_comparisons == 0:
            return 0.0
        return round((obj.wins / obj.total_comparisons) * 100, 2)
    
    def get_rank(self, obj):
        # Get rank within category and period
        higher_rated = ModelMetric.objects.filter(
            category=obj.category,
            period=obj.period,
            elo_rating__gt=obj.elo_rating
        ).values('model').distinct().count()
        
        return higher_rated + 1
    
    def get_trend(self, obj):
        # Compare with previous metric
        previous = ModelMetric.objects.filter(
            model=obj.model,
            category=obj.category,
            period=obj.period,
            calculated_at__lt=obj.calculated_at
        ).order_by('-calculated_at').first()
        
        if not previous:
            return 'stable'
        
        if obj.elo_rating > previous.elo_rating:
            return 'up'
        elif obj.elo_rating < previous.elo_rating:
            return 'down'
        return 'stable'


class LeaderboardSerializer(serializers.Serializer):
    """Serializer for leaderboard entries"""
    rank = serializers.IntegerField()
    model = AIModelListSerializer()
    metrics = ModelMetricSerializer()
    change = serializers.IntegerField(help_text="Position change from previous period")
    stats = serializers.DictField()


class CategoryLeaderboardSerializer(serializers.Serializer):
    """Serializer for category-specific leaderboard"""
    category = serializers.CharField()
    display_name = serializers.CharField()
    description = serializers.CharField()
    last_updated = serializers.DateTimeField()
    entries = LeaderboardSerializer(many=True)


class ModelPerformanceSerializer(serializers.Serializer):
    """Detailed model performance serializer"""
    model = AIModelListSerializer()
    overall_metrics = ModelMetricSerializer()
    category_breakdown = serializers.DictField()
    historical_data = serializers.ListField()
    strengths = serializers.ListField()
    weaknesses = serializers.ListField()
    recent_feedback = serializers.DictField()


class MetricAggregationSerializer(serializers.Serializer):
    """Serializer for metric aggregation requests"""
    models = serializers.ListField(
        child=serializers.UUIDField(),
        required=False
    )
    categories = serializers.ListField(
        child=serializers.CharField(),
        required=False
    )
    period = serializers.ChoiceField(
        choices=['daily', 'weekly', 'monthly', 'all_time'],
        default='all_time'
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)


class ModelComparisonMetricsSerializer(serializers.Serializer):
    """Serializer for detailed model comparison metrics"""
    model_a = AIModelListSerializer()
    model_b = AIModelListSerializer()
    head_to_head = serializers.DictField()
    performance_comparison = serializers.DictField()
    category_breakdown = serializers.DictField()
    historical_comparison = serializers.ListField()