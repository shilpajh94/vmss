import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormStep, FormStepCreateInput } from '../../domain/entities/form-builder-schema'

export class CreateFormStepUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(input: FormStepCreateInput, branchId: string | undefined): Promise<FormStep> {
    return this.formBuilderRepository.createStep(input, branchId)
  }
}
