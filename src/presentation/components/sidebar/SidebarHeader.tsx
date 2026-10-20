import { BRAND_NAME } from '../../brand'
import { BrandLogo } from '../BrandLogo'
import { PanelLeftCloseIcon, PanelLeftOpenIcon, XIcon } from '../icons'
import { NAV_DRAWER_ID, useNavDrawer } from '../../context/nav-drawer-context'
import { useSidebarCollapse } from '../../context/sidebar-collapse-context'

interface SidebarHeaderProps {
  onHome: () => void
  className?: string
}

// Logo (home link), the drawer's close button below `lg`, and the rail
// toggle from `lg` up. Collapsed, the wordmark gives way to the "V" mark and
// the toggle stacks beneath it so both fit the 48px rail interior.
export function SidebarHeader({ onHome, className = '' }: SidebarHeaderProps) {
  const { closeNav } = useNavDrawer()
  const { isCollapsed, toggleCollapsed } = useSidebarCollapse()

  return (
    <div className={`flex shrink-0 items-center gap-2 ${isCollapsed ? 'flex-col' : 'justify-between'} ${className}`}>
      <button type="button" onClick={onHome} aria-label={`${BRAND_NAME} home`} className="flex shrink-0 items-center text-left">
        {isCollapsed ? <BrandLogo variant="mark" decorative /> : <BrandLogo variant="on-dark" decorative />}
      </button>
      <button
        type="button"
        onClick={closeNav}
        aria-label="Close navigation menu"
        className="flex size-10 shrink-0 items-center justify-center rounded-lg text-sidebar-muted hover:bg-white/5 lg:hidden"
      >
        <XIcon className="size-5" />
      </button>
      <button
        type="button"
        onClick={toggleCollapsed}
        aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-expanded={!isCollapsed}
        aria-controls={NAV_DRAWER_ID}
        className="hidden size-9 shrink-0 items-center justify-center rounded-lg text-sidebar-muted hover:bg-white/5 hover:text-white focus-visible:ring-2 focus-visible:ring-white/40 focus-visible:outline-none lg:flex"
      >
        {isCollapsed ? <PanelLeftOpenIcon className="size-[18px]" /> : <PanelLeftCloseIcon className="size-[18px]" />}
      </button>
    </div>
  )
}
