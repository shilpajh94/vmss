import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { execSync } from 'node:child_process'
import { readFileSync } from 'node:fs'

// The admin sidebar footer shows the build that is actually deployed
// (app-shell "The sidebar footer shows the real build identifier"). CI passes
// VITE_BUILD_SHA; a local build falls back to git, and to nothing outside a
// checkout.
function resolveBuildSha(): string {
  const fromEnv = process.env.VITE_BUILD_SHA?.trim()
  if (fromEnv) return fromEnv.slice(0, 7)
  try {
    return execSync('git rev-parse --short HEAD', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
  } catch {
    return ''
  }
}

const appVersion: string = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf-8')).version ?? ''

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __BUILD_SHA__: JSON.stringify(resolveBuildSha()),
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://vmss-dev.mypits.org',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})
