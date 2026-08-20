import { useNavigate } from 'react-router'
import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { VisitorCategory } from '../../../../domain/entities/visitor-category-schema'

interface VisitorCategoriesTableProps {
  visitorCategories: VisitorCategory[]
  onDelete: (visitorCategory: VisitorCategory) => void
}

const COLUMN_HEADERS = ['CATEGORY NAME', 'DESCRIPTION', 'BADGE COLOR', 'NDA REQUIRED', 'ESCORT REQUIRED', 'MAX DURATION']

const BADGE_COLOR: Record<VisitorCategory['badgeColor'], { label: string; swatchClassName: string }> = {
  blue: { label: 'Blue', swatchClassName: 'bg-info' },
  orange: { label: 'Orange', swatchClassName: 'bg-warning' },
  gold: { label: 'Gold', swatchClassName: 'bg-vip' },
  grey: { label: 'Grey', swatchClassName: 'bg-text-muted' },
}

function isEscortAlwaysRequired(escortRequired: string | undefined): boolean {
  return escortRequired ? escortRequired.trim().toLowerCase().startsWith('required') : false
}

export function VisitorCategoriesTable({ visitorCategories, onDelete }: VisitorCategoriesTableProps) {
  const navigate = useNavigate()

  return (
    <div className="w-full overflow-x-auto rounded-2xl border border-border bg-surface">
      <table className="w-full text-left">
        <thead>
          <tr className="bg-border-subtle">
            {COLUMN_HEADERS.map((header) => (
              <th key={header} className="px-6 py-3.5 font-body text-[13px] font-bold text-text-muted whitespace-nowrap">
                {header}
              </th>
            ))}
            <th className="px-6 py-3.5 text-right font-body text-[13px] font-bold text-text-muted whitespace-nowrap">ACTIONS</th>
          </tr>
        </thead>
        <tbody>
          {visitorCategories.map((visitorCategory) => {
            const badgeColor = BADGE_COLOR[visitorCategory.badgeColor]
            const escortEmphasized = isEscortAlwaysRequired(visitorCategory.escortRequired)

            return (
              <tr key={visitorCategory.id} className="border-b border-border-subtle">
                <td className="px-6 py-4 font-body text-sm font-semibold text-text whitespace-nowrap">{visitorCategory.name}</td>
                <td className="max-w-[175px] truncate px-6 py-4 font-body text-sm text-text-muted">{visitorCategory.description ?? '—'}</td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center gap-2">
                    <span className={`size-5 rounded border border-border ${badgeColor.swatchClassName}`} />
                    <span className="font-body text-[13px] text-text-muted">{badgeColor.label}</span>
                  </div>
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-muted whitespace-nowrap">{visitorCategory.ndaRequired ?? '—'}</td>
                <td
                  className={`px-6 py-4 font-body text-sm whitespace-nowrap ${
                    escortEmphasized ? 'font-semibold text-danger' : 'text-text-muted'
                  }`}
                >
                  {visitorCategory.escortRequired ?? '—'}
                </td>
                <td className="px-6 py-4 font-body text-sm text-text-faint whitespace-nowrap">{visitorCategory.maxDuration ?? '—'}</td>
                <td className="px-6 py-4">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => navigate(`/admin/visitor-categories/${visitorCategory.id}/edit`)}
                      aria-label={`Edit ${visitorCategory.name}`}
                      className="flex items-center justify-center rounded-lg bg-border-subtle p-2 text-text"
                    >
                      <PencilIcon className="size-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onDelete(visitorCategory)}
                      aria-label={`Delete ${visitorCategory.name}`}
                      className="flex items-center justify-center rounded-lg bg-danger/15 p-2 text-danger"
                    >
                      <TrashIcon className="size-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
