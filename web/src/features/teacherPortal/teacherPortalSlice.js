import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/**
 * Refinement 3 — the signed-in teacher's day: subject schedule for a date and
 * the subject-restricted quick rosters.
 */

export const fetchMySchedule = createAsyncThunk(
  'teacherPortal/schedule',
  async ({ date } = {}) => api(`/api/v1/school/teachers/me/schedule${qs({ date })}`)
);

export const fetchMyRoster = createAsyncThunk(
  'teacherPortal/roster',
  async ({ date, classId, subjectId, periodNumber }) =>
    api(
      `/api/v1/school/teachers/me/roster${qs({
        date,
        class_id: classId,
        subject_id: subjectId,
        period_number: periodNumber,
      })}`
    )
);

export const saveMyRoster = createAsyncThunk('teacherPortal/saveRoster', async (payload) =>
  api('/api/v1/school/teachers/me/roster', { method: 'POST', body: payload })
);

const teacherPortalSlice = createSlice({
  name: 'teacherPortal',
  initialState: {
    teacher: null,
    slots: [],
    activePeriod: null,
    periodWindows: {},
    date: null,
    pendingSlots: 0,
    roster: null,
    busy: false,
    status: 'idle',
    error: null,
    notice: null,
  },
  reducers: {
    clearRoster(state) {
      state.roster = null;
    },
    dismissNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMySchedule.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchMySchedule.fulfilled, (state, action) => {
        state.teacher = action.payload.teacher;
        state.slots = action.payload.slots ?? [];
        state.activePeriod = action.payload.active_period ?? null;
        state.periodWindows = action.payload.period_windows ?? {};
        state.date = action.payload.date;
        state.pendingSlots = action.payload.pending_slots ?? 0;
        state.status = 'ready';
      })
      .addCase(fetchMySchedule.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'ready';
      })
      .addCase(fetchMyRoster.fulfilled, (state, action) => {
        state.roster = action.payload;
      })
      .addCase(fetchMyRoster.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(saveMyRoster.pending, (state) => {
        state.busy = true;
        state.error = null;
      })
      .addCase(saveMyRoster.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = `Marked ${action.payload.saved} student(s) for period ${action.payload.period_number}`;
        state.roster = null; // close the roster sheet
      })
      .addCase(saveMyRoster.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      });
  },
});

export const { clearRoster, dismissNotice } = teacherPortalSlice.actions;

export default teacherPortalSlice.reducer;
