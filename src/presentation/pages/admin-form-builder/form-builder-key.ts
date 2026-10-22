// Steps, fields and groups are keyed by a slug of their name. The API only
// accepts `^[a-z][a-z0-9_]*$` up to 100 characters, so a name that slugs to
// nothing ("!!!"), to a leading digit ("1st visit") or to an over-long key
// is caught here with an inline message instead of a 422 after submit.
export const FORM_BUILDER_KEY_MAX = 100
export const FORM_BUILDER_NAME_MAX = 255

export function slugifyKey(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

// `noun` names the thing in the message ("Field label", "Group name").
export function formBuilderKeyError(name: string, noun: string): string | undefined {
  if (!name.trim()) return `${noun} is required.`
  const key = slugifyKey(name)
  if (!key) return `${noun} must contain at least one letter or number.`
  if (/^\d/.test(key)) return `${noun} must start with a letter.`
  if (key.length > FORM_BUILDER_KEY_MAX) return `${noun} is too long (its key can be at most ${FORM_BUILDER_KEY_MAX} characters).`
  return undefined
}
