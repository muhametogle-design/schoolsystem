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

/* ------------------------------------------------------------------ */
/* Refinement 1 — editable syllabus: plan CRUD, national-curriculum    */
/* topic lists and audited topic logging.                              */
/* ------------------------------------------------------------------ */

export const updateSyllabusPlan = createAsyncThunk(
  'syllabus/updatePlan',
  async ({ planId, ...body }) => api(`/api/v1/school/syllabus/plans/${planId}`, { method: 'PUT', body })
);

export const deleteSyllabusPlan = createAsyncThunk('syllabus/deletePlan', async ({ planId }) =>
  api(`/api/v1/school/syllabus/plans/${planId}`, { method: 'DELETE' })
);

export const fetchPlanDetail = createAsyncThunk('syllabus/planDetail', async (planId) =>
  api(`/api/v1/school/syllabus/plans/${planId}`)
);

export const fetchPlanTopics = createAsyncThunk('syllabus/topics', async (planId) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics`)
);

export const createPlanTopic = createAsyncThunk('syllabus/createTopic', async ({ planId, ...body }) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics`, { method: 'POST', body })
);

export const updatePlanTopic = createAsyncThunk('syllabus/updateTopic', async ({ planId, topicId, ...body }) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics/${topicId}`, { method: 'PUT', body })
);

export const deletePlanTopic = createAsyncThunk('syllabus/deleteTopic', async ({ planId, topicId }) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics/${topicId}`, { method: 'DELETE' })
);

export const logTopicsCovered = createAsyncThunk('syllabus/logCovered', async ({ planId, topicIds, note, coveredOn }) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics/log-covered`, {
    method: 'POST',
    body: { topic_ids: topicIds, note, covered_on: coveredOn },
  })
);

export const undoTopicsCovered = createAsyncThunk('syllabus/undoCovered', async ({ planId, topicIds }) =>
  api(`/api/v1/school/syllabus/plans/${planId}/topics/undo-covered`, {
    method: 'POST',
    body: { topic_ids: topicIds },
  })
);

export const deleteProgressEntry = createAsyncThunk(
  'syllabus/deleteProgressEntry',
  async ({ planId, entryId }) =>
    api(`/api/v1/school/syllabus/plans/${planId}/progress/${entryId}`, { method: 'DELETE' })
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
    planEntries: [],
    topics: [],
    topicsPlanId: null,
    topicsStatus: 'idle',
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
      state.planEntries = [];
    },
    closeTopics(state) {
      state.topics = [];
      state.topicsPlanId = null;
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
      })
      /* plan edit / delete */
      .addCase(updateSyllabusPlan.fulfilled, (state, action) => {
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.notice = `Plan updated — ${updated.total_units} units, midterm gate ${updated.midterm_target_pct}%`;
      })
      .addCase(updateSyllabusPlan.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(deleteSyllabusPlan.fulfilled, (state, action) => {
        state.rows = state.rows.filter((row) => row.plan_id !== action.payload.plan_id);
        state.notice = 'Syllabus plan deleted with its topics and progress history.';
      })
      .addCase(deleteSyllabusPlan.rejected, (state, action) => {
        state.error = action.error.message;
      })
      /* plan detail (progress history for override) */
      .addCase(fetchPlanDetail.fulfilled, (state, action) => {
        state.selectedPlan = action.payload.plan;
        state.planEntries = action.payload.entries ?? [];
      })
      .addCase(deleteProgressEntry.fulfilled, (state, action) => {
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.selectedPlan = updated;
        state.planEntries = state.planEntries.filter((entry) => entry.id !== action.payload.entry_id);
        state.notice = 'Progress entry removed — stats re-derived from history.';
      })
      .addCase(deleteProgressEntry.rejected, (state, action) => {
        state.error = action.error.message;
      })
      /* national-curriculum topic checklist */
      .addCase(fetchPlanTopics.pending, (state) => {
        state.topicsStatus = 'loading';
      })
      .addCase(fetchPlanTopics.fulfilled, (state, action) => {
        state.topics = action.payload.topics ?? [];
        state.topicsPlanId = action.payload.plan_id;
        state.topicsStatus = 'ready';
      })
      .addCase(fetchPlanTopics.rejected, (state, action) => {
        state.error = action.error.message;
        state.topicsStatus = 'ready';
      })
      .addCase(createPlanTopic.fulfilled, (state, action) => {
        state.topics.push(action.payload.topic);
        state.notice = 'Topic added to the curriculum list.';
      })
      .addCase(createPlanTopic.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(updatePlanTopic.fulfilled, (state, action) => {
        const topic = action.payload.topic;
        state.topics = state.topics.map((t) => (t.id === topic.id ? topic : t));
        state.notice = 'Topic updated.';
      })
      .addCase(updatePlanTopic.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(deletePlanTopic.fulfilled, (state, action) => {
        state.topics = state.topics.filter((t) => t.id !== action.payload.topic_id);
        state.notice = 'Topic removed.';
      })
      .addCase(deletePlanTopic.rejected, (state, action) => {
        state.error = action.error.message;
      })
      .addCase(logTopicsCovered.pending, (state) => {
        state.busy = true;
        state.error = null;
      })
      .addCase(logTopicsCovered.fulfilled, (state, action) => {
        state.busy = false;
        state.topics = (action.payload.topics ?? []).map((t) => t);
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.notice = `Logged ${action.payload.ticked} topic(s) — plan now ${updated.completion_pct}%`;
      })
      .addCase(logTopicsCovered.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      })
      .addCase(undoTopicsCovered.pending, (state) => {
        state.busy = true;
        state.error = null;
      })
      .addCase(undoTopicsCovered.fulfilled, (state, action) => {
        state.busy = false;
        state.topics = action.payload.topics ?? state.topics;
        const updated = action.payload.plan;
        state.rows = state.rows.map((row) => (row.plan_id === updated.plan_id ? updated : row));
        state.notice = `Reverted ${action.payload.unticked} topic(s) — plan now ${updated.completion_pct}%`;
      })
      .addCase(undoTopicsCovered.rejected, (state, action) => {
        state.busy = false;
        state.error = action.error.message;
      });
  },
});

export const { setClassLevel, clearNotice, clearSelectedPlan, closeTopics } = syllabusSlice.actions;

export const selectSyllabusRows = (state) => state.syllabus.rows;

export default syllabusSlice.reducer;
