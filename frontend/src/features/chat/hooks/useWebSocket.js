import { useEffect, useRef } from 'react';
import { useDispatch } from 'react-redux';
import { WS_BASE_URL } from '../../../shared/api/client';
import { updateStreamingMessage } from '../store/chatSlice';
import { toast } from 'react-hot-toast';

export function useWebSocket(sessionId) {
  const dispatch = useDispatch();
  const ws = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    const token = localStorage.getItem('authToken');
    const wsUrl = `${WS_BASE_URL}/chat/session/${sessionId}/?token=${token}`;

    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      console.log('WebSocket connected');
    };

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'message_chunk':
          dispatch(updateStreamingMessage({
            sessionId,
            messageId: data.message_id,
            chunk: data.chunk,
            isComplete: false,
          }));
          break;
          
        case 'message_complete':
          dispatch(updateStreamingMessage({
            sessionId,
            messageId: data.message_id,
            chunk: '',
            isComplete: true,
          }));
          break;
          
        case 'error':
          toast.error(data.message);
          break;
          
        default:
          console.log('Unknown message type:', data.type);
      }
    };

    ws.current.onerror = (error) => {
      console.error('WebSocket error:', error);
      toast.error('Connection error');
    };

    ws.current.onclose = () => {
      console.log('WebSocket disconnected');
    };

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [sessionId, dispatch]);

  const sendMessage = (message) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      toast.error('Connection not established');
    }
  };

  return { sendMessage };
}