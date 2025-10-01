from typing import Dict, List, Optional, Tuple
from django.db.models import Count, Avg, Q, F
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import statistics
from feedback.models import Feedback
from model_metrics.models import AIModel, ModelMetric
from chat_session.models import ChatSession
from ai_model.utils import EloRatingCalculator
from django.core.cache import cache
from model_metrics.models import ModelMetric


class FeedbackService:
    """Service for managing feedback operations"""
    
    @staticmethod
    def get_session_feedback_summary(session: ChatSession) -> Dict:
        """Get comprehensive feedback summary for a session"""
        feedbacks = Feedback.objects.filter(session=session)
        
        summary = {
            'session_id': str(session.id),
            'total_feedback_count': feedbacks.count(),
            'average_rating': None,
            'rating_distribution': {},
            'preferences': {},
            'categories_mentioned': {},
            'recent_comments': []
        }
        
        # Rating statistics
        ratings = feedbacks.filter(
            feedback_type='rating',
            rating__isnull=False
        )
        
        if ratings.exists():
            summary['average_rating'] = round(
                ratings.aggregate(avg=Avg('rating'))['avg'], 2
            )
            
            # Rating distribution
            for rating in range(1, 6):
                count = ratings.filter(rating=rating).count()
                summary['rating_distribution'][rating] = count
        
        # Preference statistics for compare mode
        if session.mode == 'compare':
            preferences = feedbacks.filter(feedback_type='preference')
            
            for model in [session.model_a, session.model_b]:
                if model:
                    pref_count = preferences.filter(preferred_model=model).count()
                    summary['preferences'][model.display_name] = {
                        'count': pref_count,
                        'percentage': round(
                            (pref_count / preferences.count() * 100) 
                            if preferences.count() > 0 else 0, 2
                        )
                    }
        
        # Category analysis
        all_categories = []
        for feedback in feedbacks:
            if feedback.categories:
                all_categories.extend(feedback.categories)
        
        for category in set(all_categories):
            summary['categories_mentioned'][category] = all_categories.count(category)
        
        # Recent comments
        recent_feedbacks = feedbacks.exclude(
            comment__isnull=True
        ).exclude(
            comment=''
        ).order_by('-created_at')[:5]
        
        summary['recent_comments'] = [
            {
                'id': str(fb.id),
                'comment': fb.comment,
                'rating': fb.rating,
                'created_at': fb.created_at.isoformat(),
                'feedback_type': fb.feedback_type
            }
            for fb in recent_feedbacks
        ]
        
        return summary
    
    @staticmethod
    def get_model_feedback_stats(
        model: AIModel,
        time_period: Optional[timedelta] = None
    ) -> Dict:
        """Get feedback statistics for a specific model"""
        # Base query
        feedbacks = Feedback.objects.filter(
            Q(message__model=model) |
            Q(session__model_a=model) |
            Q(session__model_b=model)
        )
        
        if time_period:
            start_date = timezone.now() - time_period
            feedbacks = feedbacks.filter(created_at__gte=start_date)
        
        # Rating statistics
        ratings = feedbacks.filter(
            feedback_type='rating',
            rating__isnull=False,
            message__model=model
        )
        
        stats = {
            'model': model,
            'total_ratings': ratings.count(),
            'average_rating': None,
            'rating_breakdown': {},
            'total_preferences': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0,
            'categories_performance': {}
        }
        
        if ratings.exists():
            stats['average_rating'] = round(
                ratings.aggregate(avg=Avg('rating'))['avg'], 2
            )
            
            # Rating breakdown
            for rating in range(1, 6):
                stats['rating_breakdown'][rating] = ratings.filter(rating=rating).count()
        
        # Preference statistics (for compare mode)
        preference_feedbacks = Feedback.objects.filter(
            feedback_type='preference',
            session__mode='compare'
        ).filter(
            Q(session__model_a=model) | Q(session__model_b=model)
        )
        
        if time_period:
            preference_feedbacks = preference_feedbacks.filter(created_at__gte=start_date)
        
        stats['total_preferences'] = preference_feedbacks.count()
        stats['win_count'] = preference_feedbacks.filter(preferred_model=model).count()
        stats['loss_count'] = preference_feedbacks.exclude(
            preferred_model=model
        ).exclude(
            preferred_model__isnull=True
        ).count()
        
        if stats['total_preferences'] > 0:
            stats['win_rate'] = round(
                (stats['win_count'] / stats['total_preferences']) * 100, 2
            )
        
        # Category performance
        category_ratings = {}
        for feedback in ratings:
            if feedback.categories:
                for category in feedback.categories:
                    if category not in category_ratings:
                        category_ratings[category] = []
                    category_ratings[category].append(feedback.rating)
        
        for category, ratings_list in category_ratings.items():
            stats['categories_performance'][category] = {
                'average_rating': round(statistics.mean(ratings_list), 2),
                'count': len(ratings_list)
            }
        
        return stats
    
    @staticmethod
    def calculate_model_comparison_stats(
        model_a: AIModel,
        model_b: AIModel,
        time_period: Optional[timedelta] = None
    ) -> Dict:
        """Calculate head-to-head comparison statistics"""
        comparisons = Feedback.objects.filter(
            feedback_type='preference',
            session__mode='compare',
            session__model_a=model_a,
            session__model_b=model_b
        ) | Feedback.objects.filter(
            feedback_type='preference',
            session__mode='compare',
            session__model_a=model_b,
            session__model_b=model_a
        )
        
        if time_period:
            start_date = timezone.now() - time_period
            comparisons = comparisons.filter(created_at__gte=start_date)
        
        total = comparisons.count()
        model_a_wins = comparisons.filter(preferred_model=model_a).count()
        model_b_wins = comparisons.filter(preferred_model=model_b).count()
        ties = total - model_a_wins - model_b_wins
        
        return {
            'total_comparisons': total,
            'model_a': {
                'model': model_a,
                'wins': model_a_wins,
                'win_rate': round((model_a_wins / total * 100) if total > 0 else 0, 2)
            },
            'model_b': {
                'model': model_b,
                'wins': model_b_wins,
                'win_rate': round((model_b_wins / total * 100) if total > 0 else 0, 2)
            },
            'ties': ties
        }


