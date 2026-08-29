import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, getToken, setToken } from '../../api/client';

const USER_KEY = 'ne_emis_user';

const readStoredUser = () => {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export const login = createAsyncThunk('auth/login', async ({ email, password }) => {
  const data = await api('/api/auth/login', {
    method: 'POST',
    body: { email: email.trim(), password },
  });
  setToken(data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
});

export const logout = createAsyncThunk('auth/logout', async () => {
  try {
    await api('/api/auth/logout', { method: 'POST' });
  } catch {
    /* best effort — the local session is dropped regardless */
  }
  setToken(null);
  localStorage.removeItem(USER_KEY);
});

export const fetchMe = createAsyncThunk('auth/me', async () => api('/api/auth/me'));

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: readStoredUser(),
    token: getToken(),
    // With a stored token we must confirm the session with the server before
    // choosing a portal — a stale/corrupt localStorage role would otherwise
    // render the wrong workspace and every call would 403.
    bootstrapped: !getToken(),
    status: 'idle',
    error: null,
  },
  reducers: {
    clearError(state) {
      state.error = null;
    },
    sessionExpired(state) {
      state.user = null;
      state.token = null;
      state.error = 'Session expired — please sign in again.';
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(login.pending, (state) => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action) => {
        state.status = 'authenticated';
        state.user = action.payload;
        state.token = getToken();
        state.bootstrapped = true;
      })
      .addCase(login.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message;
      })
      .addCase(logout.fulfilled, (state) => {
        state.user = null;
        state.token = null;
        state.status = 'idle';
        state.bootstrapped = true;
      })
      .addCase(fetchMe.fulfilled, (state, action) => {
        // Server response is authoritative — it corrects any stale local role.
        state.user = action.payload;
        localStorage.setItem(USER_KEY, JSON.stringify(action.payload));
        state.status = 'authenticated';
        state.bootstrapped = true;
      })
      .addCase(fetchMe.rejected, (state) => {
        state.bootstrapped = true;
      });
  },
});

export const { clearError, sessionExpired } = authSlice.actions;

export const selectUser = (state) => state.auth.user;
export const selectIsState = (state) => state.auth.user?.role === 'state_inspector';
export const selectIsManager = (state) => state.auth.user?.role === 'school_manager';
export const selectIsTeacher = (state) => state.auth.user?.role === 'teacher';

export default authSlice.reducer;
