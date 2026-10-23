import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { moveItem } from '../../src/presentation/utils/move-item'

const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }, { id: 'd' }]
const ids = (list: { id: string }[] | undefined) => list?.map((item) => item.id).join('')

describe('moveItem', () => {
  test('moves down and up', () => {
    assert.equal(ids(moveItem(items, 'a', 'c')), 'bcad')
    assert.equal(ids(moveItem(items, 'd', 'b')), 'adbc')
  })

  test('leaves the input alone', () => {
    moveItem(items, 'a', 'd')
    assert.equal(ids(items), 'abcd')
  })

  test('an unknown id is no move', () => {
    assert.equal(moveItem(items, 'a', 'z'), undefined)
  })
})
