import type {
  EffectiveFormStep,
  FormField,
  FormFieldCreateInput,
  FormFieldGroup,
  FormFieldGroupCreateInput,
  FormFieldGroupUpdateInput,
  FormFieldUpdateInput,
  FormStep,
  FormStepCreateInput,
  FormStepUpdateInput,
  PublishResult,
} from '../../domain/entities/form-builder-schema'

/** `branchId` scopes every call to that branch's draft/publish; omitted (or
 * `undefined`) targets the tenant-wide default — mirrors the backend's
 * optional `X-Branch-ID` header (`form_builder/deps.py::require_form_scope`).
 */
export interface FormBuilderRepository {
  listSteps(branchId: string | undefined): Promise<FormStep[]>
  createStep(input: FormStepCreateInput, branchId: string | undefined): Promise<FormStep>
  updateStep(id: string, input: FormStepUpdateInput, branchId: string | undefined): Promise<FormStep>
  deleteStep(id: string, branchId: string | undefined): Promise<void>
  reorderSteps(orderedIds: string[], branchId: string | undefined): Promise<FormStep[]>
  listFields(stepId: string, branchId: string | undefined): Promise<FormField[]>
  createField(stepId: string, input: FormFieldCreateInput, branchId: string | undefined): Promise<FormField>
  updateField(id: string, input: FormFieldUpdateInput, branchId: string | undefined): Promise<FormField>
  deleteField(id: string, branchId: string | undefined): Promise<void>
  reorderFields(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormField[]>
  listGroups(stepId: string, branchId: string | undefined): Promise<FormFieldGroup[]>
  createGroup(stepId: string, input: FormFieldGroupCreateInput, branchId: string | undefined): Promise<FormFieldGroup>
  updateGroup(id: string, input: FormFieldGroupUpdateInput, branchId: string | undefined): Promise<FormFieldGroup>
  deleteGroup(id: string, branchId: string | undefined): Promise<void>
  reorderGroups(stepId: string, orderedIds: string[], branchId: string | undefined): Promise<FormFieldGroup[]>
  publish(branchId: string | undefined): Promise<PublishResult>
  getEffectiveForm(branchId: string | undefined): Promise<EffectiveFormStep[]>
}
