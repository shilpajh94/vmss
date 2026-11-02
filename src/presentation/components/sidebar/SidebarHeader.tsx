import { BRAND_NAME } from '../../brand'
import { BrandLogo } from '../BrandLogo'
import { CollapseSidebarIcon, ExpandSidebarIcon, XIcon } from '../icons'
import { NAV_DRAWER_ID, useNavDrawer } from '../../context/nav-drawer-context'
import { useSidebarCollapse } from '../../context/sidebar-collapse-context'
import { useRailTooltip } from './SidebarNavItem'

interface SidebarHeaderProps {
  onHome: () => void
  className?: string
}

// Logo (home link), the drawer's close button below `lg`, and the rail
// toggle from `lg` up. Collapsed, the wordmark gives way to the "V" mark and
// the toggle stacks beneath it so both fit the 48px rail interior. The
// toggle's two icons are stacked and cross-fade with a quarter turn, in step
// with SidebarFrame's width transition.
export function SidebarHeader({ onHome, className = '' }: SidebarHeaderProps) {
  const { closeNav } = useNavDrawer()
  const { isCollapsed, toggleCollapsed } = useSidebarCollapse()
  const toggleLabel = isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'
  const { handlers: tooltipHandlers, tooltip } = useRailTooltip(toggleLabel, true)
  const iconClassName =
    'absolute inset-0 size-[18px] transition-[opacity,rotate,scale] duration-standard ease-motion-out motion-reduce:transition-none'

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
        aria-label={toggleLabel}
        aria-expanded={!isCollapsed}
        aria-controls={NAV_DRAWER_ID}
        {...tooltipHandlers}
        className="hidden size-9 shrink-0 items-center justify-center rounded-lg text-sidebar-muted hover:bg-white/5 hover:text-white focus-visible:ring-2 focus-visible:ring-white/40 focus-visible:outline-none lg:flex"
      >
        <span className="relative size-[18px]">
          <CollapseSidebarIcon className={`${iconClassName} ${isCollapsed ? '-rotate-90 scale-75 opacity-0' : 'rotate-0 scale-100 opacity-100'}`} />
          <ExpandSidebarIcon className={`${iconClassName} ${isCollapsed ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-75 opacity-0'}`} />
        </span>
      </button>
      {tooltip}
    </div>
  )
}
