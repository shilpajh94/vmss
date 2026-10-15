// The page's own title row. Identity, the bell and Sign out live in the
// staff shell's shared top bar, so this holds only the title and subtitle.
export function RegistrationWorkspaceHeader() {
  return (
    <div className="flex w-full flex-col gap-1.5 border-b border-border pb-4 md:pb-5">
      <h1 className="font-display text-2xl font-extrabold text-text md:text-[28px]">Register Visitor</h1>
      <p className="font-body text-sm text-text-muted">Create a single or group pass entry request for your organization</p>
    </div>
  )
}
