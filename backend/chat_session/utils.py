from typing import Dict, List, Optional
from django.core.cache import cache
from django.db.models import Count, Avg, Q
import json
import hashlib
from datetime import datetime, timedelta, timezone
from chat_session.models import ChatSession
from message.models import Message


class SessionAnalyzer:
    """Analyze chat sessions for insights"""
    
    @staticmethod
    def get_user_session_insights(user) -> Dict:
        """Get insights about user's chat sessions"""
        
        sessions = ChatSession.objects.filter(user=user)
        
        insights = {
            'total_sessions': sessions.count(),
            'sessions_by_mode': {},
            'favorite_models': [],
            'average_session_length': 0,
            'most_active_times': {},
            'conversation_patterns': {}
        }
        
        # Sessions by mode
        mode_counts = sessions.values('mode').annotate(count=Count('id'))
        for item in mode_counts:
            insights['sessions_by_mode'][item['mode']] = item['count']
        
        # Favorite models (based on usage frequency)
        model_usage = {}
        for session in sessions:
            for model in [session.model_a, session.model_b]:
                if model:
                    model_usage[model.display_name] = model_usage.get(model.display_name, 0) + 1
        
        insights['favorite_models'] = sorted(
            [{'model': k, 'count': v} for k, v in model_usage.items()],
            key=lambda x: x['count'],
            reverse=True
        )[:5]
        
        # Average session length (in messages)
        avg_messages = sessions.annotate(
            msg_count=Count('messages')
        ).aggregate(avg=Avg('msg_count'))['avg']
        
        insights['average_session_length'] = round(avg_messages or 0, 2)
        
        # Most active times (hour of day)
        message_hours = Message.objects.filter(
            session__user=user
        ).values_list('created_at__hour', flat=True)
        
        hour_counts = {}
        for hour in message_hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        insights['most_active_times'] = dict(sorted(
            hour_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5])
        
        return insights
    
    @staticmethod
    def analyze_conversation_flow(session: 'ChatSession') -> Dict:
        """Analyze the flow of a conversation"""
        messages = session.messages.order_by('position')
        
        analysis = {
            'total_turns': 0,
            'average_message_length': {
                'user': 0,
                'assistant': 0
            },
            'response_times': [],
            'conversation_depth': 0,
            'branching_points': []
        }
        
        user_messages = []
        assistant_messages = []
        last_user_time = None
        
        for msg in messages:
            if msg.role == 'user':
                user_messages.append(len(msg.content))
                last_user_time = msg.created_at
                analysis['total_turns'] += 1
            else:
                assistant_messages.append(len(msg.content))
                
                # Calculate response time
                if last_user_time:
                    response_time = (msg.created_at - last_user_time).total_seconds()
                    analysis['response_times'].append(response_time)
            
            # Check for branching
            if len(msg.parent_message_ids) > 1:
                analysis['branching_points'].append({
                    'message_id': str(msg.id),
                    'position': msg.position,
                    'parent_count': len(msg.parent_message_ids)
                })
        
        # Calculate averages
        if user_messages:
            analysis['average_message_length']['user'] = round(
                sum(user_messages) / len(user_messages), 2
            )
        
        if assistant_messages:
            analysis['average_message_length']['assistant'] = round(
                sum(assistant_messages) / len(assistant_messages), 2
            )
        
        # Calculate conversation depth (longest path)
        analysis['conversation_depth'] = SessionAnalyzer._calculate_max_depth(messages)
        
        return analysis
    
    @staticmethod
    def _calculate_max_depth(messages) -> int:
        """Calculate the maximum depth of conversation tree"""
        if not messages:
            return 0
        
        # Build adjacency list
        children_map = {}
        root_messages = []
        
        for msg in messages:
            if not msg.parent_message_ids:
                root_messages.append(msg.id)
            
            for child_id in msg.child_ids:
                if msg.id not in children_map:
                    children_map[msg.id] = []
                children_map[msg.id].append(child_id)
        
        # DFS to find max depth
        def dfs(msg_id, depth=1):
            if msg_id not in children_map:
                return depth
            
            max_child_depth = depth
            for child_id in children_map[msg_id]:
                max_child_depth = max(max_child_depth, dfs(child_id, depth + 1))
            
            return max_child_depth
        
        max_depth = 0
        for root_id in root_messages:
            max_depth = max(max_depth, dfs(root_id))
        
        return max_depth


class SessionCache:
    """Cache manager for session data"""
    
    CACHE_PREFIX = 'session'
    DEFAULT_TIMEOUT = 3600  # 1 hour
    
    @classmethod
    def get_session_key(cls, session_id: str, suffix: str = '') -> str:
        """Generate cache key for session"""
        if suffix:
            return f"{cls.CACHE_PREFIX}:{session_id}:{suffix}"
        return f"{cls.CACHE_PREFIX}:{session_id}"
    
    @classmethod
    def cache_session_data(cls, session_id: str, data: Dict, suffix: str = '', timeout: int = None):
        """Cache session data"""
        key = cls.get_session_key(session_id, suffix)
        timeout = timeout or cls.DEFAULT_TIMEOUT
        cache.set(key, data, timeout)
    
    @classmethod
    def get_cached_session_data(cls, session_id: str, suffix: str = '') -> Optional[Dict]:
        """Get cached session data"""
        key = cls.get_session_key(session_id, suffix)
        return cache.get(key)
    
    @classmethod
    def invalidate_session_cache(cls, session_id: str):
        """Invalidate all cache entries for a session"""
        # Delete main session cache
        cache.delete(cls.get_session_key(session_id))
        
        # Delete related cache entries
        for suffix in ['stats', 'analysis', 'export']:
            cache.delete(cls.get_session_key(session_id, suffix))


class SessionHasher:
    """Generate hashes for session content"""
    
    @staticmethod
    def generate_session_hash(session: 'ChatSession') -> str:
        """Generate a hash representing the session state"""
        messages = session.messages.order_by('position')
        
        content_parts = [
            f"mode:{session.mode}",
            f"model_a:{session.model_a_id}",
            f"model_b:{session.model_b_id}",
        ]
        
        for msg in messages:
            content_parts.append(f"{msg.role}:{msg.content[:100]}")
        
        content = '|'.join(content_parts)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    @staticmethod
    def find_similar_sessions(session: 'ChatSession', threshold: float = 0.8) -> List['ChatSession']:
        """Find sessions with similar content"""
        # This is a simplified version - in production, 
        # you might want to use more sophisticated similarity measures
        
        current_hash = SessionHasher.generate_session_hash(session)
        similar_sessions = []
        
        # Check recent sessions
        recent_sessions = ChatSession.objects.filter(
            mode=session.mode,
            created_at__gte=timezone.now() - timedelta(days=7)
        ).exclude(id=session.id)[:100]
        
        for other_session in recent_sessions:
            other_hash = SessionHasher.generate_session_hash(other_session)
            
            # Simple similarity check (in production, use better algorithms)
            if current_hash[:8] == other_hash[:8]:
                similar_sessions.append(other_session)
        
        return similar_sessions[:5]