import z from "zod"

export const StaffUserSchema = z.object({
  name: z.string().min(1),
  // Distinct role names across every grant, in grant order; `["Staff"]` when none.
  roles: z.array(z.string().min(1)),
  isAdmin: z.boolean(),
  isReception: z.boolean(),
  // Each role grant and the branch it applies at (null = company-wide), so
  // a page can tell which branches the user can scope to.
  branchRoles: z.array(z.object({ roleName: z.string(), branchId: z.string().nullable() })),
})

export type StaffUser = z.infer<typeof StaffUserSchema>
