import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import { fetchCurrentUser } from '../features/auth/store/authSlice';
import { LoginPage } from '../features/auth/components/LoginPage';
import { ChatLayout } from '../features/chat/components/ChatLayout';
import { LeaderboardPage } from '../features/leaderboard/components/LeaderboardPage';
import { SharedSessionView } from '../features/chat/components/SharedSessionView';

export function AppRouter() {
  const dispatch = useDispatch();
  const { isAuthenticated, loading } = useSelector((state) => state.auth);
  
  useEffect(() => {
    const token = localStorage.getItem('authToken');
    if (token) {
      dispatch(fetchCurrentUser());
    }
  }, [dispatch]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }
  
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route 
        path="/chat" 
        element={isAuthenticated ? <ChatLayout /> : <Navigate to="/login" />} 
      />
      <Route path="/leaderboard" element={<LeaderboardPage />} />
      <Route path="/shared/:shareToken" element={<SharedSessionView />} />
      <Route path="/" element={<Navigate to="/chat" />} />
    </Routes>
  );
}