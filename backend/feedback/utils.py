from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import numpy as np
from datetime import datetime, timedelta


class FeedbackMetrics:
    """Calculate various feedback metrics"""
    
    @staticmethod
    def calculate_wilson_score(positive: int, total: int, confidence: float = 0.95) -> float:
        """
        Calculate Wilson score for ranking
        Used for ranking models with different numbers of ratings
        """
        if total == 0:
            return 0
        
        from scipy import stats
        
        z = stats.norm.ppf(1 - (1 - confidence) / 2)
        p = positive / total
        
        numerator = p + z**2 / (2 * total) - z * np.sqrt(
            (p * (1 - p) + z**2 / (4 * total)) / total
        )
        denominator = 1 + z**2 / total
        
        return numerator / denominator
    
    @staticmethod
    def calculate_weighted_rating(
        ratings: List[int],
        weights: Optional[List[float]] = None
    ) -> float:
        """Calculate weighted average rating"""
        if not ratings:
            return 0
        
        if weights is None:
            # Default weights: more recent ratings have higher weight
            weights = [1.0] * len(ratings)
        
        weighted_sum = sum(r * w for r, w in zip(ratings, weights))
        weight_total = sum(weights)
        
        return weighted_sum / weight_total if weight_total > 0 else 0
    
    @staticmethod
    def detect_rating_anomalies(
        user_ratings: List[Tuple[datetime, int]]
    ) -> List[Dict]:
        """Detect unusual rating patterns"""
        anomalies = []
        
        if len(user_ratings) < 5:
            return anomalies
        
        # Sort by date
        user_ratings.sort(key=lambda x: x[0])
        
        # Check for rapid rating changes
        for i in range(1, len(user_ratings)):
            time_diff = (user_ratings[i][0] - user_ratings[i-1][0]).total_seconds()
            rating_diff = abs(user_ratings[i][1] - user_ratings[i-1][1])
            
            # Flag if large rating change in short time
            if time_diff < 300 and rating_diff >= 3:  # 5 minutes, 3+ point change
                anomalies.append({
                    'type': 'rapid_change',
                    'timestamp': user_ratings[i][0],
                    'details': f'Rating changed by {rating_diff} points in {time_diff}s'
                })
        
        # Check for all same ratings
        unique_ratings = set(r[1] for r in user_ratings)
        if len(unique_ratings) == 1 and len(user_ratings) > 10:
            anomalies.append({
                'type': 'no_variation',
                'timestamp': user_ratings[-1][0],
                'details': f'All {len(user_ratings)} ratings are the same'
            })
        
        return anomalies


class FeedbackValidator:
    """Validate feedback data"""
    
    @staticmethod
    def validate_preference_consistency(feedbacks: List['Feedback']) -> Dict:
        """Check for consistency in preference feedback"""
        from .models import Feedback
        
        # Group by user and model pairs
        user_preferences = defaultdict(lambda: defaultdict(list))
        
        for feedback in feedbacks.filter(feedback_type='preference'):
            if feedback.session.mode != 'compare':
                continue
            
            model_pair = tuple(sorted([
                str(feedback.session.model_a_id),
                str(feedback.session.model_b_id)
            ]))
            
            user_preferences[feedback.user_id][model_pair].append(
                str(feedback.preferred_model_id)
            )
        
        # Check consistency
        inconsistencies = []
        
        for user_id, preferences in user_preferences.items():
            for model_pair, choices in preferences.items():
                if len(set(choices)) > 1:  # User chose different models
                    choice_counts = defaultdict(int)
                    for choice in choices:
                        choice_counts[choice] += 1
                    
                    inconsistencies.append({
                        'user_id': user_id,
                        'model_pair': model_pair,
                        'choices': dict(choice_counts),
                        'consistency_rate': max(choice_counts.values()) / len(choices)
                    })
        
        return {
            'total_users_checked': len(user_preferences),
            'inconsistent_users': len(inconsistencies),
            'details': inconsistencies
        }
    
    # apps/feedback/utils.py (continued)

    @staticmethod
    def validate_spam_feedback(
        user,
        time_window: timedelta = timedelta(minutes=5)
    ) -> Dict:
        """Check if user is potentially spamming feedback"""
        from .models import Feedback
        
        recent_feedback = Feedback.objects.filter(
            user=user,
            created_at__gte=timezone.now() - time_window
        )
        
        validation = {
            'is_spam': False,
            'reasons': [],
            'feedback_count': recent_feedback.count(),
            'time_window_minutes': time_window.total_seconds() / 60
        }
        
        # Check feedback rate
        if recent_feedback.count() > 10:
            validation['is_spam'] = True
            validation['reasons'].append(
                f"Too many feedbacks ({recent_feedback.count()}) in {validation['time_window_minutes']} minutes"
            )
        
        # Check for duplicate content
        comments = recent_feedback.exclude(
            comment__isnull=True
        ).exclude(
            comment=''
        ).values_list('comment', flat=True)
        
        if len(comments) > 3 and len(set(comments)) == 1:
            validation['is_spam'] = True
            validation['reasons'].append("All comments are identical")
        
        # Check for pattern in ratings
        ratings = recent_feedback.filter(
            feedback_type='rating',
            rating__isnull=False
        ).values_list('rating', flat=True)
        
        if len(ratings) > 5:
            # All same rating
            if len(set(ratings)) == 1:
                validation['is_spam'] = True
                validation['reasons'].append("All ratings are the same")
            
            # Sequential pattern (1,2,3,4,5,1,2,3,4,5...)
            if len(ratings) >= 10:
                pattern_length = 5
                is_pattern = all(
                    ratings[i] == ratings[i % pattern_length]
                    for i in range(len(ratings))
                )
                if is_pattern:
                    validation['is_spam'] = True
                    validation['reasons'].append("Ratings follow a repetitive pattern")
        
        return validation


