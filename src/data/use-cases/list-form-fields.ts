import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { FormField } from '../../domain/entities/form-builder-schema'

export class ListFormFieldsUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(stepId: string, branchId: string | undefined): Promise<FormField[]> {
    return this.formBuilderRepository.listFields(stepId, branchId)
  }
}
