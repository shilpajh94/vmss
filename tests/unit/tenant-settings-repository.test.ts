import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, test } from 'node:test'
import { ApiClient } from '../../src/data/api/api-client'
import { HttpTenantSettingsRepository } from '../../src/infrastructure/tenant-settings-repository'
import { installBrowserStubs, type BrowserStubs } from './browser-stubs'

describe('HttpTenantSettingsRepository ID verification setting', () => {
  let stubs: BrowserStubs

  beforeEach(() => {
    stubs = installBrowserStubs()
    stubs.session.setItem('token', 'staff-token')
  })

  afterEach(() => stubs.restore())

  test('defaults to required when the field is absent', async () => {
    stubs.respondWith(200, { success: true, data: { badgePrintFlowEnabled: true } })
    assert.equal(await new HttpTenantSettingsRepository(new ApiClient('http://api')).getBadgePrintRequiresIdVerification(), true)
  })

  test('reads an explicit false', async () => {
    stubs.respondWith(200, { success: true, data: { badgePrintRequiresIdVerification: false } })
    assert.equal(await new HttpTenantSettingsRepository(new ApiClient('http://api')).getBadgePrintRequiresIdVerification(), false)
  })

  test('PATCHes only the one field', async () => {
    stubs.respondWith(200, { success: true, data: { badgePrintRequiresIdVerification: false } })
    await new HttpTenantSettingsRepository(new ApiClient('http://api')).setBadgePrintRequiresIdVerification(false)

    const [request] = stubs.requests
    assert.equal(request.method, 'PATCH')
    assert.equal(request.url, 'http://api/tenants/me/settings')
    assert.deepEqual(request.body, { badgePrintRequiresIdVerification: false })
  })
})
