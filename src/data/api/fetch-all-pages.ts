// Pickers need the whole option list, but list endpoints cap `pageSize` at
// 100 (design D-W9). Reads page 1, then the remaining pages in parallel,
// stopping at `max` items so a runaway table can't stall the page.

interface PagedResponse<T> {
  data: T[]
  pagination: { totalPages: number }
}

export async function fetchAllPages<T>(
  fetchPage: (page: number, pageSize: number) => Promise<PagedResponse<T>>,
  { pageSize = 100, max = 2000 }: { pageSize?: number; max?: number } = {},
): Promise<T[]> {
  const first = await fetchPage(1, pageSize)
  const lastPage = Math.min(first.pagination.totalPages, Math.ceil(max / pageSize))
  const rest = await Promise.all(Array.from({ length: Math.max(lastPage - 1, 0) }, (_, index) => fetchPage(index + 2, pageSize)))
  return [first, ...rest].flatMap((response) => response.data).slice(0, max)
}
