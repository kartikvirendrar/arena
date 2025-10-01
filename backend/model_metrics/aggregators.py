from typing import Dict, List, Optional
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
from model_metrics.models import AIModel, ModelMetric
from feedback.models import Feedback


class MetricsAggregator:
    """Aggregate metrics across models and time periods"""
    
    @staticmethod
    def aggregate_provider_metrics(provider: str) -> Dict:
        """Aggregate metrics by provider"""
        models = AIModel.objects.filter(provider=provider, is_active=True)
        
        aggregated = {
            'provider': provider,
            'model_count': models.count(),
            'average_elo': 0,
            'total_comparisons': 0,
            'total_wins': 0,
            'average_rating': None,
            'models': []
        }
        
        total_elo = 0
        ratings = []
        
        for model in models:
            latest_metric = ModelMetric.objects.filter(
                model=model,
                category='overall',
                period='all_time'
            ).order_by('-calculated_at').first()
            
            if latest_metric:
                total_elo += latest_metric.elo_rating
                aggregated['total_comparisons'] += latest_metric.total_comparisons
                aggregated['total_wins'] += latest_metric.wins
                
                if latest_metric.average_rating:
                    ratings.append(latest_metric.average_rating)
                
                aggregated['models'].append({
                    'model': model,
                    'elo_rating': latest_metric.elo_rating,
                    'win_rate': (latest_metric.wins / latest_metric.total_comparisons * 100) 
                               if latest_metric.total_comparisons > 0 else 0
                })
        
        if models.count() > 0:
            aggregated['average_elo'] = round(total_elo / models.count(), 2)
        
        if ratings:
            aggregated['average_rating'] = round(sum(ratings) / len(ratings), 2)
        
        # Sort models by ELO
        aggregated['models'].sort(key=lambda x: x['elo_rating'], reverse=True)
        
        return aggregated
    
    @staticmethod
    def generate_time_series_metrics(
        models: List[AIModel],
        start_date: datetime,
        end_date: datetime,
        granularity: str = 'daily'
    ) -> pd.DataFrame:
        """Generate time series metrics for multiple models"""
        # Determine period based on granularity
        if granularity == 'daily':
            period = 'daily'
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        elif granularity == 'weekly':
            period = 'weekly'
            date_range = pd.date_range(start=start_date, end=end_date, freq='W')
        else:  # monthly
            period = 'monthly'
            date_range = pd.date_range(start=start_date, end=end_date, freq='M')
        
        data = []
        
        for date in date_range:
            for model in models:
                metric = ModelMetric.objects.filter(
                    model=model,
                    category='overall',
                    period=period,
                    calculated_at__date=date.date()
                ).first()
                
                if metric:
                    data.append({
                        'date': date,
                        'model': model.display_name,
                        'elo_rating': metric.elo_rating,
                        'win_rate': (metric.wins / metric.total_comparisons * 100) 
                                   if metric.total_comparisons > 0 else 0,
                        'average_rating': metric.average_rating,
                        'total_comparisons': metric.total_comparisons
                    })
        
        df = pd.DataFrame(data)
        return df
    
    @staticmethod
    def calculate_category_dominance() -> Dict[str, List[Dict]]:
        """Calculate which models dominate each category"""
        categories = [
            'overall', 'code', 'creative', 'reasoning', 
            'translation', 'summarization', 'conversation'
        ]
        
        dominance = {}
        
        for category in categories:
            # Get top models for this category
            top_metrics = ModelMetric.objects.filter(
                category=category,
                period='all_time'
            ).order_by('model', '-calculated_at').distinct('model')
            
            # Sort by ELO rating
            sorted_metrics = sorted(
                top_metrics,
                key=lambda x: x.elo_rating,
                reverse=True
            )[:5]
            
            dominance[category] = []
            
            for idx, metric in enumerate(sorted_metrics):
                dominance[category].append({
                    'rank': idx + 1,
                    'model': metric.model.display_name,
                    'provider': metric.model.provider,
                    'elo_rating': metric.elo_rating,
                    'win_rate': (metric.wins / metric.total_comparisons * 100) 
                               if metric.total_comparisons > 0 else 0,
                    'dominance_score': MetricsAggregator._calculate_dominance_score(
                        metric, sorted_metrics
                    )
                })
        
        return dominance
    
    @staticmethod
    def _calculate_dominance_score(metric: ModelMetric, all_metrics: List[ModelMetric]) -> float:
        """Calculate dominance score based on ELO gap"""
        if not all_metrics or len(all_metrics) < 2:
            return 100.0
        
        # Calculate average ELO of other models
        other_elos = [m.elo_rating for m in all_metrics if m != metric]
        if not other_elos:
            return 100.0
        
        avg_other_elo = sum(other_elos) / len(other_elos)
        
        # Dominance score based on difference
        difference = metric.elo_rating - avg_other_elo
        
        # Normalize to 0-100 scale
        # 200 point difference = 100% dominance
        dominance = min(100, max(0, (difference / 200) * 100))
        
        return round(dominance, 2)