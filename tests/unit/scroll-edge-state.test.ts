import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { edgeState } from '../../src/presentation/hooks/use-scroll-activity'

describe('edgeState', () => {
  test('a list that fits is at both ends', () => {
    assert.deepEqual(edgeState(0, 400, 400), { atTop: true, atBottom: true })
  })

  test('scrolled to the top of a long list', () => {
    assert.deepEqual(edgeState(0, 400, 900), { atTop: true, atBottom: false })
  })

  test('scrolled to the middle', () => {
    assert.deepEqual(edgeState(200, 400, 900), { atTop: false, atBottom: false })
  })

  test('scrolled to the bottom', () => {
    assert.deepEqual(edgeState(500, 400, 900), { atTop: false, atBottom: true })
  })

  test('sub-pixel positions count as the end', () => {
    assert.deepEqual(edgeState(0.6, 400, 900), { atTop: true, atBottom: false })
    assert.deepEqual(edgeState(499.4, 400, 900), { atTop: false, atBottom: true })
  })
})
