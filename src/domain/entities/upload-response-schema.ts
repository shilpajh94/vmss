import z from "zod"

export const UploadResponseSchema = z.object({
  fileRef: z.string().min(1),
})

export type UploadResponse = z.infer<typeof UploadResponseSchema>
