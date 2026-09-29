import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormStep } from '../../domain/entities/form-builder-schema'

export class ReorderFormStepsUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(orderedIds: string[], branchId: string | undefined): Promise<FormStep[]> {
    return this.formBuilderRepository.reorderSteps(orderedIds, branchId)
  }
}
