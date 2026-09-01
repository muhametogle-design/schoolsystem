import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api } from '../../api/client';

/**
 * Module 4 — encrypted backup administration (State Admin only).
 */

export const fetchBackups = createAsyncThunk('backups/fetch', async () =>
  api('/api/v1/admin/backups')
);

export const runBackup = createAsyncThunk('backups/run', async ({ kind }) =>
  api('/api/v1/admin/backups/run', { method: 'POST', body: { kind } })
);

export const verifyBackup = createAsyncThunk('backups/verify', async (backupId) =>
  api(`/api/v1/admin/backups/${backupId}/verify`)
);

export const fetchBackupAudit = createAsyncThunk('backups/audit', async () =>
  api('/api/v1/admin/backups/audit')
);

const backupsSlice = createSlice({
  name: 'backups',
  initialState: {
    backups: [],
    total: 0,
    lastBackup: null,
    config: null,
    audit: [],
    busy: false,
    status: 'idle',
    error: null,
    notice: null,
  },
  reducers: {
    dismissNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchBackups.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchBackups.fulfilled, (state, action) => {
        state.backups = action.payload.backups ?? [];
        state.total = action.payload.total ?? 0;
        state.lastBackup = action.payload.last_backup ?? null;
        state.config = action.payload.config ?? null;
        state.status = 'ready';
      })
      .addCase(fetchBackups.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'ready';
      })
      .addCase(runBackup.pending, (state) => {
        state.busy = true;
      })
      .addCase(runBackup.fulfilled, (state, action) => {
        state.busy = false;
        state.backups = [action.payload.backup, ...state.backups];
        state.lastBackup = action.payload.backup;
        state.notice = `${action.payload.backup.kind === 'full_snapshot' ? 'Full snapshot' : 'JSON delta'} created and encrypted`;
      })
      .addCase(runBackup.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(verifyBackup.fulfilled, (state, action) => {
        state.notice = action.payload.verified
          ? 'Integrity verified — SHA-256 and MD5 match'
          : 'VERIFICATION FAILED — hashes do not match';
      })
      .addCase(verifyBackup.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(fetchBackupAudit.fulfilled, (state, action) => {
        state.audit = action.payload.events ?? [];
      });
  },
});

export const { dismissNotice } = backupsSlice.actions;

export default backupsSlice.reducer;
