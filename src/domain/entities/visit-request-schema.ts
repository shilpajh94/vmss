import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { VisitorSchema } from "./visitor-schema"

export const VisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  primaryContact: VisitorSchema,
  additionalVisitors: z.array(VisitorSchema),
  visitInfo: z.object({
    purpose: z.string().min(1),
    hostNameOrEmail: z.string().min(1),
    preferredDate: z.string().min(1),
    preferredTime: z.string().min(1),
    expectedDuration: z.string().min(1),
    location: z.string().min(1),
    building: z.string().min(1),
    department: z.string().min(1),
    notes: z.string().optional(),
  }),
  carriedItems: z.object({
    categories: z.array(z.string()),
    description: z.string().optional(),
  }),
  vehicles: z.array(VehicleSchema),
  consent: z.object({
    agreedTerms: z.boolean(),
    agreedDataUse: z.boolean(),
    agreedSafety: z.boolean(),
  }),
})

export type VisitRequest = z.infer<typeof VisitRequestSchema>

export const VisitRequestResponseSchema = z.object({
  trackingId: z.string().min(1),
  status: z.string().min(1),
  submittedAt: z.string().min(1),
})

export type VisitRequestResponse = z.infer<typeof VisitRequestResponseSchema>
