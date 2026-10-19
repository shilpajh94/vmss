import { useEffect, useState, type ComponentType, type FocusEvent, type SVGProps } from 'react'
import { createPortal } from 'react-dom'
import { useLocation } from 'react-router'
import { useSidebarCollapse } from '../../context/sidebar-collapse-context'

interface TooltipAnchor {
  left: number
  top: number
}

// Shows a rail item's label beside it on hover and keyboard focus. Rendered
// through a portal: the nav list scrolls (so an absolute tooltip would be
// clipped at the rail's edge) and the sidebar wrapper's `translate` would
// capture a `fixed` one (declutter-invitation-board design.md Decision 4).
export function useRailTooltip(label: string, enabled: boolean) {
  const location = useLocation()
  const [anchor, setAnchor] = useState<TooltipAnchor | undefined>(undefined)

  const show = (element: Element) => {
    const rect = element.getBoundingClientRect()
    // +16 clears the rail's 12px side padding, so the tooltip sits just past its edge.
    setAnchor({ left: rect.right + 16, top: rect.top + rect.height / 2 })
  }
  const hide = () => setAnchor(undefined)

  useEffect(() => {
    setAnchor(undefined)
  }, [location.pathname, enabled])

  // The anchor is a snapshot; scrolling the nav would leave it stranded.
  useEffect(() => {
    if (!anchor) return
    window.addEventListener('scroll', hide, true)
    return () => window.removeEventListener('scroll', hide, true)
  }, [anchor])

  const handlers = enabled
    ? {
        onPointerEnter: (event: { currentTarget: Element }) => show(event.currentTarget),
        onPointerLeave: hide,
        onFocus: (event: FocusEvent<HTMLElement>) => {
          if (event.currentTarget.matches(':focus-visible')) show(event.currentTarget)
        },
        onBlur: hide,
      }
    : {}

  const tooltip =
    enabled && anchor
      ? createPortal(
          <span
            aria-hidden
            style={{ left: anchor.left, top: anchor.top }}
            className="pointer-events-none fixed z-[60] -translate-y-1/2 rounded-md bg-text px-2 py-1 font-body text-xs font-medium whitespace-nowrap text-surface shadow-lg"
          >
            {label}
          </span>,
          document.body,
        )
      : null

  return { handlers, tooltip }
}

interface SidebarNavItemProps {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  label: string
  isActive: boolean
  onActivate: () => void
  activeClassName: string
  inactiveClassName: string
}

export function SidebarNavItem({ icon: Icon, label, isActive, onActivate, activeClassName, inactiveClassName }: SidebarNavItemProps) {
  const { isCollapsed } = useSidebarCollapse()
  const { handlers, tooltip } = useRailTooltip(label, isCollapsed)

  return (
    <>
      <button
        type="button"
        onClick={onActivate}
        aria-label={isCollapsed ? label : undefined}
        aria-current={isActive ? 'page' : undefined}
        {...handlers}
        className={`flex w-full shrink-0 items-center rounded-lg py-3 text-left font-body text-sm font-semibold whitespace-nowrap ${
          isCollapsed ? 'justify-center px-0' : 'gap-3 px-4'
        } ${isActive ? activeClassName : inactiveClassName}`}
      >
        <Icon className="size-[18px] shrink-0" />
        {isCollapsed ? null : label}
      </button>
      {tooltip}
    </>
  )
}
