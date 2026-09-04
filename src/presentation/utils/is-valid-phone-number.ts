// Accepts common formatting (spaces, hyphens, parens, a leading +) and just
// checks the digit count falls in a plausible phone-number range, rather than
// enforcing one country's format.
export function isValidPhoneNumber(value: string): boolean {
  const digits = value.replace(/\D/g, '')
  return digits.length >= 7 && digits.length <= 15
}
