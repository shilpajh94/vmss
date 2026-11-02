// Fails on a hard-coded colour in a staff/admin component: an arbitrary hex
// colour class (`bg-[#f8fafc]`, `text-[#475569]`, `border-[#cbd5e1]`…) or a
// solid `bg-white`/`bg-black`. Those don't follow the dark theme, so they show
// up as white panels or unreadable text in it
// (add-calendar-colours-and-theme-modes design.md D3). Use a theme token
// instead — `surface`, `border-strong`, `text-secondary`, a fixed `sidebar-*`
// / `knob` / `ink` token when the colour must not change. Opacity overlays
// (`bg-black/40`) are fine. The public pages always render light, so their
// directories are exempt; mark a genuine exception with `theme-fixed` on the
// same line. Chained into `npm run lint`, like check-brand.mjs.
//
// Also fails on `bg-bg` outside the page canvas: it is white in light, so it
// passes for a card's colour there, but near-black in dark, where a control
// or inset on a card turns into a hole (fix-dark-theme-rendering design.md
// D2). Use `surface-inset` (insets, pills, icon tiles) or `surface` (a
// bordered button on a card). Canvas layouts are listed below; mark a
// one-off canvas element with a `/* page-canvas */` comment on its line.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const ROOT = 'src/presentation'
// Always-light pages (theme-mode "Public pages always render in the light theme").
const EXEMPT_DIRS = ['pages/visitor-', 'pages/staff-login', 'pages/staff-sso-login'].map((dir) => join(ROOT, dir))
const HEX_CLASS = /(?:^|[\s"'`{:])[\w-]*-\[#[0-9a-fA-F]{3,8}\]/
const SOLID_WHITE_BLACK = /(?:^|[\s"'`{:])bg-(?:white|black)(?![\w/-])/
const OPT_OUT = 'theme-fixed'
// Layouts whose `bg-bg` is the page canvas itself.
const CANVAS_FILES = [
  'components/AppShell.tsx',
  'components/PublicLayout.tsx',
  'components/invitation-board/ResponsiveBoard.tsx',
  'pages/not-found/not-found.tsx',
  'pages/not-found/route-error.tsx',
].map((file) => join(ROOT, file))
const CANVAS_BG = /(?:^|[\s"'`{:])bg-bg(?![\w/-])/
const CANVAS_MARK = 'page-canvas'

function* walk(path) {
  if (statSync(path).isDirectory()) {
    for (const entry of readdirSync(path)) yield* walk(join(path, entry))
  } else if (/\.(tsx|ts|jsx|js)$/.test(path)) {
    yield path
  }
}

const offenders = []
const canvasOffenders = []
for (const file of walk(ROOT)) {
  if (EXEMPT_DIRS.some((dir) => file.startsWith(dir))) continue
  const isCanvasFile = CANVAS_FILES.includes(file)
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, index) => {
      if ((HEX_CLASS.test(line) || SOLID_WHITE_BLACK.test(line)) && !line.includes(OPT_OUT)) {
        offenders.push(`${file}:${index + 1}: ${line.trim()}`)
      }
      if (!isCanvasFile && CANVAS_BG.test(line) && !line.includes(CANVAS_MARK)) {
        canvasOffenders.push(`${file}:${index + 1}: ${line.trim()}`)
      }
    })
}

if (offenders.length > 0) {
  console.error(`Hard-coded colour found — use a theme token so it follows the dark theme:\n${offenders.join('\n')}`)
}
if (canvasOffenders.length > 0) {
  console.error(
    `\`bg-bg\` is the page canvas; on a card use \`bg-surface-inset\` (insets, pills, icon tiles) or \`bg-surface\` (bordered buttons):\n${canvasOffenders.join('\n')}`,
  )
}
if (offenders.length > 0 || canvasOffenders.length > 0) process.exit(1)
