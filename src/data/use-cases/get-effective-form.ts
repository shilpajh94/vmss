import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormStep } from '../../domain/entities/form-builder-schema'

export class GetEffectiveFormUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(branchId: string | undefined): Promise<FormStep[]> {
    return this.formBuilderRepository.getEffectiveForm(branchId)
  }
}
