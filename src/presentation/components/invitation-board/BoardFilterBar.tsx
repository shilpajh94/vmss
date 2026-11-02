import type { ComponentType, ReactNode, SVGProps } from 'react'
import { SearchGlyphIcon, TagIcon, UsersIcon, XIcon } from '../icons'
import type { DropdownOption } from '../ui/DropdownFilter'
import { MultiSelectFilter } from '../ui/MultiSelectFilter'
import { REGISTRATION_TYPE_OPTIONS } from './filter-options'

export interface BoardExtraFilter {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  values: string[]
  options: DropdownOption[]
  onChange: (values: string[]) => void
  allLabel: string
  ariaLabel: string
}

export interface BoardDashboardChip {
  key: string
  label: string
  onRemove: () => void
}

interface BoardFilterBarProps {
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
  purposeFilter: string[]
  onPurposeFilterChange: (values: string[]) => void
  purposeOptions: DropdownOption[]
  registrationTypeFilter: string[]
  onRegistrationTypeFilterChange: (values: string[]) => void
  /** Further dropdowns after Registration Type (e.g. the admin board's Status and Source). */
  extraFilters?: BoardExtraFilter[]
  /** The dashboard drill-down the board was opened with, one removable chip per filter. */
  dashboardChips?: BoardDashboardChip[]
  isFiltering?: boolean
  onClearFilters?: () => void
  /** Rendered last in the bar, e.g. the staff dashboard's Export button. */
  trailingAction?: ReactNode
}

// Shared by the staff dashboard and the admin Invitations board so the two
// bars can't drift apart.
export function BoardFilterBar({
  search,
  onSearchChange,
  searchPlaceholder = 'Search visitor, host, REQ ID...',
  purposeFilter,
  onPurposeFilterChange,
  purposeOptions,
  registrationTypeFilter,
  onRegistrationTypeFilterChange,
  extraFilters = [],
  dashboardChips = [],
  isFiltering = false,
  onClearFilters,
  trailingAction,
}: BoardFilterBarProps) {
  // Always allowed to wrap: a forced single row clipped whatever didn't fit
  // (the admin bar's Source dropdown at 1280px, "Clear filters" once a filter
  // was set, the staff bar's Export button at 1024px). The search field's
  // 240px minimum means the controls still share one row whenever they fit.
  return (
    <div className="flex w-full flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="flex h-10 min-w-0 flex-none items-center gap-3 rounded-lg sm:flex-1 border border-border bg-surface px-3 sm:min-w-[240px] focus-within:ring-2 focus-within:ring-secondary-accent">
        <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
        <input
          type="text"
          aria-label="Search invitations by visitor or tracking ID"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder={searchPlaceholder}
          className="min-w-0 flex-1 bg-transparent font-body text-sm text-text placeholder:text-text-faint focus:outline-none max-sm:text-base"
        />
      </div>

      <MultiSelectFilter
        icon={TagIcon}
        values={purposeFilter}
        options={purposeOptions}
        onChange={onPurposeFilterChange}
        allLabel="All purposes"
        ariaLabel="Purpose of visit"
      />
      <MultiSelectFilter
        icon={UsersIcon}
        values={registrationTypeFilter}
        options={REGISTRATION_TYPE_OPTIONS}
        onChange={onRegistrationTypeFilterChange}
        allLabel="All types"
        ariaLabel="Registration type"
      />
      {extraFilters.map((filter) => (
        <MultiSelectFilter
          key={filter.ariaLabel}
          icon={filter.icon}
          values={filter.values}
          options={filter.options}
          onChange={filter.onChange}
          allLabel={filter.allLabel}
          ariaLabel={filter.ariaLabel}
        />
      ))}

      {onClearFilters && isFiltering ? (
        <button
          type="button"
          onClick={onClearFilters}
          className="min-h-10 shrink-0 px-1 font-body text-[13px] font-semibold whitespace-nowrap text-admin-accent"
        >
          Clear filters
        </button>
      ) : null}
      {trailingAction ? <div className="flex shrink-0 sm:ml-auto [&>*]:w-full sm:[&>*]:w-auto">{trailingAction}</div> : null}

      {/* Its own full-width row, so the chips explain why the board shows
          fewer cards than usual without crowding the controls. */}
      {dashboardChips.length > 0 ? (
        <div role="group" aria-label="From dashboard" className="flex min-w-0 flex-wrap items-center gap-2 sm:basis-full">
          <span className="font-body text-xs font-semibold text-text-faint">From dashboard</span>
          {dashboardChips.map((chip) => (
            <span
              key={chip.key}
              className="inline-flex max-w-full min-w-0 items-center gap-1 rounded-full border border-border bg-surface py-0.5 pr-1 pl-3 font-body text-xs font-semibold text-text"
            >
              <span className="truncate">{chip.label}</span>
              <button
                type="button"
                onClick={chip.onRemove}
                aria-label={`Remove filter ${chip.label}`}
                className="flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full text-text-faint hover:bg-border-subtle hover:text-text"
              >
                <XIcon className="size-3.5" />
              </button>
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
