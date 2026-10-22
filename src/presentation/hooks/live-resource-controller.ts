import type { LoadMode, LoadPhase } from './use-load-tracker'

export interface LiveResourceState<T, R> {
  data: T | undefined
  // Loaded once per mount and on a manual refresh, never on a poll.
  reference: R | undefined
  // 'initial' until the first load settles; 'error' if it failed.
  phase: LoadPhase
  // A user-mode load is in flight over data already on screen.
  isRefreshing: boolean
  // Background refreshes are failing after a good load: the last data stays
  // and the refresh control shows it is retrying (live-data-refresh).
  hasFailed: boolean
  // The latest failure, of a data or reference load.
  error: unknown
}

interface ControllerOptions<T, R> {
  load: () => Promise<T>
  reference?: () => Promise<R>
  onChange: (state: LiveResourceState<T, R>) => void
  // A failure the user should hear about: the initial load or a user-mode
  // one (a filter, a page, Try again, the refresh control). A failing poll
  // never calls this.
  onError?: (error: unknown) => void
}

// The framework-free core of `useLiveResource` (design D-W4), kept apart from
// React so its rules are unit-tested directly: reference data loads once, a
// failing poll only flags `hasFailed`, the next success clears it, and a
// superseded response is dropped.
export class LiveResourceController<T, R = undefined> {
  private state: LiveResourceState<T, R> = {
    data: undefined,
    reference: undefined,
    phase: 'initial',
    isRefreshing: false,
    hasFailed: false,
    error: undefined,
  }
  private latestRequestId = 0
  private latestReferenceId = 0
  private options: ControllerOptions<T, R>

  constructor(options: ControllerOptions<T, R>) {
    this.options = options
  }

  // Lets the hook swap in its latest closures without restarting anything.
  setOptions(options: ControllerOptions<T, R>): void {
    this.options = options
  }

  getState(): LiveResourceState<T, R> {
    return this.state
  }

  // For an optimistic edit after a mutation (a renamed row, a removed one).
  setData(update: (current: T | undefined) => T | undefined): void {
    this.update({ data: update(this.state.data) })
  }

  async load(mode: LoadMode = 'user'): Promise<void> {
    const requestId = ++this.latestRequestId
    const hasLoaded = this.state.phase === 'ready'
    if (!hasLoaded) this.update({ phase: 'initial' })
    else if (mode === 'user') this.update({ isRefreshing: true })

    try {
      const data = await this.options.load()
      if (requestId !== this.latestRequestId) return
      this.update({ data, phase: 'ready', isRefreshing: false, hasFailed: false, error: undefined })
    } catch (error) {
      if (requestId !== this.latestRequestId) return
      if (!hasLoaded) {
        this.update({ phase: 'error', isRefreshing: false, error })
        this.options.onError?.(error)
      } else if (mode === 'background') {
        this.update({ hasFailed: true, error })
      } else {
        this.update({ isRefreshing: false, error })
        this.options.onError?.(error)
      }
    }
  }

  async loadReference(): Promise<void> {
    const fetchReference = this.options.reference
    if (!fetchReference) return
    const referenceId = ++this.latestReferenceId
    try {
      const reference = await fetchReference()
      if (referenceId !== this.latestReferenceId) return
      this.update({ reference })
    } catch (error) {
      if (referenceId !== this.latestReferenceId) return
      // The page still works without its option lists (filters, names); the
      // next manual refresh retries them.
      this.update({ error })
    }
  }

  // Mount: reference and data together.
  async start(): Promise<void> {
    await Promise.all([this.loadReference(), this.load('user')])
  }

  // The top-bar refresh control and Try again: everything, as a user load.
  async refresh(): Promise<void> {
    await Promise.all([this.loadReference(), this.load('user')])
  }

  // The polling tick: the page's changing data only.
  async poll(): Promise<void> {
    await this.load('background')
  }

  private update(patch: Partial<LiveResourceState<T, R>>): void {
    this.state = { ...this.state, ...patch }
    this.options.onChange(this.state)
  }
}
