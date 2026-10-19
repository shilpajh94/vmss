import { useState, type ReactNode, type TransitionEvent } from 'react'

interface CollapsibleProps {
  open: boolean
  children: ReactNode
  /**
   * Classes applied only while closed, typically a negative top margin equal
   * to the parent's flex/grid gap (e.g. PAGE_HEADER_GAP_CANCEL) so the closed
   * region takes no space at all, exactly like the old conditional render.
   * The margin transitions together with the height.
   */
  closedClassName?: string
  className?: string
}

// Expands/collapses in place (ui-motion "Collapsible regions expand and
// collapse smoothly") using the grid-template-rows 0fr <-> 1fr technique,
// so no height measuring is needed and content that changes size while
// open just works. Closed content is `inert` - not focusable, not read
// out. Overflow is clipped only while animating or closed, then released
// once fully open, so an autocomplete menu or focus ring inside isn't cut
// off.
export function Collapsible({ open, children, closedClassName = '', className = '' }: CollapsibleProps) {
  const [isSettledOpen, setIsSettledOpen] = useState(open)
  if (!open && isSettledOpen) setIsSettledOpen(false)

  const handleTransitionEnd = (event: TransitionEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget || event.propertyName !== 'grid-template-rows') return
    if (open) setIsSettledOpen(true)
  }

  return (
    <div
      inert={!open}
      onTransitionEnd={handleTransitionEnd}
      // `visibility` transitions discretely: it flips to hidden only once the
      // collapse finishes (and to visible at the start of an expand), so the
      // closed content is also hidden from assistive tech and hit-testing.
      className={`grid transition-[grid-template-rows,opacity,margin,visibility] duration-standard ease-motion-out ${
        open ? 'visible grid-rows-[1fr] opacity-100' : `invisible grid-rows-[0fr] opacity-0 ${closedClassName}`
      }`}
    >
      <div className={`min-h-0 ${isSettledOpen ? 'overflow-visible' : 'overflow-hidden'}`}>
        <div className={className}>{children}</div>
      </div>
    </div>
  )
}
