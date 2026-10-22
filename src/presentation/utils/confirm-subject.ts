// How every invitation-action confirmation names what it acts on:
// "Meera Krishnan (INV-B8490B0B)", or a neutral fallback while the card's
// details aren't at hand.
export function confirmSubject(visitorName?: string, trackingId?: string): string {
  if (!visitorName) return trackingId ?? 'this visit request'
  return trackingId ? `${visitorName} (${trackingId})` : visitorName
}
