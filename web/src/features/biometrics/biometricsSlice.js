import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/**
 * Module 5 — biometric hardware management (WebAuthn) state.
 *
 * The browser ceremonies themselves live in the page component
 * (navigator.credentials); the slice only carries API state.
 */

export const fetchBiometricOverview = createAsyncThunk('biometrics/overview', async ({ limit } = {}) =>
  api(`/api/v1/school/biometrics/overview${qs({ limit })}`)
);

export const fetchVerificationLog = createAsyncThunk(
  'biometrics/log',
  async ({ purpose, result, limit } = {}) =>
    api(`/api/v1/school/biometrics/verifications${qs({ purpose, result, limit })}`)
);

export const biometricEnrollOptions = createAsyncThunk('biometrics/enrollOptions', async (body) =>
  api('/api/v1/school/biometrics/enroll/options', { method: 'POST', body })
);

export const biometricEnrollVerify = createAsyncThunk('biometrics/enrollVerify', async (body) =>
  api('/api/v1/school/biometrics/enroll/verify', { method: 'POST', body })
);

export const biometricVerifyOptions = createAsyncThunk('biometrics/verifyOptions', async (body) =>
  api('/api/v1/school/biometrics/verify/options', { method: 'POST', body })
);

export const biometricVerifyComplete = createAsyncThunk('biometrics/verifyComplete', async (body) =>
  api('/api/v1/school/biometrics/verify/complete', { method: 'POST', body })
);

export const biometricRescan = createAsyncThunk('biometrics/rescan', async (credentialId) =>
  api(`/api/v1/school/biometrics/credentials/${credentialId}/rescan`, { method: 'POST' })
);

export const biometricRevoke = createAsyncThunk('biometrics/revoke', async (credentialId) =>
  api(`/api/v1/school/biometrics/credentials/${credentialId}`, { method: 'DELETE' })
);

const biometricsSlice = createSlice({
  name: 'biometrics',
  initialState: {
    students: [],
    staff: [],
    counts: {},
    verifications: [],
    enrollTarget: null,
    station: null,
    busy: false,
    status: 'idle',
    error: null,
    notice: null,
    lastVerification: null,
  },
  reducers: {
    setEnrollTarget(state, action) {
      state.enrollTarget = action.payload; // {owner_type, owner_id, name}
    },
    setStation(state, action) {
      state.station = action.payload; // {purpose, owner_type, owner_id, name}
    },
    clearStationResult(state) {
      state.lastVerification = null;
    },
    dismissNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchBiometricOverview.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchBiometricOverview.fulfilled, (state, action) => {
        state.students = action.payload.students ?? [];
        state.staff = action.payload.staff ?? [];
        state.counts = action.payload.counts ?? {};
        state.status = 'ready';
      })
      .addCase(fetchBiometricOverview.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'ready';
      })
      .addCase(fetchVerificationLog.fulfilled, (state, action) => {
        state.verifications = action.payload.verifications ?? [];
      })
      .addCase(biometricEnrollOptions.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(biometricEnrollVerify.pending, (state) => {
        state.busy = true;
      })
      .addCase(biometricEnrollVerify.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = `Enrolled ${action.payload.credential.method} authenticator`;
      })
      .addCase(biometricEnrollVerify.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(biometricVerifyOptions.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(biometricVerifyComplete.pending, (state) => {
        state.busy = true;
      })
      .addCase(biometricVerifyComplete.fulfilled, (state, action) => {
        state.busy = false;
        state.lastVerification = action.payload;
        state.notice = `Verified ${action.payload.person} — ${action.payload.purpose.replace(/_/g, ' ')}`;
      })
      .addCase(biometricVerifyComplete.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(biometricRescan.fulfilled, (state, action) => {
        state.notice = 'Hardware re-scan: credential revoked — re-enrollment opened';
      })
      .addCase(biometricRevoke.fulfilled, (state) => {
        state.notice = 'Credential revoked';
      });
  },
});

export const {
  setEnrollTarget,
  setStation,
  clearStationResult,
  dismissNotice,
} = biometricsSlice.actions;

export default biometricsSlice.reducer;
