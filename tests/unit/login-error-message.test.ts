import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { ApiError } from '../../src/data/api/api-error'
import { loginErrorMessage } from '../../src/presentation/utils/login-error-message'

const credentials = 'Invalid email or password. Please try again.'

describe('loginErrorMessage', () => {
  test('rate limit', () => {
    assert.match(loginErrorMessage(new ApiError('Rate limit exceeded', 429), credentials), /Too many sign-in attempts/)
  })

  test('network failure and 5xx', () => {
    assert.match(loginErrorMessage(new TypeError('Failed to fetch'), credentials), /Can't reach the server/)
    assert.match(loginErrorMessage(new ApiError('Internal error', 503), credentials), /Can't reach the server/)
  })

  test('anything else reads as bad credentials', () => {
    assert.equal(loginErrorMessage(new ApiError('Invalid credentials', 401), credentials), credentials)
  })
})
