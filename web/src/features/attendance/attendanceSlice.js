import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/**
 * Attendance is fetched per class + date and then nested subject-side by the
 * UI, so a teacher can drill Grade 10 -> Mathematics -> student list.
 */
export const fetchAttendance = createAsyncThunk(
  'attendance/fetch',
  async ({ date, classId } = {}) =>
    api(`/api/v1/school/attendance${qs({ date, class_id: classId })}`)
);

export const saveAttendance = createAsyncThunk(
  'attendance/save',
  async ({ date, classId, entries }) =>
    api('/api/v1/school/attendance', {
      method: 'POST',
      body: { date, class_id: classId, entries },
    })
);

export const submitRoster = createAsyncThunk('attendance/submit', async ({ date } = {}) =>
  api('/api/v1/school/attendance/submit', { method: 'POST', body: { date } })
);

export const fetchAttendanceTrend = createAsyncThunk(
  'attendance/trend',
  async ({ days } = {}) => api(`/api/v1/school/analytics/attendance-trend${qs({ days })}`)
);

/** State-side live monitor with the Class 1-12 filter. */
export const fetchLiveAttendance = createAsyncThunk(
  'attendance/live',
  async ({ classLevel, schoolId } = {}) =>
    api(`/api/v1/state/attendance/live${qs({ class_level: classLevel, school_id: schoolId })}`)
);

export const fetchClassLevels = createAsyncThunk('attendance/classLevels', async () =>
  api('/api/v1/state/class-levels')
);

const attendanceSlice = createSlice({
  name: 'attendance',
  initialState: {
    records: {},
    allowedStatuses: [],
    date: null,
    classId: null,
    trend: [],
    averagePct: null,
    live: [],
    liveClassLevel: null,
    classLevels: [],
    status: 'idle',
    saving: false,
    error: null,
    notice: null,
  },
  reducers: {
    setFilter(state, action) {
      state.date = action.payload.date ?? state.date;
      state.classId = action.payload.classId ?? state.classId;
    },
    setLiveClassLevel(state, action) {
      state.liveClassLevel = action.payload;
    },
    clearNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchAttendance.fulfilled, (state, action) => {
        // The roster endpoint returns a {student_id: status} map plus the date.
        state.records = action.payload.statuses ?? {};
        state.allowedStatuses = action.payload.allowed_statuses ?? [];
        state.classId = action.payload.class_id ?? state.classId;
        state.date = action.payload.date ?? state.date;
        state.status = 'ready';
      })
      .addCase(fetchAttendance.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(saveAttendance.pending, (state) => {
        state.saving = true;
      })
      .addCase(saveAttendance.fulfilled, (state, action) => {
        state.saving = false;
        state.notice = action.payload.message ?? 'Attendance saved';
        state.records = action.payload.statuses ?? state.records;
      })
      .addCase(saveAttendance.rejected, (state, action) => {
        state.saving = false;
        state.error = action.error.message;
      })
      .addCase(submitRoster.fulfilled, (state, action) => {
        state.notice = action.payload.message ?? 'Daily roster submitted';
      })
      .addCase(fetchAttendanceTrend.fulfilled, (state, action) => {
        state.trend = action.payload.trend;
        state.averagePct = action.payload.average_pct;
      })
      .addCase(fetchLiveAttendance.fulfilled, (state, action) => {
        state.live = action.payload.records ?? [];
        state.liveClassLevel = action.payload.filtered_class_level ?? null;
      })
      .addCase(fetchClassLevels.fulfilled, (state, action) => {
        state.classLevels = action.payload.class_levels;
      });
  },
});

export const { setFilter, setLiveClassLevel, clearNotice } = attendanceSlice.actions;

export const selectAttendanceRecords = (state) => state.attendance.records;
export const selectAttendanceTrend = (state) => state.attendance.trend;
export const selectLiveAttendance = (state) => state.attendance.live;
export const selectClassLevels = (state) => state.attendance.classLevels;

export default attendanceSlice.reducer;
