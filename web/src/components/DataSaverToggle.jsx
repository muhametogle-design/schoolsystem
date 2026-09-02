import { useDispatch, useSelector } from 'react-redux';
import { selectSaverPref, setSaverPref } from '../features/ui/uiSlice';

const NEXT = { off: 'auto', auto: 'on', on: 'off' };
const LABEL = {
  off: 'Data saver: off',
  auto: 'Data saver: auto (2G/3G)',
  on: 'Data saver: on',
};

/**
 * Module 3 — global low-bandwidth toggle (topbar, both portals).
 *
 * Cycles off → auto → on. 'auto' follows the device's Network Information API
 * (Save-Data hint or a 2G/3G effective type). The resolved mode drives the
 * html[data-saver] CSS hooks and swaps charts for text metrics.
 */
export default function DataSaverToggle() {
  const dispatch = useDispatch();
  const pref = useSelector(selectSaverPref);

  return (
    <button
      type="button"
      className={`saver-toggle saver-toggle--${pref}`}
      onClick={() => dispatch(setSaverPref(NEXT[pref] ?? 'auto'))}
      title="Optimise the interface for low-bandwidth 2G/3G networks: removes animations, gradients and chart graphics in favour of raw text metrics."
      aria-pressed={pref === 'on'}
    >
      <span className="saver-toggle__dot" aria-hidden="true" />
      {LABEL[pref]}
    </button>
  );
}
