// Shared hover/press feedback for clickable controls (ui-motion
// "Interactive controls give immediate visual feedback"): a smooth color
// transition on the short motion step plus a slight press-in on solid
// buttons. `scale` changes only the painted box, never layout, so nothing
// around the control moves.
export const PRESS_FEEDBACK_CLASS =
  'transition-[background-color,color,border-color,box-shadow,opacity,scale] duration-fast ease-motion-out active:scale-[0.98] disabled:active:scale-100'
