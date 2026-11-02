import { useState } from 'react'
import { Modal } from '../../../components/ui/Modal'
import { PendingButton } from '../../../components/ui/PendingButton'
import { TextareaField } from '../../../components/ui/TextareaField'
import type { VisitorCategoryBulkCreateOut } from '../../../../domain/entities/visitor-category-out-schema'

interface BulkAddCategoriesModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (names: string[]) => void
  isSubmitting: boolean
  result: VisitorCategoryBulkCreateOut | undefined
}

function parseNames(text: string): string[] {
  return text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

export function BulkAddCategoriesModal({ isOpen, onClose, onSubmit, isSubmitting, result }: BulkAddCategoriesModalProps) {
  const [namesText, setNamesText] = useState('')

  const names = parseNames(namesText)

  const handleClose = () => {
    setNamesText('')
    onClose()
  }

  const handleSubmit = () => {
    if (names.length === 0) return
    onSubmit(names)
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Bulk Add Visitor Categories" maxWidthClassName="max-w-lg">
      <p className="-mt-3 font-body text-sm text-text-muted">
        One category name per line. Badge color, NDA, escort, and duration can be set per-category afterward via "Add
        Category".
      </p>

      {!result ? (
        <>
          <TextareaField
            label="Category Names"
            value={namesText}
            onChange={setNamesText}
            placeholder={'Laptop Service\nInterviews\nA.C. Worker'}
            rows={10}
          />
          <div className="flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text"
            >
              Cancel
            </button>
            <PendingButton
              onClick={handleSubmit}
              disabled={names.length === 0}
              pending={isSubmitting}
              pendingLabel="Adding…"
              className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent disabled:opacity-60"
            >
              {`Add ${names.length} ${names.length === 1 ? 'Category' : 'Categories'}`}
            </PendingButton>
          </div>
        </>
      ) : (
        <>
          <p className="font-body text-sm font-semibold text-text">
            Created {result.createdCount}, skipped {result.skippedCount}
          </p>
          <div className="flex max-h-64 flex-col gap-1.5 overflow-y-auto rounded-lg border border-border p-3">
            {result.items.map((item, index) => (
              <div key={`${item.name}-${index}`} className="flex items-center justify-between gap-3 font-body text-sm">
                <span className="text-text">{item.name}</span>
                {item.status === 'created' ? (
                  <span className="text-success-text">Created</span>
                ) : (
                  <span className="text-text-muted">{item.reason}</span>
                )}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-end">
            <button
              type="button"
              onClick={handleClose}
              className="rounded-full bg-admin-accent px-4 py-2 font-body text-[13px] font-semibold text-on-accent"
            >
              Done
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
