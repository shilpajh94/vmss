import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, test } from 'node:test'
import z from 'zod'
import { ApiClient, SESSION_EXPIRED_EVENT } from '../../src/data/api/api-client'
import { API_ENDPOINTS } from '../../src/data/api/api-endpoints'
import { installBrowserStubs, type BrowserStubs } from './browser-stubs'

const ok = { success: true, message: '', data: [] }
const anything = z.unknown()

describe('ApiClient session token (design D-W2)', () => {
  let stubs: BrowserStubs

  beforeEach(() => {
    stubs = installBrowserStubs()
  })

  afterEach(() => {
    stubs.restore()
  })

  test('sends the session token to an endpoint that does not require one', async () => {
    stubs.session.setItem('token', 'staff-token')
    stubs.respondWith(200, ok)

    await new ApiClient('http://api').makeRequest({ endpointConfig: API_ENDPOINTS.LIST_BRANCHES, parserSchema: anything })

    assert.equal(stubs.requests[0].headers.Authorization, 'Bearer staff-token')
  })

  test('sends no Authorization without a session', async () => {
    stubs.respondWith(200, ok)

    await new ApiClient('http://api').makeRequest({ endpointConfig: API_ENDPOINTS.LIST_BRANCHES, parserSchema: anything })

    assert.equal(stubs.requests[0].headers.Authorization, undefined)
  })

  test("never overwrites a caller's own Authorization (visitor proof token)", async () => {
    stubs.session.setItem('token', 'staff-token')
    stubs.respondWith(200, ok)

    await new ApiClient('http://api').makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_BRANCHES,
      headers: { Authorization: 'Bearer proof' },
      parserSchema: anything,
    })

    assert.equal(stubs.requests[0].headers.Authorization, 'Bearer proof')
  })

  test('a 401 on an optional-token endpoint clears the token without signalling expiry', async () => {
    stubs.session.setItem('token', 'stale')
    stubs.respondWith(401, { success: false, message: 'Invalid token', data: null })

    await assert.rejects(
      new ApiClient('http://api').makeRequest({ endpointConfig: API_ENDPOINTS.LIST_BRANCHES, parserSchema: anything }),
    )

    assert.equal(stubs.session.getItem('token'), null)
    assert.deepEqual(stubs.events, [])
  })

  test('a 401 on a token-required endpoint still signals session expiry', async () => {
    stubs.session.setItem('token', 'stale')
    stubs.respondWith(401, { success: false, message: 'Invalid token', data: null })

    await assert.rejects(
      new ApiClient('http://api').makeRequest({ endpointConfig: API_ENDPOINTS.LIST_HOST_EMPLOYEES, parserSchema: anything }),
    )

    assert.deepEqual(stubs.events, [SESSION_EXPIRED_EVENT])
  })
})
