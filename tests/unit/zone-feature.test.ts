import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { ApiError } from '../../src/data/api/api-error'
import { zoneFeatureStatusForError } from '../../src/presentation/utils/zone-feature'

describe('zoneFeatureStatusForError', () => {
  test('a 404 means the feature is off', () => {
    assert.equal(zoneFeatureStatusForError(new ApiError('Not found', 404)), 'disabled')
  })

  test('a 403 is a missing permission, not the feature being off', () => {
    assert.equal(zoneFeatureStatusForError(new ApiError('Forbidden', 403)), 'unknown')
  })

  test('a network failure leaves the status unknown', () => {
    assert.equal(zoneFeatureStatusForError(new TypeError('Failed to fetch')), 'unknown')
  })
})
