from rest_framework import permissions


class IsMessageOwner(permissions.BasePermission):
    """
    Permission to only allow owners of a message's session to access it
    """
    def has_object_permission(self, request, view, obj):
        # Check if user owns the session
        return obj.session.user == request.user


class CanAccessMessage(permissions.BasePermission):
    """
    Permission for accessing messages in shared sessions
    """
    def has_object_permission(self, request, view, obj):
        # Allow if session is public
        if obj.session.is_public:
            return True
        
        # Check if user owns the session
        return obj.session.user == request.user