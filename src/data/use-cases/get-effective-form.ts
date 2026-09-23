import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { EffectiveFormStep } from '../../domain/entities/form-builder-schema'

export class GetEffectiveFormUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(branchId: string | undefined): Promise<EffectiveFormStep[]> {
    return this.formBuilderRepository.getEffectiveForm(branchId)
  }
}
