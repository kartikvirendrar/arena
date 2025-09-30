# apps/ai_model/admin.py

from django.contrib import admin
from django.utils.html import format_html
from .models import AIModel, ModelMetric


@admin.register(AIModel)
class AIModelAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'provider', 'model_code', 
        'is_active', 'supports_streaming', 'capabilities_display',
        'created_at'
    ]
    list_filter = ['provider', 'is_active', 'supports_streaming', 'created_at']
    search_fields = ['display_name', 'model_name', 'model_code', 'description']
    readonly_fields = ['id', 'created_at', 'usage_stats']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'provider', 'model_name', 'model_code', 'display_name')
        }),
        ('Description', {
            'fields': ('description',)
        }),
        ('Configuration', {
            'fields': ('capabilities', 'max_tokens', 'supports_streaming', 'config')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at')
        }),
        ('Statistics', {
            'fields': ('usage_stats',),
            'classes': ('collapse',)
        })
    )
    
    def capabilities_display(self, obj):
        """Display capabilities as badges"""
        if not obj.capabilities:
            return '-'
        
        colors = {
            'text': 'blue',
            'code': 'green',
            'vision': 'purple',
            'creative': 'orange',
            'reasoning': 'red'
        }
        
        badges = []
        for cap in obj.capabilities:
            color = colors.get(cap, 'gray')
            badges.append(
                f'<span style="background-color: {color}; color: white; '
                f'padding: 2px 6px; border-radius: 3px; margin-right: 4px;">'
                f'{cap}</span>'
            )
        
        return format_html(''.join(badges))
    
    capabilities_display.short_description = 'Capabilities'
    
    def usage_stats(self, obj):
        """Display usage statistics"""
        from apps.chat.models import Message
        
        total_messages = Message.objects.filter(model=obj).count()
        latest_metric = obj.metrics.filter(
            category='overall',
            period='all_time'
        ).order_by('-calculated_at').first()
        
        stats = [
            f"<strong>Total Messages:</strong> {total_messages}",
        ]
        
        if latest_metric:
            stats.extend([
                f"<strong>ELO Rating:</strong> {latest_metric.elo_rating}",
                f"<strong>Win Rate:</strong> {latest_metric.win_rate:.1f}%",
                f"<strong>Total Comparisons:</strong> {latest_metric.total_comparisons}"
            ])
        
        return format_html('<br>'.join(stats))
    
    usage_stats.short_description = 'Usage Statistics'
    
    actions = ['activate_models', 'deactivate_models', 'test_model_connection']
    
    def activate_models(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} models activated.')
    
    activate_models.short_description = 'Activate selected models'
    
    def deactivate_models(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} models deactivated.')
    
    deactivate_models.short_description = 'Deactivate selected models'
    
    def test_model_connection(self, request, queryset):
        from .services import AIModelService
        import asyncio
        
        service = AIModelService()
        results = []
        
        for model in queryset:
            try:
                validation = service.validate_model_configuration(model)
                if validation['is_valid']:
                    results.append(f"✓ {model.display_name}: Valid")
                else:
                    results.append(f"✗ {model.display_name}: Invalid")
            except Exception as e:
                results.append(f"✗ {model.display_name}: Error - {str(e)}")
        
        self.message_user(
            request, 
            format_html('<br>'.join(results)),
            level='INFO'
        )
    
    test_model_connection.short_description = 'Test model connection'


@admin.register(ModelMetric)
class ModelMetricAdmin(admin.ModelAdmin):
    list_display = [
        'model_display', 'category', 'period', 
        'elo_rating', 'win_rate_display', 'total_comparisons',
        'calculated_at'
    ]
    list_filter = ['category', 'period', 'calculated_at']
    search_fields = ['model__display_name', 'model__model_code']
    readonly_fields = [
        'id', 'model', 'category', 'period',
        'total_comparisons', 'wins', 'losses', 'ties',
        'average_rating', 'elo_rating', 'calculated_at'
    ]
    
    def model_display(self, obj):
        return f"{obj.model.display_name} ({obj.model.provider})"
    
    model_display.short_description = 'Model'
    model_display.admin_order_field = 'model__display_name'
    
    def win_rate_display(self, obj):
        if obj.total_comparisons == 0:
            return '-'
        win_rate = (obj.wins / obj.total_comparisons) * 100
        
        # Color code based on win rate
        if win_rate >= 60:
            color = 'green'
        elif win_rate >= 40:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color,
            win_rate
        )
    
    win_rate_display.short_description = 'Win Rate'
    
    def has_add_permission(self, request):
        # Metrics are calculated automatically
        return False
    
    def has_change_permission(self, request, obj=None):
        # Metrics should not be edited manually
        return False