import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormFieldGroup, FormFieldGroupCreateInput } from '../../domain/entities/form-builder-schema'

export class CreateFormFieldGroupUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, input: FormFieldGroupCreateInput, branchId: string | undefined): Promise<FormFieldGroup> {
    return this.formBuilderRepository.createGroup(stepId, input, branchId)
  }
}