class FeedbackAnalyticsService:
    """Service for feedback analytics and metrics"""
    
    @staticmethod
    def process_new_feedback(feedback: Feedback):
        """Process new feedback and update relevant metrics"""
        if feedback.feedback_type == 'preference' and feedback.session.mode == 'compare':
            # Update ELO ratings
            FeedbackAnalyticsService._update_elo_ratings(feedback)
            
        # Update model metrics
        FeedbackAnalyticsService._update_model_metrics(feedback)
        
        # Cache invalidation
        cache_keys = [
            f"model_stats:{feedback.session.model_a_id}",
            f"model_stats:{feedback.session.model_b_id}",
            f"session_feedback:{feedback.session_id}"
        ]
        cache.delete_many([k for k in cache_keys if k])
    
    @staticmethod
    def _update_elo_ratings(feedback: Feedback):
        """Update ELO ratings based on preference feedback"""
        session = feedback.session
        
        if feedback.preferred_model == session.model_a:
            result = 'a_wins'
        elif feedback.preferred_model == session.model_b:
            result = 'b_wins'
        else:
            result = 'tie'
        
        # Update ELO ratings
        EloRatingCalculator.update_model_ratings(
            str(session.model_a_id),
            str(session.model_b_id),
            result
        )
        
        # Also update category-specific ELO if categories are specified
        if feedback.categories:
            for category in feedback.categories:
                EloRatingCalculator.update_model_ratings(
                    str(session.model_a_id),
                    str(session.model_b_id),
                    result,
                    category=category
                )
    
    @staticmethod
    def _update_model_metrics(feedback: Feedback):
        """Update model metrics based on feedback"""
        
        models_to_update = []
        
        # Determine which models to update
        if feedback.message and feedback.message.model:
            models_to_update.append(feedback.message.model)
        elif feedback.session.mode == 'compare':
            models_to_update.extend([feedback.session.model_a, feedback.session.model_b])
        elif feedback.session.model_a:
            models_to_update.append(feedback.session.model_a)
        
        # Update metrics for each model
        for model in models_to_update:
            if not model:
                continue
                
            # Get or create today's metric
            today = timezone.now().date()
            metric, created = ModelMetric.objects.get_or_create(
                model=model,
                category='overall',
                period='daily',
                calculated_at__date=today,
                defaults={'calculated_at': timezone.now()}
            )
            
            # Update based on feedback type
            if feedback.feedback_type == 'rating' and feedback.rating:
                # Update average rating
                current_ratings = Feedback.objects.filter(
                    feedback_type='rating',
                    rating__isnull=False,
                    message__model=model,
                    created_at__date=today
                )
                
                metric.average_rating = current_ratings.aggregate(
                    avg=Avg('rating')
                )['avg']
                metric.save()
    
    @staticmethod
    def get_trending_feedback_categories(days: int = 7) -> List[Dict]:
        """Get trending feedback categories"""
        start_date = timezone.now() - timedelta(days=days)
        
        feedbacks = Feedback.objects.filter(
            created_at__gte=start_date,
            categories__isnull=False
        )
        
        category_counts = {}
        for feedback in feedbacks:
            for category in feedback.categories:
                category_counts[category] = category_counts.get(category, 0) + 1
        
        # Sort by count
        trending = sorted(
            [{'category': k, 'count': v} for k, v in category_counts.items()],
            key=lambda x: x['count'],
            reverse=True
        )
        
        return trending[:10]