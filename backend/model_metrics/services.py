from typing import Dict, List, Optional, Tuple
from django.db.models import Avg, Count, Q, F, Window
from django.db.models.functions import Rank, DenseRank
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from ai_model.models import AIModel
from model_metrics.models import ModelMetric
from feedback.models import Feedback
from message.models import Message
from model_metrics.calculators import MetricsCalculator
from chat_session.models import ChatSession

class ModelMetricsService:
    """Service for managing model metrics"""
    
    @staticmethod
    def calculate_model_metrics(
        model: AIModel,
        period: str = 'all_time',
        categories: Optional[List[str]] = None
    ) -> Dict[str, ModelMetric]:
        """Calculate comprehensive metrics for a model"""
        if categories is None:
            categories = ['overall'] + list(model.capabilities or [])
        
        metrics = {}
        
        for category in categories:
            metric = MetricsCalculator.calculate_category_metrics(
                model=model,
                category=category,
                period=period
            )
            metrics[category] = metric
        
        return metrics
    
    @staticmethod
    def get_leaderboard(
        category: str = 'overall',
        period: str = 'all_time',
        limit: int = 20
    ) -> List[Dict]:
        """Get leaderboard for a specific category"""
        cache_key = f"leaderboard:{category}:{period}:{limit}"
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        # Get latest metrics for each model
        latest_metrics = ModelMetric.objects.filter(
            category=category,
            period=period
        ).order_by(
            'model', '-calculated_at'
        ).distinct('model')
        
        # Sort by ELO rating
        sorted_metrics = sorted(
            latest_metrics,
            key=lambda x: x.elo_rating,
            reverse=True
        )[:limit]
        
        leaderboard = []
        
        for idx, metric in enumerate(sorted_metrics, 1):
            # Get previous rank
            previous_metric = ModelMetric.objects.filter(
                model=metric.model,
                category=category,
                period=period,
                calculated_at__lt=metric.calculated_at
            ).order_by('-calculated_at').first()
            
            previous_rank = None
            if previous_metric:
                previous_rank = ModelMetric.objects.filter(
                    category=category,
                    period=period,
                    calculated_at__date=previous_metric.calculated_at.date(),
                    elo_rating__gt=previous_metric.elo_rating
                ).count() + 1
            
            change = 0
            if previous_rank:
                change = previous_rank - idx
            
            # Additional stats
            recent_feedback = Feedback.objects.filter(
                Q(message__model=metric.model) |
                Q(preferred_model=metric.model)
            ).filter(
                created_at__gte=timezone.now() - timedelta(days=7)
            )
            
            stats = {
                'recent_ratings': recent_feedback.filter(
                    feedback_type='rating',
                    rating__isnull=False
                ).count(),
                'recent_comparisons': recent_feedback.filter(
                    feedback_type='preference'
                ).count(),
                'usage_7d': Message.objects.filter(
                    model=metric.model,
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count()
            }
            
            leaderboard.append({
                'rank': idx,
                'model': metric.model,
                'metrics': metric,
                'change': change,
                'stats': stats
            })
        
        # Cache for 1 hour
        cache.set(cache_key, leaderboard, 3600)
        
        return leaderboard
    
    @staticmethod
    def get_model_performance_analysis(
        model: AIModel,
        time_range: Optional[timedelta] = None
    ) -> Dict:
        """Get detailed performance analysis for a model"""
        if time_range is None:
            time_range = timedelta(days=30)
        
        start_date = timezone.now() - time_range
        
        analysis = {
            'model': model,
            'overall_metrics': None,
            'category_breakdown': {},
            'historical_data': [],
            'strengths': [],
            'weaknesses': [],
            'recent_feedback': {}
        }
        
        # Get latest overall metric
        latest_overall = ModelMetric.objects.filter(
            model=model,
            category='overall',
            period='all_time'
        ).order_by('-calculated_at').first()
        
        analysis['overall_metrics'] = latest_overall
        
        # Category breakdown
        categories = ['code', 'creative', 'reasoning', 'conversation', 'translation']
        
        for category in categories:
            metric = ModelMetric.objects.filter(
                model=model,
                category=category,
                period='all_time'
            ).order_by('-calculated_at').first()
            
            if metric:
                analysis['category_breakdown'][category] = {
                    'elo_rating': metric.elo_rating,
                    'win_rate': metric.win_rate if hasattr(metric, 'win_rate') else 
                               (metric.wins / metric.total_comparisons * 100) if metric.total_comparisons > 0 else 0,
                    'average_rating': metric.average_rating,
                    'total_comparisons': metric.total_comparisons
                }
        
        # Historical data
        historical_metrics = ModelMetric.objects.filter(
            model=model,
            category='overall',
            period='daily',
            calculated_at__gte=start_date
        ).order_by('calculated_at')
        
        for metric in historical_metrics:
            analysis['historical_data'].append({
                'date': metric.calculated_at.date(),
                'elo_rating': metric.elo_rating,
                'win_rate': (metric.wins / metric.total_comparisons * 100) if metric.total_comparisons > 0 else 0,
                'average_rating': metric.average_rating
            })
        
        # Identify strengths and weaknesses
        sorted_categories = sorted(
            analysis['category_breakdown'].items(),
            key=lambda x: x[1]['elo_rating'],
            reverse=True
        )
        
        if sorted_categories:
            # Top 2 categories are strengths
            analysis['strengths'] = [
                {'category': cat, 'elo_rating': data['elo_rating']}
                for cat, data in sorted_categories[:2]
                if data['elo_rating'] > 1500  # Above baseline
            ]
            
            # Bottom 2 categories are weaknesses
            analysis['weaknesses'] = [
                {'category': cat, 'elo_rating': data['elo_rating']}
                for cat, data in sorted_categories[-2:]
                if data['elo_rating'] < 1500  # Below baseline
            ]
        
        # Recent feedback summary
        recent_feedback = Feedback.objects.filter(
            Q(message__model=model) | Q(preferred_model=model),
            created_at__gte=start_date
        )
        
        analysis['recent_feedback'] = {
            'total_feedback': recent_feedback.count(),
            'average_rating': recent_feedback.filter(
                feedback_type='rating',
                rating__isnull=False
            ).aggregate(avg=Avg('rating'))['avg'],
            'preference_wins': recent_feedback.filter(
                feedback_type='preference',
                preferred_model=model
            ).count(),
            'common_categories': ModelMetricsService._get_common_feedback_categories(recent_feedback)
        }
        
        return analysis
    
    @staticmethod
    def _get_common_feedback_categories(feedback_queryset) -> List[Dict]:
        """Get most common feedback categories"""
        category_counts = {}
        
        for feedback in feedback_queryset:
            if feedback.categories:
                for category in feedback.categories:
                    category_counts[category] = category_counts.get(category, 0) + 1
        
        sorted_categories = sorted(
            category_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return [
            {'category': cat, 'count': count}
            for cat, count in sorted_categories
        ]


class ModelComparisonService:
    """Service for comparing models"""
    
    @staticmethod
    def compare_models(
        model_a: AIModel,
        model_b: AIModel,
        categories: Optional[List[str]] = None
    ) -> Dict:
        """Generate detailed comparison between two models"""
        if categories is None:
            categories = ['overall', 'code', 'creative', 'reasoning']
        
        comparison = {
            'model_a': model_a,
            'model_b': model_b,
            'head_to_head': ModelComparisonService._get_head_to_head_stats(model_a, model_b),
            'performance_comparison': {},
            'category_breakdown': {},
            'historical_comparison': []
        }
        
        # Performance comparison
        for category in categories:
            metric_a = ModelMetric.objects.filter(
                model=model_a,
                category=category,
                period='all_time'
            ).order_by('-calculated_at').first()
            
            metric_b = ModelMetric.objects.filter(
                model=model_b,
                category=category,
                period='all_time'
            ).order_by('-calculated_at').first()
            
            if metric_a and metric_b:
                comparison['category_breakdown'][category] = {
                    'model_a': {
                        'elo_rating': metric_a.elo_rating,
                        'win_rate': (metric_a.wins / metric_a.total_comparisons * 100) if metric_a.total_comparisons > 0 else 0,
                        'average_rating': metric_a.average_rating
                    },
                    'model_b': {
                        'elo_rating': metric_b.elo_rating,
                        'win_rate': (metric_b.wins / metric_b.total_comparisons * 100) if metric_b.total_comparisons > 0 else 0,
                        'average_rating': metric_b.average_rating
                    },
                    'difference': {
                        'elo_rating': metric_a.elo_rating - metric_b.elo_rating,
                        'win_rate': ((metric_a.wins / metric_a.total_comparisons * 100) if metric_a.total_comparisons > 0 else 0) - 
                                   ((metric_b.wins / metric_b.total_comparisons * 100) if metric_b.total_comparisons > 0 else 0),
                        'average_rating': (metric_a.average_rating or 0) - (metric_b.average_rating or 0)
                    }
                }
        
        # Historical comparison (last 30 days)
        start_date = timezone.now() - timedelta(days=30)
        
        historical_a = ModelMetric.objects.filter(
            model=model_a,
            category='overall',
            period='daily',
            calculated_at__gte=start_date
        ).order_by('calculated_at').values(
            'calculated_at', 'elo_rating', 'average_rating'
        )
        
        historical_b = ModelMetric.objects.filter(
            model=model_b,
            category='overall',
            period='daily',
            calculated_at__gte=start_date
        ).order_by('calculated_at').values(
            'calculated_at', 'elo_rating', 'average_rating'
        )
        
        # Merge historical data
        dates_a = {h['calculated_at'].date(): h for h in historical_a}
        dates_b = {h['calculated_at'].date(): h for h in historical_b}
        
        all_dates = sorted(set(dates_a.keys()) | set(dates_b.keys()))
        
        for date in all_dates:
            comparison['historical_comparison'].append({
                'date': date,
                'model_a': {
                    'elo_rating': dates_a.get(date, {}).get('elo_rating'),
                    'average_rating': dates_a.get(date, {}).get('average_rating')
                } if date in dates_a else None,
                'model_b': {
                    'elo_rating': dates_b.get(date, {}).get('elo_rating'),
                    'average_rating': dates_b.get(date, {}).get('average_rating')
                } if date in dates_b else None
            })
        
        # Overall performance comparison
        latest_a = ModelMetric.objects.filter(
            model=model_a,
            category='overall',
            period='all_time'
        ).order_by('-calculated_at').first()
        
        latest_b = ModelMetric.objects.filter(
            model=model_b,
            category='overall',
            period='all_time'
        ).order_by('-calculated_at').first()
        
        if latest_a and latest_b:
            comparison['performance_comparison'] = {
                'model_a_better': latest_a.elo_rating > latest_b.elo_rating,
                'elo_difference': latest_a.elo_rating - latest_b.elo_rating,
                'win_rate_difference': ((latest_a.wins / latest_a.total_comparisons * 100) if latest_a.total_comparisons > 0 else 0) -
                                     ((latest_b.wins / latest_b.total_comparisons * 100) if latest_b.total_comparisons > 0 else 0),
                'rating_difference': (latest_a.average_rating or 0) - (latest_b.average_rating or 0)
            }
        
        return comparison
    
    @staticmethod
    def _get_head_to_head_stats(model_a: AIModel, model_b: AIModel) -> Dict:
        """Get direct head-to-head statistics"""
        
        # Find sessions where both models were compared
        comparison_sessions = ChatSession.objects.filter(
            mode='compare'
        ).filter(
            (Q(model_a=model_a) & Q(model_b=model_b)) |
            (Q(model_a=model_b) & Q(model_b=model_a))
        )
        
        # Get feedback from these sessions
        head_to_head = {
            'total_comparisons': 0,
            'model_a_wins': 0,
            'model_b_wins': 0,
            'ties': 0,
            'win_percentage': {
                'model_a': 0,
                'model_b': 0
            }
        }
        
        preference_feedback = Feedback.objects.filter(
            session__in=comparison_sessions,
            feedback_type='preference'
        )
        
        head_to_head['total_comparisons'] = preference_feedback.count()
        
        for feedback in preference_feedback:
            if feedback.preferred_model == model_a:
                head_to_head['model_a_wins'] += 1
            elif feedback.preferred_model == model_b:
                head_to_head['model_b_wins'] += 1
            else:
                head_to_head['ties'] += 1
        
        if head_to_head['total_comparisons'] > 0:
            head_to_head['win_percentage']['model_a'] = round(
                (head_to_head['model_a_wins'] / head_to_head['total_comparisons']) * 100, 2
            )
            head_to_head['win_percentage']['model_b'] = round(
                (head_to_head['model_b_wins'] / head_to_head['total_comparisons']) * 100, 2
            )
        
        return head_to_head