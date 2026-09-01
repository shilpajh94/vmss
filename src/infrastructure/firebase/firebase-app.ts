import { initializeApp, type FirebaseApp } from 'firebase/app'
import { getMessaging, type Messaging } from 'firebase/messaging'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
}

let firebaseApp: FirebaseApp | undefined
let messaging: Messaging | undefined

function isPushSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    'Notification' in window &&
    'serviceWorker' in navigator
  )
}

// Returns `undefined` when the current browser/context can't support push
// (e.g. Safari without the relevant APIs, a non-HTTPS context, or Firebase
// itself rejecting the environment) so every call site can no-op instead of
// handling a thrown error.
export function getFirebaseMessaging(): Messaging | undefined {
  if (!isPushSupported()) return undefined

  try {
    firebaseApp ??= initializeApp(firebaseConfig)
    messaging ??= getMessaging(firebaseApp)
    return messaging
  } catch (error) {
    console.error('Firebase Cloud Messaging is unavailable in this environment', error)
    return undefined
  }
}
