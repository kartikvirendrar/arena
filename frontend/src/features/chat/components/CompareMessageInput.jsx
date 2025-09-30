import { useState, useRef, useEffect } from 'react';
import { Send, Square } from 'lucide-react';
import { useDispatch } from 'react-redux';
import { apiClient } from '../../../shared/api/client';
import { endpoints } from '../../../shared/api/endpoints';
import { addMessage, updateStreamingMessage } from '../store/chatSlice';
import { v4 as uuidv4 } from 'uuid';
import { toast } from 'react-hot-toast';

export function CompareMessageInput({ sessionId, modelAId, modelBId, onMessageSent }) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const textareaRef = useRef(null);
  const dispatch = useDispatch();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  }, [input]);

  const streamComparison = async (content) => {
    const userMessageId = uuidv4();
    
    // Add user message
    dispatch(addMessage({
      sessionId,
      message: {
        id: userMessageId,
        content,
        role: 'user',
        timestamp: new Date().toISOString(),
      }
    }));

    setIsStreaming(true);

    try {
      const response = await fetch(`${apiClient.defaults.baseURL}/models/compare/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          session_id: sessionId,
          content,
          model_a_id: modelAId,
          model_b_id: modelBId,
        }),
      });

      if (!response.ok) throw new Error('Stream request failed');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      const messageIds = {
        model_a: uuidv4(),
        model_b: uuidv4(),
      };

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
                messageId: messageIds.model_a,
                chunk: '',
                isComplete: true,
              }));
              dispatch(updateStreamingMessage({
                sessionId,
                messageId: messageIds.model_b,
                chunk: '',
                isComplete: true,
              }));
            } else {
              try {
                const parsed = JSON.parse(data);
                if (parsed.model === 'model_a') {
                  dispatch(updateStreamingMessage({
                    sessionId,
                    messageId: messageIds.model_a,
                    chunk: parsed.content || '',
                    isComplete: false,
                  }));
                } else if (parsed.model === 'model_b') {
                  dispatch(updateStreamingMessage({
                    sessionId,
                    messageId: messageIds.model_b,
                    chunk: parsed.content || '',
                    isComplete: false,
                  }));
                }
              } catch (e) {
                console.error('Failed to parse SSE data:', e);
              }
            }
          }
        }
      }

      onMessageSent();
    } catch (error) {
      toast.error('Failed to send message');
    } finally {
      setIsStreaming(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const content = input.trim();
    setInput('');
    await streamComparison(content);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
        <div className="flex items-end gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your message to compare responses..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none max-h-32"
            rows="1"
            disabled={isStreaming}
          />
          
          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
          >
            {isStreaming ? <Square size={20} /> : <Send size={20} />}
          </button>
        </div>
      </form>
    </div>
  );
}