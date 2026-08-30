import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/** Class 1-12 accordion feed. */
export const fetchStudentsByClass = createAsyncThunk(
  'students/fetchByClass',
  async ({ q } = {}) => api(`/api/v1/school/students/by-class${qs({ q })}`)
);

/** Full profile for the Student Details page. */
export const fetchStudent = createAsyncThunk('students/fetchOne', async (neSid) =>
  api(`/api/v1/school/students/${encodeURIComponent(neSid)}`)
);

export const updateStudent = createAsyncThunk(
  'students/update',
  async ({ neSid, payload }) =>
    api(`/api/v1/school/students/${encodeURIComponent(neSid)}`, {
      method: 'PATCH',
      body: payload,
    })
);

export const createStudent = createAsyncThunk('students/create', async (payload) =>
  api('/api/v1/school/students', { method: 'POST', body: payload })
);

export const fetchReportCard = createAsyncThunk('students/reportCard', async (neSid) =>
  api(`/api/v1/school/students/${encodeURIComponent(neSid)}/report-card`)
);

/** Global roll-number lookup (state portal; legacy IDs remain supported). */
export const lookupStudent = createAsyncThunk('students/lookup', async (neSid) =>
  api(`/api/v1/state/students/lookup${qs({ ne_sid: neSid })}`)
);

const studentSlice = createSlice({
  name: 'students',
  initialState: {
    classes: [],
    unassigned: [],
    totalStudents: 0,
    selected: null,
    reportCard: null,
    lookup: null,
    status: 'idle',
    saving: false,
    error: null,
    notice: null,
  },
  reducers: {
    clearSelected(state) {
      state.selected = null;
      state.reportCard = null;
    },
    clearLookup(state) {
      state.lookup = null;
    },
    clearNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchStudentsByClass.fulfilled, (state, action) => {
        state.classes = action.payload.classes;
        state.unassigned = action.payload.unassigned;
        state.totalStudents = action.payload.total_students;
        state.status = 'ready';
      })
      .addCase(fetchStudentsByClass.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'failed';
      })
      .addCase(fetchStudent.fulfilled, (state, action) => {
        state.selected = action.payload;
      })
      .addCase(fetchStudent.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(updateStudent.pending, (state) => {
        state.saving = true;
      })
      .addCase(updateStudent.fulfilled, (state, action) => {
        state.saving = false;
        state.selected = action.payload.student;
        state.notice = action.payload.message;
      })
      .addCase(updateStudent.rejected, (state, action) => {
        state.saving = false;
        state.error = action.error.message;
      })
      .addCase(createStudent.fulfilled, (state, action) => {
        state.notice = action.payload.message;
      })
      .addCase(createStudent.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(fetchReportCard.fulfilled, (state, action) => {
        state.reportCard = action.payload;
      })
      .addCase(fetchReportCard.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(lookupStudent.fulfilled, (state, action) => {
        state.lookup = action.payload;
      })
      .addCase(lookupStudent.rejected, (state, action) => {
        state.error = action.error.message;
        state.lookup = null;
      });
  },
});

export const { clearSelected, clearLookup, clearNotice } = studentSlice.actions;

export const selectClasses = (state) => state.students.classes;
export const selectTotalStudents = (state) => state.students.totalStudents;
export const selectSelectedStudent = (state) => state.students.selected;
export const selectReportCard = (state) => state.students.reportCard;
export const selectLookup = (state) => state.students.lookup;

export default studentSlice.reducer;
