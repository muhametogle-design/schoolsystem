import { useEffect } from 'react';
import { useSelector } from 'react-redux';
import { selectDraft } from '../features/design/designSlice';

/**
 * Refinement 7 — instant, root-level theme application.
 *
 * Watching the design draft, this hook rewrites the accent CSS custom
 * properties on `:root` so every button, badge, progress bar and border that
 * references them updates in the same frame — no re-render cascade required.
 * Typography is swapped through `data-theme-font` on <html> (see styles.css).
 */

/** Mix a #rrggbb colour with white (`tint`) or black (`shade`) by ratio p. */
function mix(hex, p, target) {
  const n = parseInt(hex.slice(1), 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  const t = target === 'white' ? 255 : 0;
  const channel = (c) => Math.round(c + (t - c) * p);
  const to2 = (c) => channel(c).toString(16).padStart(2, '0');
  return `#${to2(r)}${to2(g)}${to2(b)}`;
}

export const accentShades = (hex) => ({
  base: hex,
  strong: mix(hex, 0.18, 'black'), // hover states
  deep: mix(hex, 0.34, 'black'), // gradients / pressed
  border: mix(hex, 0.55, 'white'), // soft borders / focus rings
  soft: mix(hex, 0.92, 'white'), // tinted surfaces
});

const FONT_STACKS = {
  sans: '"Inter", "Segoe UI", system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif',
  serif: 'Georgia, "Times New Roman", "Palatino Linotype", "Book Antiqua", serif',
  mono: '"SFMono-Regular", "JetBrains Mono", Menlo, Consolas, "Liberation Mono", monospace',
};

export function useDesignSystem() {
  const draft = useSelector(selectDraft);

  useEffect(() => {
    const root = document.documentElement;
    const shades = accentShades(draft.accent);

    // Global accent system: buttons, badges, progress bars, borders all read
    // these tokens — so one swatch click re-skins the entire platform.
    const vars = {
      '--brand-600': shades.base,
      '--brand-700': shades.strong,
      '--brand-200': shades.border,
      '--brand-50': shades.soft,
      '--accent': shades.base,
      '--accent-ink': shades.deep,
      '--accent-soft': shades.soft,
      '--info': shades.base,
      '--info-bg': shades.soft,
      '--focus-ring': shades.border,
    };
    Object.entries(vars).forEach(([key, value]) => root.style.setProperty(key, value));

    // Typography preset.
    root.dataset.themeFont = draft.font;
    root.style.setProperty('--font', FONT_STACKS[draft.font] ?? FONT_STACKS.sans);

    return () => {
      Object.keys(vars).forEach((key) => root.style.removeProperty(key));
      delete root.dataset.themeFont;
      root.style.removeProperty('--font');
    };
  }, [draft.accent, draft.font]);
}
