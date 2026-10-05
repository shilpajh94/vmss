// Verifies the effective-form parser tolerates older and unknown data
// (tolerate-unknown-form-field-types design.md Decision 3). The repo has no
// unit-test runner, so this is a standalone check:
//
//   npx tsx scripts/check-effective-form.ts [apiBaseUrl]
//
// It always parses the committed old-shape fixture (a snapshot published
// before `hideLabel`/group `visibilityCondition` existed, containing a
// removed `signature_pad` field). When an API base URL is given, e.g.
// https://vmss-new-api.ddev.site:8443, it also parses the live
// `GET /api/v1/form-builder/effective`. Exits non-zero on any failure.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { EffectiveFormStepListResponseSchema } from '../src/domain/entities/form-builder-schema.ts'

const SUPPORTED = new Set<string>([
  'text', 'email', 'phone', 'number', 'dropdown_select', 'date_picker', 'time_picker', 'toggle_switch',
  'checkbox_list', 'checkbox_single', 'radio_button', 'file_upload', 'textarea', 'static_text',
])

let failures = 0

function check(label: string, body: unknown, expectDropped: string[]): void {
  const result = EffectiveFormStepListResponseSchema.safeParse(body)
  if (!result.success) {
    failures += 1
    console.error(`FAIL ${label}: did not parse`)
    for (const issue of result.error.issues.slice(0, 10)) console.error(`  ${issue.path.join('.')}: ${issue.message}`)
    return
  }
  const fields = result.data.data.flatMap((step) => step.fields)
  const problems = [
    ...fields.filter((field) => !SUPPORTED.has(field.fieldType)).map((field) => `unsupported type ${field.fieldType} kept`),
    ...fields.filter((field) => typeof field.hideLabel !== 'boolean').map((field) => `${field.key} has no hideLabel`),
    ...result.data.data
      .flatMap((step) => step.groups)
      .filter((group) => group.visibilityCondition === undefined)
      .map((group) => `group ${group.key} has no visibilityCondition`),
    ...expectDropped.filter((key) => fields.some((field) => field.key === key)).map((key) => `${key} was not dropped`),
  ]
  if (problems.length > 0) {
    failures += 1
    console.error(`FAIL ${label}:`)
    for (const problem of problems) console.error(`  ${problem}`)
    return
  }
  console.log(`ok   ${label}: ${result.data.data.length} steps, ${fields.length} fields`)
}

const fixturePath = fileURLToPath(new URL('./fixtures/effective-form-old-shape.json', import.meta.url))
check('old-shape fixture', JSON.parse(readFileSync(fixturePath, 'utf8')), ['terms_conditions'])

const apiBase = process.argv[2]
if (apiBase) {
  // Local dev API with a self-signed certificate.
  process.env.NODE_TLS_REJECT_UNAUTHORIZED ??= '0'
  const response = await fetch(`${apiBase.replace(/\/$/, '')}/api/v1/form-builder/effective`)
  check(`live ${apiBase}`, await response.json(), [])
}

process.exit(failures > 0 ? 1 : 0)
