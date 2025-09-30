import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { fetchSessions, createSession, setActiveSession } from '../store/chatSlice';
import { logout } from '../../auth/store/authSlice';
import { Plus, MessageSquare, LogOut, User, ChevronLeft } from 'lucide-react';
import { format } from 'date-fns';

export function ChatSidebar({ isOpen, onToggle }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { sessions, activeSession } = useSelector((state) => state.chat);
  const { user } = useSelector((state) => state.auth);

  useEffect(() => {
    dispatch(fetchSessions());
  }, [dispatch]);

  const handleNewChat = async () => {
    await dispatch(createSession({ mode: 'direct' }));
  };

  const handleSelectSession = (session) => {
    dispatch(setActiveSession(session));
  };

  const handleLogout = () => {
    dispatch(logout());
    navigate('/login');
  };

  return (
    <div className={`${isOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-gray-900 text-white flex flex-col`}>
      {isOpen && (
        <>
          {/* Header */}
          <div className="p-4 border-b border-gray-700">
            <button
              onClick={handleNewChat}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg transition-colors"
            >
              <Plus size={20} />
              New Chat
            </button>
          </div>

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-2">
              {sessions.map((session) => (
                <button
                  key={session.id}
                  onClick={() => handleSelectSession(session)}
                  className={`w-full text-left p-3 rounded-lg mb-1 hover:bg-gray-800 transition-colors ${
                    activeSession?.id === session.id ? 'bg-gray-800' : ''
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <MessageSquare size={16} />
                    <div className="flex-1 overflow-hidden">
                      <div className="text-sm font-medium truncate">
                        {session.title || `Chat ${format(new Date(session.created_at), 'MMM d')}`}
                      </div>
                      <div className="text-xs text-gray-400">
                        {session.mode} • {format(new Date(session.created_at), 'h:mm a')}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* User Section */}
          <div className="border-t border-gray-700 p-4">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <User size={20} />
                <span className="text-sm">{user?.email || 'Anonymous'}</span>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 bg-gray-800 hover:bg-gray-700 px-4 py-2 rounded-lg transition-colors"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        </>
      )}
      
      {/* Toggle Button */}
      <button
        onClick={onToggle}
        className="absolute top-4 -right-3 bg-gray-800 p-1 rounded-full"
      >
        <ChevronLeft className={`transition-transform ${!isOpen ? 'rotate-180' : ''}`} size={16} />
      </button>
    </div>
  );
}