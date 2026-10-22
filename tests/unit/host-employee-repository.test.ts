import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, test } from 'node:test'
import { ApiClient } from '../../src/data/api/api-client'
import { HttpHostEmployeeRepository } from '../../src/infrastructure/host-employee-repository'
import { installBrowserStubs, type BrowserStubs } from './browser-stubs'

const employee = {
  id: 'e1',
  email: 'new.person@example.com',
  fullName: 'New Person',
  employeeCode: 'EMP-1',
  phoneNumber: null,
  designation: null,
  departmentId: 'd1',
  isActive: true,
  avatarUrl: null,
  branchRoles: [],
}

describe('HttpHostEmployeeRepository.create (design D-W7)', () => {
  let stubs: BrowserStubs

  beforeEach(() => {
    stubs = installBrowserStubs()
    stubs.session.setItem('token', 'admin-token')
  })

  afterEach(() => {
    stubs.restore()
  })

  test('creates one employee through POST /auth/employees and never resyncs the roster', async () => {
    stubs.respondWith(201, { success: true, message: '', data: employee })
    const repository = new HttpHostEmployeeRepository(new ApiClient('http://api'))

    const created = await repository.create({
      fullName: 'New Person',
      email: 'new.person@example.com',
      employeeCode: 'EMP-1',
      departmentId: 'd1',
    })

    assert.equal(created.id, 'e1')
    assert.deepEqual(
      stubs.requests.map((request) => `${request.method} ${request.url}`),
      ['POST http://api/auth/employees'],
    )
    assert.deepEqual(stubs.requests[0].body, {
      email: 'new.person@example.com',
      fullName: 'New Person',
      employeeCode: 'EMP-1',
      departmentId: 'd1',
      phoneNumber: null,
      designation: null,
    })
    assert.ok(stubs.requests.every((request) => !request.url.includes('/auth/employees/sync')))
  })
})
