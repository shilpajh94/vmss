import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormField, FormFieldUpdateInput } from '../../domain/entities/form-builder-schema'

export class UpdateFormFieldUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(id: string, input: FormFieldUpdateInput, branchId: string | undefined): Promise<FormField> {
    return this.formBuilderRepository.updateField(id, input, branchId)
  }
}
