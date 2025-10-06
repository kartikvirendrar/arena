from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, Http404
from django.db.models import Count, Prefetch, Q

from chat_session.models import ChatSession
from chat_session.serializers import (
    ChatSessionSerializer, ChatSessionCreateSerializer,
    ChatSessionListSerializer, ChatSessionShareSerializer,
    ChatSessionDuplicateSerializer, ChatSessionExportSerializer
)
from chat_session.services import ChatSessionService
from chat_session.permissions import IsSessionOwner, CanAccessSharedSession
from user.authentication import FirebaseAuthentication, AnonymousTokenAuthentication


class ChatSessionViewSet(viewsets.ModelViewSet):
    """ViewSet for chat session management"""
    authentication_classes = [FirebaseAuthentication, AnonymousTokenAuthentication]
    permission_classes = [IsAuthenticated, IsSessionOwner]
    
    def get_queryset(self):
        user = self.request.user
        queryset = ChatSession.objects.select_related('model_a', 'model_b', 'user')
        
        # Filter based on action
        if self.action == 'shared':
            # For shared endpoint, return public sessions
            queryset = queryset.filter(is_public=True)
        else:
            # For other actions, return user's sessions
            queryset = queryset.filter(user=user)
        
        # Add message count annotation for list view
        if self.action == 'list':
            queryset = queryset.annotate(
                _message_count=Count('messages')
            )
        
        # Apply filters
        mode = self.request.query_params.get('mode')
        if mode:
            queryset = queryset.filter(mode=mode)
        
        # Search in title
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(title__icontains=search)
        
        # Date filters
        created_after = self.request.query_params.get('created_after')
        if created_after:
            queryset = queryset.filter(created_at__gte=created_after)
        
        created_before = self.request.query_params.get('created_before')
        if created_before:
            queryset = queryset.filter(created_at__lte=created_before)
        
        # Model filter
        model_id = self.request.query_params.get('model_id')
        if model_id:
            queryset = queryset.filter(
                Q(model_a_id=model_id) | Q(model_b_id=model_id)
            )
        
        return queryset.order_by('-updated_at')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ChatSessionCreateSerializer
        elif self.action == 'list':
            return ChatSessionListSerializer
        elif self.action in ['share', 'unshare']:
            return ChatSessionShareSerializer
        elif self.action == 'duplicate':
            return ChatSessionDuplicateSerializer
        elif self.action == 'export':
            return ChatSessionExportSerializer
        return ChatSessionSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Handle random mode
        if serializer.validated_data['mode'] == 'random':
            session = ChatSessionService.create_session_with_random_models(
                user=request.user,
                metadata=serializer.validated_data.get('metadata')
            )
        else:
            session = serializer.save()
        
        # Return full serializer data
        return Response(
            ChatSessionSerializer(session, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Share a session publicly"""
        session = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        serializer.update(session, serializer.validated_data)
        
        return Response({
            'share_token': session.share_token,
            'share_url': ChatSessionSerializer(
                session, 
                context={'request': request}
            ).data['share_url']
        })
    
    @action(detail=True, methods=['post'])
    def unshare(self, request, pk=None):
        """Unshare a session"""
        session = self.get_object()
        session.is_public = False
        session.share_token = None
        session.save()
        
        return Response({'status': 'unshared'})
    
    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Duplicate a session"""
        session = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        new_session = ChatSessionService.duplicate_session(
            session=session,
            user=request.user,
            include_messages=serializer.validated_data.get('include_messages', False),
            new_title=serializer.validated_data.get('new_title')
        )
        
        return Response(
            ChatSessionSerializer(new_session, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def export(self, request, pk=None):
        """Export session data"""
        session = self.get_object()
        serializer = self.get_serializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        content, content_type = ChatSessionService.export_session(
            session=session,
            **serializer.validated_data
        )
        
        # Determine filename
        format = serializer.validated_data['format']
        filename = f"chat_session_{session.id}.{format}"
        
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, pk=None):
        """Get session statistics"""
        session = self.get_object()
        stats = ChatSessionService.get_session_statistics(session)
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def shared(self, request):
        """Get public shared sessions"""
        queryset = self.filter_queryset(self.get_queryset())
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Get trending sessions"""
        limit = int(request.query_params.get('limit', 10))
        trending_sessions = ChatSessionService.get_trending_sessions(limit=limit)
        
        serializer = ChatSessionSerializer(
            trending_sessions, 
            many=True,
            context={'request': request}
        )
        
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def transfer_ownership(self, request, pk=None):
        """Transfer session ownership to authenticated user"""
        session = self.get_object()
        
        # Only allow transfer from anonymous to authenticated users
        if not session.user.is_anonymous:
            return Response(
                {'error': 'Can only transfer sessions from anonymous users'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if request.user.is_anonymous:
            return Response(
                {'error': 'Cannot transfer to anonymous user'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Transfer ownership
        old_user = session.user
        session.user = request.user
        session.expires_at = None  # Remove expiration
        session.metadata['transferred_from'] = str(old_user.id)
        session.metadata['transferred_at'] = timezone.now().isoformat()
        session.save()
        
        return Response({
            'status': 'transferred',
            'session_id': str(session.id)
        })


class SharedChatSessionView(viewsets.ReadOnlyModelViewSet):
    """View for accessing shared sessions via share token"""
    authentication_classes = []  # No authentication required
    permission_classes = [CanAccessSharedSession]
    serializer_class = ChatSessionSerializer
    lookup_field = 'share_token'
    
    def get_queryset(self):
        return ChatSession.objects.filter(
            is_public=True,
            share_token__isnull=False
        ).select_related('model_a', 'model_b', 'user')
    
    def get_object(self):
        share_token = self.kwargs.get('share_token')
        
        # Try to get by share token
        try:
            return ChatSession.objects.get(share_token=share_token)
        except ChatSession.DoesNotExist:
            raise Http404("Session not found")