import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import {
  firstEnabled,
  initialActiveIndex,
  lastEnabled,
  nextEnabledIndex,
  typeaheadMatch,
} from '../../src/presentation/components/ui/select-navigation'

const options = [
  { value: 'a', label: 'Annex', disabled: true },
  { value: 'b', label: 'Block B' },
  { value: 'c', label: 'Warehouse' },
  { value: 'd', label: 'West Wing', disabled: true },
  { value: 'e', label: 'Wellness' },
  { value: 'f', label: 'Zeta', disabled: true },
]

describe('first/last enabled', () => {
  test('skip disabled ends', () => {
    assert.equal(firstEnabled(options), 1)
    assert.equal(lastEnabled(options), 4)
  })

  test('all disabled is -1', () => {
    const none = [{ label: 'x', disabled: true }]
    assert.equal(firstEnabled(none), -1)
    assert.equal(lastEnabled(none), -1)
  })
})

describe('nextEnabledIndex', () => {
  test('skips disabled options', () => {
    assert.equal(nextEnabledIndex(options, 2, 1), 4)
    assert.equal(nextEnabledIndex(options, 4, -1), 2)
  })

  test('clamps at the ends instead of wrapping', () => {
    assert.equal(nextEnabledIndex(options, 4, 1), 4)
    assert.equal(nextEnabledIndex(options, 1, -1), 1)
  })

  test('starts from the matching end with nothing active', () => {
    assert.equal(nextEnabledIndex(options, -1, 1), 1)
    assert.equal(nextEnabledIndex(options, -1, -1), 4)
  })
})

describe('initialActiveIndex', () => {
  test('is the selected option', () => {
    assert.equal(initialActiveIndex(options, 'e'), 4)
  })

  test('falls back to the first enabled option', () => {
    assert.equal(initialActiveIndex(options, ''), 1)
    assert.equal(initialActiveIndex(options, 'a'), 1)
  })
})

describe('typeaheadMatch', () => {
  test('a single letter jumps to the next match, skipping disabled', () => {
    assert.equal(typeaheadMatch(options, 'w', 1), 2)
    assert.equal(typeaheadMatch(options, 'w', 2), 4)
  })

  test('a repeated letter cycles and wraps', () => {
    assert.equal(typeaheadMatch(options, 'ww', 4), 2)
  })

  test('a multi-character buffer keeps a still-matching current option', () => {
    assert.equal(typeaheadMatch(options, 'wel', 4), 4)
    assert.equal(typeaheadMatch(options, 'war', 4), 2)
  })

  test('is case-insensitive and -1 when nothing matches', () => {
    assert.equal(typeaheadMatch(options, 'B', -1), 1)
    assert.equal(typeaheadMatch(options, 'q', 1), -1)
    assert.equal(typeaheadMatch(options, '', 1), -1)
  })
})
