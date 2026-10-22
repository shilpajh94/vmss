import { useCallback } from 'react'
import { getToken } from 'firebase/messaging'
import { getFirebaseMessaging } from '../../infrastructure/firebase/firebase-app'
import { useAppDependencies } from '../context/app-dependencies-context'
import { useToast } from '../components/toast/toast-context'

// Session-scoped: a fresh registration happens on the next login in a new
// tab/session rather than persisting across browser restarts. Its presence
// is also what distinguishes "permission granted and registered" from
// "permission granted but not registered yet".
export const FCM_TOKEN_STORAGE_KEY = 'fcmToken'

export type PushUnavailableReason = 'insecure-context' | 'unsupported'

export type PushState =
  | { status: 'enabled' }
  | { status: 'off' }
  | { status: 'blocked' }
  | { status: 'unavailable'; reason: PushUnavailableReason }

// Browsers quiet or auto-block a permission prompt that isn't a direct
// response to a click, and a `denied` permission can never be re-prompted by
// the page — so only `enablePush` (wired to a button's onClick) ever prompts.
export function getPushState(): PushState {
  if (typeof window === 'undefined' || !window.isSecureContext) {
    return { status: 'unavailable', reason: 'insecure-context' }
  }
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !getFirebaseMessaging()) {
    return { status: 'unavailable', reason: 'unsupported' }
  }
  if (Notification.permission === 'denied') return { status: 'blocked' }
  if (Notification.permission === 'granted' && sessionStorage.getItem(FCM_TOKEN_STORAGE_KEY)) {
    return { status: 'enabled' }
  }
  return { status: 'off' }
}

// The automatic refresh runs on sign-in, tab focus and a timer; toast only
// its first failure per page load so a persistent problem can't spam.
let hasReportedRefreshFailure = false

const REGISTRATION_FAILED_MESSAGE = "Couldn't turn on push notifications for this browser. You'll still see them in the bell."

export function usePushNotifications() {
  const { registerDeviceUseCase, unregisterDeviceUseCase } = useAppDependencies()
  const toast = useToast()

  const registerWithGrantedPermission = useCallback(async (): Promise<void> => {
    const messaging = getFirebaseMessaging()
    if (!messaging) return

    const token = await getToken(messaging, { vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY })
    if (!token) throw new Error('Firebase returned no registration token')

    await registerDeviceUseCase.execute(token)
    sessionStorage.setItem(FCM_TOKEN_STORAGE_KEY, token)
  }, [registerDeviceUseCase])

  // Must only be called from a click handler — it may show the browser's
  // permission prompt. Returns the resulting state for the caller to render.
  const enablePush = useCallback(async (): Promise<PushState> => {
    const before = getPushState()
    if (before.status === 'unavailable' || before.status === 'blocked') return before

    try {
      if (Notification.permission === 'default') {
        await Notification.requestPermission()
      }
      if (Notification.permission === 'granted') {
        await registerWithGrantedPermission()
      }
    } catch (error) {
      console.error('Failed to register device for push notifications', error)
      toast.error(REGISTRATION_FAILED_MESSAGE)
    }
    return getPushState()
  }, [registerWithGrantedPermission, toast])

  // Never prompts: re-registers (picking up a rotated FCM token) only when
  // the user already granted permission.
  const refreshRegistrationIfGranted = useCallback(async (): Promise<void> => {
    const state = getPushState()
    if (state.status === 'unavailable' || Notification.permission !== 'granted') return

    try {
      await registerWithGrantedPermission()
    } catch (error) {
      console.error('Failed to refresh push notification registration', error)
      if (!hasReportedRefreshFailure) {
        hasReportedRefreshFailure = true
        toast.error(REGISTRATION_FAILED_MESSAGE)
      }
    }
  }, [registerWithGrantedPermission, toast])

  const unregisterCurrentDevice = useCallback(async () => {
    const token = sessionStorage.getItem(FCM_TOKEN_STORAGE_KEY)
    if (!token) return

    try {
      await unregisterDeviceUseCase.execute(token)
    } catch (error) {
      console.error('Failed to unregister device for push notifications', error)
    } finally {
      sessionStorage.removeItem(FCM_TOKEN_STORAGE_KEY)
    }
  }, [unregisterDeviceUseCase])

  return { enablePush, refreshRegistrationIfGranted, unregisterCurrentDevice }
}
