import type { FormBuilderRepository } from '../repositories/form-builder-repository'
import type { PublishResult } from '../../domain/entities/form-builder-schema'

export class PublishFormConfigUseCase {
  private readonly formBuilderRepository: FormBuilderRepository

  constructor(formBuilderRepository: FormBuilderRepository) {
    this.formBuilderRepository = formBuilderRepository
  }

  async execute(branchId: string | undefined): Promise<PublishResult> {
    return this.formBuilderRepository.publish(branchId)
  }
}
