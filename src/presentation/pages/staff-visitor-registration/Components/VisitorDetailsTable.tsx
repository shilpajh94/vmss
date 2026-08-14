import { PencilIcon, TrashIcon } from '../../../components/icons'
import type { StaffVisitorFormEntry } from '../types'

interface VisitorDetailsTableProps {
  visitors: StaffVisitorFormEntry[]
  onEdit: (index: number) => void
  onRemove: (index: number) => void
}

export function VisitorDetailsTable({ visitors, onEdit, onRemove }: VisitorDetailsTableProps) {
  if (visitors.length === 0) return null

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full text-left text-body">
        <thead className="border-b border-border bg-border-subtle text-caption font-bold text-text-muted uppercase">
          <tr>
            <th className="px-4 py-2.5">#</th>
            <th className="px-4 py-2.5">Full Name</th>
            <th className="px-4 py-2.5">Email / Phone</th>
            <th className="px-4 py-2.5">ID Proof</th>
            <th className="px-4 py-2.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {visitors.map((visitor, index) => (
            <tr key={index} className="border-t border-border text-text">
              <td className="px-4 py-3 font-semibold">{index + 1}</td>
              <td className="px-4 py-3">{visitor.fullName}</td>
              <td className="px-4 py-3">{visitor.email || visitor.phone}</td>
              <td className="px-4 py-3">{visitor.idProofType}</td>
              <td className="px-4 py-3">
                <div className="flex items-center justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => onEdit(index)}
                    aria-label="Edit visitor"
                    className="flex size-8 items-center justify-center rounded-lg border border-border text-text"
                  >
                    <PencilIcon className="size-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemove(index)}
                    aria-label="Remove visitor"
                    className="flex size-8 items-center justify-center rounded-lg border border-border text-danger"
                  >
                    <TrashIcon className="size-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
