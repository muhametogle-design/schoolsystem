import { createSlice } from '@reduxjs/toolkit';

/**
 * Module 3 — Low-bandwidth "Data Saver" mode.
 *
 * Three user preferences resolved against device signals:
 *   'auto' — honour Network Information API (Save-Data hint, 2G/3G classes)
 *   'on'   — forced on
 *   'off'  — forced off
 *
 * The resolved mode is written to <html data-saver="1"> so plain CSS can strip
 * animations/gradients/shadows and components can swap charts for text
 * metrics. The preference survives reloads in localStorage.
 */

const PREF_KEY = 'ne_emis_data_saver';
const SLOW_NETWORKS = new Set(['slow-2g', '2g', '3g']);

function readPref() {
  try {
    const value = window.localStorage.getItem(PREF_KEY);
    return value === 'on' || value === 'off' || value === 'auto' ? value : 'auto';
  } catch {
    return 'auto';
  }
}

function deviceWantsSaver() {
  try {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!conn) return false;
    if (conn.saveData) return true;
    return SLOW_NETWORKS.has(String(conn.effectiveType || '').toLowerCase());
  } catch {
    return false;
  }
}

export function resolveSaver(pref) {
  if (pref === 'on') return { effective: 'on', reason: 'Manually enabled' };
  if (pref === 'off') return { effective: 'off', reason: null };
  return deviceWantsSaver()
    ? { effective: 'on', reason: 'Slow network detected (2G/3G or Save-Data)' }
    : { effective: 'off', reason: null };
}

function applyToDocument(effective) {
  try {
    if (effective === 'on') document.documentElement.dataset.saver = '1';
    else delete document.documentElement.dataset.saver;
  } catch {
    /* non-DOM environment — nothing to do */
  }
}

const savedPref = readPref();
const initialResolve = resolveSaver(savedPref);
applyToDocument(initialResolve.effective);

const uiSlice = createSlice({
  name: 'ui',
  initialState: {
    pref: savedPref,
    effective: initialResolve.effective,
    reason: initialResolve.reason,
  },
  reducers: {
    setSaverPref(state, action) {
      const pref = action.payload === 'on' || action.payload === 'off' || action.payload === 'auto'
        ? action.payload
        : 'auto';
      state.pref = pref;
      const resolved = resolveSaver(pref);
      state.effective = resolved.effective;
      state.reason = resolved.effective === 'on' ? (pref === 'on' ? 'Manually enabled' : resolved.reason) : null;
      applyToDocument(resolved.effective);
      try {
        window.localStorage.setItem(PREF_KEY, pref);
      } catch {
        /* storage may be unavailable — in-memory preference still applies */
      }
    },
    refreshSaverDetection(state) {
      const resolved = resolveSaver(state.pref);
      state.effective = resolved.effective;
      state.reason = resolved.effective === 'on' ? (state.pref === 'on' ? 'Manually enabled' : resolved.reason) : null;
      applyToDocument(resolved.effective);
    },
  },
});

export const { setSaverPref, refreshSaverDetection } = uiSlice.actions;

export const selectSaverPref = (state) => state.ui.pref;
export const selectSaverActive = (state) => state.ui.effective === 'on';
export const selectSaverReason = (state) => state.ui.reason;

export default uiSlice.reducer;
