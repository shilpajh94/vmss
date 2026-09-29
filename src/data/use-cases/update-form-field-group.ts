import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormFieldGroup, FormFieldGroupUpdateInput } from '../../domain/entities/form-builder-schema'

export class UpdateFormFieldGroupUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(id: string, input: FormFieldGroupUpdateInput, branchId: string | undefined): Promise<FormFieldGroup> {
    return this.formBuilderRepository.updateGroup(id, input, branchId)
  }
}
