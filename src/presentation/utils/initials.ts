// The app-wide initials rule for person avatars (person-avatars spec): the
// first letters of the first two words of a name ("Aadarsh S Kumar" -> "AS",
// "  priya  " -> "P", "" -> ""), so a person reads the same on every surface.
export function initialsFor(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join('')
}
