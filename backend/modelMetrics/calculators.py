from typing import Dict, Optional
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
import math

from apps.ai_model.models import AIModel, ModelMetric
from apps.feedback.models import Feedback
from apps.message.models import Message


class MetricsCalculator:
    """Calculate various metrics for models"""
    
    @staticmethod
    def calculate_category_metrics(
        model: AIModel,
        category: str,
        period: str = 'all_time'
    ) -> ModelMetric:
        """Calculate metrics for a specific category"""
        # Determine time range
        if period == 'daily':
            start_date = timezone.now() - timedelta(days=1)
        elif period == 'weekly':
            start_date = timezone.now() - timedelta(weeks=1)
        elif period == 'monthly':
            start_date = timezone.now() - timedelta(days=30)
        else:  # all_time
            start_date = None
        
        # Get or create metric
        metric, created = ModelMetric.objects.get_or_create(
            model=model,
            category=category,
            period=period,
            calculated_at__date=timezone.now().date() if period != 'all_time' else None,
            defaults={
                'calculated_at': timezone.now(),
                'elo_rating': 1500  # Default ELO
            }
        )
        
        # Base feedback query
        feedback_query = Feedback.objects.all()
        if start_date:
            feedback_query = feedback_query.filter(created_at__gte=start_date)
        
        # Calculate ratings
        if category == 'overall':
            ratings = feedback_query.filter(
                feedback_type='rating',
                rating__isnull=False,
                message__model=model
            )
        else:
            # Category-specific ratings
            ratings = feedback_query.filter(
                feedback_type='rating',
                rating__isnull=False,
                message__model=model,
                categories__contains=[category]
            )
        
        if ratings.exists():
            metric.average_rating = ratings.aggregate(avg=Avg('rating'))['avg']
        
        # Calculate comparison stats
        if category == 'overall':
            comparisons = feedback_query.filter(
                feedback_type='preference',
                session__mode='compare'
            ).filter(
                Q(session__model_a=model) | Q(session__model_b=model)
            )
        else:
            comparisons = feedback_query.filter(
                feedback_type='preference',
                session__mode='compare',
                categories__contains=[category]
            ).filter(
                Q(session__model_a=model) | Q(session__model_b=model)
            )
        
        metric.total_comparisons = comparisons.count()
        metric.wins = comparisons.filter(preferred_model=model).count()
        metric.losses = comparisons.exclude(
            preferred_model=model
        ).exclude(
            preferred_model__isnull=True
        ).count()
        metric.ties = metric.total_comparisons - metric.wins - metric.losses
        
        # Calculate usage metrics
        usage_metrics = MetricsCalculator._calculate_usage_metrics(
            model, category, start_date
        )
        
        # Store additional data in metadata
        if not hasattr(metric, 'metadata'):
            metric.metadata = {}
        
        metric.metadata.update(usage_metrics)
        
        # Save metric
        metric.save()
        
        return metric
    
    @staticmethod
    def _calculate_usage_metrics(
        model: AIModel,
        category: str,
        start_date: Optional[timezone.datetime]
    ) -> Dict:
        """Calculate usage-based metrics"""
        message_query = Message.objects.filter(model=model)
        
        if start_date:
            message_query = message_query.filter(created_at__gte=start_date)
        
        usage_metrics = {
            'total_messages': message_query.count(),
            'unique_sessions': message_query.values('session').distinct().count(),
            'unique_users': message_query.values('session__user').distinct().count(),
            'avg_response_length': None,
            'success_rate': None
        }
        
        # Average response length
        avg_length = message_query.aggregate(
            avg_length=Avg(models.Length('content'))
        )['avg_length']
        
        if avg_length:
            usage_metrics['avg_response_length'] = round(avg_length, 2)
        
        # Success rate
        total_messages = usage_metrics['total_messages']
        if total_messages > 0:
            successful = message_query.filter(status='success').count()
            usage_metrics['success_rate'] = round(
                (successful / total_messages) * 100, 2
            )
        
        return usage_metrics
    
    @staticmethod
    def calculate_percentile_rank(
        model: AIModel,
        category: str = 'overall',
        metric_type: str = 'elo_rating'
    ) -> float:
        """Calculate percentile rank for a model"""
        latest_metric = ModelMetric.objects.filter(
            model=model,
            category=category,
            period='all_time'
        ).order_by('-calculated_at').first()
        
        if not latest_metric:
            return 0.0
        
        metric_value = getattr(latest_metric, metric_type, 0)
        
        # Count models with lower values
        all_metrics = ModelMetric.objects.filter(
            category=category,
            period='all_time'
        ).order_by('model', '-calculated_at').distinct('model')
        
        total_models = all_metrics.count()
        if total_models <= 1:
            return 100.0
        
        lower_count = sum(
            1 for m in all_metrics
            if getattr(m, metric_type, 0) < metric_value
        )
        
        percentile = (lower_count / (total_models - 1)) * 100
        return round(percentile, 2)


class EloCalculator:
    """Advanced ELO rating calculations"""
    
    K_FACTOR = 32
    INITIAL_RATING = 1500
    
    @staticmethod
    def calculate_expected_score(rating_a: float, rating_b: float) -> float:
        """Calculate expected score for player A"""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    
    @staticmethod
    def calculate_new_ratings(
        rating_a: float,
        rating_b: float,
        score_a: float
    ) -> Tuple[float, float]:
        """Calculate new ELO ratings"""
        expected_a = EloCalculator.calculate_expected_score(rating_a, rating_b)
        expected_b = 1 - expected_a
        
        new_rating_a = rating_a + EloCalculator.K_FACTOR * (score_a - expected_a)
        new_rating_b = rating_b + EloCalculator.K_FACTOR * ((1 - score_a) - expected_b)
        
        return round(new_rating_a), round(new_rating_b)
    
    @staticmethod
    def calculate_confidence_interval(
        wins: int,
        total: int,
        confidence: float = 0.95
    ) -> Tuple[float, float]:
        """Calculate confidence interval for win rate"""
        if total == 0:
            return 0.0, 0.0
        
        from scipy import stats
        
        p = wins / total
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        
        interval = z * math.sqrt((p * (1 - p)) / total)
        
        lower = max(0, p - interval)
        upper = min(1, p + interval)
        
        return round(lower * 100, 2), round(upper * 100, 2)