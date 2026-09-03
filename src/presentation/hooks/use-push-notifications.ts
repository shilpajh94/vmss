import { useCallback } from 'react'
import { getToken } from 'firebase/messaging'
import { getFirebaseMessaging } from '../../infrastructure/firebase/firebase-app'
import { useAppDependencies } from '../context/app-dependencies-context'

// Session-scoped: a fresh registration/permission prompt happens on the next login
// in a new tab/session rather than persisting across browser restarts.
export const FCM_TOKEN_STORAGE_KEY = 'fcmToken'

// Register is also re-run on mount, on an interval, and on tab focus for an
// already-signed-in device (see PushNotificationsProvider) so a rotated FCM
// token gets re-registered without a full reload, since there is no persistent
// onTokenRefresh-equivalent listener. Unregister is only called explicitly from
// the sign-out call site.
export function usePushNotifications() {
  const { registerDeviceUseCase, unregisterDeviceUseCase } = useAppDependencies()

  const registerCurrentDevice = useCallback(async () => {
    try {
      const messaging = getFirebaseMessaging()
      if (!messaging) return

      if (Notification.permission === 'default') {
        await Notification.requestPermission()
      }
      if (Notification.permission !== 'granted') return

      const token = await getToken(messaging, { vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY })
      if (!token) return

      await registerDeviceUseCase.execute(token)
      sessionStorage.setItem(FCM_TOKEN_STORAGE_KEY, token)
    } catch (error) {
      console.error('Failed to register device for push notifications', error)
    }
  }, [registerDeviceUseCase])

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

  return { registerCurrentDevice, unregisterCurrentDevice }
}
