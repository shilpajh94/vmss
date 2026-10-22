import assert from 'node:assert/strict'
import { describe, test } from 'node:test'
import { LiveResourceController, type LiveResourceState } from '../../src/presentation/hooks/live-resource-controller'

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function setup<T, R = undefined>(load: () => Promise<T>, reference?: () => Promise<R>) {
  const errors: unknown[] = []
  let state: LiveResourceState<T, R> | undefined
  const controller = new LiveResourceController<T, R>({
    load,
    reference,
    onChange: (next) => {
      state = next
    },
    onError: (error) => errors.push(error),
  })
  return { controller, errors, state: () => state ?? controller.getState() }
}

describe('LiveResourceController (design D-W4)', () => {
  test('reference data loads once; polls re-fetch only the data', async () => {
    let dataCalls = 0
    let referenceCalls = 0
    const { controller, state } = setup(
      async () => ++dataCalls,
      async () => {
        referenceCalls += 1
        return ['branch']
      },
    )

    await controller.start()
    await controller.poll()
    await controller.poll()

    assert.equal(referenceCalls, 1)
    assert.equal(dataCalls, 3)
    assert.deepEqual(state().reference, ['branch'])

    await controller.refresh()
    assert.equal(referenceCalls, 2)
  })

  test('a failing poll sets hasFailed, keeps the data and reports no error', async () => {
    let fail = false
    const { controller, errors, state } = setup(async () => {
      if (fail) throw new Error('down')
      return 'rows'
    })

    await controller.start()
    fail = true
    await controller.poll()

    assert.equal(state().hasFailed, true)
    assert.equal(state().data, 'rows')
    assert.equal(state().phase, 'ready')
    assert.deepEqual(errors, [])
  })

  test('recovery clears hasFailed', async () => {
    let fail = false
    const { controller, state } = setup(async () => {
      if (fail) throw new Error('down')
      return 'rows'
    })

    await controller.start()
    fail = true
    await controller.poll()
    fail = false
    await controller.poll()

    assert.equal(state().hasFailed, false)
  })

  test('only the initial load and user loads report a failure', async () => {
    let fail = true
    const { controller, errors, state } = setup(async () => {
      if (fail) throw new Error('down')
      return 'rows'
    })

    await controller.start()
    assert.equal(state().phase, 'error')
    assert.equal(errors.length, 1)

    fail = false
    await controller.refresh()
    fail = true
    await controller.load('user')
    assert.equal(errors.length, 2)
    await controller.poll()
    assert.equal(errors.length, 2)
  })

  test('an out-of-order response is ignored', async () => {
    const slow = deferred<string>()
    const fast = deferred<string>()
    const responses = [slow.promise, fast.promise]
    const { controller, state } = setup(() => responses.shift()!)

    const first = controller.load('user')
    const second = controller.load('user')
    fast.resolve('newer')
    await second
    slow.resolve('older')
    await first

    assert.equal(state().data, 'newer')
  })
})
