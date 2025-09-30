from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.ai_model.models import AIModel
from apps.model_metrics.calculators import MetricsCalculator


class Command(BaseCommand):
    help = 'Calculate all metrics for all models'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--period',
            type=str,
            default='all_time',
            help='Period to calculate (daily, weekly, monthly, all_time)'
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Specific model ID to calculate'
        )
        parser.add_argument(
            '--category',
            type=str,
            default='overall',
            help='Category to calculate'
        )
    
    def handle(self, *args, **options):
        period = options['period']
        category = options['category']
        model_id = options.get('model')
        
        if model_id:
            try:
                models = [AIModel.objects.get(id=model_id)]
            except AIModel.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Model {model_id} not found'))
                return
        else:
            models = AIModel.objects.filter(is_active=True)
        
        self.stdout.write(f'Calculating {period} metrics for {models.count()} models...')
        
        success_count = 0
        error_count = 0
        
        for model in models:
            try:
                metric = MetricsCalculator.calculate_category_metrics(
                    model=model,
                    category=category,
                    period=period
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {model.display_name}: ELO {metric.elo_rating}, '
                        f'Win Rate {(metric.wins/metric.total_comparisons*100) if metric.total_comparisons > 0 else 0:.1f}%'
                    )
                )
                success_count += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ {model.display_name}: {str(e)}')
                )
                error_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted: {success_count} successful, {error_count} errors'
            )
        )