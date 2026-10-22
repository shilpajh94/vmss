import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

const RELOADED_KEY = 'app:reloaded-for-chunk'

// After a deploy, a tab still running the old `index.html` asks for chunk
// names that no longer exist. That surfaces as a failed dynamic import;
// reloading once picks up the new build. The flag stops a genuinely broken
// chunk (or an offline device) from reloading forever: the second failure
// reaches the router's error page instead.
function isChunkLoadError(error: unknown): boolean {
  return (
    error instanceof TypeError ||
    (error instanceof Error && /dynamically imported module|Importing a module script failed|Loading chunk/i.test(error.message))
  )
}

function readReloadedFlag(): boolean {
  try {
    return sessionStorage.getItem(RELOADED_KEY) !== null
  } catch {
    return true
  }
}

function writeReloadedFlag(value: boolean): void {
  try {
    if (value) sessionStorage.setItem(RELOADED_KEY, '1')
    else sessionStorage.removeItem(RELOADED_KEY)
  } catch {
    // Storage blocked: no automatic reload, the error page offers one.
  }
}

// `React.lazy` for a page module's named export, with the one-time reload
// on a stale-chunk error (design D13, app-performance "Route Groups Are
// Loaded on Demand").
// oxlint-disable-next-line no-explicit-any -- React.lazy's own constraint.
type AnyComponent = ComponentType<any>

export function lazyPage<K extends string, M extends Record<K, AnyComponent>>(load: () => Promise<M>, exportName: K): LazyExoticComponent<M[K]> {
  return lazy(async () => {
    try {
      const module = await load()
      writeReloadedFlag(false)
      return { default: module[exportName] }
    } catch (error) {
      if (isChunkLoadError(error) && !readReloadedFlag()) {
        writeReloadedFlag(true)
        window.location.reload()
        // Never settles: the page is going away.
        return new Promise<never>(() => undefined)
      }
      throw error
    }
  })
}
