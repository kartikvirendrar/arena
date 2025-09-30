from typing import Dict, List, Optional
from django.db.models import Count, Avg, Q, F
from django.utils import timezone
from datetime import timedelta
import pandas as pd
from collections import defaultdict


class FeedbackAnalyzer:
    """Advanced analytics for feedback data"""
    
    @staticmethod
    def analyze_user_preferences(user, time_period: Optional[timedelta] = None) -> Dict:
        """Analyze user's feedback patterns and preferences"""
        from .models import Feedback
        
        feedbacks = Feedback.objects.filter(user=user)
        
        if time_period:
            start_date = timezone.now() - time_period
            feedbacks = feedbacks.filter(created_at__gte=start_date)
        
        analysis = {
            'total_feedback_given': feedbacks.count(),
            'feedback_by_type': {},
            'average_rating_given': None,
            'preferred_models': [],
            'favorite_categories': [],
            'feedback_frequency': {},
            'consistency_score': 0
        }
        
        # Feedback by type
        for feedback_type in ['rating', 'preference', 'report']:
            count = feedbacks.filter(feedback_type=feedback_type).count()
            analysis['feedback_by_type'][feedback_type] = count
        
        # Average rating given
        ratings = feedbacks.filter(
            feedback_type='rating',
            rating__isnull=False
        )
        if ratings.exists():
            analysis['average_rating_given'] = round(
                ratings.aggregate(avg=Avg('rating'))['avg'], 2
            )
        
        # Preferred models
        model_preferences = defaultdict(int)
        preference_feedbacks = feedbacks.filter(
            feedback_type='preference',
            preferred_model__isnull=False
        )
        
        for feedback in preference_feedbacks:
            model_preferences[feedback.preferred_model.display_name] += 1
        
        analysis['preferred_models'] = sorted(
            [{'model': k, 'count': v} for k, v in model_preferences.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:5]
        
        # Favorite categories
        all_categories = []
        for feedback in feedbacks:
            if feedback.categories:
                all_categories.extend(feedback.categories)
        
        category_counts = defaultdict(int)
        for category in all_categories:
            category_counts[category] += 1
        
        analysis['favorite_categories'] = sorted(
            [{'category': k, 'count': v} for k, v in category_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:5]
        
        # Feedback frequency (by day of week)
        feedback_dates = feedbacks.values_list('created_at', flat=True)
        day_counts = defaultdict(int)
        
        for date in feedback_dates:
            day_name = date.strftime('%A')
            day_counts[day_name] += 1
        
        analysis['feedback_frequency'] = dict(day_counts)
        
        # Calculate consistency score
        analysis['consistency_score'] = FeedbackAnalyzer._calculate_consistency_score(
            feedbacks
        )
        
        return analysis
    
    @staticmethod
    def _calculate_consistency_score(feedbacks) -> float:
        """Calculate how consistent a user is in their feedback"""
        # Check rating consistency
        model_ratings = defaultdict(list)
        
        for feedback in feedbacks.filter(
            feedback_type='rating',
            rating__isnull=False,
            message__model__isnull=False
        ):
            model_ratings[feedback.message.model_id].append(feedback.rating)
        
        # Calculate standard deviation for each model
        consistency_scores = []
        
        for model_id, ratings in model_ratings.items():
            if len(ratings) > 1:
                import statistics
                std_dev = statistics.stdev(ratings)
                # Lower std dev = higher consistency
                consistency = max(0, 100 - (std_dev * 20))
                consistency_scores.append(consistency)
        
        if consistency_scores:
            return round(sum(consistency_scores) / len(consistency_scores), 2)
        
        return 0.0
    
    @staticmethod
    def generate_feedback_report(
        start_date: timezone.datetime,
        end_date: timezone.datetime
    ) -> Dict:
        """Generate comprehensive feedback report for a time period"""
        from .models import Feedback
        from apps.ai_model.models import AIModel
        
        feedbacks = Feedback.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        report = {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'summary': {
                'total_feedback': feedbacks.count(),
                'unique_users': feedbacks.values('user').distinct().count(),
                'unique_sessions': feedbacks.values('session').distinct().count()
            },
            'feedback_types': {},
            'model_performance': {},
            'category_insights': {},
            'user_engagement': {}
        }
        
        # Feedback types breakdown
        for feedback_type in ['rating', 'preference', 'report']:
            type_feedbacks = feedbacks.filter(feedback_type=feedback_type)
            report['feedback_types'][feedback_type] = {
                'count': type_feedbacks.count(),
                'percentage': round(
                    (type_feedbacks.count() / feedbacks.count() * 100) 
                    if feedbacks.count() > 0 else 0, 2
                )
            }
        
        # Model performance
        for model in AIModel.objects.filter(is_active=True):
            model_feedbacks = feedbacks.filter(
                Q(message__model=model) |
                Q(preferred_model=model)
            )
            
            if model_feedbacks.exists():
                ratings = model_feedbacks.filter(
                    feedback_type='rating',
                    rating__isnull=False
                )
                
                preferences = feedbacks.filter(
                    feedback_type='preference',
                    session__mode='compare'
                ).filter(
                    Q(session__model_a=model) | Q(session__model_b=model)
                )
                
                wins = preferences.filter(preferred_model=model).count()
                
                report['model_performance'][model.display_name] = {
                    'total_feedback': model_feedbacks.count(),
                    'average_rating': round(
                        ratings.aggregate(avg=Avg('rating'))['avg'], 2
                    ) if ratings.exists() else None,
                    'preference_wins': wins,
                    'preference_total': preferences.count(),
                    'win_rate': round(
                        (wins / preferences.count() * 100) 
                        if preferences.count() > 0 else 0, 2
                    )
                }
        
        return report