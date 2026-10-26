// Pieces the sign-in forms and the public visitor forms share, so they read alike.

export function AuthFormHeading({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col gap-2">
      <h1 className="font-display text-[30px] leading-tight font-bold text-text xshort:text-[26px]">{title}</h1>
      {description && <p className="font-body text-[14px] leading-normal text-text-muted">{description}</p>}
    </div>
  )
}

export function AuthErrorAlert({ title, message }: { title?: string; message: string }) {
  return (
    <div role="alert" className="flex items-start gap-2.5 rounded-lg border border-danger/30 bg-danger/5 px-3.5 py-3">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" className="mt-px shrink-0 text-danger" aria-hidden>
        <path
          d="M12 8v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <div className="flex flex-col gap-0.5">
        {title && <p className="font-body text-[14px] font-semibold text-danger">{title}</p>}
        <p className="font-body text-[13px] leading-snug text-danger">{message}</p>
      </div>
    </div>
  )
}

export function AuthSecurityNote({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center gap-2">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" className="shrink-0 text-text-faint" aria-hidden>
        <path
          d="M12 2 4 5v6c0 5 3.4 8.4 8 11 4.6-2.6 8-6 8-11V5l-8-3Z"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <p className="text-center font-body text-[12px] text-text-faint">{text}</p>
    </div>
  )
}

// The hover lift moves the button 1px up; the `after:` strip under it keeps
// covering the row it left, so a pointer resting on the bottom edge doesn't
// flicker the hover on and off.
export const AUTH_PRIMARY_BUTTON_CLASS =
  'relative after:absolute after:inset-x-0 after:top-full after:h-0.5 flex w-full items-center justify-center gap-2.5 rounded-lg bg-secondary-accent px-6 py-3.5 font-body text-[15px] font-semibold text-white shadow-[0_8px_20px_-6px_rgba(6,182,212,0.55)] transition-[transform,box-shadow] duration-[var(--motion-fast)] hover:-translate-y-px hover:shadow-[0_12px_24px_-6px_rgba(6,182,212,0.6)] disabled:translate-y-0 disabled:opacity-60'
