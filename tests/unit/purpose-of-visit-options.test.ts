import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { purposeStoredValues } from '../../src/presentation/utils/purpose-of-visit-options'

describe('purposeStoredValues', () => {
  test('a purpose is also matched under its legacy slug', () => {
    assert.deepEqual(purposeStoredValues('Interview'), ['Interview', 'interview'])
    assert.deepEqual(purposeStoredValues('Vendor / Contractor'), ['Vendor / Contractor', 'vendor-contractor'])
  })

  test('an unknown label is matched as typed', () => {
    assert.deepEqual(purposeStoredValues('Something else'), ['Something else'])
  })
})
