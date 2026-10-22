import z from "zod"

export const StaffUserSchema = z.object({
  name: z.string().min(1),
  role: z.string().min(1),
  isAdmin: z.boolean(),
  isReception: z.boolean(),
  // Each role grant and the branch it applies at (null = company-wide), so
  // a page can tell which branches the user can scope to. `permissionCodes`
  // is what the role grants; it is absent from an API that predates it.
  branchRoles: z.array(
    z.object({ roleName: z.string(), branchId: z.string().nullable(), permissionCodes: z.array(z.string()).optional() }),
  ),
})

export type StaffUser = z.infer<typeof StaffUserSchema>
