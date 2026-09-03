import z from "zod"

export const HostSearchResultSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  email: z.string().min(1),
  department: z.string().optional(),
})

export type HostSearchResult = z.infer<typeof HostSearchResultSchema>
