import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { api } from '../../api/client';

/**
 * Dynamic Design System engine.
 *
 * - `published` mirrors the tenant's live configuration from the API.
 * - `draft` is the manager's local working copy ('Save Progress' persists it
 *   to localStorage only — nothing reaches live users until 'Push Live').
 * - CSS variables are applied at :root by applyDesignToDom(), so one change
 *   recolours every button, badge, progress bar and border simultaneously.
 */

export const ACCENT_CHOICES = ['#2563eb', '#059669', '#d97706', '#dc2626', '#7c3aed'];

export const FONT_CHOICES = [
  { id: 'sans', label: 'System Sans-Serif', stack: "'Inter', 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif" },
  { id: 'serif', label: 'Classic Serif', stack: "Georgia, 'Iowan Old Style', 'Times New Roman', Times, serif" },
  { id: 'mono', label: 'Monospace Technical', stack: "'SFMono-Regular', 'JetBrains Mono', Menlo, Consolas, monospace" },
];

export const BLOCK_DEFS = [
  { id: 'profileCard', label: 'Profile Card' },
  { id: 'academicOverview', label: 'Academic Overview' },
  { id: 'attendanceSummary', label: 'Attendance Summary' },
  { id: 'biometricsBadge', label: 'Biometrics Badge' },
];

export const DEFAULT_DESIGN = {
  accent: '#2563eb',
  font: 'sans',
  blocks: { profileCard: true, academicOverview: true, attendanceSummary: true, biometricsBadge: true },
};

const DRAFT_KEY = 'ne_emis_design_draft';

const readDraft = () => {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const writeDraft = (draft) => {
  try {
    if (draft) window.localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    else window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* private-mode browsers: draft survives in memory only */
  }
};

/** Push the active configuration into :root CSS variables. */
export function applyDesignToDom(config) {
  const root = document.documentElement;
  const accent = config?.accent ?? DEFAULT_DESIGN.accent;
  const font = FONT_CHOICES.find((f) => f.id === (config?.font ?? 'sans')) ?? FONT_CHOICES[0];
  root.style.setProperty('--ui-accent', accent);
  root.style.setProperty('--ui-accent-soft', `${accent}1f`); // 12% alpha wash
  root.style.setProperty('--font', font.stack);
}

export const fetchUiConfig = createAsyncThunk('design/fetch', async () => {
  return api('/api/v1/school/ui-config');
});

export const publishUiConfig = createAsyncThunk('design/publish', async (config) => {
  const data = await api('/api/v1/school/ui-config', { method: 'PUT', body: config });
  return data.config;
});

const designSlice = createSlice({
  name: 'design',
  initialState: {
    published: DEFAULT_DESIGN,
    draft: readDraft(),
    canPublish: false,
    drawerOpen: false,
    mobileSim: false,
    dirty: Boolean(readDraft()),
    draftSavedAt: null,
    publishing: false,
    notice: null,
    error: null,
  },
  reducers: {
    toggleDrawer(state, action) {
      state.drawerOpen = action.payload ?? !state.drawerOpen;
    },
    toggleMobileSim(state) {
      state.mobileSim = !state.mobileSim;
    },
    updateDraft(state, action) {
      const base = state.draft ?? state.published ?? DEFAULT_DESIGN;
      state.draft = {
        ...base,
        ...action.payload,
        blocks: { ...base.blocks, ...(action.payload.blocks ?? {}) },
      };
      state.dirty = true;
      state.notice = null;
    },
    saveDraft(state) {
      writeDraft(state.draft);
      state.draftSavedAt = new Date().toISOString();
      state.notice = 'Draft saved locally — live users are unaffected until you push.';
    },
    discardDraft(state) {
      state.draft = null;
      state.dirty = false;
      writeDraft(null);
      state.notice = 'Draft discarded — reverted to the live design.';
    },
    clearDesignNotice(state) {
      state.notice = null;
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchUiConfig.fulfilled, (state, action) => {
        state.published = { ...DEFAULT_DESIGN, ...action.payload.config };
        state.canPublish = Boolean(action.payload.can_publish);
      })
      .addCase(publishUiConfig.pending, (state) => {
        state.publishing = true;
        state.error = null;
      })
      .addCase(publishUiConfig.fulfilled, (state, action) => {
        state.publishing = false;
        state.published = { ...DEFAULT_DESIGN, ...action.payload };
        state.draft = null;
        state.dirty = false;
        writeDraft(null);
        state.notice = 'Design pushed live — every user session now renders this configuration.';
      })
      .addCase(publishUiConfig.rejected, (state, action) => {
        state.publishing = false;
        state.error = action.error.message;
      });
  },
});

export const {
  toggleDrawer,
  toggleMobileSim,
  updateDraft,
  saveDraft,
  discardDraft,
  clearDesignNotice,
} = designSlice.actions;

/** The configuration currently rendered: the manager's draft wins locally. */
export const selectActiveDesign = (state) =>
  state.design.draft ?? state.design.published ?? DEFAULT_DESIGN;

export const selectBlocks = (state) => selectActiveDesign(state).blocks ?? DEFAULT_DESIGN.blocks;

export default designSlice.reducer;
