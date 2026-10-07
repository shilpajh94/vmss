import { useState } from 'react'
import { CustomFieldsSection } from '../../../../components/dynamic-fields/CustomFieldsSection'
import type { DynamicFieldValue } from '../../../../components/dynamic-fields/DynamicField'
import { resolveGroupFlatValues } from '../../../../components/dynamic-fields/field-group-visibility'
import { FieldGroupsSection } from '../../../../components/dynamic-fields/FieldGroupsSection'
import { formatDynamicFieldValue } from '../../../../components/dynamic-fields/format-dynamic-field-value'
import type { GroupInstance } from '../../../../components/dynamic-fields/RepeatableFieldGroup'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { TextField } from '../../../../components/ui/TextField'
import type { EffectiveFormFieldGroup, FormField } from '../../../../../domain/entities/form-builder-schema'
import type { VehicleFormEntry } from '../../types'

function createEmptyVehicle(vehicleTypeOptions: string[]): VehicleFormEntry {
  return { vehicleType: vehicleTypeOptions[0] ?? '', licensePlate: '', makeModel: '', color: '', customFieldValues: {} }
}

export interface VehicleInfoFieldState {
  makeModelActive: boolean
  makeModelRequired: boolean
  colorActive: boolean
  colorRequired: boolean
  /** Branch-configured (form-builder) Vehicle Type choices — the field's
   * own `options`, not a fixed set
   * (make-id-proof-and-vehicle-type-configurable). */
  vehicleTypeOptions: string[]
}

interface VehicleInfoStepProps {
  vehicles: VehicleFormEntry[]
  onChange: (vehicles: VehicleFormEntry[]) => void
  errors: Record<string, string>
  /** Branch-configured (form-builder) active/required state for the
   * non-locked `make_model`/`color` fields — `vehicleType`/`licensePlate`
   * are locked and always shown/required.
   */
  vehicleInfoFields: VehicleInfoFieldState
  /** Admin-authored (non-system) Vehicle Info fields
   * (add-generic-custom-field-support) — each vehicle's own answers live
   * on its own `customFieldValues`, independent of every other vehicle's. */
  customFields: FormField[]
  /** Vehicle Info's own admin-defined field groups
   * (add-repeatable-field-groups / add-conditional-field-groups), rendered
   * once for the whole step (not per-vehicle) via `FieldGroupsSection` —
   * same pattern as the Visitor Info step's own groups. */
  groups: EffectiveFormFieldGroup[]
  /** Every non-system Vehicle Info field, including grouped ones — used to
   * resolve `groups`' `fieldKeys` (`customFields` above excludes them). */
  groupFields: FormField[]
  groupValues: Record<string, GroupInstance[]>
  onGroupValuesChange: (groupValues: Record<string, GroupInstance[]>) => void
  /** Required for an active `file_upload` field among `customFields`/one of
   * `groups` to render a working upload control instead of falling back to
   * "not supported". */
  uploadFile?: (file: File) => Promise<string>
  getFilePreviewUrl?: (fileRef?: string) => string | undefined
}

