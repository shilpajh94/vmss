import type { FormBuilderRepository } from '../repositories/form-builder-repository'

export class DeleteFormFieldGroupUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(id: string, branchId: string | undefined): Promise<void> {
    return this.formBuilderRepository.deleteGroup(id, branchId)
  }
}
