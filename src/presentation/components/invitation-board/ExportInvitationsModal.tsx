import { useState } from 'react'
import { Modal } from '../ui/Modal'
import { SelectField } from '../ui/SelectField'
import { TextField } from '../ui/TextField'
import { SegmentedToggle } from '../ui/SegmentedToggle'
import type { InvitationExportFormat } from '../../../data/repositories/visit-request-summary-repository'
import { STATUS_OPTIONS, exportDateLabel } from './filter-options'

export interface InvitationExportChoice {
  status: string
  dateFrom: string
  dateTo: string
  format: InvitationExportFormat
}

interface ExportInvitationsModalProps {
  isOpen: boolean
  /** The board's Status filter ('' = All statuses) — the dialog's starting value. */
  initialStatus: string
  /** Labels for the board's other active filters, which the export also applies. */
  appliedFilters: string[]
  isExporting: boolean
  errorMessage?: string
  onConfirm: (choice: InvitationExportChoice) => void
  onClose: () => void
}

const FORMAT_OPTIONS = [
  { value: 'csv', label: 'CSV' },
  { value: 'xlsx', label: 'Excel' },
]

const LABEL_CLASS = 'font-body text-[13px] font-semibold text-text'

export function ExportInvitationsModal({ isOpen, onClose, isExporting, ...formProps }: ExportInvitationsModalProps) {
  const handleClose = () => {
    if (isExporting) return
    onClose()
  }

  // The form only mounts while open, so every opening starts again from the
  // board's current Status filter — and editing it never touches the board.
  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Export invitations">
      {isOpen ? <ExportInvitationsForm {...formProps} isExporting={isExporting} onCancel={handleClose} /> : null}
    </Modal>
  )
}

interface ExportInvitationsFormProps {
  initialStatus: string
  appliedFilters: string[]
  isExporting: boolean
  errorMessage?: string
  onConfirm: (choice: InvitationExportChoice) => void
  onCancel: () => void
}

function ExportInvitationsForm({ initialStatus, appliedFilters, isExporting, errorMessage, onConfirm, onCancel }: ExportInvitationsFormProps) {
  const [status, setStatus] = useState(initialStatus)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [format, setFormat] = useState<InvitationExportFormat>('csv')

  // YYYY-MM-DD strings compare correctly as text.
  const isRangeInverted = Boolean(dateFrom && dateTo && dateFrom > dateTo)

  return (
    <div className="flex flex-col gap-4">
      <SelectField
        label="Status"
        labelClassName={LABEL_CLASS}
        value={status}
        onChange={setStatus}
        options={STATUS_OPTIONS}
        placeholder="All statuses"
        placeholderSelectable
      />

      <div className="flex flex-col gap-1.5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField label="From" labelClassName={LABEL_CLASS} type="date" value={dateFrom} onChange={setDateFrom} />
          <TextField
            label="To"
            labelClassName={LABEL_CLASS}
            type="date"
            value={dateTo}
            onChange={setDateTo}
            error={isRangeInverted ? 'The To date must not be before the From date.' : undefined}
          />
        </div>
        <p className="font-body text-xs text-text-muted">
          Optional. Filters by {exportDateLabel(status).toLowerCase()}; leave both empty to include every date.
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className={LABEL_CLASS}>Format</span>
        <SegmentedToggle options={FORMAT_OPTIONS} value={format} onChange={(value) => setFormat(value as InvitationExportFormat)} variant="divided" />
      </div>

      <div className="flex flex-col gap-1 rounded-lg border border-border bg-bg px-3 py-2">
        <span className="font-body text-xs font-semibold text-text-muted">Also applies the board's filters</span>
        <p className="font-body text-[13px] text-text">{appliedFilters.length > 0 ? appliedFilters.join(' · ') : 'No other filters'}</p>
      </div>

      {errorMessage ? (
        <p role="alert" className="font-body text-[13px] text-danger">
          {errorMessage}
        </p>
      ) : null}

      <div className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={onCancel}
          disabled={isExporting}
          className="rounded-full border border-border bg-surface px-4 py-2 font-body text-[13px] font-semibold text-text disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={isExporting || isRangeInverted}
          onClick={() => onConfirm({ status, dateFrom, dateTo, format })}
          className="rounded-full bg-secondary-accent px-4 py-2 font-body text-[13px] font-semibold text-white disabled:opacity-50"
        >
          {isExporting ? 'Exporting…' : 'Export'}
        </button>
      </div>
    </div>
  )
}
