import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api } from '../../api/client';

/**
 * Refinement 5 — Role-gated photo & media management engine.
 *
 * The upload/delete thunks below are only ever dispatched by UI that has
 * already checked the School Manager role, and the backend re-enforces the
 * gate (403 for teachers, FIREWALL 403 for state roles). Teachers and
 * students consume photo_data read-only on profile payloads.
 */

export const uploadStudentPhoto = createAsyncThunk(
  'media/uploadStudentPhoto',
  async ({ key, photoData }) =>
    api(`/api/v1/school/media/students/${encodeURIComponent(key)}/photo`, {
      method: 'PUT',
      body: { photo_data: photoData },
    })
);

export const deleteStudentPhoto = createAsyncThunk('media/deleteStudentPhoto', async ({ key }) =>
  api(`/api/v1/school/media/students/${encodeURIComponent(key)}/photo`, { method: 'DELETE' })
);

export const uploadTeacherPhoto = createAsyncThunk(
  'media/uploadTeacherPhoto',
  async ({ teacherId, photoData }) =>
    api(`/api/v1/school/media/teachers/${teacherId}/photo`, {
      method: 'PUT',
      body: { photo_data: photoData },
    })
);

export const deleteTeacherPhoto = createAsyncThunk('media/deleteTeacherPhoto', async ({ teacherId }) =>
  api(`/api/v1/school/media/teachers/${teacherId}/photo`, { method: 'DELETE' })
);

const mediaSlice = createSlice({
  name: 'media',
  initialState: { busy: false, error: null, notice: null },
  reducers: {
    clearMediaNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    const pending = (state) => {
      state.busy = true;
      state.error = null;
      state.notice = null;
    };
    const rejected = (state, action) => {
      state.busy = false;
      state.error = action.error.message;
    };
    builder
      .addCase(uploadStudentPhoto.pending, pending)
      .addCase(uploadStudentPhoto.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = action.payload?.message ?? 'Photo updated.';
      })
      .addCase(uploadStudentPhoto.rejected, rejected)
      .addCase(deleteStudentPhoto.pending, pending)
      .addCase(deleteStudentPhoto.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = action.payload?.message ?? 'Photo removed.';
      })
      .addCase(deleteStudentPhoto.rejected, rejected)
      .addCase(uploadTeacherPhoto.pending, pending)
      .addCase(uploadTeacherPhoto.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = action.payload?.message ?? 'Staff photo updated.';
      })
      .addCase(uploadTeacherPhoto.rejected, rejected)
      .addCase(deleteTeacherPhoto.pending, pending)
      .addCase(deleteTeacherPhoto.fulfilled, (state, action) => {
        state.busy = false;
        state.notice = action.payload?.message ?? 'Staff photo removed.';
      })
      .addCase(deleteTeacherPhoto.rejected, rejected);
  },
});

export const { clearMediaNotice } = mediaSlice.actions;

export const selectMediaBusy = (state) => state.media.busy;
export const selectMediaError = (state) => state.media.error;
export const selectMediaNotice = (state) => state.media.notice;

export default mediaSlice.reducer;
