/* eslint-disable no-undef */
importScripts('https://www.gstatic.com/firebasejs/12.18.0/firebase-app-compat.js')
importScripts('https://www.gstatic.com/firebasejs/12.18.0/firebase-messaging-compat.js')

// Public web app config only — safe to ship in a service worker. No VAPID key here;
// that's only needed client-side for getToken(), not for receiving background messages.
firebase.initializeApp({
  apiKey: 'AIzaSyDp21Nj9ciKESKpgI-Cw2lJ9bzN-S3y-MA',
  authDomain: 'vmss-b2c5b.firebaseapp.com',
  projectId: 'vmss-b2c5b',
  storageBucket: 'vmss-b2c5b.firebasestorage.app',
  messagingSenderId: '642488733766',
  appId: '1:642488733766:web:0c119b6264e29425daba47',
  measurementId: 'G-GEVBJM9KBW',
})

const messaging = firebase.messaging()

// The real push payload's `data` carries `invitationId` (and `trackingId`/`action`),
// not a recipient-role field, so admin vs. staff is inferred from whichever area
// an already-open tab (if any) is in rather than from the payload itself. Keep in
// sync with `buildInvitationPath` in src/presentation/utils/notification-links.ts
// (a service worker can't import app modules) — staff land on the invitations
// board, not `/staff/dashboard`, which is the KPI dashboard.
function buildInvitationUrl(data, isAdminContext) {
  const invitationId = data && data.invitationId
  const basePath = isAdminContext ? '/admin/invitations' : '/staff/invitations'
  return invitationId ? `${basePath}?invitationId=${encodeURIComponent(invitationId)}` : basePath
}

messaging.onBackgroundMessage((payload) => {
  // Keep in sync with BRAND_NAME in src/presentation/brand.ts (a service
  // worker can't import app modules).
  const notificationTitle = (payload.notification && payload.notification.title) || 'Visimio'
  const notificationBody = (payload.notification && payload.notification.body) || ''

  self.registration.showNotification(notificationTitle, {
    body: notificationBody,
    icon: '/apple-touch-icon.png',
    data: payload.data,
  })
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      const isAdminContext = clientList.some((client) => client.url.includes('/admin'))
      const url = buildInvitationUrl(event.notification.data, isAdminContext)

      for (const client of clientList) {
        if ('focus' in client) {
          client.navigate(url)
          return client.focus()
        }
      }
      return self.clients.openWindow(url)
    }),
  )
})
