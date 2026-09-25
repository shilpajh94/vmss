import z from 'zod'
import { API_ENDPOINTS } from '../data/api/api-endpoints'
import type { ApiClient } from '../data/api/api-client'
import type { FormBuilderRepository } from '../data/repositories/form-builder-repository'
import {
  EffectiveFormStepListResponseSchema,
  FormFieldGroupListResponseSchema,
  FormFieldGroupResponseSchema,
  FormFieldListResponseSchema,
  FormFieldResponseSchema,
  FormStepListResponseSchema,
  FormStepResponseSchema,
  PublishResponseSchema,
  type EffectiveFormStep,
  type FormField,
  type FormFieldCreateInput,
  type FormFieldGroup,
  type FormFieldGroupCreateInput,
  type FormFieldGroupUpdateInput,
  type FormFieldUpdateInput,
  type FormStep,
  type FormStepCreateInput,
  type FormStepUpdateInput,
  type PublishResult,
} from '../domain/entities/form-builder-schema'

function branchHeaders(branchId: string | undefined): Record<string, string> {
  return branchId ? { 'X-Branch-ID': branchId } : {}
}

export class HttpFormBuilderRepository implements FormBuilderRepository {
  private readonly apiClient: ApiClient

  constructor(apiClient: ApiClient) {
    this.apiClient = apiClient
  }

  async listSteps(branchId: string | undefined): Promise<FormStep[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_FORM_STEPS,
      headers: branchHeaders(branchId),
      parserSchema: FormStepListResponseSchema,
    })
    return response.data
  }

  async createStep(input: FormStepCreateInput, branchId: string | undefined): Promise<FormStep> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_FORM_STEP,
      body: input,
      headers: branchHeaders(branchId),
      parserSchema: FormStepResponseSchema,
    })
    return response.data
  }

  async updateStep(id: string, input: FormStepUpdateInput, branchId: string | undefined): Promise<FormStep> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_FORM_STEP,
      body: input,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: FormStepResponseSchema,
    })
    return response.data
  }

  async deleteStep(id: string, branchId: string | undefined): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_FORM_STEP,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: z.unknown(),
    })
  }

  async reorderSteps(orderedIds: string[], branchId: string | undefined): Promise<FormStep[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.REORDER_FORM_STEPS,
      body: { orderedIds },
      headers: branchHeaders(branchId),
      parserSchema: FormStepListResponseSchema,
    })
    return response.data
  }

  async listFields(stepId: string, branchId: string | undefined): Promise<FormField[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_FORM_FIELDS,
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldListResponseSchema,
    })
    return response.data
  }

  async createField(stepId: string, input: FormFieldCreateInput, branchId: string | undefined): Promise<FormField> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_FORM_FIELD,
      body: input,
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldResponseSchema,
    })
    return response.data
  }

  async updateField(id: string, input: FormFieldUpdateInput, branchId: string | undefined): Promise<FormField> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_FORM_FIELD,
      body: input,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldResponseSchema,
    })
    return response.data
  }

  async deleteField(id: string, branchId: string | undefined): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_FORM_FIELD,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: z.unknown(),
    })
  }

  async reorderFields(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormField[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.REORDER_FORM_FIELDS,
      body: { orderedIds },
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldListResponseSchema,
    })
    return response.data
  }

  async listGroups(stepId: string, branchId: string | undefined): Promise<FormFieldGroup[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.LIST_FORM_FIELD_GROUPS,
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldGroupListResponseSchema,
    })
    return response.data
  }

  async createGroup(
    stepId: string,
    input: FormFieldGroupCreateInput,
    branchId: string | undefined,
  ): Promise<FormFieldGroup> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.CREATE_FORM_FIELD_GROUP,
      body: input,
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldGroupResponseSchema,
    })
    return response.data
  }

  async updateGroup(
    id: string,
    input: FormFieldGroupUpdateInput,
    branchId: string | undefined,
  ): Promise<FormFieldGroup> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.UPDATE_FORM_FIELD_GROUP,
      body: input,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldGroupResponseSchema,
    })
    return response.data
  }

  async deleteGroup(id: string, branchId: string | undefined): Promise<void> {
    await this.apiClient.makeRequest<unknown>({
      endpointConfig: API_ENDPOINTS.DELETE_FORM_FIELD_GROUP,
      pathParams: { id },
      headers: branchHeaders(branchId),
      parserSchema: z.unknown(),
    })
  }

  async reorderGroups(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormFieldGroup[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.REORDER_FORM_FIELD_GROUPS,
      body: { orderedIds },
      pathParams: { stepId },
      headers: branchHeaders(branchId),
      parserSchema: FormFieldGroupListResponseSchema,
    })
    return response.data
  }

  async publish(branchId: string | undefined): Promise<PublishResult> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.PUBLISH_FORM_CONFIG,
      headers: branchHeaders(branchId),
      parserSchema: PublishResponseSchema,
    })
    return response.data
  }

  async getEffectiveForm(branchId: string | undefined): Promise<EffectiveFormStep[]> {
    const response = await this.apiClient.makeRequest({
      endpointConfig: API_ENDPOINTS.GET_EFFECTIVE_FORM,
      headers: branchHeaders(branchId),
      parserSchema: EffectiveFormStepListResponseSchema,
    })
    return response.data
  }
}
