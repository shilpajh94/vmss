import { AdminDevicesList } from '../admin-devices/admin-devices-list'

export function AdminReceptionDesksPage() {
  return (
    <AdminDevicesList
      operatingMode="kiosk"
      title="Reception Desks"
      noun="reception desks"
      description="Review, approve, and manage registered reception desk devices"
    />
  )
}
