import z from "zod"

export const StaffUserSchema = z.object({
  name: z.string().min(1),
  role: z.string().min(1),
})

export type StaffUser = z.infer<typeof StaffUserSchema>