export function VehicleInfoStep({
  vehicles,
  onChange,
  errors,
  vehicleInfoFields,
  customFields,
  groups,
  groupFields,
  groupValues,
  onGroupValuesChange,
  uploadFile,
  getFilePreviewUrl,
}: VehicleInfoStepProps) {
  const [draftVehicle, setDraftVehicle] = useState<VehicleFormEntry | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({})

  const startAddVehicle = () => {
    setEditingIndex(null)
    setDraftErrors({})
    setDraftVehicle(createEmptyVehicle(vehicleInfoFields.vehicleTypeOptions))
  }

  const startEditVehicle = (index: number) => {
    setEditingIndex(index)
    setDraftErrors({})
    setDraftVehicle(vehicles[index])
  }

  const cancelDraft = () => {
    setDraftVehicle(null)
    setEditingIndex(null)
    setDraftErrors({})
  }

  const commitDraft = () => {
    if (!draftVehicle) return
    const errors: Record<string, string> = {}
    if (!draftVehicle.licensePlate) errors.licensePlate = 'License plate number is required.'
    if (vehicleInfoFields.makeModelActive && vehicleInfoFields.makeModelRequired && !draftVehicle.makeModel) {
      errors.makeModel = 'Make / Model is required.'
    }
    if (vehicleInfoFields.colorActive && vehicleInfoFields.colorRequired && !draftVehicle.color) {
      errors.color = 'Color is required.'
    }
    if (Object.keys(errors).length > 0) {
      setDraftErrors(errors)
      return
    }
    if (editingIndex === null) {
      onChange([...vehicles, draftVehicle])
    } else {
      onChange(vehicles.map((vehicle, index) => (index === editingIndex ? draftVehicle : vehicle)))
    }
    setDraftVehicle(null)
    setEditingIndex(null)
    setDraftErrors({})
  }

  const removeVehicle = (index: number) => {
    onChange(vehicles.filter((_, vehicleIndex) => vehicleIndex !== index))
  }

  // Unlike Visitor Info, Vehicle Info has no single step-level "current"
  // entry to seed a group condition from — every field lives on a specific
  // vehicle instance, not the step itself — so this only resolves values
  // from the step's own non-repeatable groups (see `resolveGroupFlatValues`).
  const groupFlatValues = resolveGroupFlatValues(groups, groupValues, {})

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-h3 text-text">Vehicle Information</h3>
          <p className="text-body text-text-muted">List the vehicles you will be bringing to the premises.</p>
        </div>
        <button type="button" onClick={startAddVehicle} className="rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-white">
          + Add Vehicle
        </button>
      </div>

      {errors.vehicles && <p className="text-caption text-danger">{errors.vehicles}</p>}

      {vehicles.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-left text-body">
            <thead className="bg-surface text-caption text-text-muted">
              <tr>
                <th className="px-4 py-2">#</th>
                <th className="px-4 py-2">Vehicle Type</th>
                <th className="px-4 py-2">License Plate</th>
                <th className="px-4 py-2">Make / Model</th>
                <th className="px-4 py-2">Color</th>
                {customFields.map((field) => (
                  <th key={field.key} className="px-4 py-2">
                    {field.label}
                  </th>
                ))}
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((vehicle, index) => (
                <tr key={index} className="border-t border-border-subtle text-text">
                  <td className="px-4 py-2">{index + 1}</td>
                  <td className="px-4 py-2">{vehicle.vehicleType}</td>
                  <td className="px-4 py-2">{vehicle.licensePlate}</td>
                  <td className="px-4 py-2">{vehicle.makeModel}</td>
                  <td className="px-4 py-2">{vehicle.color}</td>
                  {customFields.map((field) => (
                    <td key={field.key} className="px-4 py-2">
                      {formatDynamicFieldValue(field, (vehicle.customFieldValues as Record<string, DynamicFieldValue> | undefined)?.[field.key])}
                    </td>
                  ))}
                  <td className="px-4 py-2">
                    <button type="button" onClick={() => startEditVehicle(index)} className="mr-2 text-secondary-accent">
                      Edit
                    </button>
                    <button type="button" onClick={() => removeVehicle(index)} className="text-danger">
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {draftVehicle && (
        <div className="flex flex-col gap-4 rounded-lg border border-border-subtle bg-surface p-4">
          <h4 className="text-body font-semibold text-text">Add New Vehicle</h4>
          <div className="flex flex-col gap-1.5">
            <span className="text-body font-medium text-text">Vehicle Type</span>
            <SegmentedToggle
              options={vehicleInfoFields.vehicleTypeOptions.map((option) => ({ value: option, label: option }))}
              value={draftVehicle.vehicleType}
              onChange={(vehicleType) => setDraftVehicle({ ...draftVehicle, vehicleType })}
              variant="pill"
            />
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <TextField
              label="License Plate"
              placeholder="Enter plate number"
              value={draftVehicle.licensePlate}
              onChange={(licensePlate) => setDraftVehicle({ ...draftVehicle, licensePlate })}
              error={draftErrors.licensePlate}
              required
            />
            {vehicleInfoFields.makeModelActive && (
              <TextField
                label="Make / Model"
                placeholder="e.g. Honda City"
                value={draftVehicle.makeModel}
                onChange={(makeModel) => setDraftVehicle({ ...draftVehicle, makeModel })}
                error={draftErrors.makeModel}
                required={vehicleInfoFields.makeModelRequired}
              />
            )}
            {vehicleInfoFields.colorActive && (
              <TextField
                label="Color"
                placeholder="e.g. White"
                value={draftVehicle.color}
                onChange={(color) => setDraftVehicle({ ...draftVehicle, color })}
                error={draftErrors.color}
                required={vehicleInfoFields.colorRequired}
              />
            )}
          </div>
          <CustomFieldsSection
            fields={customFields}
            value={(draftVehicle.customFieldValues ?? {}) as Record<string, DynamicFieldValue>}
            onChange={(customFieldValues) => setDraftVehicle({ ...draftVehicle, customFieldValues })}
            uploadFile={uploadFile}
            getFilePreviewUrl={getFilePreviewUrl}
          />
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={commitDraft} className="rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-white">
              Add to List
            </button>
            <button type="button" onClick={cancelDraft} className="text-body font-semibold text-text-muted">
              Cancel
            </button>
          </div>
        </div>
      )}

      <FieldGroupsSection
        groups={groups}
        fields={groupFields}
        flatValues={groupFlatValues}
        groupValues={groupValues}
        onGroupValuesChange={onGroupValuesChange}
        uploadFile={uploadFile}
        getFilePreviewUrl={getFilePreviewUrl}
      />
    </div>
  )
}
