import { copyrightLine } from '../../../brand'

export function StaffLoginFooter() {
  return (
    <footer className="relative flex shrink-0 w-full flex-col items-start gap-3 border-t sm:flex-row sm:items-center sm:justify-between border-border px-4 md:px-12 py-6 xshort:py-3 font-body text-[12px] text-[#cbd5e1]">
      <p>{copyrightLine()}</p>
      <div className="flex items-start gap-6">
        <a href="#" className="hover:text-white">
          Security Policy
        </a>
        <a href="#" className="hover:text-white">
          Terms of Service
        </a>
      </div>
    </footer>
  )
}
