import { AdminDevicesList } from '../admin-devices/admin-devices-list'

export function AdminSecurityGatesPage() {
  return (
    <AdminDevicesList
      operatingMode="security"
      title="Security Gates"
      noun="security gates"
      description="Review, approve, and manage registered security gate devices"
    />
  )
}
