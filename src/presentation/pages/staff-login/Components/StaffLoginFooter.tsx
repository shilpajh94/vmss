import { SECURITY_POLICY_URL, TERMS_URL, copyrightLine, footerLinks } from '../../../brand'

const LINKS = footerLinks([
  { label: 'Security Policy', href: SECURITY_POLICY_URL },
  { label: 'Terms of Service', href: TERMS_URL },
])

export function StaffLoginFooter() {
  return (
    <footer className="relative flex shrink-0 w-full flex-col items-start gap-3 border-t sm:flex-row sm:items-center sm:justify-between border-border px-4 md:px-12 py-6 xshort:py-3 font-body text-[12px] text-[#cbd5e1]">
      <p>{copyrightLine()}</p>
      {LINKS.length > 0 && (
        <div className="flex items-start gap-6">
          {LINKS.map((link) => (
            <a key={link.label} href={link.href} className="hover:text-white">
              {link.label}
            </a>
          ))}
        </div>
      )}
    </footer>
  )
}
