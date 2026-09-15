/** Turns an admin-configured field/option key (e.g. `laptop_tablet`) into a
 * readable label (`Laptop Tablet`) for display — form-builder's `options`
 * are a flat `string[]` with no separate display-label field, so this is
 * the client-side fallback for presenting them, not a substitute for an
 * admin choosing a clearer key in the first place.
 */
export function prettifyKey(key: string): string {
  return key
    .split('_')
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}
