import { useCallback } from 'react';
import { useDispatch } from 'react-redux';
import { apiClient } from '../../../shared/api/client';
import { endpoints } from '../../../shared/api/endpoints';
import { addMessage, updateStreamingMessage } from '../store/chatSlice';
import { v4 as uuidv4 } from 'uuid';

export function useStreamingMessage() {
  const dispatch = useDispatch();

  const streamMessage = useCallback(async ({
    sessionId,
    content,
    modelId,
    parentMessageIds = []
  }) => {
    const userMessageId = uuidv4();
    const aiMessageId = uuidv4();

    // Add user message immediately
    dispatch(addMessage({
      sessionId,
      message: {
        id: userMessageId,
        content,
        role: 'user',
        timestamp: new Date().toISOString(),
        parent_message_ids: parentMessageIds,
      }
    }));

    try {
      const response = await fetch(`${apiClient.defaults.baseURL}${endpoints.messages.stream}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          content,
          model_id: modelId,
          parent_message_ids: [userMessageId],
        }),
      });

      if (!response.ok) throw new Error('Stream request failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') {
              dispatch(updateStreamingMessage({
                sessionId,
                messageId: aiMessageId,
                chunk: '',
                isComplete: true,
              }));
            } else {
              try {
                const parsed = JSON.parse(data);
                dispatch(updateStreamingMessage({
                  sessionId,
                  messageId: aiMessageId,
                  chunk: parsed.content || '',
                  isComplete: false,
                }));
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error('Streaming error:', error);
      throw error;
    }
  }, [dispatch]);

  return { streamMessage };
}