import { useState } from 'react';
import { useSelector } from 'react-redux';
import { ChatSidebar } from './ChatSidebar';
import { ChatWindow } from './ChatWindow';
import { ModelSelector } from './ModelSelector';

export function ChatLayout() {
  const { activeSession } = useSelector((state) => state.chat);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  return (
    <div className="flex h-screen bg-gray-100">
      {/* Sidebar */}
      <ChatSidebar isOpen={isSidebarOpen} onToggle={() => setIsSidebarOpen(!isSidebarOpen)} />
      
      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-gray-900">
              {activeSession ? `Session: ${activeSession.title || activeSession.id}` : 'New Chat'}
            </h1>
            <ModelSelector />
          </div>
        </header>
        
        {/* Chat Window */}
        <ChatWindow />
      </div>
    </div>
  );
}