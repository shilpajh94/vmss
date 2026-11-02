import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { configuredEmail, configuredUrl } from '../../src/presentation/utils/configured-value'

describe('footer link settings', () => {
  test('accepts a real https URL and address', () => {
    assert.equal(configuredUrl(' https://example.com/privacy '), 'https://example.com/privacy')
    assert.equal(configuredEmail('support@example.com'), 'support@example.com')
  })

  test('an unset or unresolved pipeline variable hides the link', () => {
    for (const value of [undefined, '', '   ', '$(VITE_PRIVACY_URL)', 'http://example.com', 'javascript:alert(1)', '#']) {
      assert.equal(configuredUrl(value), null, String(value))
    }
    assert.equal(configuredEmail('$(VITE_SUPPORT_EMAIL)'), null)
    assert.equal(configuredEmail('not-an-email'), null)
  })
})
