import z from "zod"

export const DevicePlatformSchema = z.enum(["web", "android", "ios"])

export type DevicePlatform = z.infer<typeof DevicePlatformSchema>

export const DeviceSchema = z.object({
  id: z.string().min(1),
  platform: DevicePlatformSchema,
  lastSeenAt: z.string().min(1),
})

export type Device = z.infer<typeof DeviceSchema>

export const DeviceRegisterRequestSchema = z.object({
  fcmToken: z.string().min(1),
  platform: DevicePlatformSchema,
})

export type DeviceRegisterRequest = z.infer<typeof DeviceRegisterRequestSchema>

export const DeviceResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DeviceSchema,
})

export type DeviceResponse = z.infer<typeof DeviceResponseSchema>

export const UnregisterDeviceResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.null(),
})

export type UnregisterDeviceResponse = z.infer<typeof UnregisterDeviceResponseSchema>
