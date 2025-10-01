from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
import json
from model_metrics.models import ModelMetric
from django.http import HttpResponse
from model_metrics.utils import MetricExporter
from model_metrics.calculators import MetricsCalculator

@admin.register(ModelMetric)
class ModelMetricAdmin(admin.ModelAdmin):
    list_display = [
        'model_name', 'category', 'period', 'elo_rating_display',
        'win_rate_display', 'total_comparisons', 'average_rating_display',
        'calculated_at'
    ]
    list_filter = ['category', 'period', 'calculated_at']
    search_fields = ['model__display_name', 'model__model_code']
    readonly_fields = [
        'id', 'model_link', 'category', 'period',
        'detailed_stats', 'performance_chart', 'metadata_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'model_link', 'category', 'period')
        }),
        ('Metrics', {
            'fields': ('elo_rating', 'total_comparisons', 'wins', 'losses', 'ties', 'average_rating')
        }),
        ('Analysis', {
            'fields': ('detailed_stats', 'performance_chart'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('metadata_display', 'calculated_at'),
            'classes': ('collapse',)
        })
    )
    
    def model_name(self, obj):
        return f"{obj.model.display_name} ({obj.model.provider})"
    model_name.short_description = 'Model'
    model_name.admin_order_field = 'model__display_name'
    
    def model_link(self, obj):
        url = reverse('admin:ai_model_aimodel_change', args=[obj.model.id])
        return format_html('<a href="{}">{}</a>', url, obj.model.display_name)
    model_link.short_description = 'Model'
    
    def elo_rating_display(self, obj):
        # Color code based on rating
        if obj.elo_rating >= 1700:
            color = 'green'
        elif obj.elo_rating >= 1500:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.elo_rating
        )
    elo_rating_display.short_description = 'ELO Rating'
    elo_rating_display.admin_order_field = 'elo_rating'
    
    def win_rate_display(self, obj):
        if obj.total_comparisons == 0:
            return '-'
        
        win_rate = (obj.wins / obj.total_comparisons) * 100
        
        # Color code
        if win_rate >= 60:
            color = 'green'
        elif win_rate >= 40:
            color = 'orange'
        else:
            color = 'red'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, win_rate
        )
    win_rate_display.short_description = 'Win Rate'
    
    def average_rating_display(self, obj):
        if not obj.average_rating:
            return '-'
        
        stars = '★' * int(obj.average_rating) + '☆' * (5 - int(obj.average_rating))
        
        return format_html(
            '{} <span style="color: gray;">({:.2f})</span>',
            stars, obj.average_rating
        )
    average_rating_display.short_description = 'Avg Rating'
    
    def detailed_stats(self, obj):
        """Display detailed statistics"""
        stats = []
        
        # apps/model_metrics/admin.py (continued)

    def detailed_stats(self, obj):
        """Display detailed statistics"""
        stats = []
        
        if obj.total_comparisons > 0:
            win_pct = (obj.wins / obj.total_comparisons) * 100
            loss_pct = (obj.losses / obj.total_comparisons) * 100
            tie_pct = (obj.ties / obj.total_comparisons) * 100
            
            stats.append('<h4>Battle Results</h4>')
            stats.append(f'<div style="margin-bottom: 10px;">')
            stats.append(f'<div style="background: #4CAF50; width: {win_pct}%; height: 20px; float: left; color: white; text-align: center;">{obj.wins}</div>')
            stats.append(f'<div style="background: #f44336; width: {loss_pct}%; height: 20px; float: left; color: white; text-align: center;">{obj.losses}</div>')
            stats.append(f'<div style="background: #FF9800; width: {tie_pct}%; height: 20px; float: left; color: white; text-align: center;">{obj.ties}</div>')
            stats.append(f'</div>')
            stats.append(f'<div style="clear: both; margin-top: 25px;">')
            stats.append(f'Wins: {obj.wins} ({win_pct:.1f}%) | Losses: {obj.losses} ({loss_pct:.1f}%) | Ties: {obj.ties} ({tie_pct:.1f}%)')
            stats.append(f'</div>')
        
        # Rank information
        percentile = MetricsCalculator.calculate_percentile_rank(
            obj.model, obj.category, 'elo_rating'
        )
        stats.append(f'<h4>Ranking</h4>')
        stats.append(f'<p>Percentile: {percentile:.1f}% (better than {percentile:.1f}% of models)</p>')
        
        # Recent trend
        recent_metrics = ModelMetric.objects.filter(
            model=obj.model,
            category=obj.category,
            period=obj.period
        ).order_by('-calculated_at')[:5]
        
        if len(recent_metrics) > 1:
            trend = recent_metrics[0].elo_rating - recent_metrics[-1].elo_rating
            trend_symbol = '↑' if trend > 0 else '↓' if trend < 0 else '→'
            stats.append(f'<h4>Recent Trend</h4>')
            stats.append(f'<p>ELO Change: {trend_symbol} {abs(trend)} points</p>')
        
        return format_html(''.join(stats))
    detailed_stats.short_description = 'Detailed Statistics'
    
    def performance_chart(self, obj):
        """Display a simple performance chart"""
        # Get historical data
        historical = ModelMetric.objects.filter(
            model=obj.model,
            category=obj.category,
            period='daily'
        ).order_by('-calculated_at')[:30]
        
        if not historical:
            return "No historical data available"
        
        # Create simple ASCII chart
        max_elo = max(h.elo_rating for h in historical)
        min_elo = min(h.elo_rating for h in historical)
        range_elo = max_elo - min_elo if max_elo != min_elo else 1
        
        chart_html = ['<pre style="font-family: monospace; background: #f5f5f5; padding: 10px;">']
        chart_html.append('ELO Rating Trend (Last 30 days)\n')
        chart_html.append(f'{max_elo} |')
        
        # Create chart
        chart_height = 10
        for i in range(chart_height):
            line = f'{" " * 6}|'
            for h in reversed(historical):
                normalized = (h.elo_rating - min_elo) / range_elo
                if normalized >= (chart_height - i - 1) / chart_height:
                    line += '█'
                else:
                    line += ' '
            chart_html.append(line)
        
        chart_html.append(f'{min_elo} |{"_" * len(historical)}')
        chart_html.append(f'{" " * 6} {historical[-1].calculated_at.strftime("%m/%d")} {"" * (len(historical) - 10)} {historical[0].calculated_at.strftime("%m/%d")}')
        chart_html.append('</pre>')
        
        return format_html('\n'.join(chart_html))
    performance_chart.short_description = 'Performance Chart'
    
    def metadata_display(self, obj):
        """Display metadata in formatted way"""
        if not hasattr(obj, 'metadata') or not obj.metadata:
            return "No metadata"
        
        return format_html(
            '<pre style="background: #f5f5f5; padding: 10px;">{}</pre>',
            json.dumps(obj.metadata, indent=2)
        )
    metadata_display.short_description = 'Metadata'
    
    actions = ['recalculate_metrics', 'export_metrics', 'compare_selected']
    
    def recalculate_metrics(self, request, queryset):
        """Recalculate metrics for selected entries"""
        
        updated = 0
        for metric in queryset:
            new_metric = MetricsCalculator.calculate_category_metrics(
                model=metric.model,
                category=metric.category,
                period=metric.period
            )
            updated += 1
        
        self.message_user(request, f'Recalculated {updated} metrics')
    recalculate_metrics.short_description = 'Recalculate selected metrics'
    
    def export_metrics(self, request, queryset):
        """Export selected metrics to CSV"""
        
        csv_content = MetricExporter.export_to_csv(list(queryset))
        
        response = HttpResponse(csv_content, content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="model_metrics.csv"'
        
        return response
    export_metrics.short_description = 'Export selected metrics to CSV'
    
    def compare_selected(self, request, queryset):
        """Compare selected models"""
        if queryset.count() != 2:
            self.message_user(
                request,
                'Please select exactly 2 metrics to compare',
                level='ERROR'
            )
            return
        
        metrics = list(queryset)
        
        comparison = f"""
        Model Comparison:
        
        {metrics[0].model.display_name}:
        - ELO: {metrics[0].elo_rating}
        - Win Rate: {(metrics[0].wins / metrics[0].total_comparisons * 100) if metrics[0].total_comparisons > 0 else 0:.1f}%
        - Avg Rating: {metrics[0].average_rating or 'N/A'}
        
        {metrics[1].model.display_name}:
        - ELO: {metrics[1].elo_rating}
        - Win Rate: {(metrics[1].wins / metrics[1].total_comparisons * 100) if metrics[1].total_comparisons > 0 else 0:.1f}%
        - Avg Rating: {metrics[1].average_rating or 'N/A'}
        
        Difference:
        - ELO: {abs(metrics[0].elo_rating - metrics[1].elo_rating)} points
        - Winner: {metrics[0].model.display_name if metrics[0].elo_rating > metrics[1].elo_rating else metrics[1].model.display_name}
        """
        
        self.message_user(request, comparison)
    compare_selected.short_description = 'Compare selected models'
    
    def has_add_permission(self, request):
        # Metrics are calculated automatically
        return False
    
    def has_change_permission(self, request, obj=None):
        # Metrics should not be edited manually
        return False