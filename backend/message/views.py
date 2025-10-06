from ai_model.llm_interactions import get_model_output
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import asyncio
from message.models import Message
from message.serializers import (
    MessageSerializer, MessageCreateSerializer, MessageStreamSerializer,
    MessageTreeSerializer, MessageBranchSerializer, MessageRegenerateSerializer
)
from message.services import MessageService, MessageComparisonService
from message.streaming import StreamingManager
from message.permissions import IsMessageOwner
from chat_session.models import ChatSession
from user.authentication import FirebaseAuthentication, AnonymousTokenAuthentication
from django.db import transaction
from django.http import StreamingHttpResponse
import threading
import queue

class MessageViewSet(viewsets.ModelViewSet):
    """ViewSet for message management"""
    authentication_classes = [FirebaseAuthentication, AnonymousTokenAuthentication]
    permission_classes = [IsAuthenticated, IsMessageOwner]
    queryset = Message.objects.select_related('model', 'session')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return MessageCreateSerializer
        elif self.action == 'stream':
            return MessageStreamSerializer
        elif self.action == 'tree':
            return MessageTreeSerializer
        elif self.action == 'branch':
            return MessageBranchSerializer
        elif self.action == 'regenerate':
            return MessageRegenerateSerializer
        return MessageSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by session
        session_id = self.request.query_params.get('session_id')
        if session_id:
            queryset = queryset.filter(session_id=session_id)
        
        # Filter by role
        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.order_by('session', 'position')
    
    def create(self, request, *args, **kwargs):
        """Create a new message"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Verify user owns the session
        session = serializer.validated_data['session']
        if session.user != request.user:
            return Response(
                {'error': 'You do not own this session'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        message = serializer.save()
        
        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'])
    def stream(self, request):
        """Stream a message response"""
        serializer = MessageStreamSerializer(data=request.data.get('messages'), many=True)
        serializer.is_valid(raise_exception=True)
        
        # Get session from last message or session_id
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session = get_object_or_404(ChatSession, id=session_id, user=request.user)

        for message in serializer.validated_data:
            if message['role'] == 'user':
                user_message = message
            elif message['role'] == 'assistant':
                if session.mode == 'direct':
                    assistant_message = message
                else:
                    if message['participant'] == 'a':
                        assistant_message_a = message
                    else:
                        assistant_message_b = message

        # Create user message
        with transaction.atomic():
            user_message = MessageService.create_message(
                session=session,
                message_obj=user_message
            )
            if session.mode == 'direct':
                assistant_message = MessageService.create_message(
                    session=session,
                    message_obj=assistant_message
                )
            else:
                assistant_message_a = MessageService.create_message(
                    session=session,
                    message_obj=assistant_message_a
                )
                assistant_message_b = MessageService.create_message(
                    session=session,
                    message_obj=assistant_message_b
                )
        
        # # Stream response(s)
        # if session.mode == 'compare':
        #     generator = MessageComparisonService.stream_dual_responses(
        #         session=session,
        #         user_message=user_message,
        #         temperature=serializer.validated_data['temperature'],
        #         max_tokens=serializer.validated_data['max_tokens']
        #     )
        # else:
        #     generator = MessageService.stream_assistant_message(
        #         session=session,
        #         user_message=user_message,
        #         assistant_message=assistant_message,
        #     )
            
        # return StreamingManager.create_streaming_response(generator)
        
        history = MessageService._get_conversation_history(session)
        history.pop()

        def generate():
            if session.mode == 'direct':
                try:
                    full_content = ""
                    for chunk in get_model_output(
                        system_prompt="We will be rendering your response on a frontend. so please add spaces or indentation or nextline chars or bullet or numberings etc. suitably for code or the text. wherever required, and do not add any comments about this instruction in your response.",
                        user_prompt=user_message.content,
                        history=history,
                        model="google/gemma-3-12b-it",
                    ):
                        if chunk:
                            full_content += chunk
                            escaped_chunk = chunk.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '')
                            yield f'a0:"{escaped_chunk}"\n'
                    
                    assistant_message.content = full_content
                    assistant_message.status = 'success'
                    assistant_message.save()
                    
                    yield 'ad:{"finishReason":"stop"}\n'
                except Exception as e:
                    assistant_message.status = 'error'
                    assistant_message.save()
                    yield f'ad:{{"finishReason":"error","error":"{str(e)}"}}\n'
            else:
                chunk_queue = queue.Queue()
        
                def stream_model_a():
                    full_content_a = ""
                    try:
                        for chunk in get_model_output(
                            system_prompt="We will be rendering your response on a frontend. so please add spaces or indentation or nextline chars or bullet or numberings etc. suitably for code or the text. wherever required, and do not add any comments about this instruction in your response.",
                            user_prompt=user_message.content,
                            history=history,
                            model="google/gemma-3-12b-it"
                        ):
                            if chunk:
                                full_content_a += chunk
                                escaped_chunk = chunk.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '')
                                chunk_queue.put(('a', f'a0:"{escaped_chunk}"\n'))
                        
                        assistant_message_a.content = full_content_a
                        assistant_message_a.status = 'success'
                        assistant_message_a.save()
                        
                        chunk_queue.put(('a', 'ad:{"finishReason":"stop"}\n'))
                        
                    except Exception as e:
                        assistant_message_a.status = 'error'
                        assistant_message_a.save()
                        chunk_queue.put(('a', f'ad:{{"finishReason":"error","error":"{str(e)}"}}\n'))
                    finally:
                        chunk_queue.put(('a', None))

                def stream_model_b():
                    full_content_b = ""
                    try:
                        for chunk in get_model_output(
                            system_prompt="We will be rendering your response on a frontend. so please add spaces or indentation or nextline chars or bullet or numberings etc. suitably for code or the text. wherever required, and do not add any comments about this instruction in your response.",
                            user_prompt=user_message.content,
                            history=history,
                            model="Qwen/Qwen3-30B-A3B"
                        ):
                            if chunk:
                                full_content_b += chunk
                                escaped_chunk = chunk.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '')
                                chunk_queue.put(('b', f'b0:"{escaped_chunk}"\n'))
                        
                        assistant_message_b.content = full_content_b
                        assistant_message_b.status = 'success'
                        assistant_message_b.save()
                        
                        chunk_queue.put(('b', 'bd:{"finishReason":"stop"}\n'))
                        
                    except Exception as e:
                        assistant_message_b.status = 'error'
                        assistant_message_b.save()
                        chunk_queue.put(('b', f'bd:{{"finishReason":"error","error":"{str(e)}"}}\n'))
                    finally:
                        chunk_queue.put(('b', None))

                thread_a = threading.Thread(target=stream_model_a)
                thread_b = threading.Thread(target=stream_model_b)
                
                thread_a.start()
                thread_b.start()
                
                completed = {'a': False, 'b': False}
                
                while not all(completed.values()):
                    try:
                        model, chunk = chunk_queue.get(timeout=0.1)
                        if chunk is None:
                            completed[model] = True
                        else:
                            yield chunk
                    except queue.Empty:
                        continue
                
                thread_a.join()
                thread_b.join()
    
        return StreamingHttpResponse(generate(), content_type='text/plain')

    
    @action(detail=True, methods=['get'])
    def tree(self, request, pk=None):
        """Get message tree starting from this message"""
        message = self.get_object()
        
        # Find root messages
        root_messages = []
        current = message
        
        while current.parent_message_ids:
            parent_id = current.parent_message_ids[0]  # Follow first parent
            try:
                current = Message.objects.get(id=parent_id)
            except Message.DoesNotExist:
                break
        
        root_messages.append(current)
        
        # Build tree from root
        tree = MessageService.get_message_tree(current.id)
        
        return Response(tree)
    
    @action(detail=True, methods=['post'])
    def branch(self, request, pk=None):
        """Create a branch from this message"""
        parent_message = self.get_object()
        serializer = MessageBranchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        branch_message = MessageService.create_branch(
            parent_message=parent_message,
            content=serializer.validated_data['content'],
            branch_type=serializer.validated_data.get('branch_type', 'alternative')
        )
        
        return Response(
            MessageSerializer(branch_message).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def regenerate(self, request, pk=None):
        """Regenerate an assistant message"""
        message = self.get_object()
        serializer = MessageRegenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create regenerated message
        new_message = MessageService.regenerate_message(
            message=message,
            **serializer.validated_data
        )
        
        # Stream the regenerated response
        generator = MessageService.stream_assistant_message(
            session=message.session,
            user_message=Message.objects.get(id=message.parent_message_ids[0]),
            model=new_message.model,
            participant=message.participant,
            temperature=serializer.validated_data['temperature'],
            max_tokens=serializer.validated_data['max_tokens']
        )
        
        # Update the new message ID in the generator
        async def update_generator():
            async for item in generator:
                if item.get('message_id'):
                    item['message_id'] = str(new_message.id)
                yield item
        
        return StreamingManager.create_streaming_response(update_generator())
    
    @action(detail=False, methods=['get'])
    def conversation_path(self, request):
        """Get conversation path between two messages"""
        start_id = request.query_params.get('start_id')
        end_id = request.query_params.get('end_id')
        
        if not start_id or not end_id:
            return Response(
                {'error': 'start_id and end_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_message = Message.objects.get(id=start_id)
            end_message = Message.objects.get(id=end_id)
        except Message.DoesNotExist:
            return Response(
                {'error': 'Message not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Find path between messages
        path = MessageService.find_conversation_path(start_message, end_message)
        
        return Response({
            'path': MessageSerializer(path, many=True).data,
            'distance': len(path)
        })