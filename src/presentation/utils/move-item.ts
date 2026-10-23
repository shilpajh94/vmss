// A drag-and-drop reorder: the item with `fromId` moved to where `toId` is.
// Returns undefined when either id isn't in the list (a stale drop), so the
// caller can ignore it. The input is never mutated.
export function moveItem<T extends { id: string }>(items: readonly T[], fromId: unknown, toId: unknown): T[] | undefined {
  const fromIndex = items.findIndex((item) => item.id === fromId)
  const toIndex = items.findIndex((item) => item.id === toId)
  if (fromIndex === -1 || toIndex === -1) return undefined
  const reordered = [...items]
  const [moved] = reordered.splice(fromIndex, 1)
  reordered.splice(toIndex, 0, moved)
  return reordered
}
