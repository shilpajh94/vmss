export function PortalFooter() {
  return (
    <footer className="w-full border-t border-border bg-surface px-12 py-10">
      <div className="flex w-full items-center justify-between">
        <div className="flex w-[400px] flex-col gap-1">
          <div className="flex items-center gap-2">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary">
              <span className="font-display text-[18px] font-extrabold text-white">V</span>
            </div>
            <span className="font-display text-[18px] font-extrabold text-text">VisitorPass</span>
          </div>
          <p className="font-body text-[13px] text-text-muted">Secure corporate guest registry and access automation.</p>
        </div>
        <div className="flex items-start gap-6 whitespace-nowrap font-body text-[13px] text-text-muted">
          <a href="#" className="hover:text-text">
            Privacy Policy
          </a>
          <a href="#" className="hover:text-text">
            Terms of Service
          </a>
          <a href="mailto:support@visitorpass.co" className="hover:text-text">
            Support Contact: support@visitorpass.co
          </a>
        </div>
      </div>
    </footer>
  )
}
