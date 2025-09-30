from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Feedback
from apps.ai_model.utils import EloRatingCalculator


@receiver(post_save, sender=Feedback)
def process_feedback_signal(sender, instance, created, **kwargs):
    """Process feedback after creation"""
    if not created:
        return
    
    # Update ELO ratings for preference feedback
    if instance.feedback_type == 'preference' and instance.session.mode == 'compare':
        if instance.preferred_model:
            # Determine result
            if instance.preferred_model == instance.session.model_a:
                result = 'a_wins'
            elif instance.preferred_model == instance.session.model_b:
                result = 'b_wins'
            else:
                result = 'tie'
            
            # Update ratings asynchronously
            from .tasks import update_model_metrics_from_feedback
            update_model_metrics_from_feedback.delay()