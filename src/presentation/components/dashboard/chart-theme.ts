import { useMemo } from 'react'
import { useThemeMode } from '../../context/theme-mode-context'

// Trend series hues: the dataviz reference palette's first three slots,
// validated on this app's white surface with every pair checked (worst CVD
// ΔE 9.2, normal-vision ΔE 24.0). Aqua is below 3:1 against the surface, so
// the trend always ships its legend, tooltip and hidden data table.
// Fixed per series and never reassigned, so a colour always means the same
// series. Defined as theme tokens in styles/theme.css; these are fallbacks.
const SERIES_TOKENS = {
  scheduled: ['--color-chart-scheduled', '#2a78d6'],
  checkedIn: ['--color-chart-checked-in', '#1baf7a'],
  noShow: ['--color-chart-no-show', '#eb6834'],
} as const

const INK_TOKENS = {
  accent: ['--color-admin-accent', '#0b8b84'],
  grid: ['--color-border-subtle', '#f1f5f9'],
  axis: ['--color-border', '#e2e8f0'],
  mutedText: ['--color-text-faint', '#94a3b8'],
  text: ['--color-text', '#0f172a'],
  surface: ['--color-surface', '#ffffff'],
} as const

export type ChartTheme = Record<keyof typeof SERIES_TOKENS | keyof typeof INK_TOKENS, string>

function readToken(styles: CSSStyleDeclaration, [token, fallback]: readonly [string, string]): string {
  return styles.getPropertyValue(token).trim() || fallback
}

function readChartTheme(): ChartTheme {
  const styles = getComputedStyle(document.documentElement)
  const entries = Object.entries({ ...SERIES_TOKENS, ...INK_TOKENS }).map(([name, token]) => [name, readToken(styles, token)])
  return Object.fromEntries(entries) as ChartTheme
}

// Recharts needs concrete colours rather than Tailwind classes, so the theme
// tokens are resolved from the document, again whenever the applied theme
// changes. Read during render: a switch puts `data-theme` on <html> before
// React re-renders (theme-mode-context `switchTheme`), so the charts get
// their new colours in the same frame as everything else
// (improve-calendar-scale-and-theme-switch design.md W4).
export function useChartTheme(): ChartTheme {
  const { resolved } = useThemeMode()
  // `resolved` is the trigger: the values come from the document.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(readChartTheme, [resolved])
}
