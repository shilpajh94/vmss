import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, test } from 'node:test'
import { ApiClient } from '../../src/data/api/api-client'
import { HttpVisitTimelineRepository } from '../../src/infrastructure/visit-timeline-repository'
import { installBrowserStubs, type BrowserStubs } from './browser-stubs'

const body = {
  success: true,
  message: 'Success',
  data: [
    { eventType: 'badge_reprinted', occurredAt: '2026-11-03T10:00:00Z', summary: 'Badge reprinted: Torn badge', actorName: 'Asha Rao' },
    { eventType: 'checked_in', occurredAt: '2026-11-03T09:00:00Z', summary: 'Checked in via QR', actorName: null },
    { eventType: 'zone_entered', occurredAt: '2026-11-03T09:05:00Z', summary: 'Entered lobby', actorName: null },
  ],
  pagination: { page: 1, pageSize: 20, total: 3, totalPages: 1 },
}

describe('HttpVisitTimelineRepository', () => {
  let stubs: BrowserStubs

  beforeEach(() => {
    stubs = installBrowserStubs()
    stubs.session.setItem('token', 'staff-token')
  })

  afterEach(() => {
    stubs.restore()
  })

  test('parses null actors and unknown event types without failing', async () => {
    stubs.respondWith(200, body)
    const response = await new HttpVisitTimelineRepository(new ApiClient('http://api')).listForInvitation('inv-1')

    assert.equal(response.data[1].actorName, null)
    assert.equal(response.data[2].eventType, 'zone_entered')
    assert.equal(response.pagination.total, 3)
  })

  test('requests the invitation endpoint with the query, skipping unset values', async () => {
    stubs.respondWith(200, body)
    await new HttpVisitTimelineRepository(new ApiClient('http://api')).listForInvitation('inv-1', {
      page: 2,
      pageSize: 20,
      sortOrder: 'asc',
      occurredAfter: undefined,
    })

    const [request] = stubs.requests
    assert.equal(request.method, 'GET')
    assert.equal(request.url, 'http://api/invitations/inv-1/timeline?page=2&pageSize=20&sortOrder=asc')
    assert.equal(request.headers.Authorization, 'Bearer staff-token')
  })

  test('requests the visitor endpoint for a co-visitor', async () => {
    stubs.respondWith(200, body)
    await new HttpVisitTimelineRepository(new ApiClient('http://api')).listForVisitor('vis-9')

    assert.equal(stubs.requests[0].url, 'http://api/visitors/vis-9/timeline')
  })
})
