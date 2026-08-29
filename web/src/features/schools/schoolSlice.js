import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api, qs } from '../../api/client';

/* ----------------------------- School ERP ------------------------------ */

export const fetchOverview = createAsyncThunk('schools/overview', async () =>
  api('/api/v1/school/overview')
);

export const fetchKpis = createAsyncThunk('schools/kpis', async () =>
  api('/api/v1/school/analytics/kpis')
);

/** PAID / PENDING / NOT_PAID / SCHOLARSHIP — manager only. */
export const fetchTuitionStatus = createAsyncThunk('schools/tuitionStatus', async () =>
  api('/api/v1/school/analytics/tuition-status')
);

export const fetchPerformance = createAsyncThunk('schools/performance', async ({ exam } = {}) =>
  api(`/api/v1/school/analytics/performance${qs({ exam_name: exam })}`)
);

export const fetchClasses = createAsyncThunk('schools/classes', async () =>
  api('/api/v1/school/classes')
);

/** Subjects are catalogued per class *level* (e.g. "Class 10"), not class id. */
export const fetchSubjects = createAsyncThunk('schools/subjects', async ({ classLevel } = {}) =>
  api(`/api/v1/school/subjects${qs({ class_level: classLevel })}`)
);

/* --------------------------- State oversight --------------------------- */

export const fetchInstitutions = createAsyncThunk('schools/institutions', async () =>
  api('/api/v1/state/institutions')
);

export const fetchInstitution = createAsyncThunk('schools/institution', async (schoolId) =>
  api(`/api/v1/state/institutions/${schoolId}`)
);

export const fetchTeacher = createAsyncThunk('schools/teacher', async (teacherId) =>
  api(`/api/v1/state/teachers/${teacherId}`)
);

const schoolSlice = createSlice({
  name: 'schools',
  initialState: {
    overview: null,
    kpis: null,
    tuition: null,
    performance: null,
    classes: [],
    subjects: [],
    institutions: [],
    institution: null,
    teacher: null,
    activeSchoolId: null,
    activeTeacherId: null,
    status: 'idle',
    error: null,
  },
  reducers: {
    setActiveSchool(state, action) {
      state.activeSchoolId = action.payload;
    },
    clearTeacher(state) {
      state.activeTeacherId = null;
      state.teacher = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOverview.fulfilled, (state, action) => {
        state.overview = action.payload;
      })
      .addCase(fetchKpis.fulfilled, (state, action) => {
        state.kpis = action.payload;
      })
      .addCase(fetchTuitionStatus.fulfilled, (state, action) => {
        state.tuition = action.payload;
      })
      .addCase(fetchTuitionStatus.rejected, (state, action) => {
        state.tuition = { restricted: true, reason: action.error.message };
      })
      .addCase(fetchPerformance.fulfilled, (state, action) => {
        state.performance = action.payload;
      })
      .addCase(fetchClasses.fulfilled, (state, action) => {
        state.classes = action.payload.classes ?? [];
      })
      .addCase(fetchSubjects.fulfilled, (state, action) => {
        state.subjects = action.payload.subjects ?? [];
      })
      .addCase(fetchInstitutions.fulfilled, (state, action) => {
        state.institutions = action.payload.institutions;
        state.status = 'ready';
      })
      .addCase(fetchInstitution.fulfilled, (state, action) => {
        state.institution = action.payload;
      })
      .addCase(fetchTeacher.pending, (state, action) => {
        state.activeTeacherId = action.meta.arg;
      })
      .addCase(fetchTeacher.fulfilled, (state, action) => {
        state.teacher = action.payload;
      })
      .addCase(fetchInstitutions.rejected, (state, action) => {
        state.error = action.error.message;
      });
  },
});

export const { setActiveSchool, clearTeacher } = schoolSlice.actions;

export const selectInstitutions = (state) => state.schools.institutions;
export const selectInstitution = (state) => state.schools.institution;
export const selectTeacher = (state) => state.schools.teacher;
export const selectKpis = (state) => state.schools.kpis;
export const selectTuition = (state) => state.schools.tuition;
export const selectPerformance = (state) => state.schools.performance;
export const selectClasses = (state) => state.schools.classes;
export const selectSubjects = (state) => state.schools.subjects;

export default schoolSlice.reducer;
