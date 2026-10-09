import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormFieldGroup } from '../../domain/entities/form-builder-schema'

export class ReorderFormFieldGroupsUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormFieldGroup[]> {
    return this.formBuilderRepository.reorderGroups(stepId, orderedIds, branchId)
  }
}
