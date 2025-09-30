from django.contrib import admin
from user.models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        'display_name', 'email', 'auth_provider', 
        'is_anonymous', 'is_active', 'created_at'
    ]
    list_filter = ['auth_provider', 'is_anonymous', 'is_active', 'created_at']
    search_fields = ['email', 'display_name', 'firebase_uid']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'display_name', 'email', 'auth_provider')
        }),
        ('Authentication', {
            'fields': ('firebase_uid', 'is_anonymous', 'anonymous_expires_at')
        }),
        ('Status', {
            'fields': ('is_active', 'created_at', 'updated_at')
        }),
        ('Preferences', {
            'fields': ('preferences',),
            'classes': ('collapse',)
        })
    )