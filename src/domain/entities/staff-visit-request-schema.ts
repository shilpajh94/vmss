import z from "zod"
import { VehicleSchema } from "./vehicle-schema"
import { StaffVisitorSchema } from "./staff-visitor-schema"

export const StaffVisitRequestSchema = z.object({
  registrationType: z.enum(["individual", "group"]),
  primaryContact: StaffVisitorSchema,
  additionalVisitors: z.array(StaffVisitorSchema),
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

export type StaffVisitRequest = z.infer<typeof StaffVisitRequestSchema>
