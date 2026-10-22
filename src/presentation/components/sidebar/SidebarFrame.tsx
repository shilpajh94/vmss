import type { ReactNode } from 'react'
import { useSidebarCollapse } from '../../context/sidebar-collapse-context'

interface SidebarFrameProps {
  /** Docked width when expanded, e.g. `lg:w-[280px]`, plus its drawer width. */
  expandedWidthClassName: string
  /** Vertical gap between header, nav, and footer when expanded. */
  gapClassName: string
  children: ReactNode
}

// The `<aside>` every role's sidebar renders into (declutter-invitation-board
// design.md Decision 3). Collapsed, it shrinks to a 72px icon rail; the
// width eases between the two states unless the user prefers reduced motion.
export function SidebarFrame({ expandedWidthClassName, gapClassName, children }: SidebarFrameProps) {
  const { isCollapsed } = useSidebarCollapse()
  return (
    <aside
      className={`flex h-full shrink-0 flex-col self-stretch overflow-hidden bg-sidebar transition-[width,padding] duration-200 ease-out motion-reduce:transition-none lg:h-auto ${
        isCollapsed ? 'w-[72px] gap-4 px-3 py-6' : `${expandedWidthClassName} ${gapClassName} p-6`
      }`}
    >
      {children}
    </aside>
  )
}
