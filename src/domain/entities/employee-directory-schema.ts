import z from "zod"

export const EmployeeDirectoryEntrySchema = z.object({
  id: z.string().min(1),
  fullName: z.string().min(1),
  designation: z.string().optional(),
  departmentId: z.string().optional(),
})

export type EmployeeDirectoryEntry = z.infer<typeof EmployeeDirectoryEntrySchema>
