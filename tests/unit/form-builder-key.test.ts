import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { formBuilderKeyError, slugifyKey } from '../../src/presentation/pages/admin-form-builder/form-builder-key'

describe('form builder keys', () => {
  test('slugs a name the way the API expects', () => {
    assert.equal(slugifyKey('  Company Name! '), 'company_name')
  })

  test('accepts an ordinary name', () => {
    assert.equal(formBuilderKeyError('Company Name', 'Field label'), undefined)
  })

  test('rejects a blank or symbol-only name', () => {
    assert.match(formBuilderKeyError('   ', 'Field label') ?? '', /required/)
    assert.match(formBuilderKeyError('!!! ---', 'Field label') ?? '', /letter or number/)
  })

  test('rejects a key that starts with a digit', () => {
    assert.match(formBuilderKeyError('1st visit', 'Step name') ?? '', /start with a letter/)
  })

  test('rejects a key over 100 characters', () => {
    assert.equal(formBuilderKeyError('a'.repeat(100), 'Group name'), undefined)
    assert.match(formBuilderKeyError('a'.repeat(101), 'Group name') ?? '', /too long/)
  })
})
