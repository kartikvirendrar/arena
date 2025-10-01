from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import json
import csv
import io
from ai_model.models import AIModel
from model_metrics.models import ModelMetric

class MetricStatistics:
    """Statistical utilities for metrics"""
    
    @staticmethod
    def calculate_trend(data_points: List[Tuple[datetime, float]]) -> Dict:
        """Calculate trend statistics from time series data"""
        if len(data_points) < 2:
            return {
                'direction': 'stable',
                'slope': 0,
                'r_squared': 0,
                'change_percent': 0
            }
        
        # Sort by date
        data_points.sort(key=lambda x: x[0])
        
        # Convert to arrays
        x = np.array([(point[0] - data_points[0][0]).days for point in data_points])
        y = np.array([point[1] for point in data_points])
        
        # Calculate linear regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Calculate percentage change
        change_percent = ((y[-1] - y[0]) / y[0] * 100) if y[0] != 0 else 0
        
        # Determine direction
        if slope > 0.1:
            direction = 'improving'
        elif slope < -0.1:
            direction = 'declining'
        else:
            direction = 'stable'
        
        return {
            'direction': direction,
            'slope': round(slope, 4),
            'r_squared': round(r_value ** 2, 4),
            'change_percent': round(change_percent, 2),
            'p_value': round(p_value, 4)
        }
    
    @staticmethod
    def calculate_volatility(ratings: List[float]) -> float:
        """Calculate rating volatility (standard deviation)"""
        if len(ratings) < 2:
            return 0.0
        
        return round(np.std(ratings), 2)
    
    @staticmethod
    def detect_outliers(data: List[float], threshold: float = 2.0) -> List[int]:
        """Detect outliers using z-score method"""
        if len(data) < 3:
            return []
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std == 0:
            return []
        
        z_scores = [(x - mean) / std for x in data]
        
        return [i for i, z in enumerate(z_scores) if abs(z) > threshold]


class LeaderboardFormatter:
    """Format leaderboard data for display"""
    
    @staticmethod
    def format_leaderboard_entry(
        rank: int,
        model: 'AIModel',
        metric: 'ModelMetric',
        previous_rank: Optional[int] = None
    ) -> Dict:
        """Format a single leaderboard entry"""
        entry = {
            'rank': rank,
            'model': {
                'id': str(model.id),
                'name': model.display_name,
                'provider': model.provider,
                'code': model.model_code
            },
            'metrics': {
                'elo_rating': metric.elo_rating,
                'win_rate': round((metric.wins / metric.total_comparisons * 100) 
                                 if metric.total_comparisons > 0 else 0, 2),
                'total_battles': metric.total_comparisons,
                'average_rating': metric.average_rating
            },
            'change_indicator': LeaderboardFormatter._get_change_indicator(rank, previous_rank)
        }
        
        return entry
    
    @staticmethod
    def _get_change_indicator(current_rank: int, previous_rank: Optional[int]) -> Dict:
        """Get change indicator for rank movement"""
        if previous_rank is None:
            return {
                'type': 'new',
                'value': 0,
                'symbol': '🆕'
            }
        
        change = previous_rank - current_rank
        
        if change > 0:
            return {
                'type': 'up',
                'value': change,
                'symbol': '↑'
            }
        elif change < 0:
            return {
                'type': 'down',
                'value': abs(change),
                'symbol': '↓'
            }
        else:
            return {
                'type': 'stable',
                'value': 0,
                'symbol': '→'
            }
    
    @staticmethod
    def format_comparison_result(
        model_a: Dict,
        model_b: Dict,
        category: str
    ) -> Dict:
        """Format model comparison result"""
        a_rating = model_a.get('elo_rating', 0)
        b_rating = model_b.get('elo_rating', 0)
        
        # Calculate win probability
        win_probability_a = 1 / (1 + 10 ** ((b_rating - a_rating) / 400))
        
        return {
            'category': category,
            'winner': 'model_a' if a_rating > b_rating else 'model_b' if b_rating > a_rating else 'tie',
            'rating_difference': abs(a_rating - b_rating),
            'win_probability': {
                'model_a': round(win_probability_a * 100, 2),
                'model_b': round((1 - win_probability_a) * 100, 2)
            }
        }


class MetricExporter:
    """Export metrics in various formats"""
    
    @staticmethod
    def export_to_csv(metrics: List['ModelMetric']) -> str:
        """Export metrics to CSV format"""
        
        output = io.StringIO()
        
        fieldnames = [
            'model_name', 'provider', 'category', 'period',
            'elo_rating', 'win_rate', 'total_comparisons',
            'wins', 'losses', 'ties', 'average_rating',
            'calculated_at'
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for metric in metrics:
            writer.writerow({
                'model_name': metric.model.display_name,
                'provider': metric.model.provider,
                'category': metric.category,
                'period': metric.period,
                'elo_rating': metric.elo_rating,
                'win_rate': round((metric.wins / metric.total_comparisons * 100) 
                                 if metric.total_comparisons > 0 else 0, 2),
                'total_comparisons': metric.total_comparisons,
                'wins': metric.wins,
                'losses': metric.losses,
                'ties': metric.ties,
                'average_rating': metric.average_rating,
                'calculated_at': metric.calculated_at.isoformat()
            })
        
        return output.getvalue()
    
    @staticmethod
    def export_leaderboard_json(leaderboard: List[Dict]) -> str:
        """Export leaderboard to JSON format"""
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_models': len(leaderboard),
            'entries': []
        }
        
        for entry in leaderboard:
            export_data['entries'].append({
                'rank': entry['rank'],
                'model': entry['model'].display_name,
                'provider': entry['model'].provider,
                'elo_rating': entry['metrics'].elo_rating,
                'win_rate': entry.get('win_rate', 0),
                'total_battles': entry['metrics'].total_comparisons,
                'average_rating': entry['metrics'].average_rating
            })
        
        return json.dumps(export_data, indent=2)