import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import type { StaffUser } from '../../src/domain/entities/staff-user-schema'
import { ADMIN_AREA_PERMISSIONS, permissionsFor } from '../../src/presentation/utils/permissions'

function user(branchRoles: StaffUser['branchRoles']): StaffUser {
  return { name: 'Test', roles: [branchRoles[0]?.roleName ?? 'Staff'], isAdmin: false, isReception: false, branchRoles }
}

describe('permissionsFor (design D-W1)', () => {
  test('a custom role gets exactly the codes it grants', () => {
    const permissions = permissionsFor(user([{ roleName: 'Night Desk', branchId: null, permissionCodes: ['invitations:checkout'] }]))
    assert.equal(permissions.can('invitations:checkout'), true)
    assert.equal(permissions.can('invitations:create'), false)
    assert.equal(permissions.canAny(ADMIN_AREA_PERMISSIONS), false)
  })

  test('a branch-scoped grant applies at its own branch only', () => {
    const permissions = permissionsFor(user([{ roleName: 'Host', branchId: 'b1', permissionCodes: ['invitations:approve'] }]))
    assert.equal(permissions.can('invitations:approve', 'b1'), true)
    assert.equal(permissions.can('invitations:approve', 'b2'), false)
    assert.equal(permissions.can('invitations:approve'), true)
  })

  test('a company-wide grant applies at every branch', () => {
    const permissions = permissionsFor(user([{ roleName: 'Admin', branchId: null, permissionCodes: ['branches:manage'] }]))
    assert.equal(permissions.can('branches:manage', 'b9'), true)
    assert.equal(permissions.canAny(ADMIN_AREA_PERMISSIONS), true)
  })

  test('falls back to the standard role names when the API sends no codes', () => {
    const admin = permissionsFor(user([{ roleName: 'Admin', branchId: null }]))
    assert.equal(admin.can('devices:manage'), true)
    const reception = permissionsFor(user([{ roleName: 'reception', branchId: 'b1' }]))
    assert.equal(reception.can('invitations:checkout'), true)
    assert.equal(reception.canAny(ADMIN_AREA_PERMISSIONS), false)
    const custom = permissionsFor(user([{ roleName: 'Night Desk', branchId: null }]))
    assert.equal(custom.can('invitations:view'), false)
  })

  test('no user, no permissions', () => {
    assert.equal(permissionsFor(undefined).can('invitations:view'), false)
  })
})
