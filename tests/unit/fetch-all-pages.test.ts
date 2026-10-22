import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { fetchAllPages } from '../../src/data/api/fetch-all-pages'

function pagedSource(total: number) {
  const calls: number[] = []
  const fetchPage = async (page: number, pageSize: number) => {
    calls.push(page)
    const start = (page - 1) * pageSize
    const data = Array.from({ length: Math.max(Math.min(pageSize, total - start), 0) }, (_, index) => start + index)
    return { data, pagination: { totalPages: Math.ceil(total / pageSize) } }
  }
  return { calls, fetchPage }
}

describe('fetchAllPages (design D-W9)', () => {
  test('collects every page past the first 100', async () => {
    const source = pagedSource(250)
    const items = await fetchAllPages(source.fetchPage)
    assert.equal(items.length, 250)
    assert.deepEqual(source.calls.sort(), [1, 2, 3])
  })

  test('makes one request for a single page', async () => {
    const source = pagedSource(3)
    assert.equal((await fetchAllPages(source.fetchPage)).length, 3)
    assert.deepEqual(source.calls, [1])
  })

  test('stops at max', async () => {
    const source = pagedSource(5000)
    const items = await fetchAllPages(source.fetchPage, { max: 300 })
    assert.equal(items.length, 300)
    assert.deepEqual(source.calls.sort(), [1, 2, 3])
  })
})
