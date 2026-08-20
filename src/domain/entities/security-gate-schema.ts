import z from "zod"

export const SecurityGateSchema = z.object({
  id: z.string().min(1),
  buildingId: z.string().min(1),
  buildingName: z.string(),
  floorId: z.string().optional(),
  floorName: z.string().optional(),
  name: z.string().min(1),
  gateType: z.enum(["bidirectional", "entry_only", "exit_only", "high_security"]).default("bidirectional"),
  authMethod: z.string().optional(),
  connectivityStatus: z.enum(["online", "maintenance", "offline"]).default("online"),
})

export type SecurityGate = z.infer<typeof SecurityGateSchema>

export type SecurityGateInput = Omit<SecurityGate, "id" | "buildingName" | "floorName">
