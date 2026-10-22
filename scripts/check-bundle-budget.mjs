// Fails the build check when the JavaScript the landing page downloads up
// front exceeds its budget (app-performance "Public Pages Stay Within a
// Download Budget", design D-W10). Reads the built `dist/index.html` (its
// entry script and the modulepreload links Vite writes for that entry's
// static imports), follows each chunk's own static imports to be safe, and
// sums their gzipped sizes. Dynamic `import()` targets — the lazy pages —
// don't count. Run after `vite build`, as `npm run build:check` does.
// `vite.config.ts` is skip-worktree, so this reads index.html rather than a
// build manifest that would need a config change.
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { gzipSync } from 'node:zlib'

const BUDGET_KB = 350
const DIST = 'dist'

const indexPath = join(DIST, 'index.html')
if (!existsSync(indexPath)) {
  console.error('dist/index.html not found — run `vite build` first.')
  process.exit(1)
}

const html = readFileSync(indexPath, 'utf8')
const entryFiles = [
  ...html.matchAll(/<script[^>]+type="module"[^>]+src="\/([^"]+\.js)"/g),
  ...html.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="\/([^"]+\.js)"/g),
].map((match) => match[1])

// `import{a as b}from"./x.js"` / `import"./x.js"` — not `import("./x.js")`.
const STATIC_IMPORT = /(?:^|[;\s}])import\s*(?:[\w$*{}\s,]+?\s*from\s*)?["'](\.{1,2}\/[^"']+\.js)["']/g

const seen = new Set()
const queue = [...entryFiles]
while (queue.length > 0) {
  const file = queue.shift()
  if (seen.has(file)) continue
  seen.add(file)
  const source = readFileSync(join(DIST, file), 'utf8')
  const directory = file.slice(0, file.lastIndexOf('/') + 1)
  for (const match of source.matchAll(STATIC_IMPORT)) {
    queue.push(new URL(match[1], `file:///${directory}`).pathname.slice(1))
  }
}

const sizes = [...seen].map((file) => ({ file, kb: gzipSync(readFileSync(join(DIST, file))).length / 1024 }))
sizes.sort((a, b) => b.kb - a.kb)
const totalKb = sizes.reduce((sum, { kb }) => sum + kb, 0)

for (const { file, kb } of sizes) console.log(`  ${kb.toFixed(2).padStart(8)} kB  ${file}`)
console.log(`Landing page initial JS: ${totalKb.toFixed(2)} kB gzipped (budget ${BUDGET_KB} kB).`)

if (totalKb > BUDGET_KB) {
  console.error(`Over budget by ${(totalKb - BUDGET_KB).toFixed(2)} kB.`)
  process.exit(1)
}
