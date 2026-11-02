import z from "zod"
import { PaginationMetaSchema } from "./pagination-meta-schema"

export const DeviceOperatingModeSchema = z.enum(["kiosk", "security"])

export type DeviceOperatingMode = z.infer<typeof DeviceOperatingModeSchema>

export const DeviceApprovalStatusSchema = z.enum(["pending", "approved"])

export type DeviceApprovalStatus = z.infer<typeof DeviceApprovalStatusSchema>

export const DeviceSchema = z.object({
  id: z.string(),
  deviceId: z.string(),
  name: z.string(),
  branchId: z.string().nullish(),
  branchName: z.string().nullish(),
  buildingId: z.string().nullish(),
  buildingName: z.string().nullish(),
  operatingMode: DeviceOperatingModeSchema,
  approvalStatus: DeviceApprovalStatusSchema,
  isActive: z.boolean(),
  approvedAt: z.string().nullish(),
  createdAt: z.string(),
  canApprove: z.boolean().default(false),
  canEnable: z.boolean().default(false),
  canDisable: z.boolean().default(false),
})

export type Device = z.infer<typeof DeviceSchema>

/** Compact device reference embedded in invitation check-in/check-out responses. */
export const DeviceSummarySchema = z.object({
  id: z.string(),
  deviceId: z.string(),
  name: z.string(),
  operatingMode: z.string(),
})

export type DeviceSummary = z.infer<typeof DeviceSummarySchema>

export const DeviceResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: DeviceSchema,
})

export const DeviceListResponseSchema = z.object({
  success: z.boolean(),
  message: z.string(),
  data: z.array(DeviceSchema),
  pagination: PaginationMetaSchema,
})

export type DeviceListResponse = z.infer<typeof DeviceListResponseSchema>
