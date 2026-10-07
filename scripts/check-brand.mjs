// Fails when the retired product name reappears in shipped code
// (brand-identity capability: "VisitorPass" SHALL NOT appear in the portal).
// Chained into `npm run lint` so a copy-pasted old snippet can't slip back in.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const RETIRED_NAME = /VisitorPass/
const ROOTS = ['src', 'public', 'index.html']
const TEXT_FILE = /\.(tsx?|jsx?|mjs|css|html|json|svg|md)$/

function* walk(path) {
  if (statSync(path).isDirectory()) {
    for (const entry of readdirSync(path)) yield* walk(join(path, entry))
  } else if (TEXT_FILE.test(path)) {
    yield path
  }
}

const offenders = []
for (const root of ROOTS) {
  for (const file of walk(root)) {
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, index) => {
        if (RETIRED_NAME.test(line)) offenders.push(`${file}:${index + 1}: ${line.trim()}`)
      })
  }
}

if (offenders.length > 0) {
  console.error(`Retired brand name found — use BRAND_NAME from src/presentation/brand.ts:\n${offenders.join('\n')}`)
  process.exit(1)
}
