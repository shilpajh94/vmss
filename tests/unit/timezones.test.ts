import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { timezoneOptions, toIanaTimezone } from '../../src/presentation/utils/timezones'

const january = new Date('2026-01-15T12:00:00Z')

describe('timezones (design D-W8)', () => {
  test('upgrades a legacy GMT offset to the preferred zone with that offset', () => {
    assert.equal(toIanaTimezone('GMT+05:30', january), 'Asia/Kolkata')
    assert.equal(toIanaTimezone('GMT+00:00', january), 'Europe/London')
    assert.equal(toIanaTimezone('GMT-05:00', january), 'America/New_York')
  })

  test('falls back to any zone with the offset, and leaves IANA names alone', () => {
    assert.equal(toIanaTimezone('GMT+05:45', january), 'Asia/Kathmandu')
    assert.equal(toIanaTimezone('Asia/Dubai', january), 'Asia/Dubai')
  })

  test('labels options with their offset, ordered by offset', () => {
    const options = timezoneOptions(undefined, january)
    const kolkata = options.find((option) => option.value === 'Asia/Kolkata')
    assert.equal(kolkata?.label, '(GMT+05:30) Asia/Kolkata')
    const offsets = options.map((option) => option.label.slice(4, 10))
    assert.equal(offsets[0].startsWith('-'), true)
    assert.ok(options.some((option) => option.value === 'UTC'))
    assert.ok(!options.some((option) => option.value === 'Asia/Calcutta'))
  })

  test('keeps a stored zone the browser does not list', () => {
    assert.ok(timezoneOptions('Mars/Olympus_Mons', january).some((option) => option.value === 'Mars/Olympus_Mons'))
  })
})
