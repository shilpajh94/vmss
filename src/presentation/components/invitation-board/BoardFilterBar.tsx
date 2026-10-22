import type { ComponentType, ReactNode, SVGProps } from 'react'
import { SearchGlyphIcon, TagIcon, UsersIcon } from '../icons'
import { DropdownFilter, type DropdownOption } from '../ui/DropdownFilter'
import { REGISTRATION_TYPE_OPTIONS } from './filter-options'

export interface BoardExtraFilter {
  icon: ComponentType<SVGProps<SVGSVGElement>>
  value: string
  options: DropdownOption[]
  onChange: (value: string) => void
  ariaLabel: string
}

interface BoardFilterBarProps {
  search: string
  onSearchChange: (value: string) => void
  searchPlaceholder?: string
  purposeFilter: string
  onPurposeFilterChange: (value: string) => void
  purposeOptions: DropdownOption[]
  registrationTypeFilter: string
  onRegistrationTypeFilterChange: (value: string) => void
  /** Further dropdowns after Registration Type (e.g. the admin board's Status and Source). */
  extraFilters?: BoardExtraFilter[]
  isFiltering?: boolean
  onClearFilters?: () => void
  /** Rendered last in the bar, e.g. the staff dashboard's Export button. */
  trailingAction?: ReactNode
}

const REGISTRATION_TYPE_FILTER_OPTIONS: DropdownOption[] = [{ value: 'all', label: 'All types' }, ...REGISTRATION_TYPE_OPTIONS]

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

      <DropdownFilter icon={TagIcon} value={purposeFilter} options={purposeOptions} onChange={onPurposeFilterChange} ariaLabel="Purpose of visit" />
      <DropdownFilter
        icon={UsersIcon}
        value={registrationTypeFilter}
        options={REGISTRATION_TYPE_FILTER_OPTIONS}
        onChange={onRegistrationTypeFilterChange}
        ariaLabel="Registration type"
      />
      {extraFilters.map((filter) => (
        <DropdownFilter
          key={filter.ariaLabel}
          icon={filter.icon}
          value={filter.value}
          options={filter.options}
          onChange={filter.onChange}
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
    </div>
  )
}
