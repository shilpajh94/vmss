import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormField } from '../../domain/entities/form-builder-schema'

export class ReorderFormFieldsUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormField[]> {
    return this.formBuilderRepository.reorderFields(stepId, orderedIds, branchId)
  }
}
