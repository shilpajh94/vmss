import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import type { StaffUser } from '../../src/domain/entities/staff-user-schema'
import { postSignInPath, safeReturnPath, signInPathFor } from '../../src/presentation/utils/return-path'

const origin = 'https://app.example.com'

function staff(codes: string[], extra: Partial<StaffUser> = {}): StaffUser {
  return {
    name: 'Test',
    role: 'Host',
    isAdmin: false,
    isReception: false,
    branchRoles: [{ roleName: 'Host', branchId: null, permissionCodes: codes }],
    ...extra,
  }
}

describe('return path (staff-login spec)', () => {
  test('round-trips the requested page and its query string', () => {
    const loginUrl = signInPathFor('/staff/login', { pathname: '/staff/invitations', search: '?invitationId=X' })
    const from = new URL(loginUrl, origin).searchParams.get('from')
    assert.equal(safeReturnPath(from, origin), '/staff/invitations?invitationId=X')
  })

  test('ignores anything outside the app', () => {
    assert.equal(safeReturnPath('https://evil.example.com/x', origin), undefined)
    assert.equal(safeReturnPath('//evil.example.com/x', origin), undefined)
    assert.equal(safeReturnPath('javascript:alert(1)', origin), undefined)
    assert.equal(safeReturnPath('/admin/login', origin), undefined)
    assert.equal(safeReturnPath(null, origin), undefined)
  })

  test('falls back to the landing page for an area the user may not use', () => {
    assert.equal(postSignInPath(staff(['invitations:view']), '/admin/branches', origin), '/staff/dashboard')
    assert.equal(postSignInPath(staff(['branches:manage'], { isAdmin: true }), '/admin/branches', origin), '/admin/branches')
    assert.equal(postSignInPath(staff(['invitations:view']), '/reception/dashboard', origin), '/staff/dashboard')
    assert.equal(postSignInPath(staff(['invitations:view']), 'https://evil.example.com', origin), '/staff/dashboard')
  })
})
