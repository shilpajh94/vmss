// Up to two initials from a display name ("Meera Krishnan" -> "MK"), for the
// signed-in user's avatar in the staff, admin and reception top bars.
export function initialsFor(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}
