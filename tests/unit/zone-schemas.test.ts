import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { EmergencyInsideResponseSchema } from '../../src/domain/entities/emergency-inside-schema'
import { ZoneIdsResponseSchema, ZoneListResponseSchema } from '../../src/domain/entities/zone-schema'

const envelope = { success: true, message: 'ok' }

describe('zone schemas', () => {
  test('a zone list parses and defaults missing gateIds to an empty list', () => {
    const parsed = ZoneListResponseSchema.parse({
      ...envelope,
      data: [
        { id: 'z1', branchId: 'b1', name: 'Lab', code: 'LAB', buildingId: null, floorId: null, gateIds: ['g1'], isActive: true },
        { id: 'z2', branchId: 'b1', name: 'Lobby', code: 'LOB', isActive: false },
      ],
      pagination: { page: 1, pageSize: 20, total: 2, totalPages: 1 },
    })
    assert.deepEqual(parsed.data[0]?.gateIds, ['g1'])
    assert.deepEqual(parsed.data[1]?.gateIds, [])
  })

  test('mapping responses reduce to zone ids from every accepted shape', () => {
    const shapes = [
      ['z1', 'z2'],
      [{ id: 'z1' }, { id: 'z2' }],
      [{ zoneId: 'z1' }, { zoneId: 'z2' }],
      { zoneIds: ['z1', 'z2'] },
      { zones: [{ id: 'z1' }, { id: 'z2' }] },
    ]
    for (const data of shapes) {
      assert.deepEqual(ZoneIdsResponseSchema.parse({ ...envelope, data }), ['z1', 'z2'])
    }
  })

  test('an empty mapping parses as an empty list', () => {
    assert.deepEqual(ZoneIdsResponseSchema.parse({ ...envelope, data: { zoneIds: [] } }), [])
  })

  test('the inside report parses with an empty unzoned group', () => {
    const report = EmergencyInsideResponseSchema.parse({
      ...envelope,
      data: {
        zones: [
          {
            zoneId: 'z1',
            zoneName: 'Lab',
            branchId: 'b1',
            visitors: [{ invitationId: 'i1', visitorName: 'Asha', hostName: 'Ravi', badgeNumber: 'B-7', enteredAt: '2026-11-04T09:00:00Z' }],
          },
        ],
        unzoned: [],
        totalInside: 1,
      },
    })
    assert.equal(report.totalInside, 1)
    assert.equal(report.zones[0]?.visitors[0]?.visitorName, 'Asha')
    assert.deepEqual(report.unzoned, [])
  })
})
