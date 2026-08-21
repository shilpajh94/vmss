import { useState } from 'react'
import { SegmentedToggle } from '../../../../components/ui/SegmentedToggle'
import { TextField } from '../../../../components/ui/TextField'
import type { Vehicle } from '../../../../../domain/entities/vehicle-schema'

const VEHICLE_TYPE_OPTIONS = [
  { value: '2_wheeler', label: '2 Wheeler' },
  { value: '4_wheeler', label: '4 Wheeler' },
  { value: 'heavy', label: 'Heavy' },
]

function createEmptyVehicle(): Vehicle {
  return { vehicleType: '2_wheeler', licensePlate: '', makeModel: '', color: '' }
}

interface VehicleInfoStepProps {
  vehicles: Vehicle[]
  onChange: (vehicles: Vehicle[]) => void
  errors: Record<string, string>
}

export function VehicleInfoStep({ vehicles, onChange, errors }: VehicleInfoStepProps) {
  const [draftVehicle, setDraftVehicle] = useState<Vehicle | null>(null)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [draftError, setDraftError] = useState<string | undefined>(undefined)

  const startAddVehicle = () => {
    setEditingIndex(null)
    setDraftError(undefined)
    setDraftVehicle(createEmptyVehicle())
  }

  const startEditVehicle = (index: number) => {
    setEditingIndex(index)
    setDraftError(undefined)
    setDraftVehicle(vehicles[index])
  }

  const cancelDraft = () => {
    setDraftVehicle(null)
    setEditingIndex(null)
    setDraftError(undefined)
  }

  const commitDraft = () => {
    if (!draftVehicle) return
    if (!draftVehicle.licensePlate || !draftVehicle.makeModel || !draftVehicle.color) {
      setDraftError('License plate, make/model, and color are required.')
      return
    }
    if (editingIndex === null) {
      onChange([...vehicles, draftVehicle])
    } else {
      onChange(vehicles.map((vehicle, index) => (index === editingIndex ? draftVehicle : vehicle)))
    }
    setDraftVehicle(null)
    setEditingIndex(null)
    setDraftError(undefined)
  }

  const removeVehicle = (index: number) => {
    onChange(vehicles.filter((_, vehicleIndex) => vehicleIndex !== index))
  }

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
                <th className="px-4 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((vehicle, index) => (
                <tr key={index} className="border-t border-border-subtle text-text">
                  <td className="px-4 py-2">{index + 1}</td>
                  <td className="px-4 py-2">{VEHICLE_TYPE_OPTIONS.find((option) => option.value === vehicle.vehicleType)?.label}</td>
                  <td className="px-4 py-2">{vehicle.licensePlate}</td>
                  <td className="px-4 py-2">{vehicle.makeModel}</td>
                  <td className="px-4 py-2">{vehicle.color}</td>
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
              options={VEHICLE_TYPE_OPTIONS}
              value={draftVehicle.vehicleType}
              onChange={(vehicleType) => setDraftVehicle({ ...draftVehicle, vehicleType: vehicleType as Vehicle['vehicleType'] })}
            />
          </div>
          <div className="grid grid-cols-3 gap-4">
            <TextField
              label="License Plate"
              placeholder="Enter plate number"
              value={draftVehicle.licensePlate}
              onChange={(licensePlate) => setDraftVehicle({ ...draftVehicle, licensePlate })}
            />
            <TextField
              label="Make / Model"
              placeholder="e.g. Honda City"
              value={draftVehicle.makeModel}
              onChange={(makeModel) => setDraftVehicle({ ...draftVehicle, makeModel })}
            />
            <TextField
              label="Color"
              placeholder="e.g. White"
              value={draftVehicle.color}
              onChange={(color) => setDraftVehicle({ ...draftVehicle, color })}
            />
          </div>
          {draftError && <p className="text-caption text-danger">{draftError}</p>}
          <div className="flex gap-3">
            <button type="button" onClick={commitDraft} className="rounded-lg bg-secondary-accent px-4 py-2 text-body font-semibold text-white">
              Add to List
            </button>
            <button type="button" onClick={cancelDraft} className="text-body font-semibold text-text-muted">
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
