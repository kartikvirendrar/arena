import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from chat_session.models import ChatSession
from message.models import Message


class ChatSessionConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat session updates"""
    
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_group_name = f'session_{self.session_id}'
        
        # Verify user has access to this session
        if not await self.verify_session_access():
            await self.close()
            return
        
        # Join session group
        await self.channel_layer.group_add(
            self.session_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial session state
        await self.send_session_state()
    
    async def disconnect(self, close_code):
        # Leave session group
        await self.channel_layer.group_discard(
            self.session_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        if message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'timestamp': data.get('timestamp')
            }))
        
        elif message_type == 'typing_indicator':
            # Broadcast typing indicator to other users
            await self.channel_layer.group_send(
                self.session_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': str(self.scope['user'].id),
                    'is_typing': data.get('is_typing', False)
                }
            )
        
        elif message_type == 'request_state':
            await self.send_session_state()
    
    async def typing_indicator(self, event):
        # Don't send typing indicator back to sender
        if event['user_id'] != str(self.scope['user'].id):
            await self.send(text_data=json.dumps({
                'type': 'typing_indicator',
                'user_id': event['user_id'],
                'is_typing': event['is_typing']
            }))
    
    async def message_update(self, event):
        """Handle message updates"""
        await self.send(text_data=json.dumps({
            'type': 'message_update',
            'message': event['message'],
            'action': event.get('action', 'created')
        }))
    
    async def session_update(self, event):
        """Handle session updates"""
        await self.send(text_data=json.dumps({
            'type': 'session_update',
            'session': event['session'],
            'action': event.get('action', 'updated')
        }))
    
    @database_sync_to_async
    def verify_session_access(self):
        """Verify user has access to this session"""
        try:
            session = ChatSession.objects.get(id=self.session_id)
            user = self.scope['user']
            
            # Check if user owns the session or it's public
            if session.user == user or session.is_public:
                return True
            
            # Check for share token in query params
            share_token = self.scope['query_string'].decode().split('share_token=')[-1]
            if share_token and session.share_token == share_token:
                return True
            
            return False
        except ChatSession.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_session_state(self):
        """Get current session state"""
        session = ChatSession.objects.select_related(
            'model_a', 'model_b', 'user'
        ).get(id=self.session_id)
        
        # Get recent messages
        messages = Message.objects.filter(
            session=session
        ).order_by('-position')[:50]
        
        return {
            'session': {
                'id': str(session.id),
                'mode': session.mode,
                'title': session.title,
                'model_a': {
                    'id': str(session.model_a.id),
                    'name': session.model_a.display_name
                } if session.model_a else None,
                'model_b': {
                    'id': str(session.model_b.id),
                    'name': session.model_b.display_name
                } if session.model_b else None,
            },
            'messages': [
                {
                    'id': str(msg.id),
                    'role': msg.role,
                    'content': msg.content,
                    'position': msg.position,
                    'participant': msg.participant,
                    'status': msg.status,
                    'created_at': msg.created_at.isoformat()
                }
                for msg in reversed(messages)
            ]
        }
    
    async def send_session_state(self):
        """Send current session state to client"""
        state = await self.get_session_state()
        await self.send(text_data=json.dumps({
            'type': 'session_state',
            **state
        }))