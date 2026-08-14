import { FilterIcon, RefreshCcwIcon, SearchGlyphIcon } from './icons'

interface SearchActionBarProps {
  search: string
  onSearchChange: (value: string) => void
  onRefresh: () => void
}

export function SearchActionBar({ search, onSearchChange, onRefresh }: SearchActionBarProps) {
  return (
    <div className="flex w-full items-center gap-6">
      <div className="flex flex-1 items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3">
        <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search visitor, host, REQ ID..."
          className="flex-1 bg-transparent font-body text-sm text-text placeholder:text-text-faint focus:outline-none"
        />
        <button
          type="button"
          onClick={onRefresh}
          className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-[#cbd5e1] bg-bg"
          aria-label="Refresh"
        >
          <RefreshCcwIcon className="size-4 text-text-muted" />
        </button>
        <button type="button" className="flex shrink-0 items-center gap-1.5 rounded-md bg-bg px-3 py-1.5 font-body text-xs font-semibold text-text-muted">
          <FilterIcon className="size-3.5" />
          Filters
        </button>
      </div>

      <button
        type="button"
        onClick={onRefresh}
        className="flex shrink-0 items-center gap-2 rounded-lg border border-[#cbd5e1] bg-bg px-3 py-2 font-body text-[13px] font-semibold text-[#334155]"
      >
        <RefreshCcwIcon className="size-4" />
        Refresh
      </button>
    </div>
  )
}
