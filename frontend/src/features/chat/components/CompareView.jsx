import { useState } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ThumbsUp } from 'lucide-react';
import { apiClient } from '../../../shared/api/client';
import { endpoints } from '../../../shared/api/endpoints';
import { toast } from 'react-hot-toast';
import { CompareMessageInput } from './CompareMessageInput';

export function CompareView({ session, messages, streamingMessages }) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastMessagePair, setLastMessagePair] = useState(null);

  const handlePreference = async (preference) => {
    try {
      await apiClient.post(endpoints.feedback.submit, {
        session_id: session.id,
        type: 'preference',
        preference: preference,
        model_a_id: session.model_a.id,
        model_b_id: session.model_b.id,
      });
      toast.success('Preference recorded');
      setShowFeedback(false);
    } catch (error) {
      toast.error('Failed to submit preference');
    }
  };

  // Split messages for each model
  const modelAMessages = messages.filter((msg, idx) => 
    msg.role === 'user' || (msg.role === 'assistant' && idx % 2 === 1)
  );
  const modelBMessages = messages.filter((msg, idx) => 
    msg.role === 'user' || (msg.role === 'assistant' && idx % 2 === 0)
  );

  return (
    <div className="flex-1 flex flex-col">
      {/* Compare Header */}
      <div className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="text-sm">
              <span className="font-medium">Model A:</span> {session.model_a?.name || 'Random'}
            </div>
            <div className="text-gray-300">vs</div>
            <div className="text-sm">
              <span className="font-medium">Model B:</span> {session.model_b?.name || 'Random'}
            </div>
          </div>
          {showFeedback && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600">Which response was better?</span>
              <button
                onClick={() => handlePreference('model_a')}
                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200"
              >
                Model A
              </button>
              <button
                onClick={() => handlePreference('model_b')}
                className="px-3 py-1 bg-green-100 text-green-700 rounded-lg hover:bg-green-200"
              >
                Model B
              </button>
              <button
                onClick={() => handlePreference('tie')}
                className="px-3 py-1 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Tie
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Side by side message lists */}
      <div className="flex-1 flex">
        <div className="flex-1 border-r border-gray-200">
          <MessageList
            messages={modelAMessages}
            streamingMessages={streamingMessages}
            sessionId={session.id}
          />
        </div>
        <div className="flex-1">
          <MessageList
            messages={modelBMessages}
            streamingMessages={streamingMessages}
            sessionId={session.id}
          />
        </div>
      </div>

      {/* Shared Input */}
      <CompareMessageInput
        sessionId={session.id} 
        modelAId={session.model_a?.id}
        modelBId={session.model_b?.id}
        onMessageSent={() => setShowFeedback(true)}
      />
    </div>
  );
}