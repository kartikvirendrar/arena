from rest_framework import serializers
from django.db import transaction
from .models import Feedback
from apps.ai_model.models import AIModel
from apps.chat_session.models import ChatSession
from apps.message.models import Message
from apps.ai_model.serializers import AIModelListSerializer


class FeedbackSerializer(serializers.ModelSerializer):
    """Full feedback serializer"""
    preferred_model = AIModelListSerializer(read_only=True)
    session_info = serializers.SerializerMethodField()
    message_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Feedback
        fields = [
            'id', 'user', 'session', 'message', 'feedback_type',
            'preferred_model', 'rating', 'categories', 'comment',
            'created_at', 'session_info', 'message_info'
        ]
        read_only_fields = ['id', 'user', 'created_at']
    
    def get_session_info(self, obj):
        return {
            'id': str(obj.session.id),
            'mode': obj.session.mode,
            'title': obj.session.title
        }
    
    def get_message_info(self, obj):
        if obj.message:
            return {
                'id': str(obj.message.id),
                'role': obj.message.role,
                'content_preview': obj.message.content[:100]
            }
        return None


class FeedbackCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating feedback"""
    session_id = serializers.UUIDField(required=True)
    message_id = serializers.UUIDField(required=False, allow_null=True)
    preferred_model_id = serializers.UUIDField(required=False, allow_null=True)
    
    class Meta:
        model = Feedback
        fields = [
            'session_id', 'message_id', 'feedback_type',
            'preferred_model_id', 'rating', 'categories', 'comment'
        ]
    
    def validate_rating(self, value):
        if value is not None and self.initial_data.get('feedback_type') != 'rating':
            raise serializers.ValidationError(
                "Rating is only valid for 'rating' feedback type"
            )
        return value
    
    def validate_preferred_model_id(self, value):
        if value is not None and self.initial_data.get('feedback_type') != 'preference':
            raise serializers.ValidationError(
                "Preferred model is only valid for 'preference' feedback type"
            )
        if value:
            try:
                AIModel.objects.get(id=value)
            except AIModel.DoesNotExist:
                raise serializers.ValidationError("Model not found")
        return value
    
    def validate_categories(self, value):
        """Validate feedback categories"""
        valid_categories = [
            'accuracy', 'helpfulness', 'creativity', 'speed',
            'relevance', 'completeness', 'clarity', 'conciseness',
            'technical_accuracy', 'tone', 'formatting'
        ]
        
        if value:
            invalid_categories = set(value) - set(valid_categories)
            if invalid_categories:
                raise serializers.ValidationError(
                    f"Invalid categories: {invalid_categories}"
                )
        return value
    
    def validate(self, attrs):
        feedback_type = attrs.get('feedback_type')
        
        # Validate session exists and user has access
        try:
            session = ChatSession.objects.get(id=attrs['session_id'])
        except ChatSession.DoesNotExist:
            raise serializers.ValidationError("Session not found")
        
        # Check if user has access to the session
        user = self.context['request'].user
        if session.user != user and not session.is_public:
            raise serializers.ValidationError("You don't have access to this session")
        
        # Validate message if provided
        if attrs.get('message_id'):
            try:
                message = Message.objects.get(
                    id=attrs['message_id'],
                    session=session
                )
                attrs['message'] = message
            except Message.DoesNotExist:
                raise serializers.ValidationError("Message not found in session")
        
        # Type-specific validations
        if feedback_type == 'preference':
            if session.mode != 'compare':
                raise serializers.ValidationError(
                    "Preference feedback is only valid for compare mode sessions"
                )
            if not attrs.get('preferred_model_id'):
                raise serializers.ValidationError(
                    "Preferred model is required for preference feedback"
                )
            
            # Validate preferred model is one of the session models
            preferred_model_id = attrs['preferred_model_id']
            if preferred_model_id not in [session.model_a_id, session.model_b_id]:
                raise serializers.ValidationError(
                    "Preferred model must be one of the session models"
                )
                
        elif feedback_type == 'rating':
            if not attrs.get('rating'):
                raise serializers.ValidationError(
                    "Rating is required for rating feedback"
                )
                
        attrs['session'] = session
        return attrs
    
    def create(self, validated_data):
        # Remove the ID fields
        validated_data.pop('session_id', None)
        validated_data.pop('message_id', None)
        preferred_model_id = validated_data.pop('preferred_model_id', None)
        
        # Set user from request
        validated_data['user'] = self.context['request'].user
        
        # Set preferred model
        if preferred_model_id:
            validated_data['preferred_model_id'] = preferred_model_id
        
        # Create feedback
        feedback = super().create(validated_data)
        
        # Trigger analytics update
        from .services import FeedbackAnalyticsService
        FeedbackAnalyticsService.process_new_feedback(feedback)
        
        return feedback


class BulkFeedbackSerializer(serializers.Serializer):
    """Serializer for bulk feedback submission"""
    feedbacks = serializers.ListField(
        child=FeedbackCreateSerializer(),
        min_length=1,
        max_length=50
    )
    
    def create(self, validated_data):
        feedbacks_data = validated_data['feedbacks']
        created_feedbacks = []
        
        with transaction.atomic():
            for feedback_data in feedbacks_data:
                feedback_data['user'] = self.context['request'].user
                feedback = Feedback.objects.create(**feedback_data)
                created_feedbacks.append(feedback)
        
        # Process analytics for all feedbacks
        from .services import FeedbackAnalyticsService
        for feedback in created_feedbacks:
            FeedbackAnalyticsService.process_new_feedback(feedback)
        
        return created_feedbacks


class SessionFeedbackSummarySerializer(serializers.Serializer):
    """Serializer for session feedback summary"""
    session_id = serializers.UUIDField()
    total_feedback_count = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    rating_distribution = serializers.DictField()
    preferences = serializers.DictField()
    categories_mentioned = serializers.DictField()
    recent_comments = serializers.ListField()


class ModelFeedbackStatsSerializer(serializers.Serializer):
    """Serializer for model feedback statistics"""
    model = AIModelListSerializer()
    total_ratings = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    total_preferences = serializers.IntegerField()
    win_count = serializers.IntegerField()
    loss_count = serializers.IntegerField()
    win_rate = serializers.FloatField()
    categories_performance = serializers.DictField()