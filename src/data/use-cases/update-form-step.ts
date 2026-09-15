import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormStep, FormStepUpdateInput } from '../../domain/entities/form-builder-schema'

export class UpdateFormStepUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(id: string, input: FormStepUpdateInput, branchId: string | undefined): Promise<FormStep> {
    return this.formBuilderRepository.updateStep(id, input, branchId)
  }
}
