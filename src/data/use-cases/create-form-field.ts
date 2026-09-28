import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormField, FormFieldCreateInput } from '../../domain/entities/form-builder-schema'

export class CreateFormFieldUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, input: FormFieldCreateInput, branchId: string | undefined): Promise<FormField> {
    return this.formBuilderRepository.createField(stepId, input, branchId)
  }
}