class FeedbackExporter:
    """Export feedback data in various formats"""
    
    @staticmethod
    def export_to_csv(feedbacks, include_pii: bool = False) -> str:
        """Export feedback to CSV format"""
        import csv
        import io
        
        output = io.StringIO()
        
        fieldnames = [
            'id', 'created_at', 'feedback_type', 'rating',
            'session_id', 'session_mode', 'model_a', 'model_b',
            'preferred_model', 'categories', 'comment'
        ]
        
        if include_pii:
            fieldnames.extend(['user_id', 'user_email'])
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for feedback in feedbacks:
            row = {
                'id': str(feedback.id),
                'created_at': feedback.created_at.isoformat(),
                'feedback_type': feedback.feedback_type,
                'rating': feedback.rating,
                'session_id': str(feedback.session_id),
                'session_mode': feedback.session.mode,
                'model_a': feedback.session.model_a.display_name if feedback.session.model_a else '',
                'model_b': feedback.session.model_b.display_name if feedback.session.model_b else '',
                'preferred_model': feedback.preferred_model.display_name if feedback.preferred_model else '',
                'categories': ', '.join(feedback.categories or []),
                'comment': feedback.comment or ''
            }
            
            if include_pii:
                row['user_id'] = str(feedback.user_id)
                row['user_email'] = feedback.user.email or 'anonymous'
            
            writer.writerow(row)
        
        return output.getvalue()
    
    @staticmethod
    def export_analytics_summary(
        start_date: datetime,
        end_date: datetime,
        model_ids: Optional[List[str]] = None
    ) -> Dict:
        """Export analytics summary for reporting"""
        from .models import Feedback
        from apps.ai_model.models import AIModel
        
        # Base query
        feedbacks = Feedback.objects.filter(
            created_at__range=[start_date, end_date]
        )
        
        if model_ids:
            feedbacks = feedbacks.filter(
                Q(message__model_id__in=model_ids) |
                Q(preferred_model_id__in=model_ids) |
                Q(session__model_a_id__in=model_ids) |
                Q(session__model_b_id__in=model_ids)
            )
        
        summary = {
            'metadata': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'generated_at': timezone.now().isoformat()
            },
            'overview': {
                'total_feedback': feedbacks.count(),
                'unique_users': feedbacks.values('user').distinct().count(),
                'unique_sessions': feedbacks.values('session').distinct().count()
            },
            'by_type': {},
            'model_performance': {},
            'daily_breakdown': {}
        }
        
        # Feedback by type
        for f_type in ['rating', 'preference', 'report']:
            type_feedback = feedbacks.filter(feedback_type=f_type)
            summary['by_type'][f_type] = {
                'count': type_feedback.count(),
                'users': type_feedback.values('user').distinct().count()
            }
        
        # Model performance
        models = AIModel.objects.filter(is_active=True)
        if model_ids:
            models = models.filter(id__in=model_ids)
        
        for model in models:
            # Ratings
            ratings = feedbacks.filter(
                feedback_type='rating',
                message__model=model,
                rating__isnull=False
            )
            
            # Preferences
            preferences = feedbacks.filter(
                feedback_type='preference'
            ).filter(
                Q(session__model_a=model) | Q(session__model_b=model)
            )
            
            wins = preferences.filter(preferred_model=model).count()
            
            summary['model_performance'][model.display_name] = {
                'ratings': {
                    'count': ratings.count(),
                    'average': ratings.aggregate(avg=Avg('rating'))['avg'],
                    'distribution': dict(
                        ratings.values('rating').annotate(count=Count('id')).values_list('rating', 'count')
                    )
                },
                'preferences': {
                    'total_comparisons': preferences.count(),
                    'wins': wins,
                    'win_rate': (wins / preferences.count() * 100) if preferences.count() > 0 else 0
                }
            }
        
        # Daily breakdown
        current_date = start_date.date()
        while current_date <= end_date.date():
            day_feedback = feedbacks.filter(
                created_at__date=current_date
            )
            
            summary['daily_breakdown'][current_date.isoformat()] = {
                'total': day_feedback.count(),
                'ratings': day_feedback.filter(feedback_type='rating').count(),
                'preferences': day_feedback.filter(feedback_type='preference').count(),
                'reports': day_feedback.filter(feedback_type='report').count()
            }
            
            current_date += timedelta(days=1)
        
        return summary