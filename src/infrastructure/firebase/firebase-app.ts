import type { Messaging } from 'firebase/messaging'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
}

type MessagingModule = typeof import('firebase/messaging')

export interface FirebaseMessagingApi {
  messaging: Messaging
  getToken: MessagingModule['getToken']
  onMessage: MessagingModule['onMessage']
}

export function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    'Notification' in window &&
    'serviceWorker' in navigator
  )
}

let loading: Promise<FirebaseMessagingApi | undefined> | undefined
let hasFailed = false
let resolveReady: (api: FirebaseMessagingApi) => void = () => undefined
const ready = new Promise<FirebaseMessagingApi>((resolve) => {
  resolveReady = resolve
})

// True once Firebase itself rejected this environment (bad config, a
// browser it doesn't support), so push reads as unavailable from then on.
export function hasFirebaseFailed(): boolean {
  return hasFailed
}

// The Firebase SDK is downloaded only here, the first time a signed-in
// session with push permission needs it (app-performance "The
// Push-Notification SDK Is Loaded Only for Signed-In Staff"), never in the
// initial bundle. Resolves to `undefined` when the browser/context can't
// support push, so every call site can no-op instead of handling a throw.
export function loadFirebaseMessaging(): Promise<FirebaseMessagingApi | undefined> {
  if (!isPushSupported()) return Promise.resolve(undefined)

  loading ??= Promise.all([import('firebase/app'), import('firebase/messaging')])
    .then(([app, messagingModule]) => {
      const api: FirebaseMessagingApi = {
        messaging: messagingModule.getMessaging(app.initializeApp(firebaseConfig)),
        getToken: messagingModule.getToken,
        onMessage: messagingModule.onMessage,
      }
      resolveReady(api)
      return api
    })
    .catch((error: unknown) => {
      console.error('Firebase Cloud Messaging is unavailable in this environment', error)
      hasFailed = true
      return undefined
    })
  return loading
}

// Resolves once something has loaded the SDK, without loading it itself: the
// foreground-message listener waits on this rather than pulling Firebase
// into a public page that never signs in.
export function whenFirebaseMessagingReady(): Promise<FirebaseMessagingApi> {
  return ready
}
