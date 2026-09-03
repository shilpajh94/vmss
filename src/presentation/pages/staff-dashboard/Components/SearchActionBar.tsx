import { SearchGlyphIcon, TagIcon, UsersIcon } from '../../../components/icons'
import { DropdownFilter, type DropdownOption } from '../../../components/ui/DropdownFilter'

interface SearchActionBarProps {
  search: string
  onSearchChange: (value: string) => void
  purposeFilter: string
  onPurposeFilterChange: (value: string) => void
  purposeOptions: DropdownOption[]
  registrationTypeFilter: string
  onRegistrationTypeFilterChange: (value: string) => void
}

const REGISTRATION_TYPE_OPTIONS: DropdownOption[] = [
  { value: 'all', label: 'All types' },
  { value: 'individual', label: 'Individual' },
  { value: 'group', label: 'Group' },
]

export function SearchActionBar({
  search,
  onSearchChange,
  purposeFilter,
  onPurposeFilterChange,
  purposeOptions,
  registrationTypeFilter,
  onRegistrationTypeFilterChange,
}: SearchActionBarProps) {
  return (
    <div className="flex w-full items-center gap-3">
      <div className="flex flex-1 items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3">
        <SearchGlyphIcon className="size-4 shrink-0 text-text-faint" />
        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search visitor, host, REQ ID..."
          className="flex-1 bg-transparent font-body text-sm text-text placeholder:text-text-faint focus:outline-none"
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
    </div>
  )
}
