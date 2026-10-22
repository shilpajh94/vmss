// A deliberately loose shape check (something@something.tld). The API's
// `EmailStr` is the real validator; this only catches a typo before submit.
export const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isValidEmail(value: string): boolean {
  return EMAIL_PATTERN.test(value.trim())
}
