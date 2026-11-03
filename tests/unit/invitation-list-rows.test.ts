import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { flattenBoardColumns } from '../../src/presentation/components/invitation-board/invitation-list-rows'
import type { VisitRequestSummary } from '../../src/domain/entities/visit-request-summary-schema'

function request(id: string, overrides: Partial<VisitRequestSummary> = {}): VisitRequestSummary {
  return {
    id,
    trackingId: `T-${id}`,
    primaryContactFullName: `Visitor ${id}`,
    purposeOfVisit: null,
    registrationType: 'individual',
    visitorCategoryId: null,
    source: 'web',
    status: 'submitted',
    submittedAt: null,
    approvedAt: null,
    expiresAt: '2026-12-31T00:00:00Z',
    ...overrides,
  }
}

describe('flattenBoardColumns', () => {
  test('merges columns, tags each row with its column and sorts newest visit first', () => {
    const rows = flattenBoardColumns([
      { status: 'requested', label: 'Requested', requests: [request('a', { preferredVisitDate: '2026-11-01', preferredVisitTime: '09:00' })] },
      {
        status: 'approved',
        label: 'Approved',
        requests: [
          request('b', { status: 'approved', preferredVisitDate: '2026-11-03', preferredVisitTime: '08:00' }),
          request('c', { status: 'approved', preferredVisitDate: '2026-11-03', preferredVisitTime: '15:30' }),
        ],
      },
    ])

    assert.deepEqual(rows.map((row) => row.request.id), ['c', 'b', 'a'])
    assert.equal(rows[0].columnStatus, 'approved')
    assert.equal(rows[2].statusLabel, 'Requested')
  })

  test('a missing time counts as midnight and a missing date falls back to submittedAt', () => {
    const rows = flattenBoardColumns([
      {
        status: 'requested',
        label: 'Requested',
        requests: [
          request('no-time', { preferredVisitDate: '2026-11-02' }),
          request('submitted-only', { submittedAt: '2026-11-04T10:00:00Z' }),
        ],
      },
    ])

    assert.deepEqual(rows.map((row) => row.request.id), ['submitted-only', 'no-time'])
  })

  test('an invitation with no usable date sorts last and nothing is dropped', () => {
    const rows = flattenBoardColumns([
      { status: 'requested', label: 'Requested', requests: [request('none'), request('dated', { preferredVisitDate: '2026-11-01' })] },
      { status: 'denied', label: 'Denied', requests: [] },
    ])

    assert.deepEqual(rows.map((row) => row.request.id), ['dated', 'none'])
  })
})
