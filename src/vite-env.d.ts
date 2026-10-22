/// <reference types="vite/client" />

// Injected by vite.config.ts `define`.
declare const __APP_VERSION__: string
declare const __BUILD_SHA__: string

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_SSO_TENANT_SLUG: string
  readonly VITE_FIREBASE_API_KEY: string
  readonly VITE_FIREBASE_AUTH_DOMAIN: string
  readonly VITE_FIREBASE_PROJECT_ID: string
  readonly VITE_FIREBASE_STORAGE_BUCKET: string
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID: string
  readonly VITE_FIREBASE_APP_ID: string
  readonly VITE_FIREBASE_MEASUREMENT_ID: string
  readonly VITE_FIREBASE_VAPID_KEY: string
  readonly VITE_SUPPORT_EMAIL?: string
}
