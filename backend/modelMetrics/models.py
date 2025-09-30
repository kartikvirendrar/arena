from django.db import models
from django.utils import timezone
from aiModel.models import AIModel
import uuid

class ModelMetric(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('all_time', 'All Time')
    ]
    
    CATEGORY_CHOICES = [
        ('overall', 'Overall'),
        ('text', 'Text Generation'),
        ('code', 'Code Generation'),
        ('creative', 'Creative Writing'),
        ('reasoning', 'Reasoning'),
        ('translation', 'Translation'),
        ('summarization', 'Summarization'),
        ('conversation', 'Conversation'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model = models.ForeignKey(AIModel, on_delete=models.CASCADE, related_name='metrics')
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)
    total_comparisons = models.IntegerField(default=0)
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    ties = models.IntegerField(default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    elo_rating = models.IntegerField(default=1500)
    period = models.CharField(max_length=50, choices=PERIOD_CHOICES)
    calculated_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'model_metrics'
        unique_together = ['model', 'category', 'period', 'calculated_at']
        indexes = [
            models.Index(fields=['model', 'category', '-calculated_at']),
            models.Index(fields=['category', 'elo_rating']),
            models.Index(fields=['period', 'calculated_at']),
        ]
        ordering = ['-calculated_at']
    
    @property
    def win_rate(self):
        if self.total_comparisons == 0:
            return 0
        return (self.wins / self.total_comparisons) * 100
    
    def __str__(self):
        return f"{self.model.display_name} - {self.category} ({self.period})"