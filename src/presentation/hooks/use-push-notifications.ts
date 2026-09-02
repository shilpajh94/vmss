import { useCallback } from 'react'
import { getToken } from 'firebase/messaging'
import { getFirebaseMessaging } from '../../infrastructure/firebase/firebase-app'
import { useAppDependencies } from '../context/app-dependencies-context'

// Session-scoped: a fresh registration/permission prompt happens on the next login
// in a new tab/session rather than persisting across browser restarts.
export const FCM_TOKEN_STORAGE_KEY = 'fcmToken'

// Register/unregister are called explicitly from sign-in and sign-out call sites
// (not run as a mount effect) so the device lifecycle stays easy to trace.
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
