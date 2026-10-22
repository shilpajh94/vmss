// Where a notification about an invitation opens. The payload carries no
// recipient-role field, so admin vs. staff is inferred from the area the
// current page is in. Keep in sync with `buildInvitationUrl` in
// public/firebase-messaging-sw.js (a service worker can't import app modules).
export function buildInvitationPath(invitationId: string): string {
  const basePath = window.location.pathname.startsWith('/admin') ? '/admin/invitations' : '/staff/invitations'
  return `${basePath}?invitationId=${encodeURIComponent(invitationId)}`
}
