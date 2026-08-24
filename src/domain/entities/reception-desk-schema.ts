import z from "zod"

export const ReceptionDeskSchema = z.object({
  id: z.string().min(1),
  buildingId: z.string().min(1),
  buildingName: z.string(),
  floorId: z.string().min(1),
  floorName: z.string().optional(),
  name: z.string().min(1),
  code: z.string().min(1),
  receptionistUserId: z.string().optional(),
  receptionistName: z.string().optional(),
  operatingHoursFrom: z.string().optional(),
  operatingHoursTo: z.string().optional(),
  status: z.enum(["active", "maintenance", "inactive"]).default("active"),
})

export type ReceptionDesk = z.infer<typeof ReceptionDeskSchema>

export type ReceptionDeskInput = Omit<ReceptionDesk, "id" | "buildingName" | "floorName" | "receptionistName">
