import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import type { InvitationTrackOut } from '../../src/domain/entities/invitation-track-out-schema'
import { toTrackingLookupResponse } from '../../src/infrastructure/visit-tracking-repository'

function lookup(status: string) {
  return toTrackingLookupResponse({
    trackingId: 'VR-1',
    status,
    primaryContactFullName: 'Ada Visitor',
  } as InvitationTrackOut)
}

describe('tracking status mapping (visitor-track-request spec)', () => {
  test('a denied request reads as denied, in the error tone', () => {
    const response = lookup('denied')
    assert.equal(response.statusLabel, 'Denied')
    assert.equal(response.statusTone, 'danger')
  })

  test('checked in and out advance the timeline past Approved', () => {
    assert.equal(lookup('checked_in').timelineStage, 'checked-out')
    assert.equal(lookup('checked_out').timelineStage, 'complete')
  })

  test('archived reads as expired', () => {
    assert.equal(lookup('archived').statusLabel, 'Expired')
  })

  test('an unknown status shows its raw value in a neutral tone without resetting the timeline', () => {
    const response = lookup('on_hold')
    assert.equal(response.statusLabel, 'On Hold')
    assert.equal(response.statusTone, 'neutral')
    assert.equal(response.timelineStage, 'unknown')
  })
})
