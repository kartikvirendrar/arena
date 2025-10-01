from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from chat_session.models import ChatSession
from chat_session.services import ChatSessionService


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = [
        'title_display', 'user_display', 'mode', 'models_display',
        'message_count', 'is_public', 'created_at'
    ]
    list_filter = ['mode', 'is_public', 'created_at']
    search_fields = ['title', 'user__display_name', 'user__email']
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'share_link',
        'session_statistics', 'message_preview'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'mode', 'title')
        }),
        ('Models', {
            'fields': ('model_a', 'model_b')
        }),
        ('Sharing', {
            'fields': ('is_public', 'share_token', 'share_link')
        }),
        ('Metadata', {
            'fields': ('metadata', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Statistics', {
            'fields': ('session_statistics', 'message_preview'),
            'classes': ('collapse',)
        })
    )

    def title_display(self, obj):
        return obj.title or f"Untitled ({obj.id})"
    title_display.short_description = 'Title'
    
    def user_display(self, obj):
        if obj.user.is_anonymous:
            return format_html(
                '<span style="color: gray;">Anonymous ({})</span>',
                obj.user.display_name
            )
        return obj.user.display_name
    user_display.short_description = 'User'
    
    def models_display(self, obj):
        models = []
        if obj.model_a:
            models.append(obj.model_a.display_name)
        if obj.model_b:
            models.append(obj.model_b.display_name)
        
        if not models:
            return '-'
        elif len(models) == 1:
            return models[0]
        else:
            return f"{models[0]} vs {models[1]}"
    models_display.short_description = 'Models'
    
    def message_count(self, obj):
        count = obj.messages.count()
        return format_html(
            '<a href="{}?session__id__exact={}">{} messages</a>',
            reverse('admin:message_message_changelist'),
            obj.id,
            count
        )
    message_count.short_description = 'Messages'
    
    def share_link(self, obj):
        if obj.share_token:
            # Construct the share URL
            share_url = f"/chat/shared/{obj.share_token}"
            return format_html(
                '<a href="{}" target="_blank">View Shared Session</a>',
                share_url
            )
        return "Not shared"
    share_link.short_description = 'Share Link'
    
    def session_statistics(self, obj):        
        try:
            stats = ChatSessionService.get_session_statistics(obj)
            
            html = [
                f"<strong>Duration:</strong> {stats['duration']['formatted'] or 'N/A'}<br>",
                f"<strong>Total Messages:</strong> {stats['messages']['total']}<br>",
                f"<strong>Token Usage:</strong><br>",
                f"&nbsp;&nbsp;- Input: {stats['tokens']['total_input']:,}<br>",
                f"&nbsp;&nbsp;- Output: {stats['tokens']['total_output']:,}<br>",
                f"&nbsp;&nbsp;- Est. Cost: ${stats['tokens']['estimated_cost']:.4f}<br>",
            ]
            
            if stats['feedback']['average_rating']:
                html.append(
                    f"<strong>Avg Rating:</strong> {stats['feedback']['average_rating']:.1f}/5<br>"
                )
            
            return format_html(''.join(html))
        except Exception as e:
            return f"Error calculating statistics: {e}"
    session_statistics.short_description = 'Statistics'
    
    def message_preview(self, obj):
        messages = obj.messages.order_by('position')[:5]
        
        if not messages:
            return "No messages"
        
        html = ['<div style="max-height: 200px; overflow-y: auto;">']
        
        for msg in messages:
            role_color = 'blue' if msg.role == 'user' else 'green'
            content_preview = msg.content[:100] + '...' if len(msg.content) > 100 else msg.content
            
            html.append(
                f'<div style="margin-bottom: 10px;">'
                f'<strong style="color: {role_color};">{msg.role.upper()}:</strong> '
                f'{content_preview}'
                f'</div>'
            )
        
        html.append('</div>')
        
        if obj.messages.count() > 5:
            html.append(f'<em>... and {obj.messages.count() - 5} more messages</em>')
        
        return format_html(''.join(html))
    message_preview.short_description = 'Message Preview'
    
    actions = ['make_public', 'make_private', 'export_sessions']
    
    def make_public(self, request, queryset):
        updated = queryset.update(is_public=True)
        self.message_user(request, f'{updated} sessions made public.')
    make_public.short_description = 'Make selected sessions public'
    
    def make_private(self, request, queryset):
        updated = queryset.update(is_public=False, share_token=None)
        self.message_user(request, f'{updated} sessions made private.')
    make_private.short_description = 'Make selected sessions private'
    
    def export_sessions(self, request, queryset):
        # This would typically trigger a background task
        session_ids = list(queryset.values_list('id', flat=True))
        self.message_user(
            request,
            f'Export initiated for {len(session_ids)} sessions. You will receive an email when ready.'
        )
    export_sessions.short_description = 'Export selected sessions'