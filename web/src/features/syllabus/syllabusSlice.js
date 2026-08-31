import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/**
 * Module 2 — syllabus completion tracker state (Classes 1-12).
 */

export const fetchSyllabusSummary = createAsyncThunk(
  'syllabus/summary',
  async ({ classLevel, term } = {}) =>
    api(`/api/v1/school/syllabus/summary${qs({ class_level: classLevel, term })}`)
);

export const fetchSyllabusPlan = createAsyncThunk('syllabus/plan', async (planId) =>
  api(`/api/v1/school/syllabus/plans/${planId}`)
);

export const recordSyllabusProgress = createAsyncThunk(
  'syllabus/recordProgress',
  async ({ planId, unitsAfter, note, entryDate }) =>
    api(`/api/v1/school/syllabus/plans/${planId}/progress`, {
      method: 'POST',
      body: { units_after: unitsAfter, note, entry_date: entryDate },
    })
);

export const updateBenchmarks = createAsyncThunk(
  'syllabus/benchmarks',
  async ({ planId, midtermTargetPct, finalTargetPct, midtermDate }) =>
    api(`/api/v1/school/syllabus/plans/${planId}/benchmarks`, {
      method: 'PUT',
      body: {
        midterm_target_pct: midtermTargetPct,
        final_target_pct: finalTargetPct,
        midterm_date: midtermDate,
      },
    })
);

const syllabusSlice = createSlice({
  name: 'syllabus',
  initialState: {
    rows: [],
    counts: { 'On Track': 0, Ahead: 0, 'Behind Schedule': 0 },
    averageCompletionPct: 0,
    flaggedCount: 0,
    classLevelsAvailable: [],
    allClassLevels: [],
    classLevel: null,
    selectedPlan: null,
    status: 'idle',
    busy: false,
    error: null,
    notice: null,
  },
  reducers: {
    setClassLevel(state, action) {
      state.classLevel = action.payload;
    },
    clearNotice(state) {
      state.notice = null;
      state.error = null;
    },
    clearSelectedPlan(state) {
      state.selectedPlan = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchSyllabusSummary.pending, (state) => {
        state.status = 'loading';
      })
      .addCase(fetchSyllabusSummary.fulfilled, (state, action) => {
        const payload = action.payload;
        state.rows = payload.rows ?? [];
        state.counts = payload.counts ?? state.counts;
        state.averageCompletionPct = payload.average_completion_pct ?? 0;
        state.flaggedCount = payload.flagged_count ?? 0;
        state.classLevelsAvailable = payload.class_levels_available ?? [];
        state.allClassLevels = payload.all_class_levels ?? [];
        state.status = 'ready';
      })
      .addCase(fetchSyllabusSummary.rejected, (state, action) => {
        state.error = action.error.message;
        state.status = 'ready';
      })
      .addCase(fetchSyllabusPlan.fulfilled, (state, action) => {
        state.selectedPlan = action.payload;
      })
      .addCase(recordSyllabusProgress.pending, (state) => {
        state.busy = true;
        state.error = null;
      })
      .addCase(recordSyllabusProgress.fulfilled, (state, action) => {
        state.busy = false;
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.notice = `Progress recorded — ${updated.completion_pct}% (${updated.status})`;
      })
      .addCase(recordSyllabusProgress.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(updateBenchmarks.fulfilled, (state, action) => {
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.notice = `Benchmarks updated — midterm ${updated.midterm_target_pct}%, final ${updated.final_target_pct}%`;
      })
      .addCase(updateBenchmarks.rejected, (state, action) => {
        state.error = action.error.message;
      });
  },
});

export const { setClassLevel, clearNotice, clearSelectedPlan } = syllabusSlice.actions;

export const selectSyllabusRows = (state) => state.syllabus.rows;

export default syllabusSlice.reducer;
