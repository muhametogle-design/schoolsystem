import { useEffect } from 'react';
import { useDispatch, useSelector } from 'react-redux';
import {
  refreshSaverDetection,
  selectSaverActive,
} from '../features/ui/uiSlice';

/** True when the low-bandwidth Data Saver mode is resolved active. */
export function useDataSaver() {
  return useSelector(selectSaverActive);
}

/**
 * Watches device network signals (Save-Data hint, effectiveType 2G/3G) and
 * re-resolves the saver whenever they change while the preference is 'auto'.
 */
export function useDataSaverDetection() {
  const dispatch = useDispatch();
  const pref = useSelector((state) => state.ui.pref);

  useEffect(() => {
    if (pref !== 'auto') return undefined;
    const refresh = () => dispatch(refreshSaverDetection());
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    conn?.addEventListener?.('change', refresh);
    return () => conn?.removeEventListener?.('change', refresh);
  }, [pref, dispatch]);
}
