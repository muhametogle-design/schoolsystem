import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import {
  api,
  clearStoredUser,
  getStoredUser,
  getToken,
  setStoredUser,
  setToken,
} from '../../api/client';

// A cookie-backed session is deliberately supported when a mobile browser or
// embedded context declines localStorage. The in-memory login state lets that
// browser enter immediately, while the cookie authorizes subsequent API calls.
export const login = createAsyncThunk('auth/login', async ({ email, password }) => {
  const data = await api('/api/auth/login', {
    method: 'POST',
    body: { email: email.trim(), password },
  });
  setToken(data.access_token);
  setStoredUser(data.user);
  return data.user;
});

export const logout = createAsyncThunk('auth/logout', async () => {
  try {
    await api('/api/auth/logout', { method: 'POST' });
  } catch {
    /* best effort — the local session is dropped regardless */
  }
  setToken(null);
  clearStoredUser();
});

export const fetchMe = createAsyncThunk('auth/me', async () => {
  try {
    return await api('/api/auth/me');
  } catch (error) {
    // Keep the browser's cookie as the source of truth, but clear any stale
    // JS-accessible session data so the sign-in form can recover cleanly.
    setToken(null);
    clearStoredUser();
    throw error;
  }
});

const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: getStoredUser(),
    token: getToken(),
    // Always probe /me once: an HttpOnly cookie may exist even when this
    // browser does not permit JavaScript-accessible persistent storage.
    bootstrapped: false,
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
        state.bootstrapped = true;
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
        setStoredUser(action.payload);
        state.status = 'authenticated';
        state.bootstrapped = true;
      })
      .addCase(fetchMe.rejected, (state) => {
        // A 401 here is normal for a first visit with no cookie yet; do not
        // present it as an error, simply render the sign-in form.
        state.user = null;
        state.token = null;
        state.status = 'idle';
        state.bootstrapped = true;
      });
  },
});

export const { clearError, sessionExpired } = authSlice.actions;

export const selectUser = (state) => state.auth.user;
const STATE_ROLES = new Set(['state_admin', 'inspector', 'state_inspector']);

export const selectIsState = (state) => STATE_ROLES.has(state.auth.user?.role);
export const selectIsStateAdmin = (state) => state.auth.user?.role === 'state_admin';
export const selectIsManager = (state) => state.auth.user?.role === 'school_manager';
export const selectIsTeacher = (state) => state.auth.user?.role === 'teacher';

export default authSlice.reducer;
