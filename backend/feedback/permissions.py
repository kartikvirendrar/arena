from rest_framework import permissions


class IsFeedbackOwner(permissions.BasePermission):
    """
    Permission to only allow owners of feedback to edit it
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions for feedback on public sessions
        if request.method in permissions.SAFE_METHODS and obj.session.is_public:
            return True
        
        # Write permissions only for feedback owner
        return obj.user == request.user


class CanProvideFeedback(permissions.BasePermission):
    """
    Permission to check if user can provide feedback on a session
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        session_id = request.data.get('session_id')
        if not session_id:
            return True  # Will be validated in serializer
        
        try:
            from apps.chat_session.models import ChatSession
            session = ChatSession.objects.get(id=session_id)
            return session.user == request.user or session.is_public
        except ChatSession.DoesNotExist:
            return False