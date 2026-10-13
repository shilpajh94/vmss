import type { ComponentType, SVGProps } from 'react'
import { SearchGlyphIcon, TagIcon, UsersIcon } from '../icons'
import { DropdownFilter, type DropdownOption } from '../ui/DropdownFilter'

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
}

const REGISTRATION_TYPE_OPTIONS: DropdownOption[] = [
  { value: 'all', label: 'All types' },
  { value: 'individual', label: 'Individual' },
  { value: 'group', label: 'Group' },
]

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
}: BoardFilterBarProps) {
  // Four dropdowns plus a usable search field only fit on one row from `xl`
  // inside the admin shell; the staff bar's two fit from `lg`.
  const noWrapClass = extraFilters.length > 0 ? 'xl:flex-nowrap' : 'lg:flex-nowrap'

  return (
    <div className={`flex w-full flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center ${noWrapClass}`}>
      <div className="flex h-10 min-w-0 flex-none items-center gap-3 rounded-lg sm:flex-1 border border-border bg-surface px-3 sm:min-w-[240px]">
        <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
        <input
          type="text"
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
        options={REGISTRATION_TYPE_OPTIONS}
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
    </div>
  )
}
