// The few browser globals the data layer touches, faked for `node --test`.

export interface RecordedRequest {
  url: string
  method: string
  headers: Record<string, string>
  body: unknown
}

export interface BrowserStubs {
  session: Storage
  requests: RecordedRequest[]
  events: string[]
  respondWith(status: number, body: unknown): void
  restore(): void
}

class MemoryStorage implements Storage {
  private readonly items = new Map<string, string>()
  get length(): number {
    return this.items.size
  }
  clear(): void {
    this.items.clear()
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null
  }
  removeItem(key: string): void {
    this.items.delete(key)
  }
  setItem(key: string, value: string): void {
    this.items.set(key, value)
  }
}

export function installBrowserStubs(): BrowserStubs {
  const saved = { fetch: globalThis.fetch, sessionStorage: globalThis.sessionStorage, window: globalThis.window }
  const session = new MemoryStorage()
  const requests: RecordedRequest[] = []
  const events: string[] = []
  const responses: Array<{ status: number; body: unknown }> = []

  Object.assign(globalThis, {
    sessionStorage: session,
    window: { dispatchEvent: (event: Event) => events.push(event.type) },
    fetch: async (url: string, init: RequestInit = {}) => {
      requests.push({
        url,
        method: init.method ?? 'GET',
        headers: { ...(init.headers as Record<string, string>) },
        body: typeof init.body === 'string' ? JSON.parse(init.body) : init.body,
      })
      const next = responses.length > 1 ? responses.shift()! : responses[0]
      return new Response(JSON.stringify(next.body), { status: next.status, headers: { 'Content-Type': 'application/json' } })
    },
  })

  return {
    session,
    requests,
    events,
    respondWith(status, body) {
      responses.push({ status, body })
    },
    restore() {
      Object.assign(globalThis, saved)
    },
  }
}
