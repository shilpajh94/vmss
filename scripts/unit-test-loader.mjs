// Lets `node --test` run the app's TypeScript sources as-is: Node strips the
// types natively (the app's `erasableSyntaxOnly` keeps that possible), but the
// sources import siblings without an extension, as Vite allows. This resolve
// hook retries such a relative import with `.ts`, `.tsx`, then `/index.ts`.
import { register } from 'node:module'

register(
  'data:text/javascript,' +
    encodeURIComponent(`
      export async function resolve(specifier, context, next) {
        try {
          return await next(specifier, context)
        } catch (error) {
          if (!specifier.startsWith('.') || /\\.[cm]?[jt]sx?$/.test(specifier)) throw error
          for (const suffix of ['.ts', '.tsx', '/index.ts']) {
            try {
              return await next(specifier + suffix, context)
            } catch {}
          }
          throw error
        }
      }
    `),
)
