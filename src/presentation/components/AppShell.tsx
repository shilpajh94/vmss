import type { ReactNode } from 'react'

interface AppShellProps {
  sidebar: ReactNode
  topBar?: ReactNode
  mainClassName?: string
  children: ReactNode
}

// Fixes the sidebar/top bar in place and confines scrolling to the content
// region: `h-screen` + `overflow-hidden` on the outer wrapper (not
// `min-h-screen`) caps the shell at the viewport so only `<main>` scrolls,
// vertically or horizontally.
export function AppShell({ sidebar, topBar, mainClassName, children }: AppShellProps) {
  return (
    <div className="flex h-screen w-full items-stretch overflow-hidden bg-bg">
      {sidebar}

      <div className="flex h-screen flex-1 flex-col overflow-hidden">
        {topBar}

        <main className={mainClassName ?? 'flex flex-1 flex-col gap-page-section overflow-y-auto overflow-x-hidden p-page-content'}>
          {children}
        </main>
      </div>
    </div>
  )
}
