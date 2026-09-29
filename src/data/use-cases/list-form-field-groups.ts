import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormFieldGroup } from '../../domain/entities/form-builder-schema'

export class ListFormFieldGroupsUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, branchId: string | undefined): Promise<FormFieldGroup[]> {
    return this.formBuilderRepository.listGroups(stepId, branchId)
  }
}
