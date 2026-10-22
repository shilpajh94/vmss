import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { validateFloorNumbers } from '../../src/presentation/pages/admin-floors/floor-form-validation'
import { wholeNumberRangeError } from '../../src/presentation/utils/whole-number-range'

describe('whole-number fields', () => {
  test('visitor-category max duration rejects 0, negatives and decimals', () => {
    const rules = { label: 'Max duration', min: 1 }
    assert.equal(wholeNumberRangeError(undefined, rules), undefined)
    assert.equal(wholeNumberRangeError(480, rules), undefined)
    assert.match(wholeNumberRangeError(0, rules) ?? '', /at least 1/)
    assert.match(wholeNumberRangeError(-5, rules) ?? '', /at least 1/)
    assert.match(wholeNumberRangeError(1.5, rules) ?? '', /whole number/)
  })

  test("floor numbers follow the API's range, with 0 as the ground floor", () => {
    assert.deepEqual(validateFloorNumbers({ floorNumber: 0, capacity: 0 }), {})
    assert.deepEqual(validateFloorNumbers({ floorNumber: -2, capacity: 40 }), {})
    assert.ok(validateFloorNumbers({ floorNumber: undefined, capacity: 0 }).floorNumber)
    assert.ok(validateFloorNumbers({ floorNumber: 201, capacity: 0 }).floorNumber)
    assert.ok(validateFloorNumbers({ floorNumber: 1, capacity: -1 }).capacity)
    assert.ok(validateFloorNumbers({ floorNumber: 1, capacity: 100_001 }).capacity)
  })
})
