import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { ApiError } from '../../src/data/api/api-error.ts'
import { describePrintError, isFeatureOff } from '../../src/presentation/utils/badge-print-errors.ts'

describe('badge print errors', () => {
  it('maps each missing prerequisite on a 409', () => {
    assert.match(describePrintError(new ApiError('id_not_verified', 409), 'print'), /ID verified/)
    assert.match(describePrintError(new ApiError('photo_missing', 409), 'print'), /photo/i)
    assert.match(describePrintError(new ApiError('visit_not_approved', 409), 'print'), /not approved/)
  })

  it('points to Reprint when a badge is already active', () => {
    assert.match(describePrintError(new ApiError('A badge is already active', 409), 'print'), /Reprint/)
  })

  it('points to Print when reprinting before a first print', () => {
    assert.match(describePrintError(new ApiError('No badge printed yet; print first', 409), 'reprint'), /Print badge/)
  })

  it('treats only 404 as feature off', () => {
    assert.equal(isFeatureOff(new ApiError('Not found', 404)), true)
    assert.equal(isFeatureOff(new ApiError('Conflict', 409)), false)
    assert.equal(isFeatureOff(new ApiError('Visit not found', 404)), false)
  })
})
