// Fast2SMS (SMS/WhatsApp delivery) only reaches Indian mobiles: +91XXXXXXXXXX,
// 91XXXXXXXXXX, 0XXXXXXXXXX or 10 digits starting 6-9. The API doesn't reject
// other numbers, so the form has to.
export function isValidIndianMobileNumber(value: string): boolean {
  const digits = value.replace(/[\s\-()]/g, '').replace(/^\+/, '')
  return /^(91|0)?[6-9]\d{9}$/.test(digits)
}
