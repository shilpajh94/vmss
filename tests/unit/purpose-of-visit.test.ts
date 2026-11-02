import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { PURPOSE_OF_VISIT_OPTIONS, purposeLabel } from '../../src/presentation/utils/purpose-of-visit-options'

describe('purpose of visit (QA F11)', () => {
  test('options submit their label', () => {
    assert.ok(PURPOSE_OF_VISIT_OPTIONS.every((option) => option.value === option.label))
    assert.ok(PURPOSE_OF_VISIT_OPTIONS.some((option) => option.value === 'Business Meeting'))
  })

  test('a legacy slug reads as its label; other values are unchanged', () => {
    assert.equal(purposeLabel('business-meeting'), 'Business Meeting')
    assert.equal(purposeLabel('Site survey'), 'Site survey')
    assert.equal(purposeLabel(null), null)
  })
})
