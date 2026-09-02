import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/**
 * Module 1 — teacher absence & substitution engine state.
 */

export const fetchAbsences = createAsyncThunk(
  'absences/fetch',
  async ({ date } = {}) => api(`/api/v1/school/absences${qs({ date })}`)
);

export const fetchTimetable = createAsyncThunk(
  'absences/timetable',
  async ({ day } = {}) => api(`/api/v1/school/timetable${qs({ day })}`)
);

export const logAbsence = createAsyncThunk(
  'absences/log',
  async ({ teacherId, date, reason }) =>
    api('/api/v1/school/absences', {
      method: 'POST',
      body: { teacher_id: teacherId, absence_date: date, reason },
    })
);

export const fetchRecommendations = createAsyncThunk(
  'absences/recommendations',
  async (absenceId) => api(`/api/v1/school/absences/${absenceId}/recommendations`)
);

export const confirmSubstitution = createAsyncThunk(
  'absences/confirm',
  async ({ absenceId, periodNumber, classId, substituteTeacherId }) =>
    api('/api/v1/school/substitutions', {
      method: 'POST',
      body: {
        absence_id: absenceId,
        period_number: periodNumber,
        class_id: classId,
        substitute_teacher_id: substituteTeacherId,
      },
    })
);

export const autoAssign = createAsyncThunk('absences/autoAssign', async (absenceId) =>
  api(`/api/v1/school/absences/${absenceId}/auto-assign`, { method: 'POST' })
);

export const cancelAbsence = createAsyncThunk('absences/cancel', async (absenceId) =>
  api(`/api/v1/school/absences/${absenceId}`, { method: 'DELETE' })
);

const absenceSlice = createSlice({
  name: 'absences',
  initialState: {
    list: [],
    timetable: [],
    panel: null,
    lastResult: null,
    status: 'idle',
    busy: false,
    error: null,
    notice: null,
  },
  reducers: {
    clearPanel(state) {
      state.panel = null;
      state.lastResult = null;
      state.error = null;
      state.notice = null;
    },
    dismissNotice(state) {
      state.notice = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchAbsences.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchAbsences.fulfilled, (state, action) => {
        state.list = action.payload.absences ?? [];
        state.status = 'ready';
      })
      .addCase(fetchAbsences.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'ready';
      })
      .addCase(fetchTimetable.fulfilled, (state, action) => {
        state.timetable = action.payload.slots ?? [];
      })
      .addCase(logAbsence.pending, (state) => {
        state.busy = true;
        state.error = null;
      })
      .addCase(logAbsence.fulfilled, (state, action) => {
        state.busy = false;
        state.panel = action.payload.panel;
        state.notice = 'Absence logged — coverage recommendations generated';
      })
      .addCase(logAbsence.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(fetchRecommendations.fulfilled, (state, action) => {
        state.panel = action.payload;
      })
      .addCase(fetchRecommendations.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(confirmSubstitution.pending, (state) => {
        state.busy = true;
      })
      .addCase(confirmSubstitution.fulfilled, (state, action) => {
        state.busy = false;
        state.panel = action.payload.panel;
        state.notice = 'Substitute confirmed';
      })
      .addCase(confirmSubstitution.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(autoAssign.pending, (state) => {
        state.busy = true;
      })
      .addCase(autoAssign.fulfilled, (state, action) => {
        state.busy = false;
        state.panel = action.payload.panel;
        state.notice = `Auto-covered ${action.payload.assigned} period(s)`;
      })
      .addCase(autoAssign.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(cancelAbsence.fulfilled, (state, action) => {
        state.notice = 'Absence cancelled';
        state.panel = null;
      });
  },
});

export const { clearPanel, dismissNotice } = absenceSlice.actions;

export const selectAbsencePanel = (state) => state.absences.panel;

export default absenceSlice.reducer;
