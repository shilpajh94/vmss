import assert from 'node:assert/strict'
import { afterEach, beforeEach, describe, test } from 'node:test'
import z from 'zod'
import { ApiClient } from '../../src/data/api/api-client'
import { API_ENDPOINTS } from '../../src/data/api/api-endpoints'
import { ApiError } from '../../src/data/api/api-error'
import { apiFieldErrors, toUserMessage } from '../../src/presentation/utils/to-user-message'
import { installBrowserStubs, type BrowserStubs } from './browser-stubs'

const fallback = 'Something went wrong saving the branch. Please try again.'

describe('toUserMessage (design D-W5)', () => {
  test('shows a 4xx message from the envelope', () => {
    assert.equal(toUserMessage(new ApiError('A branch with code HQ already exists', 409), fallback), 'A branch with code HQ already exists')
  })

  test('leads with the first field error of a 422', () => {
    const error = new ApiError('Invalid request: name: too long; code: required', 422, { name: 'too long', code: 'required' })
    assert.equal(toUserMessage(error, fallback), 'Name: too long')
  })

  test('falls back for a 5xx, a network failure, a body with no message and a non-API error', () => {
    assert.equal(toUserMessage(new ApiError('Internal Server Error', 500), fallback), fallback)
    assert.equal(toUserMessage(new TypeError('Failed to fetch'), fallback), fallback)
    assert.equal(toUserMessage(new ApiError('Request failed with status 400', 400), fallback), fallback)
    assert.equal(toUserMessage(new Error('ZodError: expected string'), fallback), fallback)
  })

  test('maps field errors onto form keys', () => {
    assert.deepEqual(apiFieldErrors(new ApiError('', 422, { 'body.contactEmail': 'not an email' })), { contactEmail: 'not an email' })
  })
})

describe('ApiClient field errors', () => {
  let stubs: BrowserStubs

  beforeEach(() => {
    stubs = installBrowserStubs()
  })

  afterEach(() => {
    stubs.restore()
  })

  test("carry the envelope's `errors` list on the ApiError", async () => {
    stubs.respondWith(422, {
      success: false,
      message: 'Invalid request: name: String should have at most 255 characters',
      errors: [{ field: 'name', message: 'String should have at most 255 characters' }],
    })

    const error = await new ApiClient('http://api')
      .makeRequest({ endpointConfig: API_ENDPOINTS.LIST_BRANCHES, parserSchema: z.unknown() })
      .catch((caught: unknown) => caught)

    assert.ok(error instanceof ApiError)
    assert.deepEqual(error.fieldErrors, { name: 'String should have at most 255 characters' })
  })
})
