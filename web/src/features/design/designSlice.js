import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api } from '../../api/client';

/**
 * Refinements 7-8 — Dynamic design system, layout blocks & publishing.
 *
 * Two-tier configuration model mirroring the Publishing Control Bar:
 *
 *   live    — the theme stored in the production database, read back by every
 *             user in the tenant (GET /api/v1/school/design-config).
 *   draft   — the manager's working copy editing in the Design & Layout
 *             drawer; applied on-screen instantly (CSS variables) so changes
 *             preview in real time.
 *
 *   Save Progress  → persists `draft` to localStorage only (draft survives
 *                    reloads but never reaches other users).
 *   Push Live      → PUT to the API; on success live = draft for everyone and
 *                    the local draft marker is cleared.
 */

const DRAFT_KEY = 'ne_emis_design_draft';

export const ACCENT_PALETTE = [
  { hex: '#2563eb', name: 'Royal Blue' },
  { hex: '#059669', name: 'Emerald Green' },
  { hex: '#d97706', name: 'Amber Ochre' },
  { hex: '#dc2626', name: 'Crimson Red' },
  { hex: '#7c3aed', name: 'Violet Purple' },
];

export const FONT_PRESETS = [
  { id: 'sans', name: 'System Sans-Serif', sample: 'Aa — clean & modern' },
  { id: 'serif', name: 'Classic Serif', sample: 'Aa — formal & editorial' },
  { id: 'mono', name: 'Monospace Technical', sample: 'Aa — precise & data-led' },
];

export const BLOCK_DEFS = [
  { id: 'profileCard', name: 'Profile Card', hint: 'School identity snapshot on the dashboard' },
  { id: 'academicOverview', name: 'Academic Overview', hint: 'Grade distribution & subject averages' },
  { id: 'attendanceSummary', name: 'Attendance Summary', hint: '14-day attendance trend card' },
  { id: 'biometricsBadge', name: 'Biometrics Badge', hint: 'Biometric enrolment status chip card' },
];

const DEFAULT_DRAFT = {
  accent: ACCENT_PALETTE[0].hex,
  font: 'sans',
  blocks: Object.fromEntries(BLOCK_DEFS.map((block) => [block.id, true])),
};

function readLocalDraft() {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return {
      accent: ACCENT_PALETTE.some((c) => c.hex === parsed.accent) ? parsed.accent : DEFAULT_DRAFT.accent,
      font: FONT_PRESETS.some((f) => f.id === parsed.font) ? parsed.font : DEFAULT_DRAFT.font,
      blocks: { ...DEFAULT_DRAFT.blocks, ...(parsed.blocks ?? {}) },
    };
  } catch {
    return null;
  }
}

function writeLocalDraft(draft) {
  try {
    window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* storage unavailable — the in-memory draft still previews */
  }
}

function clearLocalDraft() {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

export const fetchDesignConfig = createAsyncThunk('design/fetch', async () =>
  api('/api/v1/school/design-config')
);

export const publishDesignConfig = createAsyncThunk('design/publish', async (draft) =>
  api('/api/v1/school/design-config', { method: 'PUT', body: draft })
);

const savedDraft = readLocalDraft();

const designSlice = createSlice({
  name: 'design',
  initialState: {
    live: null, // server-published configuration
    draft: savedDraft ?? { ...DEFAULT_DRAFT, blocks: { ...DEFAULT_DRAFT.blocks } },
    dirty: Boolean(savedDraft), // unsaved-in-production changes
    localSaved: Boolean(savedDraft), // a Save Progress snapshot exists locally
    status: 'idle',
    publishStatus: 'idle',
    drawerOpen: false,
    mobilePreview: false,
    confirmPublish: false,
    notice: null,
    error: null,
  },
  reducers: {
    setAccent(state, action) {
      state.draft.accent = action.payload;
      state.dirty = true;
    },
    setFont(state, action) {
      state.draft.font = action.payload;
      state.dirty = true;
    },
    toggleBlock(state, action) {
      const block = action.payload;
      state.draft.blocks[block] = !state.draft.blocks[block];
      state.dirty = true;
    },
    saveDraftLocal(state) {
      writeLocalDraft(state.draft);
      state.localSaved = true;
      state.notice = 'Draft saved on this device — other users still see the live theme.';
    },
    discardDraft(state) {
      clearLocalDraft();
      const base = state.live ?? DEFAULT_DRAFT;
      state.draft = { accent: base.accent, font: base.font, blocks: { ...base.blocks } };
      state.dirty = false;
      state.localSaved = false;
      state.notice = 'Draft discarded — the live theme is back on screen.';
    },
    setDrawerOpen(state, action) {
      state.drawerOpen = action.payload;
    },
    setMobilePreview(state, action) {
      state.mobilePreview = action.payload;
    },
    setConfirmPublish(state, action) {
      state.confirmPublish = action.payload;
    },
    clearDesignNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchDesignConfig.fulfilled, (state, action) => {
        state.status = 'ready';
        const cfg = action.payload?.config;
        state.live = cfg
          ? { accent: cfg.accent, font: cfg.font, blocks: { ...cfg.blocks }, published_at: cfg.published_at, published_by: cfg.published_by }
          : null;
        // A locally saved draft always wins on screen until it is pushed live
        // or discarded — that is the whole point of the two-tier flow.
        if (state.localSaved) return;
        if (state.live) {
          state.draft = { accent: state.live.accent, font: state.live.font, blocks: { ...state.live.blocks } };
          state.dirty = false;
        }
      })
      .addCase(fetchDesignConfig.rejected, (state) => {
        state.status = 'failed';
      })
      .addCase(publishDesignConfig.pending, (state) => {
        state.publishStatus = 'publishing';
        state.error = null;
      })
      .addCase(publishDesignConfig.fulfilled, (state, action) => {
        state.publishStatus = 'published';
        const cfg = action.payload?.config;
        if (cfg) {
          state.live = { accent: cfg.accent, font: cfg.font, blocks: { ...cfg.blocks }, published_at: cfg.published_at, published_by: cfg.published_by };
          state.draft = { accent: cfg.accent, font: cfg.font, blocks: { ...cfg.blocks } };
        }
        state.dirty = false;
        state.localSaved = false;
        state.confirmPublish = false;
        clearLocalDraft();
        state.notice = action.payload?.message ?? 'Design system pushed live.';
      })
      .addCase(publishDesignConfig.rejected, (state, action) => {
        state.publishStatus = 'failed';
        state.confirmPublish = false;
        state.error = action.error.message;
      });
  },
});

export const {
  setAccent,
  setFont,
  toggleBlock,
  saveDraftLocal,
  discardDraft,
  setDrawerOpen,
  setMobilePreview,
  setConfirmPublish,
  clearDesignNotice,
} = designSlice.actions;

export const selectDraft = (state) => state.design.draft;
export const selectLive = (state) => state.design.live;
export const selectBlocks = (state) => state.design.draft.blocks;
export const selectIsDirty = (state) => state.design.dirty;
export const selectDrawerOpen = (state) => state.design.drawerOpen;
export const selectMobilePreview = (state) => state.design.mobilePreview;
export const selectConfirmPublish = (state) => state.design.confirmPublish;
export const selectPublishStatus = (state) => state.design.publishStatus;

export default designSlice.reducer;
