import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { apiClient } from '../../../shared/api/client';
import { endpoints } from '../../../shared/api/endpoints';

// Async thunks
export const loginWithGoogle = createAsyncThunk(
  'auth/loginWithGoogle',
  async (googleToken) => {
    const response = await apiClient.post(endpoints.auth.google, { token: googleToken });
    return response.data;
  }
);

export const loginAnonymously = createAsyncThunk(
  'auth/loginAnonymously',
  async () => {
    const response = await apiClient.post(endpoints.auth.anonymous);
    return response.data;
  }
);

export const fetchCurrentUser = createAsyncThunk(
  'auth/fetchCurrentUser',
  async () => {
    const response = await apiClient.get(endpoints.auth.currentUser);
    return response.data;
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    isAuthenticated: false,
    isAnonymous: false,
    loading: false,
    error: null,
  },
  reducers: {
    logout: (state) => {
      state.user = null;
      state.isAuthenticated = false;
      state.isAnonymous = false;
      localStorage.removeItem('authToken');
    },
  },
  extraReducers: (builder) => {
    // Google login
    builder
      .addCase(loginWithGoogle.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(loginWithGoogle.fulfilled, (state, action) => {
        state.loading = false;
        state.user = action.payload.user;
        state.isAuthenticated = true;
        state.isAnonymous = false;
        localStorage.setItem('authToken', action.payload.token);
      })
      .addCase(loginWithGoogle.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message;
      });
    
    // Anonymous login
    builder
      .addCase(loginAnonymously.fulfilled, (state, action) => {
        state.user = action.payload.user;
        state.isAuthenticated = true;
        state.isAnonymous = true;
        localStorage.setItem('authToken', action.payload.token);
      });
    
    // Fetch current user
    builder
      .addCase(fetchCurrentUser.fulfilled, (state, action) => {
        state.user = action.payload;
        state.isAuthenticated = true;
        state.isAnonymous = action.payload.is_anonymous;
      });
  },
});

export const { logout } = authSlice.actions;
export default authSlice.reducer;