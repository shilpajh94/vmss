// Fails on a breakpoint-less `col-span-<n>` (n >= 2). Inside a responsive
// grid like `grid-cols-1 sm:grid-cols-2`, such a span makes the browser add
// an implicit column on phones, packing every field two-up and squeezing
// them (fix-form-grid-collapse-on-phone). `col-span-full` spans whatever
// columns exist instead. Breakpoint-prefixed spans (`sm:col-span-2`) are
// fine; mark a genuinely fixed multi-column grid with `grid-span-ok` on the
// same line. Chained into `npm run lint`, like check-brand.mjs.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

// A class token `col-span-2`..`col-span-12` not preceded by a variant
// (`sm:`, `max-md:`, `[&>*]:`…) — i.e. at the start of the token.
const BARE_SPAN = /(?:^|[\s"'`{])col-span-(?:[2-9]|1[0-2])(?![\w-])/
const OPT_OUT = 'grid-span-ok'

function* walk(path) {
  if (statSync(path).isDirectory()) {
    for (const entry of readdirSync(path)) yield* walk(join(path, entry))
  } else if (/\.(tsx|ts|jsx|js)$/.test(path)) {
    yield path
  }
}

const offenders = []
for (const file of walk('src')) {
  readFileSync(file, 'utf8')
    .split('\n')
    .forEach((line, index) => {
      if (BARE_SPAN.test(line) && !line.includes(OPT_OUT)) offenders.push(`${file}:${index + 1}: ${line.trim()}`)
    })
}

if (offenders.length > 0) {
  console.error(
    `Breakpoint-less col-span found — use col-span-full (or a prefixed span like sm:col-span-2) so a one-column phone grid doesn't gain an implicit column:\n${offenders.join('\n')}`,
  )
  process.exit(1)
}
