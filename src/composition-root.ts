import { ApiClient } from './data/api/api-client'
import type { VisitRequestRepository } from './data/repositories/visit-request-repository'
import type { VisitRequestSummaryRepository } from './data/repositories/visit-request-summary-repository'
import type { VisitTrackingRepository } from './data/repositories/visit-tracking-repository'
import type { VisitorOtpRepository } from './data/repositories/visitor-otp-repository'
import type { VisitorPortalRepository } from './data/repositories/visitor-portal-repository'
import type { StaffAuthRepository } from './data/repositories/staff-auth-repository'
import type { SsoAuthRepository } from './data/repositories/sso-auth-repository'
import type { StaffVisitRequestRepository } from './data/repositories/staff-visit-request-repository'
import type { StaffVisitorLookupRepository } from './data/repositories/staff-visitor-lookup-repository'
import type { AuditTrailRepository } from './data/repositories/audit-trail-repository'
import type { OrganisationConfigRepository } from './data/repositories/organisation-config-repository'
import type { BranchRepository } from './data/repositories/branch-repository'
import type { DepartmentRepository } from './data/repositories/department-repository'
import type { BuildingRepository } from './data/repositories/building-repository'
import type { FloorRepository } from './data/repositories/floor-repository'
import type { DashboardRepository } from './data/repositories/dashboard-repository'
import type { CalendarRepository } from './data/repositories/calendar-repository'
import type { HostEmployeeRepository } from './data/repositories/host-employee-repository'
import type { EmployeeDirectoryRepository } from './data/repositories/employee-directory-repository'
import type { KioskRepository } from './data/repositories/kiosk-repository'
import type { DeviceRepository } from './data/repositories/device-repository'
import type { KioskLocationValidationRepository } from './data/repositories/kiosk-location-validation-repository'
import type { VisitorCategoryRepository } from './data/repositories/visitor-category-repository'
import type { ApprovalWorkflowRuleRepository } from './data/repositories/approval-workflow-rule-repository'
import type { NotificationRepository } from './data/repositories/notification-repository'
import type { FormBuilderRepository } from './data/repositories/form-builder-repository'
import { SubmitVisitRequestUseCase } from './data/use-cases/submit-visit-request'
import { SubmitStaffVisitRequestUseCase } from './data/use-cases/submit-staff-visit-request'
import { LookupStaffVisitorByEmailUseCase } from './data/use-cases/lookup-staff-visitor-by-email'
import { LookupStaffVisitorByPhoneUseCase } from './data/use-cases/lookup-staff-visitor-by-phone'
import { GetAuditTrailUseCase } from './data/use-cases/get-audit-trail'
import { RequestAuditReportUseCase } from './data/use-cases/request-audit-report'
import { GetAuditReportUseCase } from './data/use-cases/get-audit-report'
import { DownloadAuditReportUseCase } from './data/use-cases/download-audit-report'
import { TrackVisitRequestUseCase } from './data/use-cases/track-visit-request'
import { RequestVisitorOtpUseCase } from './data/use-cases/request-visitor-otp'
import { VerifyVisitorOtpUseCase } from './data/use-cases/verify-visitor-otp'
import { GetVisitorPortalMeUseCase } from './data/use-cases/get-visitor-portal-me'
import { LoginStaffUseCase } from './data/use-cases/login-staff'
import { StartSsoLoginUseCase } from './data/use-cases/start-sso-login'
import { ExchangeSsoCodeUseCase } from './data/use-cases/exchange-sso-code'
import { ListVisitRequestsUseCase } from './data/use-cases/list-visit-requests'
import { ApproveInvitationUseCase } from './data/use-cases/approve-invitation'
import { GetInvitationDetailUseCase } from './data/use-cases/get-invitation-detail'
import { RescheduleInvitationUseCase } from './data/use-cases/reschedule-invitation'
import { EditInvitationUseCase } from './data/use-cases/edit-invitation'
import { DenyInvitationUseCase } from './data/use-cases/deny-invitation'
import { RevertInvitationApprovalUseCase } from './data/use-cases/revert-invitation-approval'
import { CheckOutInvitationUseCase } from './data/use-cases/check-out-invitation'
import { ExportInvitationsUseCase } from './data/use-cases/export-invitations'
import { ApproveInvitationStepUseCase } from './data/use-cases/approve-invitation-step'
import { RejectInvitationStepUseCase } from './data/use-cases/reject-invitation-step'
import { DelegateInvitationStepUseCase } from './data/use-cases/delegate-invitation-step'
import { GetCurrentStaffUserUseCase } from './data/use-cases/get-current-staff-user'
import { GetOrganisationConfigUseCase } from './data/use-cases/get-organisation-config'
import { UpdateOrganisationConfigUseCase } from './data/use-cases/update-organisation-config'
import { ListBranchesUseCase } from './data/use-cases/list-branches'
import { ListBranchesPageUseCase } from './data/use-cases/list-branches-page'
import { CreateBranchUseCase } from './data/use-cases/create-branch'
import { UpdateBranchUseCase } from './data/use-cases/update-branch'
import { DeleteBranchUseCase } from './data/use-cases/delete-branch'
import { ListDepartmentsUseCase } from './data/use-cases/list-departments'
import { ListDepartmentsPageUseCase } from './data/use-cases/list-departments-page'
import { CreateDepartmentUseCase } from './data/use-cases/create-department'
import { UpdateDepartmentUseCase } from './data/use-cases/update-department'
import { DeleteDepartmentUseCase } from './data/use-cases/delete-department'
import { ListBuildingsUseCase } from './data/use-cases/list-buildings'
import { ListBuildingsPageUseCase } from './data/use-cases/list-buildings-page'
import { CreateBuildingUseCase } from './data/use-cases/create-building'
import { UpdateBuildingUseCase } from './data/use-cases/update-building'
import { DeleteBuildingUseCase } from './data/use-cases/delete-building'
import { ListFloorsUseCase } from './data/use-cases/list-floors'
import { ListFloorsPageUseCase } from './data/use-cases/list-floors-page'
import { CreateFloorUseCase } from './data/use-cases/create-floor'
import { UpdateFloorUseCase } from './data/use-cases/update-floor'
import { DeleteFloorUseCase } from './data/use-cases/delete-floor'
import { GetDashboardOverviewUseCase } from './data/use-cases/get-dashboard-overview'
import { GetMyDashboardOverviewUseCase } from './data/use-cases/get-my-dashboard-overview'
import { GetDashboardAnalyticsUseCase } from './data/use-cases/get-dashboard-analytics'
import { GetMyDashboardAnalyticsUseCase } from './data/use-cases/get-my-dashboard-analytics'
import { GetCalendarFeedUseCase } from './data/use-cases/get-calendar-feed'
import { GetCalendarDayPageUseCase } from './data/use-cases/get-calendar-day-page'
import { ListRecentCheckinsUseCase } from './data/use-cases/list-recent-checkins'
import { ListHostEmployeesUseCase } from './data/use-cases/list-host-employees'
import { ListHostEmployeesPageUseCase } from './data/use-cases/list-host-employees-page'
import { ListEmployeeDirectoryUseCase } from './data/use-cases/list-employee-directory'
import { CreateHostEmployeeUseCase } from './data/use-cases/create-host-employee'
import { ListRolesUseCase } from './data/use-cases/list-roles'
import { ListRolesPageUseCase } from './data/use-cases/list-roles-page'
import { CreateRoleUseCase } from './data/use-cases/create-role'
import { ListPermissionsUseCase } from './data/use-cases/list-permissions'
import { UpdateRolePermissionsUseCase } from './data/use-cases/update-role-permissions'
import { ResyncRolePermissionsUseCase } from './data/use-cases/resync-role-permissions'
import { AssignHostEmployeeRoleUseCase } from './data/use-cases/assign-host-employee-role'
import { RevokeHostEmployeeRoleUseCase } from './data/use-cases/revoke-host-employee-role'
import { DisableHostEmployeeUseCase } from './data/use-cases/disable-host-employee'
import { EnableHostEmployeeUseCase } from './data/use-cases/enable-host-employee'
import { DeleteHostEmployeeUseCase } from './data/use-cases/delete-host-employee'
import { ListKiosksPageUseCase } from './data/use-cases/list-kiosks-page'
import { GetKioskUseCase } from './data/use-cases/get-kiosk'
import { CreateKioskUseCase } from './data/use-cases/create-kiosk'
import { UpdateKioskUseCase } from './data/use-cases/update-kiosk'
import { SetKioskVisibilityUseCase } from './data/use-cases/set-kiosk-visibility'
import { DeleteKioskUseCase } from './data/use-cases/delete-kiosk'
import { ListDevicesPageUseCase } from './data/use-cases/list-devices-page'
import { ApproveDeviceUseCase } from './data/use-cases/approve-device'
import { EnableDeviceUseCase } from './data/use-cases/enable-device'
import { DisableDeviceUseCase } from './data/use-cases/disable-device'
import { DeleteDeviceUseCase } from './data/use-cases/delete-device'
import { GetKioskLocationValidationUseCase } from './data/use-cases/get-kiosk-location-validation'
import { UpdateKioskLocationValidationUseCase } from './data/use-cases/update-kiosk-location-validation'
import { ListVisitorCategoriesUseCase } from './data/use-cases/list-visitor-categories'
import { ListVisitorCategoriesPageUseCase } from './data/use-cases/list-visitor-categories-page'
import { CreateVisitorCategoryUseCase } from './data/use-cases/create-visitor-category'
import { BulkCreateVisitorCategoriesUseCase } from './data/use-cases/bulk-create-visitor-categories'
import { UpdateVisitorCategoryUseCase } from './data/use-cases/update-visitor-category'
import { DeleteVisitorCategoryUseCase } from './data/use-cases/delete-visitor-category'
import { ListFormStepsUseCase } from './data/use-cases/list-form-steps'
import { CreateFormStepUseCase } from './data/use-cases/create-form-step'
import { UpdateFormStepUseCase } from './data/use-cases/update-form-step'
import { DeleteFormStepUseCase } from './data/use-cases/delete-form-step'
import { ReorderFormStepsUseCase } from './data/use-cases/reorder-form-steps'
import { ListFormFieldsUseCase } from './data/use-cases/list-form-fields'
import { CreateFormFieldUseCase } from './data/use-cases/create-form-field'
import { UpdateFormFieldUseCase } from './data/use-cases/update-form-field'
import { DeleteFormFieldUseCase } from './data/use-cases/delete-form-field'
import { ReorderFormFieldsUseCase } from './data/use-cases/reorder-form-fields'
import { ListFormFieldGroupsUseCase } from './data/use-cases/list-form-field-groups'
import { CreateFormFieldGroupUseCase } from './data/use-cases/create-form-field-group'
import { UpdateFormFieldGroupUseCase } from './data/use-cases/update-form-field-group'
import { DeleteFormFieldGroupUseCase } from './data/use-cases/delete-form-field-group'
import { ReorderFormFieldGroupsUseCase } from './data/use-cases/reorder-form-field-groups'
import { PublishFormConfigUseCase } from './data/use-cases/publish-form-config'
import { GetEffectiveFormUseCase } from './data/use-cases/get-effective-form'
import { ListApprovalWorkflowRulesUseCase } from './data/use-cases/list-approval-workflow-rules'
import { SaveWorkflowUseCase } from './data/use-cases/save-workflow'
import { DeleteWorkflowUseCase } from './data/use-cases/delete-workflow'
import { RegisterDeviceUseCase } from './data/use-cases/register-device'
import { UnregisterDeviceUseCase } from './data/use-cases/unregister-device'
import { ListNotificationsUseCase } from './data/use-cases/list-notifications'
import { GetUnreadNotificationCountUseCase } from './data/use-cases/get-unread-notification-count'
import { MarkNotificationReadUseCase } from './data/use-cases/mark-notification-read'
import { MarkAllNotificationsReadUseCase } from './data/use-cases/mark-all-notifications-read'
import { HttpVisitRequestRepository } from './infrastructure/visit-request-repository'
import { HttpVisitRequestSummaryRepository } from './infrastructure/visit-request-summary-repository'
import { HttpVisitTrackingRepository } from './infrastructure/visit-tracking-repository'
import { HttpVisitorOtpRepository } from './infrastructure/visitor-otp-repository'
import { HttpVisitorPortalRepository } from './infrastructure/visitor-portal-repository'
import { HttpStaffAuthRepository } from './infrastructure/staff-auth-repository'
import { HttpSsoAuthRepository } from './infrastructure/sso-auth-repository'
import { HttpStaffVisitRequestRepository } from './infrastructure/staff-visit-request-repository'
import { HttpStaffVisitorLookupRepository } from './infrastructure/staff-visitor-lookup-repository'
import { HttpAuditTrailRepository } from './infrastructure/audit-trail-repository'
import { HttpOrganisationConfigRepository } from './infrastructure/organisation-config-repository'
import { HttpBranchRepository } from './infrastructure/branch-repository'
import { HttpDepartmentRepository } from './infrastructure/department-repository'
import { HttpBuildingRepository } from './infrastructure/building-repository'
import { HttpFloorRepository } from './infrastructure/floor-repository'
import { HttpDashboardRepository } from './infrastructure/dashboard-repository'
import { HttpCalendarRepository } from './infrastructure/calendar-repository'
import { HttpHostEmployeeRepository } from './infrastructure/host-employee-repository'
import { HttpEmployeeDirectoryRepository } from './infrastructure/employee-directory-repository'
import { HttpKioskRepository } from './infrastructure/kiosk-repository'
import { HttpDeviceRepository } from './infrastructure/device-repository'
import { HttpKioskLocationValidationRepository } from './infrastructure/kiosk-location-validation-repository'
import { HttpVisitorCategoryRepository } from './infrastructure/visitor-category-repository'
import { HttpFormBuilderRepository } from './infrastructure/form-builder-repository'
import { HttpApprovalWorkflowRuleRepository } from './infrastructure/approval-workflow-rule-repository'
import { HttpNotificationRepository } from './infrastructure/notification-repository'

export interface AppDependencies {
  apiClient: ApiClient
  submitVisitRequestUseCase: SubmitVisitRequestUseCase
  trackVisitRequestUseCase: TrackVisitRequestUseCase
  requestVisitorOtpUseCase: RequestVisitorOtpUseCase
  verifyVisitorOtpUseCase: VerifyVisitorOtpUseCase
  getVisitorPortalMeUseCase: GetVisitorPortalMeUseCase
  loginStaffUseCase: LoginStaffUseCase
  startSsoLoginUseCase: StartSsoLoginUseCase
  exchangeSsoCodeUseCase: ExchangeSsoCodeUseCase
  listVisitRequestsUseCase: ListVisitRequestsUseCase
  approveInvitationUseCase: ApproveInvitationUseCase
  getInvitationDetailUseCase: GetInvitationDetailUseCase
  rescheduleInvitationUseCase: RescheduleInvitationUseCase
  editInvitationUseCase: EditInvitationUseCase
  denyInvitationUseCase: DenyInvitationUseCase
  revertInvitationApprovalUseCase: RevertInvitationApprovalUseCase
  checkOutInvitationUseCase: CheckOutInvitationUseCase
  exportInvitationsUseCase: ExportInvitationsUseCase
  approveInvitationStepUseCase: ApproveInvitationStepUseCase
  rejectInvitationStepUseCase: RejectInvitationStepUseCase
  delegateInvitationStepUseCase: DelegateInvitationStepUseCase
  getCurrentStaffUserUseCase: GetCurrentStaffUserUseCase
  submitStaffVisitRequestUseCase: SubmitStaffVisitRequestUseCase
  lookupStaffVisitorByEmailUseCase: LookupStaffVisitorByEmailUseCase
  lookupStaffVisitorByPhoneUseCase: LookupStaffVisitorByPhoneUseCase
  getAuditTrailUseCase: GetAuditTrailUseCase
  requestAuditReportUseCase: RequestAuditReportUseCase
  getAuditReportUseCase: GetAuditReportUseCase
  downloadAuditReportUseCase: DownloadAuditReportUseCase
  getOrganisationConfigUseCase: GetOrganisationConfigUseCase
  updateOrganisationConfigUseCase: UpdateOrganisationConfigUseCase
  listBranchesUseCase: ListBranchesUseCase
  listBranchesPageUseCase: ListBranchesPageUseCase
  createBranchUseCase: CreateBranchUseCase
  updateBranchUseCase: UpdateBranchUseCase
  deleteBranchUseCase: DeleteBranchUseCase
  listDepartmentsUseCase: ListDepartmentsUseCase
  listDepartmentsPageUseCase: ListDepartmentsPageUseCase
  createDepartmentUseCase: CreateDepartmentUseCase
  updateDepartmentUseCase: UpdateDepartmentUseCase
  deleteDepartmentUseCase: DeleteDepartmentUseCase
  listBuildingsUseCase: ListBuildingsUseCase
  listBuildingsPageUseCase: ListBuildingsPageUseCase
  createBuildingUseCase: CreateBuildingUseCase
  updateBuildingUseCase: UpdateBuildingUseCase
  deleteBuildingUseCase: DeleteBuildingUseCase
  listFloorsUseCase: ListFloorsUseCase
  listFloorsPageUseCase: ListFloorsPageUseCase
  createFloorUseCase: CreateFloorUseCase
  updateFloorUseCase: UpdateFloorUseCase
  deleteFloorUseCase: DeleteFloorUseCase
  getDashboardOverviewUseCase: GetDashboardOverviewUseCase
  getMyDashboardOverviewUseCase: GetMyDashboardOverviewUseCase
  getDashboardAnalyticsUseCase: GetDashboardAnalyticsUseCase
  getMyDashboardAnalyticsUseCase: GetMyDashboardAnalyticsUseCase
  getCalendarFeedUseCase: GetCalendarFeedUseCase
  getCalendarDayPageUseCase: GetCalendarDayPageUseCase
  listRecentCheckinsUseCase: ListRecentCheckinsUseCase
  listHostEmployeesUseCase: ListHostEmployeesUseCase
  listHostEmployeesPageUseCase: ListHostEmployeesPageUseCase
  listEmployeeDirectoryUseCase: ListEmployeeDirectoryUseCase
  createHostEmployeeUseCase: CreateHostEmployeeUseCase
  listRolesUseCase: ListRolesUseCase
  listRolesPageUseCase: ListRolesPageUseCase
  createRoleUseCase: CreateRoleUseCase
  listPermissionsUseCase: ListPermissionsUseCase
  updateRolePermissionsUseCase: UpdateRolePermissionsUseCase
  resyncRolePermissionsUseCase: ResyncRolePermissionsUseCase
  assignHostEmployeeRoleUseCase: AssignHostEmployeeRoleUseCase
  revokeHostEmployeeRoleUseCase: RevokeHostEmployeeRoleUseCase
  disableHostEmployeeUseCase: DisableHostEmployeeUseCase
  enableHostEmployeeUseCase: EnableHostEmployeeUseCase
  deleteHostEmployeeUseCase: DeleteHostEmployeeUseCase
  listKiosksPageUseCase: ListKiosksPageUseCase
  getKioskUseCase: GetKioskUseCase
  createKioskUseCase: CreateKioskUseCase
  updateKioskUseCase: UpdateKioskUseCase
  setKioskVisibilityUseCase: SetKioskVisibilityUseCase
  deleteKioskUseCase: DeleteKioskUseCase
  listDevicesPageUseCase: ListDevicesPageUseCase
  approveDeviceUseCase: ApproveDeviceUseCase
  enableDeviceUseCase: EnableDeviceUseCase
  disableDeviceUseCase: DisableDeviceUseCase
  deleteDeviceUseCase: DeleteDeviceUseCase
  getKioskLocationValidationUseCase: GetKioskLocationValidationUseCase
  updateKioskLocationValidationUseCase: UpdateKioskLocationValidationUseCase
  listVisitorCategoriesUseCase: ListVisitorCategoriesUseCase
  listVisitorCategoriesPageUseCase: ListVisitorCategoriesPageUseCase
  createVisitorCategoryUseCase: CreateVisitorCategoryUseCase
  bulkCreateVisitorCategoriesUseCase: BulkCreateVisitorCategoriesUseCase
  updateVisitorCategoryUseCase: UpdateVisitorCategoryUseCase
  deleteVisitorCategoryUseCase: DeleteVisitorCategoryUseCase
  listApprovalWorkflowRulesUseCase: ListApprovalWorkflowRulesUseCase
  saveWorkflowUseCase: SaveWorkflowUseCase
  deleteWorkflowUseCase: DeleteWorkflowUseCase
  registerDeviceUseCase: RegisterDeviceUseCase
  unregisterDeviceUseCase: UnregisterDeviceUseCase
  listNotificationsUseCase: ListNotificationsUseCase
  getUnreadNotificationCountUseCase: GetUnreadNotificationCountUseCase
  markNotificationReadUseCase: MarkNotificationReadUseCase
  markAllNotificationsReadUseCase: MarkAllNotificationsReadUseCase
  listFormStepsUseCase: ListFormStepsUseCase
  createFormStepUseCase: CreateFormStepUseCase
  updateFormStepUseCase: UpdateFormStepUseCase
  deleteFormStepUseCase: DeleteFormStepUseCase
  reorderFormStepsUseCase: ReorderFormStepsUseCase
  listFormFieldsUseCase: ListFormFieldsUseCase
  createFormFieldUseCase: CreateFormFieldUseCase
  updateFormFieldUseCase: UpdateFormFieldUseCase
  deleteFormFieldUseCase: DeleteFormFieldUseCase
  reorderFormFieldsUseCase: ReorderFormFieldsUseCase
  listFormFieldGroupsUseCase: ListFormFieldGroupsUseCase
  createFormFieldGroupUseCase: CreateFormFieldGroupUseCase
  updateFormFieldGroupUseCase: UpdateFormFieldGroupUseCase
  deleteFormFieldGroupUseCase: DeleteFormFieldGroupUseCase
  reorderFormFieldGroupsUseCase: ReorderFormFieldGroupsUseCase
  publishFormConfigUseCase: PublishFormConfigUseCase
  getEffectiveFormUseCase: GetEffectiveFormUseCase
}

export function createApp(): AppDependencies {
  let apiClient: ApiClient | undefined
  let visitRequestRepository: VisitRequestRepository | undefined
  let visitRequestSummaryRepository: VisitRequestSummaryRepository | undefined
  let visitTrackingRepository: VisitTrackingRepository | undefined
  let visitorOtpRepository: VisitorOtpRepository | undefined
  let visitorPortalRepository: VisitorPortalRepository | undefined
  let staffAuthRepository: StaffAuthRepository | undefined
  let ssoAuthRepository: SsoAuthRepository | undefined
  let submitVisitRequestUseCase: SubmitVisitRequestUseCase | undefined
  let trackVisitRequestUseCase: TrackVisitRequestUseCase | undefined
  let requestVisitorOtpUseCase: RequestVisitorOtpUseCase | undefined
  let verifyVisitorOtpUseCase: VerifyVisitorOtpUseCase | undefined
  let getVisitorPortalMeUseCase: GetVisitorPortalMeUseCase | undefined
  let loginStaffUseCase: LoginStaffUseCase | undefined
  let startSsoLoginUseCase: StartSsoLoginUseCase | undefined
  let exchangeSsoCodeUseCase: ExchangeSsoCodeUseCase | undefined
  let listVisitRequestsUseCase: ListVisitRequestsUseCase | undefined
  let approveInvitationUseCase: ApproveInvitationUseCase | undefined
  let getInvitationDetailUseCase: GetInvitationDetailUseCase | undefined
  let rescheduleInvitationUseCase: RescheduleInvitationUseCase | undefined
  let editInvitationUseCase: EditInvitationUseCase | undefined
  let denyInvitationUseCase: DenyInvitationUseCase | undefined
  let revertInvitationApprovalUseCase: RevertInvitationApprovalUseCase | undefined
  let checkOutInvitationUseCase: CheckOutInvitationUseCase | undefined
  let exportInvitationsUseCase: ExportInvitationsUseCase | undefined
  let approveInvitationStepUseCase: ApproveInvitationStepUseCase | undefined
  let rejectInvitationStepUseCase: RejectInvitationStepUseCase | undefined
  let delegateInvitationStepUseCase: DelegateInvitationStepUseCase | undefined
  let getCurrentStaffUserUseCase: GetCurrentStaffUserUseCase | undefined
  let staffVisitRequestRepository: StaffVisitRequestRepository | undefined
  let submitStaffVisitRequestUseCase: SubmitStaffVisitRequestUseCase | undefined
  let staffVisitorLookupRepository: StaffVisitorLookupRepository | undefined
  let lookupStaffVisitorByEmailUseCase: LookupStaffVisitorByEmailUseCase | undefined
  let lookupStaffVisitorByPhoneUseCase: LookupStaffVisitorByPhoneUseCase | undefined
  let auditTrailRepository: AuditTrailRepository | undefined
  let getAuditTrailUseCase: GetAuditTrailUseCase | undefined
  let requestAuditReportUseCase: RequestAuditReportUseCase | undefined
  let getAuditReportUseCase: GetAuditReportUseCase | undefined
  let downloadAuditReportUseCase: DownloadAuditReportUseCase | undefined
  let organisationConfigRepository: OrganisationConfigRepository | undefined
  let getOrganisationConfigUseCase: GetOrganisationConfigUseCase | undefined
  let updateOrganisationConfigUseCase: UpdateOrganisationConfigUseCase | undefined
  let branchRepository: BranchRepository | undefined
  let listBranchesUseCase: ListBranchesUseCase | undefined
  let listBranchesPageUseCase: ListBranchesPageUseCase | undefined
  let createBranchUseCase: CreateBranchUseCase | undefined
  let updateBranchUseCase: UpdateBranchUseCase | undefined
  let deleteBranchUseCase: DeleteBranchUseCase | undefined
  let departmentRepository: DepartmentRepository | undefined
  let listDepartmentsUseCase: ListDepartmentsUseCase | undefined
  let listDepartmentsPageUseCase: ListDepartmentsPageUseCase | undefined
  let createDepartmentUseCase: CreateDepartmentUseCase | undefined
  let updateDepartmentUseCase: UpdateDepartmentUseCase | undefined
  let deleteDepartmentUseCase: DeleteDepartmentUseCase | undefined
  let buildingRepository: BuildingRepository | undefined
  let listBuildingsUseCase: ListBuildingsUseCase | undefined
  let listBuildingsPageUseCase: ListBuildingsPageUseCase | undefined
  let createBuildingUseCase: CreateBuildingUseCase | undefined
  let updateBuildingUseCase: UpdateBuildingUseCase | undefined
  let deleteBuildingUseCase: DeleteBuildingUseCase | undefined
  let floorRepository: FloorRepository | undefined
  let listFloorsUseCase: ListFloorsUseCase | undefined
  let listFloorsPageUseCase: ListFloorsPageUseCase | undefined
  let createFloorUseCase: CreateFloorUseCase | undefined
  let updateFloorUseCase: UpdateFloorUseCase | undefined
  let deleteFloorUseCase: DeleteFloorUseCase | undefined
  let dashboardRepository: DashboardRepository | undefined
  let getDashboardOverviewUseCase: GetDashboardOverviewUseCase | undefined
  let getMyDashboardOverviewUseCase: GetMyDashboardOverviewUseCase | undefined
  let getDashboardAnalyticsUseCase: GetDashboardAnalyticsUseCase | undefined
  let getMyDashboardAnalyticsUseCase: GetMyDashboardAnalyticsUseCase | undefined
  let calendarRepository: CalendarRepository | undefined
  let getCalendarFeedUseCase: GetCalendarFeedUseCase | undefined
  let getCalendarDayPageUseCase: GetCalendarDayPageUseCase | undefined
  let listRecentCheckinsUseCase: ListRecentCheckinsUseCase | undefined
  let hostEmployeeRepository: HostEmployeeRepository | undefined
  let listHostEmployeesUseCase: ListHostEmployeesUseCase | undefined
  let listHostEmployeesPageUseCase: ListHostEmployeesPageUseCase | undefined
  let employeeDirectoryRepository: EmployeeDirectoryRepository | undefined
  let listEmployeeDirectoryUseCase: ListEmployeeDirectoryUseCase | undefined
  let createHostEmployeeUseCase: CreateHostEmployeeUseCase | undefined
  let listRolesUseCase: ListRolesUseCase | undefined
  let listRolesPageUseCase: ListRolesPageUseCase | undefined
  let createRoleUseCase: CreateRoleUseCase | undefined
  let listPermissionsUseCase: ListPermissionsUseCase | undefined
  let updateRolePermissionsUseCase: UpdateRolePermissionsUseCase | undefined
  let resyncRolePermissionsUseCase: ResyncRolePermissionsUseCase | undefined
  let assignHostEmployeeRoleUseCase: AssignHostEmployeeRoleUseCase | undefined
  let revokeHostEmployeeRoleUseCase: RevokeHostEmployeeRoleUseCase | undefined
  let disableHostEmployeeUseCase: DisableHostEmployeeUseCase | undefined
  let enableHostEmployeeUseCase: EnableHostEmployeeUseCase | undefined
  let deleteHostEmployeeUseCase: DeleteHostEmployeeUseCase | undefined
  let kioskRepository: KioskRepository | undefined
  let listKiosksPageUseCase: ListKiosksPageUseCase | undefined
  let getKioskUseCase: GetKioskUseCase | undefined
  let createKioskUseCase: CreateKioskUseCase | undefined
  let updateKioskUseCase: UpdateKioskUseCase | undefined
  let setKioskVisibilityUseCase: SetKioskVisibilityUseCase | undefined
  let deleteKioskUseCase: DeleteKioskUseCase | undefined
  let deviceRepository: DeviceRepository | undefined
  let listDevicesPageUseCase: ListDevicesPageUseCase | undefined
  let approveDeviceUseCase: ApproveDeviceUseCase | undefined
  let enableDeviceUseCase: EnableDeviceUseCase | undefined
  let disableDeviceUseCase: DisableDeviceUseCase | undefined
  let deleteDeviceUseCase: DeleteDeviceUseCase | undefined
  let kioskLocationValidationRepository: KioskLocationValidationRepository | undefined
  let getKioskLocationValidationUseCase: GetKioskLocationValidationUseCase | undefined
  let updateKioskLocationValidationUseCase: UpdateKioskLocationValidationUseCase | undefined
  let visitorCategoryRepository: VisitorCategoryRepository | undefined
  let listVisitorCategoriesUseCase: ListVisitorCategoriesUseCase | undefined
  let listVisitorCategoriesPageUseCase: ListVisitorCategoriesPageUseCase | undefined
  let createVisitorCategoryUseCase: CreateVisitorCategoryUseCase | undefined
  let bulkCreateVisitorCategoriesUseCase: BulkCreateVisitorCategoriesUseCase | undefined
  let updateVisitorCategoryUseCase: UpdateVisitorCategoryUseCase | undefined
  let deleteVisitorCategoryUseCase: DeleteVisitorCategoryUseCase | undefined
  let formBuilderRepository: FormBuilderRepository | undefined
  let listFormStepsUseCase: ListFormStepsUseCase | undefined
  let createFormStepUseCase: CreateFormStepUseCase | undefined
  let updateFormStepUseCase: UpdateFormStepUseCase | undefined
  let deleteFormStepUseCase: DeleteFormStepUseCase | undefined
  let reorderFormStepsUseCase: ReorderFormStepsUseCase | undefined
  let listFormFieldsUseCase: ListFormFieldsUseCase | undefined
  let createFormFieldUseCase: CreateFormFieldUseCase | undefined
  let updateFormFieldUseCase: UpdateFormFieldUseCase | undefined
  let deleteFormFieldUseCase: DeleteFormFieldUseCase | undefined
  let reorderFormFieldsUseCase: ReorderFormFieldsUseCase | undefined
  let listFormFieldGroupsUseCase: ListFormFieldGroupsUseCase | undefined
  let createFormFieldGroupUseCase: CreateFormFieldGroupUseCase | undefined
  let updateFormFieldGroupUseCase: UpdateFormFieldGroupUseCase | undefined
  let deleteFormFieldGroupUseCase: DeleteFormFieldGroupUseCase | undefined
  let reorderFormFieldGroupsUseCase: ReorderFormFieldGroupsUseCase | undefined
  let publishFormConfigUseCase: PublishFormConfigUseCase | undefined
  let getEffectiveFormUseCase: GetEffectiveFormUseCase | undefined
  let approvalWorkflowRuleRepository: ApprovalWorkflowRuleRepository | undefined
  let listApprovalWorkflowRulesUseCase: ListApprovalWorkflowRulesUseCase | undefined
  let saveWorkflowUseCase: SaveWorkflowUseCase | undefined
  let deleteWorkflowUseCase: DeleteWorkflowUseCase | undefined
  let notificationRepository: NotificationRepository | undefined
  let registerDeviceUseCase: RegisterDeviceUseCase | undefined
  let unregisterDeviceUseCase: UnregisterDeviceUseCase | undefined
  let listNotificationsUseCase: ListNotificationsUseCase | undefined
  let getUnreadNotificationCountUseCase: GetUnreadNotificationCountUseCase | undefined
  let markNotificationReadUseCase: MarkNotificationReadUseCase | undefined
  let markAllNotificationsReadUseCase: MarkAllNotificationsReadUseCase | undefined

  const resolveApiClient = (): ApiClient => {
    apiClient ??= new ApiClient(import.meta.env.VITE_API_BASE_URL)
    return apiClient
  }

  const resolveVisitRequestRepository = (): VisitRequestRepository => {
    visitRequestRepository ??= new HttpVisitRequestRepository(resolveApiClient())
    return visitRequestRepository
  }

  const resolveVisitTrackingRepository = (): VisitTrackingRepository => {
    visitTrackingRepository ??= new HttpVisitTrackingRepository(resolveApiClient())
    return visitTrackingRepository
  }

  const resolveSubmitVisitRequestUseCase = (): SubmitVisitRequestUseCase => {
    submitVisitRequestUseCase ??= new SubmitVisitRequestUseCase(resolveVisitRequestRepository())
    return submitVisitRequestUseCase
  }

  const resolveTrackVisitRequestUseCase = (): TrackVisitRequestUseCase => {
    trackVisitRequestUseCase ??= new TrackVisitRequestUseCase(resolveVisitTrackingRepository())
    return trackVisitRequestUseCase
  }

  const resolveVisitorOtpRepository = (): VisitorOtpRepository => {
    visitorOtpRepository ??= new HttpVisitorOtpRepository(resolveApiClient())
    return visitorOtpRepository
  }

  const resolveRequestVisitorOtpUseCase = (): RequestVisitorOtpUseCase => {
    requestVisitorOtpUseCase ??= new RequestVisitorOtpUseCase(resolveVisitorOtpRepository())
    return requestVisitorOtpUseCase
  }

  const resolveVerifyVisitorOtpUseCase = (): VerifyVisitorOtpUseCase => {
    verifyVisitorOtpUseCase ??= new VerifyVisitorOtpUseCase(resolveVisitorOtpRepository())
    return verifyVisitorOtpUseCase
  }

  const resolveVisitorPortalRepository = (): VisitorPortalRepository => {
    visitorPortalRepository ??= new HttpVisitorPortalRepository(resolveApiClient())
    return visitorPortalRepository
  }

  const resolveGetVisitorPortalMeUseCase = (): GetVisitorPortalMeUseCase => {
    getVisitorPortalMeUseCase ??= new GetVisitorPortalMeUseCase(resolveVisitorPortalRepository())
    return getVisitorPortalMeUseCase
  }

  const resolveStaffAuthRepository = (): StaffAuthRepository => {
    staffAuthRepository ??= new HttpStaffAuthRepository(resolveApiClient())
    return staffAuthRepository
  }

  const resolveLoginStaffUseCase = (): LoginStaffUseCase => {
    loginStaffUseCase ??= new LoginStaffUseCase(resolveStaffAuthRepository())
    return loginStaffUseCase
  }

  const resolveSsoAuthRepository = (): SsoAuthRepository => {
    ssoAuthRepository ??= new HttpSsoAuthRepository(resolveApiClient())
    return ssoAuthRepository
  }

  const resolveStartSsoLoginUseCase = (): StartSsoLoginUseCase => {
    startSsoLoginUseCase ??= new StartSsoLoginUseCase(resolveSsoAuthRepository(), import.meta.env.VITE_SSO_TENANT_SLUG)
    return startSsoLoginUseCase
  }

  const resolveExchangeSsoCodeUseCase = (): ExchangeSsoCodeUseCase => {
    exchangeSsoCodeUseCase ??= new ExchangeSsoCodeUseCase(resolveSsoAuthRepository())
    return exchangeSsoCodeUseCase
  }

  const resolveVisitRequestSummaryRepository = (): VisitRequestSummaryRepository => {
    visitRequestSummaryRepository ??= new HttpVisitRequestSummaryRepository(resolveApiClient())
    return visitRequestSummaryRepository
  }

  const resolveListVisitRequestsUseCase = (): ListVisitRequestsUseCase => {
    listVisitRequestsUseCase ??= new ListVisitRequestsUseCase(resolveVisitRequestSummaryRepository())
    return listVisitRequestsUseCase
  }

  const resolveApproveInvitationUseCase = (): ApproveInvitationUseCase => {
    approveInvitationUseCase ??= new ApproveInvitationUseCase(resolveVisitRequestSummaryRepository())
    return approveInvitationUseCase
  }

  const resolveGetInvitationDetailUseCase = (): GetInvitationDetailUseCase => {
    getInvitationDetailUseCase ??= new GetInvitationDetailUseCase(resolveVisitRequestSummaryRepository())
    return getInvitationDetailUseCase
  }

  const resolveRescheduleInvitationUseCase = (): RescheduleInvitationUseCase => {
    rescheduleInvitationUseCase ??= new RescheduleInvitationUseCase(resolveVisitRequestSummaryRepository())
    return rescheduleInvitationUseCase
  }

  const resolveEditInvitationUseCase = (): EditInvitationUseCase => {
    editInvitationUseCase ??= new EditInvitationUseCase(resolveVisitRequestSummaryRepository())
    return editInvitationUseCase
  }

  const resolveDenyInvitationUseCase = (): DenyInvitationUseCase => {
    denyInvitationUseCase ??= new DenyInvitationUseCase(resolveVisitRequestSummaryRepository())
    return denyInvitationUseCase
  }

  const resolveRevertInvitationApprovalUseCase = (): RevertInvitationApprovalUseCase => {
    revertInvitationApprovalUseCase ??= new RevertInvitationApprovalUseCase(resolveVisitRequestSummaryRepository())
    return revertInvitationApprovalUseCase
  }

  const resolveCheckOutInvitationUseCase = (): CheckOutInvitationUseCase => {
    checkOutInvitationUseCase ??= new CheckOutInvitationUseCase(resolveVisitRequestSummaryRepository())
    return checkOutInvitationUseCase
  }

  const resolveExportInvitationsUseCase = (): ExportInvitationsUseCase => {
    exportInvitationsUseCase ??= new ExportInvitationsUseCase(resolveVisitRequestSummaryRepository())
    return exportInvitationsUseCase
  }

  const resolveApproveInvitationStepUseCase = (): ApproveInvitationStepUseCase => {
    approveInvitationStepUseCase ??= new ApproveInvitationStepUseCase(resolveVisitRequestSummaryRepository())
    return approveInvitationStepUseCase
  }

  const resolveRejectInvitationStepUseCase = (): RejectInvitationStepUseCase => {
    rejectInvitationStepUseCase ??= new RejectInvitationStepUseCase(resolveVisitRequestSummaryRepository())
    return rejectInvitationStepUseCase
  }

  const resolveDelegateInvitationStepUseCase = (): DelegateInvitationStepUseCase => {
    delegateInvitationStepUseCase ??= new DelegateInvitationStepUseCase(resolveVisitRequestSummaryRepository())
    return delegateInvitationStepUseCase
  }

  const resolveGetCurrentStaffUserUseCase = (): GetCurrentStaffUserUseCase => {
    getCurrentStaffUserUseCase ??= new GetCurrentStaffUserUseCase(resolveStaffAuthRepository())
    return getCurrentStaffUserUseCase
  }

  const resolveStaffVisitRequestRepository = (): StaffVisitRequestRepository => {
    staffVisitRequestRepository ??= new HttpStaffVisitRequestRepository(resolveApiClient())
    return staffVisitRequestRepository
  }

  const resolveSubmitStaffVisitRequestUseCase = (): SubmitStaffVisitRequestUseCase => {
    submitStaffVisitRequestUseCase ??= new SubmitStaffVisitRequestUseCase(resolveStaffVisitRequestRepository())
    return submitStaffVisitRequestUseCase
  }

  const resolveStaffVisitorLookupRepository = (): StaffVisitorLookupRepository => {
    staffVisitorLookupRepository ??= new HttpStaffVisitorLookupRepository(resolveApiClient())
    return staffVisitorLookupRepository
  }

  const resolveLookupStaffVisitorByEmailUseCase = (): LookupStaffVisitorByEmailUseCase => {
    lookupStaffVisitorByEmailUseCase ??= new LookupStaffVisitorByEmailUseCase(resolveStaffVisitorLookupRepository())
    return lookupStaffVisitorByEmailUseCase
  }

  const resolveLookupStaffVisitorByPhoneUseCase = (): LookupStaffVisitorByPhoneUseCase => {
    lookupStaffVisitorByPhoneUseCase ??= new LookupStaffVisitorByPhoneUseCase(resolveStaffVisitorLookupRepository())
    return lookupStaffVisitorByPhoneUseCase
  }

  const resolveAuditTrailRepository = (): AuditTrailRepository => {
    auditTrailRepository ??= new HttpAuditTrailRepository(resolveApiClient())
    return auditTrailRepository
  }

  const resolveGetAuditTrailUseCase = (): GetAuditTrailUseCase => {
    getAuditTrailUseCase ??= new GetAuditTrailUseCase(resolveAuditTrailRepository())
    return getAuditTrailUseCase
  }

  const resolveRequestAuditReportUseCase = (): RequestAuditReportUseCase => {
    requestAuditReportUseCase ??= new RequestAuditReportUseCase(resolveAuditTrailRepository())
    return requestAuditReportUseCase
  }

  const resolveGetAuditReportUseCase = (): GetAuditReportUseCase => {
    getAuditReportUseCase ??= new GetAuditReportUseCase(resolveAuditTrailRepository())
    return getAuditReportUseCase
  }

  const resolveDownloadAuditReportUseCase = (): DownloadAuditReportUseCase => {
    downloadAuditReportUseCase ??= new DownloadAuditReportUseCase(resolveAuditTrailRepository())
    return downloadAuditReportUseCase
  }

  const resolveOrganisationConfigRepository = (): OrganisationConfigRepository => {
    organisationConfigRepository ??= new HttpOrganisationConfigRepository(resolveApiClient())
    return organisationConfigRepository
  }

  const resolveGetOrganisationConfigUseCase = (): GetOrganisationConfigUseCase => {
    getOrganisationConfigUseCase ??= new GetOrganisationConfigUseCase(resolveOrganisationConfigRepository())
    return getOrganisationConfigUseCase
  }

  const resolveUpdateOrganisationConfigUseCase = (): UpdateOrganisationConfigUseCase => {
    updateOrganisationConfigUseCase ??= new UpdateOrganisationConfigUseCase(resolveOrganisationConfigRepository())
    return updateOrganisationConfigUseCase
  }

  const resolveBranchRepository = (): BranchRepository => {
    branchRepository ??= new HttpBranchRepository(resolveApiClient())
    return branchRepository
  }

  const resolveListBranchesUseCase = (): ListBranchesUseCase => {
    listBranchesUseCase ??= new ListBranchesUseCase(resolveBranchRepository())
    return listBranchesUseCase
  }

  const resolveListBranchesPageUseCase = (): ListBranchesPageUseCase => {
    listBranchesPageUseCase ??= new ListBranchesPageUseCase(resolveBranchRepository())
    return listBranchesPageUseCase
  }

  const resolveCreateBranchUseCase = (): CreateBranchUseCase => {
    createBranchUseCase ??= new CreateBranchUseCase(resolveBranchRepository())
    return createBranchUseCase
  }

  const resolveUpdateBranchUseCase = (): UpdateBranchUseCase => {
    updateBranchUseCase ??= new UpdateBranchUseCase(resolveBranchRepository())
    return updateBranchUseCase
  }

  const resolveDeleteBranchUseCase = (): DeleteBranchUseCase => {
    deleteBranchUseCase ??= new DeleteBranchUseCase(resolveBranchRepository())
    return deleteBranchUseCase
  }

  const resolveDepartmentRepository = (): DepartmentRepository => {
    departmentRepository ??= new HttpDepartmentRepository(resolveApiClient(), resolveBranchRepository())
    return departmentRepository
  }

  const resolveListDepartmentsUseCase = (): ListDepartmentsUseCase => {
    listDepartmentsUseCase ??= new ListDepartmentsUseCase(resolveDepartmentRepository())
    return listDepartmentsUseCase
  }

  const resolveListDepartmentsPageUseCase = (): ListDepartmentsPageUseCase => {
    listDepartmentsPageUseCase ??= new ListDepartmentsPageUseCase(resolveDepartmentRepository())
    return listDepartmentsPageUseCase
  }

  const resolveCreateDepartmentUseCase = (): CreateDepartmentUseCase => {
    createDepartmentUseCase ??= new CreateDepartmentUseCase(resolveDepartmentRepository())
    return createDepartmentUseCase
  }

  const resolveUpdateDepartmentUseCase = (): UpdateDepartmentUseCase => {
    updateDepartmentUseCase ??= new UpdateDepartmentUseCase(resolveDepartmentRepository())
    return updateDepartmentUseCase
  }

  const resolveDeleteDepartmentUseCase = (): DeleteDepartmentUseCase => {
    deleteDepartmentUseCase ??= new DeleteDepartmentUseCase(resolveDepartmentRepository())
    return deleteDepartmentUseCase
  }

  const resolveBuildingRepository = (): BuildingRepository => {
    buildingRepository ??= new HttpBuildingRepository(resolveApiClient(), resolveBranchRepository())
    return buildingRepository
  }

  const resolveListBuildingsUseCase = (): ListBuildingsUseCase => {
    listBuildingsUseCase ??= new ListBuildingsUseCase(resolveBuildingRepository())
    return listBuildingsUseCase
  }

  const resolveListBuildingsPageUseCase = (): ListBuildingsPageUseCase => {
    listBuildingsPageUseCase ??= new ListBuildingsPageUseCase(resolveBuildingRepository())
    return listBuildingsPageUseCase
  }

  const resolveCreateBuildingUseCase = (): CreateBuildingUseCase => {
    createBuildingUseCase ??= new CreateBuildingUseCase(resolveBuildingRepository())
    return createBuildingUseCase
  }

  const resolveUpdateBuildingUseCase = (): UpdateBuildingUseCase => {
    updateBuildingUseCase ??= new UpdateBuildingUseCase(resolveBuildingRepository())
    return updateBuildingUseCase
  }

  const resolveDeleteBuildingUseCase = (): DeleteBuildingUseCase => {
    deleteBuildingUseCase ??= new DeleteBuildingUseCase(resolveBuildingRepository())
    return deleteBuildingUseCase
  }

  const resolveFloorRepository = (): FloorRepository => {
    floorRepository ??= new HttpFloorRepository(resolveApiClient())
    return floorRepository
  }

  const resolveListFloorsUseCase = (): ListFloorsUseCase => {
    listFloorsUseCase ??= new ListFloorsUseCase(resolveFloorRepository())
    return listFloorsUseCase
  }

  const resolveListFloorsPageUseCase = (): ListFloorsPageUseCase => {
    listFloorsPageUseCase ??= new ListFloorsPageUseCase(resolveFloorRepository())
    return listFloorsPageUseCase
  }

  const resolveCreateFloorUseCase = (): CreateFloorUseCase => {
    createFloorUseCase ??= new CreateFloorUseCase(resolveFloorRepository())
    return createFloorUseCase
  }

  const resolveUpdateFloorUseCase = (): UpdateFloorUseCase => {
    updateFloorUseCase ??= new UpdateFloorUseCase(resolveFloorRepository())
    return updateFloorUseCase
  }

  const resolveDeleteFloorUseCase = (): DeleteFloorUseCase => {
    deleteFloorUseCase ??= new DeleteFloorUseCase(resolveFloorRepository())
    return deleteFloorUseCase
  }

  const resolveDashboardRepository = (): DashboardRepository => {
    dashboardRepository ??= new HttpDashboardRepository(resolveApiClient())
    return dashboardRepository
  }

  const resolveGetDashboardOverviewUseCase = (): GetDashboardOverviewUseCase => {
    getDashboardOverviewUseCase ??= new GetDashboardOverviewUseCase(resolveDashboardRepository())
    return getDashboardOverviewUseCase
  }

  const resolveGetMyDashboardOverviewUseCase = (): GetMyDashboardOverviewUseCase => {
    getMyDashboardOverviewUseCase ??= new GetMyDashboardOverviewUseCase(resolveDashboardRepository())
    return getMyDashboardOverviewUseCase
  }

  const resolveGetDashboardAnalyticsUseCase = (): GetDashboardAnalyticsUseCase => {
    getDashboardAnalyticsUseCase ??= new GetDashboardAnalyticsUseCase(resolveDashboardRepository())
    return getDashboardAnalyticsUseCase
  }

  const resolveGetMyDashboardAnalyticsUseCase = (): GetMyDashboardAnalyticsUseCase => {
    getMyDashboardAnalyticsUseCase ??= new GetMyDashboardAnalyticsUseCase(resolveDashboardRepository())
    return getMyDashboardAnalyticsUseCase
  }

  const resolveCalendarRepository = (): CalendarRepository => {
    calendarRepository ??= new HttpCalendarRepository(resolveApiClient())
    return calendarRepository
  }

  const resolveGetCalendarFeedUseCase = (): GetCalendarFeedUseCase => {
    getCalendarFeedUseCase ??= new GetCalendarFeedUseCase(resolveCalendarRepository())
    return getCalendarFeedUseCase
  }

  const resolveGetCalendarDayPageUseCase = (): GetCalendarDayPageUseCase => {
    getCalendarDayPageUseCase ??= new GetCalendarDayPageUseCase(resolveCalendarRepository())
    return getCalendarDayPageUseCase
  }

  const resolveListRecentCheckinsUseCase = (): ListRecentCheckinsUseCase => {
    listRecentCheckinsUseCase ??= new ListRecentCheckinsUseCase(resolveDashboardRepository())
    return listRecentCheckinsUseCase
  }

  const resolveHostEmployeeRepository = (): HostEmployeeRepository => {
    hostEmployeeRepository ??= new HttpHostEmployeeRepository(resolveApiClient())
    return hostEmployeeRepository
  }

  const resolveListHostEmployeesPageUseCase = (): ListHostEmployeesPageUseCase => {
    listHostEmployeesPageUseCase ??= new ListHostEmployeesPageUseCase(resolveHostEmployeeRepository())
    return listHostEmployeesPageUseCase
  }

  const resolveListHostEmployeesUseCase = (): ListHostEmployeesUseCase => {
    listHostEmployeesUseCase ??= new ListHostEmployeesUseCase(resolveHostEmployeeRepository())
    return listHostEmployeesUseCase
  }

  const resolveEmployeeDirectoryRepository = (): EmployeeDirectoryRepository => {
    employeeDirectoryRepository ??= new HttpEmployeeDirectoryRepository(resolveApiClient())
    return employeeDirectoryRepository
  }

  const resolveListEmployeeDirectoryUseCase = (): ListEmployeeDirectoryUseCase => {
    listEmployeeDirectoryUseCase ??= new ListEmployeeDirectoryUseCase(resolveEmployeeDirectoryRepository())
    return listEmployeeDirectoryUseCase
  }

  const resolveCreateHostEmployeeUseCase = (): CreateHostEmployeeUseCase => {
    createHostEmployeeUseCase ??= new CreateHostEmployeeUseCase(resolveHostEmployeeRepository())
    return createHostEmployeeUseCase
  }

  const resolveListRolesPageUseCase = (): ListRolesPageUseCase => {
    listRolesPageUseCase ??= new ListRolesPageUseCase(resolveHostEmployeeRepository())
    return listRolesPageUseCase
  }

  const resolveListRolesUseCase = (): ListRolesUseCase => {
    listRolesUseCase ??= new ListRolesUseCase(resolveHostEmployeeRepository())
    return listRolesUseCase
  }

  const resolveCreateRoleUseCase = (): CreateRoleUseCase => {
    createRoleUseCase ??= new CreateRoleUseCase(resolveHostEmployeeRepository())
    return createRoleUseCase
  }

  const resolveListPermissionsUseCase = (): ListPermissionsUseCase => {
    listPermissionsUseCase ??= new ListPermissionsUseCase(resolveHostEmployeeRepository())
    return listPermissionsUseCase
  }

  const resolveUpdateRolePermissionsUseCase = (): UpdateRolePermissionsUseCase => {
    updateRolePermissionsUseCase ??= new UpdateRolePermissionsUseCase(resolveHostEmployeeRepository())
    return updateRolePermissionsUseCase
  }

  const resolveResyncRolePermissionsUseCase = (): ResyncRolePermissionsUseCase => {
    resyncRolePermissionsUseCase ??= new ResyncRolePermissionsUseCase(resolveHostEmployeeRepository())
    return resyncRolePermissionsUseCase
  }

  const resolveAssignHostEmployeeRoleUseCase = (): AssignHostEmployeeRoleUseCase => {
    assignHostEmployeeRoleUseCase ??= new AssignHostEmployeeRoleUseCase(resolveHostEmployeeRepository())
    return assignHostEmployeeRoleUseCase
  }

  const resolveDisableHostEmployeeUseCase = (): DisableHostEmployeeUseCase => {
    disableHostEmployeeUseCase ??= new DisableHostEmployeeUseCase(resolveHostEmployeeRepository())
    return disableHostEmployeeUseCase
  }

  const resolveEnableHostEmployeeUseCase = (): EnableHostEmployeeUseCase => {
    enableHostEmployeeUseCase ??= new EnableHostEmployeeUseCase(resolveHostEmployeeRepository())
    return enableHostEmployeeUseCase
  }

  const resolveDeleteHostEmployeeUseCase = (): DeleteHostEmployeeUseCase => {
    deleteHostEmployeeUseCase ??= new DeleteHostEmployeeUseCase(resolveHostEmployeeRepository())
    return deleteHostEmployeeUseCase
  }

  const resolveRevokeHostEmployeeRoleUseCase = (): RevokeHostEmployeeRoleUseCase => {
    revokeHostEmployeeRoleUseCase ??= new RevokeHostEmployeeRoleUseCase(resolveHostEmployeeRepository())
    return revokeHostEmployeeRoleUseCase
  }

  const resolveKioskRepository = (): KioskRepository => {
    kioskRepository ??= new HttpKioskRepository(resolveApiClient())
    return kioskRepository
  }

  const resolveListKiosksPageUseCase = (): ListKiosksPageUseCase => {
    listKiosksPageUseCase ??= new ListKiosksPageUseCase(resolveKioskRepository())
    return listKiosksPageUseCase
  }

  const resolveGetKioskUseCase = (): GetKioskUseCase => {
    getKioskUseCase ??= new GetKioskUseCase(resolveKioskRepository())
    return getKioskUseCase
  }

  const resolveCreateKioskUseCase = (): CreateKioskUseCase => {
    createKioskUseCase ??= new CreateKioskUseCase(resolveKioskRepository())
    return createKioskUseCase
  }

  const resolveUpdateKioskUseCase = (): UpdateKioskUseCase => {
    updateKioskUseCase ??= new UpdateKioskUseCase(resolveKioskRepository())
    return updateKioskUseCase
  }

  const resolveSetKioskVisibilityUseCase = (): SetKioskVisibilityUseCase => {
    setKioskVisibilityUseCase ??= new SetKioskVisibilityUseCase(resolveKioskRepository())
    return setKioskVisibilityUseCase
  }

  const resolveDeleteKioskUseCase = (): DeleteKioskUseCase => {
    deleteKioskUseCase ??= new DeleteKioskUseCase(resolveKioskRepository())
    return deleteKioskUseCase
  }

  const resolveDeviceRepository = (): DeviceRepository => {
    deviceRepository ??= new HttpDeviceRepository(resolveApiClient())
    return deviceRepository
  }

  const resolveListDevicesPageUseCase = (): ListDevicesPageUseCase => {
    listDevicesPageUseCase ??= new ListDevicesPageUseCase(resolveDeviceRepository())
    return listDevicesPageUseCase
  }

  const resolveApproveDeviceUseCase = (): ApproveDeviceUseCase => {
    approveDeviceUseCase ??= new ApproveDeviceUseCase(resolveDeviceRepository())
    return approveDeviceUseCase
  }

  const resolveEnableDeviceUseCase = (): EnableDeviceUseCase => {
    enableDeviceUseCase ??= new EnableDeviceUseCase(resolveDeviceRepository())
    return enableDeviceUseCase
  }

  const resolveDisableDeviceUseCase = (): DisableDeviceUseCase => {
    disableDeviceUseCase ??= new DisableDeviceUseCase(resolveDeviceRepository())
    return disableDeviceUseCase
  }

  const resolveDeleteDeviceUseCase = (): DeleteDeviceUseCase => {
    deleteDeviceUseCase ??= new DeleteDeviceUseCase(resolveDeviceRepository())
    return deleteDeviceUseCase
  }

  const resolveKioskLocationValidationRepository = (): KioskLocationValidationRepository => {
    kioskLocationValidationRepository ??= new HttpKioskLocationValidationRepository(resolveApiClient())
    return kioskLocationValidationRepository
  }

  const resolveGetKioskLocationValidationUseCase = (): GetKioskLocationValidationUseCase => {
    getKioskLocationValidationUseCase ??= new GetKioskLocationValidationUseCase(resolveKioskLocationValidationRepository())
    return getKioskLocationValidationUseCase
  }

  const resolveUpdateKioskLocationValidationUseCase = (): UpdateKioskLocationValidationUseCase => {
    updateKioskLocationValidationUseCase ??= new UpdateKioskLocationValidationUseCase(resolveKioskLocationValidationRepository())
    return updateKioskLocationValidationUseCase
  }

  const resolveVisitorCategoryRepository = (): VisitorCategoryRepository => {
    visitorCategoryRepository ??= new HttpVisitorCategoryRepository(resolveApiClient())
    return visitorCategoryRepository
  }

  const resolveListVisitorCategoriesPageUseCase = (): ListVisitorCategoriesPageUseCase => {
    listVisitorCategoriesPageUseCase ??= new ListVisitorCategoriesPageUseCase(resolveVisitorCategoryRepository())
    return listVisitorCategoriesPageUseCase
  }

  const resolveListVisitorCategoriesUseCase = (): ListVisitorCategoriesUseCase => {
    listVisitorCategoriesUseCase ??= new ListVisitorCategoriesUseCase(resolveVisitorCategoryRepository())
    return listVisitorCategoriesUseCase
  }

  const resolveCreateVisitorCategoryUseCase = (): CreateVisitorCategoryUseCase => {
    createVisitorCategoryUseCase ??= new CreateVisitorCategoryUseCase(resolveVisitorCategoryRepository())
    return createVisitorCategoryUseCase
  }

  const resolveBulkCreateVisitorCategoriesUseCase = (): BulkCreateVisitorCategoriesUseCase => {
    bulkCreateVisitorCategoriesUseCase ??= new BulkCreateVisitorCategoriesUseCase(resolveVisitorCategoryRepository())
    return bulkCreateVisitorCategoriesUseCase
  }

  const resolveUpdateVisitorCategoryUseCase = (): UpdateVisitorCategoryUseCase => {
    updateVisitorCategoryUseCase ??= new UpdateVisitorCategoryUseCase(resolveVisitorCategoryRepository())
    return updateVisitorCategoryUseCase
  }

  const resolveDeleteVisitorCategoryUseCase = (): DeleteVisitorCategoryUseCase => {
    deleteVisitorCategoryUseCase ??= new DeleteVisitorCategoryUseCase(resolveVisitorCategoryRepository())
    return deleteVisitorCategoryUseCase
  }

  const resolveFormBuilderRepository = (): FormBuilderRepository => {
    formBuilderRepository ??= new HttpFormBuilderRepository(resolveApiClient())
    return formBuilderRepository
  }

  const resolveListFormStepsUseCase = (): ListFormStepsUseCase => {
    listFormStepsUseCase ??= new ListFormStepsUseCase(resolveFormBuilderRepository())
    return listFormStepsUseCase
  }

  const resolveCreateFormStepUseCase = (): CreateFormStepUseCase => {
    createFormStepUseCase ??= new CreateFormStepUseCase(resolveFormBuilderRepository())
    return createFormStepUseCase
  }

  const resolveUpdateFormStepUseCase = (): UpdateFormStepUseCase => {
    updateFormStepUseCase ??= new UpdateFormStepUseCase(resolveFormBuilderRepository())
    return updateFormStepUseCase
  }

  const resolveDeleteFormStepUseCase = (): DeleteFormStepUseCase => {
    deleteFormStepUseCase ??= new DeleteFormStepUseCase(resolveFormBuilderRepository())
    return deleteFormStepUseCase
  }

  const resolveReorderFormStepsUseCase = (): ReorderFormStepsUseCase => {
    reorderFormStepsUseCase ??= new ReorderFormStepsUseCase(resolveFormBuilderRepository())
    return reorderFormStepsUseCase
  }

  const resolveListFormFieldsUseCase = (): ListFormFieldsUseCase => {
    listFormFieldsUseCase ??= new ListFormFieldsUseCase(resolveFormBuilderRepository())
    return listFormFieldsUseCase
  }

  const resolveCreateFormFieldUseCase = (): CreateFormFieldUseCase => {
    createFormFieldUseCase ??= new CreateFormFieldUseCase(resolveFormBuilderRepository())
    return createFormFieldUseCase
  }

  const resolveUpdateFormFieldUseCase = (): UpdateFormFieldUseCase => {
    updateFormFieldUseCase ??= new UpdateFormFieldUseCase(resolveFormBuilderRepository())
    return updateFormFieldUseCase
  }

  const resolveDeleteFormFieldUseCase = (): DeleteFormFieldUseCase => {
    deleteFormFieldUseCase ??= new DeleteFormFieldUseCase(resolveFormBuilderRepository())
    return deleteFormFieldUseCase
  }

  const resolveReorderFormFieldsUseCase = (): ReorderFormFieldsUseCase => {
    reorderFormFieldsUseCase ??= new ReorderFormFieldsUseCase(resolveFormBuilderRepository())
    return reorderFormFieldsUseCase
  }

  const resolveListFormFieldGroupsUseCase = (): ListFormFieldGroupsUseCase => {
    listFormFieldGroupsUseCase ??= new ListFormFieldGroupsUseCase(resolveFormBuilderRepository())
    return listFormFieldGroupsUseCase
  }

  const resolveCreateFormFieldGroupUseCase = (): CreateFormFieldGroupUseCase => {
    createFormFieldGroupUseCase ??= new CreateFormFieldGroupUseCase(resolveFormBuilderRepository())
    return createFormFieldGroupUseCase
  }

  const resolveUpdateFormFieldGroupUseCase = (): UpdateFormFieldGroupUseCase => {
    updateFormFieldGroupUseCase ??= new UpdateFormFieldGroupUseCase(resolveFormBuilderRepository())
    return updateFormFieldGroupUseCase
  }

  const resolveDeleteFormFieldGroupUseCase = (): DeleteFormFieldGroupUseCase => {
    deleteFormFieldGroupUseCase ??= new DeleteFormFieldGroupUseCase(resolveFormBuilderRepository())
    return deleteFormFieldGroupUseCase
  }

  const resolveReorderFormFieldGroupsUseCase = (): ReorderFormFieldGroupsUseCase => {
    reorderFormFieldGroupsUseCase ??= new ReorderFormFieldGroupsUseCase(resolveFormBuilderRepository())
    return reorderFormFieldGroupsUseCase
  }

  const resolvePublishFormConfigUseCase = (): PublishFormConfigUseCase => {
    publishFormConfigUseCase ??= new PublishFormConfigUseCase(resolveFormBuilderRepository())
    return publishFormConfigUseCase
  }

  const resolveGetEffectiveFormUseCase = (): GetEffectiveFormUseCase => {
    getEffectiveFormUseCase ??= new GetEffectiveFormUseCase(resolveFormBuilderRepository())
    return getEffectiveFormUseCase
  }

  const resolveApprovalWorkflowRuleRepository = (): ApprovalWorkflowRuleRepository => {
    approvalWorkflowRuleRepository ??= new HttpApprovalWorkflowRuleRepository(resolveApiClient())
    return approvalWorkflowRuleRepository
  }

  const resolveListApprovalWorkflowRulesUseCase = (): ListApprovalWorkflowRulesUseCase => {
    listApprovalWorkflowRulesUseCase ??= new ListApprovalWorkflowRulesUseCase(resolveApprovalWorkflowRuleRepository())
    return listApprovalWorkflowRulesUseCase
  }

  const resolveSaveWorkflowUseCase = (): SaveWorkflowUseCase => {
    saveWorkflowUseCase ??= new SaveWorkflowUseCase(resolveApprovalWorkflowRuleRepository())
    return saveWorkflowUseCase
  }

  const resolveDeleteWorkflowUseCase = (): DeleteWorkflowUseCase => {
    deleteWorkflowUseCase ??= new DeleteWorkflowUseCase(resolveApprovalWorkflowRuleRepository())
    return deleteWorkflowUseCase
  }

  const resolveNotificationRepository = (): NotificationRepository => {
    notificationRepository ??= new HttpNotificationRepository(resolveApiClient())
    return notificationRepository
  }

  const resolveRegisterDeviceUseCase = (): RegisterDeviceUseCase => {
    registerDeviceUseCase ??= new RegisterDeviceUseCase(resolveNotificationRepository())
    return registerDeviceUseCase
  }

  const resolveUnregisterDeviceUseCase = (): UnregisterDeviceUseCase => {
    unregisterDeviceUseCase ??= new UnregisterDeviceUseCase(resolveNotificationRepository())
    return unregisterDeviceUseCase
  }

  const resolveListNotificationsUseCase = (): ListNotificationsUseCase => {
    listNotificationsUseCase ??= new ListNotificationsUseCase(resolveNotificationRepository())
    return listNotificationsUseCase
  }

  const resolveGetUnreadNotificationCountUseCase = (): GetUnreadNotificationCountUseCase => {
    getUnreadNotificationCountUseCase ??= new GetUnreadNotificationCountUseCase(resolveNotificationRepository())
    return getUnreadNotificationCountUseCase
  }

  const resolveMarkNotificationReadUseCase = (): MarkNotificationReadUseCase => {
    markNotificationReadUseCase ??= new MarkNotificationReadUseCase(resolveNotificationRepository())
    return markNotificationReadUseCase
  }

  const resolveMarkAllNotificationsReadUseCase = (): MarkAllNotificationsReadUseCase => {
    markAllNotificationsReadUseCase ??= new MarkAllNotificationsReadUseCase(resolveNotificationRepository())
    return markAllNotificationsReadUseCase
  }

  return {
    get apiClient() {
      return resolveApiClient()
    },
    get submitVisitRequestUseCase() {
      return resolveSubmitVisitRequestUseCase()
    },
    get trackVisitRequestUseCase() {
      return resolveTrackVisitRequestUseCase()
    },
    get requestVisitorOtpUseCase() {
      return resolveRequestVisitorOtpUseCase()
    },
    get verifyVisitorOtpUseCase() {
      return resolveVerifyVisitorOtpUseCase()
    },
    get getVisitorPortalMeUseCase() {
      return resolveGetVisitorPortalMeUseCase()
    },
    get loginStaffUseCase() {
      return resolveLoginStaffUseCase()
    },
    get startSsoLoginUseCase() {
      return resolveStartSsoLoginUseCase()
    },
    get exchangeSsoCodeUseCase() {
      return resolveExchangeSsoCodeUseCase()
    },
    get listVisitRequestsUseCase() {
      return resolveListVisitRequestsUseCase()
    },
    get getInvitationDetailUseCase() {
      return resolveGetInvitationDetailUseCase()
    },
    get rescheduleInvitationUseCase() {
      return resolveRescheduleInvitationUseCase()
    },
    get editInvitationUseCase() {
      return resolveEditInvitationUseCase()
    },
    get denyInvitationUseCase() {
      return resolveDenyInvitationUseCase()
    },
    get revertInvitationApprovalUseCase() {
      return resolveRevertInvitationApprovalUseCase()
    },
    get checkOutInvitationUseCase() {
      return resolveCheckOutInvitationUseCase()
    },
    get exportInvitationsUseCase() {
      return resolveExportInvitationsUseCase()
    },
    get approveInvitationStepUseCase() {
      return resolveApproveInvitationStepUseCase()
    },
    get rejectInvitationStepUseCase() {
      return resolveRejectInvitationStepUseCase()
    },
    get delegateInvitationStepUseCase() {
      return resolveDelegateInvitationStepUseCase()
    },
    get approveInvitationUseCase() {
      return resolveApproveInvitationUseCase()
    },
    get getCurrentStaffUserUseCase() {
      return resolveGetCurrentStaffUserUseCase()
    },
    get submitStaffVisitRequestUseCase() {
      return resolveSubmitStaffVisitRequestUseCase()
    },
    get lookupStaffVisitorByEmailUseCase() {
      return resolveLookupStaffVisitorByEmailUseCase()
    },
    get lookupStaffVisitorByPhoneUseCase() {
      return resolveLookupStaffVisitorByPhoneUseCase()
    },
    get getAuditTrailUseCase() {
      return resolveGetAuditTrailUseCase()
    },
    get requestAuditReportUseCase() {
      return resolveRequestAuditReportUseCase()
    },
    get getAuditReportUseCase() {
      return resolveGetAuditReportUseCase()
    },
    get downloadAuditReportUseCase() {
      return resolveDownloadAuditReportUseCase()
    },
    get getOrganisationConfigUseCase() {
      return resolveGetOrganisationConfigUseCase()
    },
    get updateOrganisationConfigUseCase() {
      return resolveUpdateOrganisationConfigUseCase()
    },
    get listBranchesUseCase() {
      return resolveListBranchesUseCase()
    },
    get listBranchesPageUseCase() {
      return resolveListBranchesPageUseCase()
    },
    get createBranchUseCase() {
      return resolveCreateBranchUseCase()
    },
    get updateBranchUseCase() {
      return resolveUpdateBranchUseCase()
    },
    get deleteBranchUseCase() {
      return resolveDeleteBranchUseCase()
    },
    get listDepartmentsUseCase() {
      return resolveListDepartmentsUseCase()
    },
    get listDepartmentsPageUseCase() {
      return resolveListDepartmentsPageUseCase()
    },
    get createDepartmentUseCase() {
      return resolveCreateDepartmentUseCase()
    },
    get updateDepartmentUseCase() {
      return resolveUpdateDepartmentUseCase()
    },
    get deleteDepartmentUseCase() {
      return resolveDeleteDepartmentUseCase()
    },
    get listBuildingsUseCase() {
      return resolveListBuildingsUseCase()
    },
    get listBuildingsPageUseCase() {
      return resolveListBuildingsPageUseCase()
    },
    get createBuildingUseCase() {
      return resolveCreateBuildingUseCase()
    },
    get updateBuildingUseCase() {
      return resolveUpdateBuildingUseCase()
    },
    get deleteBuildingUseCase() {
      return resolveDeleteBuildingUseCase()
    },
    get listFloorsUseCase() {
      return resolveListFloorsUseCase()
    },
    get listFloorsPageUseCase() {
      return resolveListFloorsPageUseCase()
    },
    get createFloorUseCase() {
      return resolveCreateFloorUseCase()
    },
    get updateFloorUseCase() {
      return resolveUpdateFloorUseCase()
    },
    get deleteFloorUseCase() {
      return resolveDeleteFloorUseCase()
    },
    get getDashboardOverviewUseCase() {
      return resolveGetDashboardOverviewUseCase()
    },
    get getMyDashboardOverviewUseCase() {
      return resolveGetMyDashboardOverviewUseCase()
    },
    get getDashboardAnalyticsUseCase() {
      return resolveGetDashboardAnalyticsUseCase()
    },
    get getMyDashboardAnalyticsUseCase() {
      return resolveGetMyDashboardAnalyticsUseCase()
    },
    get getCalendarFeedUseCase() {
      return resolveGetCalendarFeedUseCase()
    },
    get getCalendarDayPageUseCase() {
      return resolveGetCalendarDayPageUseCase()
    },
    get listRecentCheckinsUseCase() {
      return resolveListRecentCheckinsUseCase()
    },
    get listHostEmployeesUseCase() {
      return resolveListHostEmployeesUseCase()
    },
    get listHostEmployeesPageUseCase() {
      return resolveListHostEmployeesPageUseCase()
    },
    get listEmployeeDirectoryUseCase() {
      return resolveListEmployeeDirectoryUseCase()
    },
    get createHostEmployeeUseCase() {
      return resolveCreateHostEmployeeUseCase()
    },
    get listRolesUseCase() {
      return resolveListRolesUseCase()
    },
    get listRolesPageUseCase() {
      return resolveListRolesPageUseCase()
    },
    get createRoleUseCase() {
      return resolveCreateRoleUseCase()
    },
    get listPermissionsUseCase() {
      return resolveListPermissionsUseCase()
    },
    get updateRolePermissionsUseCase() {
      return resolveUpdateRolePermissionsUseCase()
    },
    get resyncRolePermissionsUseCase() {
      return resolveResyncRolePermissionsUseCase()
    },
    get assignHostEmployeeRoleUseCase() {
      return resolveAssignHostEmployeeRoleUseCase()
    },
    get disableHostEmployeeUseCase() {
      return resolveDisableHostEmployeeUseCase()
    },
    get enableHostEmployeeUseCase() {
      return resolveEnableHostEmployeeUseCase()
    },
    get deleteHostEmployeeUseCase() {
      return resolveDeleteHostEmployeeUseCase()
    },
    get revokeHostEmployeeRoleUseCase() {
      return resolveRevokeHostEmployeeRoleUseCase()
    },
    get listKiosksPageUseCase() {
      return resolveListKiosksPageUseCase()
    },
    get getKioskUseCase() {
      return resolveGetKioskUseCase()
    },
    get createKioskUseCase() {
      return resolveCreateKioskUseCase()
    },
    get updateKioskUseCase() {
      return resolveUpdateKioskUseCase()
    },
    get setKioskVisibilityUseCase() {
      return resolveSetKioskVisibilityUseCase()
    },
    get deleteKioskUseCase() {
      return resolveDeleteKioskUseCase()
    },
    get listDevicesPageUseCase() {
      return resolveListDevicesPageUseCase()
    },
    get approveDeviceUseCase() {
      return resolveApproveDeviceUseCase()
    },
    get enableDeviceUseCase() {
      return resolveEnableDeviceUseCase()
    },
    get disableDeviceUseCase() {
      return resolveDisableDeviceUseCase()
    },
    get deleteDeviceUseCase() {
      return resolveDeleteDeviceUseCase()
    },
    get getKioskLocationValidationUseCase() {
      return resolveGetKioskLocationValidationUseCase()
    },
    get updateKioskLocationValidationUseCase() {
      return resolveUpdateKioskLocationValidationUseCase()
    },
    get listVisitorCategoriesUseCase() {
      return resolveListVisitorCategoriesUseCase()
    },
    get listVisitorCategoriesPageUseCase() {
      return resolveListVisitorCategoriesPageUseCase()
    },
    get createVisitorCategoryUseCase() {
      return resolveCreateVisitorCategoryUseCase()
    },
    get bulkCreateVisitorCategoriesUseCase() {
      return resolveBulkCreateVisitorCategoriesUseCase()
    },
    get updateVisitorCategoryUseCase() {
      return resolveUpdateVisitorCategoryUseCase()
    },
    get deleteVisitorCategoryUseCase() {
      return resolveDeleteVisitorCategoryUseCase()
    },
    get listApprovalWorkflowRulesUseCase() {
      return resolveListApprovalWorkflowRulesUseCase()
    },
    get saveWorkflowUseCase() {
      return resolveSaveWorkflowUseCase()
    },
    get deleteWorkflowUseCase() {
      return resolveDeleteWorkflowUseCase()
    },
    get registerDeviceUseCase() {
      return resolveRegisterDeviceUseCase()
    },
    get unregisterDeviceUseCase() {
      return resolveUnregisterDeviceUseCase()
    },
    get listNotificationsUseCase() {
      return resolveListNotificationsUseCase()
    },
    get getUnreadNotificationCountUseCase() {
      return resolveGetUnreadNotificationCountUseCase()
    },
    get markNotificationReadUseCase() {
      return resolveMarkNotificationReadUseCase()
    },
    get markAllNotificationsReadUseCase() {
      return resolveMarkAllNotificationsReadUseCase()
    },
    get listFormStepsUseCase() {
      return resolveListFormStepsUseCase()
    },
    get createFormStepUseCase() {
      return resolveCreateFormStepUseCase()
    },
    get updateFormStepUseCase() {
      return resolveUpdateFormStepUseCase()
    },
    get deleteFormStepUseCase() {
      return resolveDeleteFormStepUseCase()
    },
    get reorderFormStepsUseCase() {
      return resolveReorderFormStepsUseCase()
    },
    get listFormFieldsUseCase() {
      return resolveListFormFieldsUseCase()
    },
    get createFormFieldUseCase() {
      return resolveCreateFormFieldUseCase()
    },
    get updateFormFieldUseCase() {
      return resolveUpdateFormFieldUseCase()
    },
    get deleteFormFieldUseCase() {
      return resolveDeleteFormFieldUseCase()
    },
    get reorderFormFieldsUseCase() {
      return resolveReorderFormFieldsUseCase()
    },
    get listFormFieldGroupsUseCase() {
      return resolveListFormFieldGroupsUseCase()
    },
    get createFormFieldGroupUseCase() {
      return resolveCreateFormFieldGroupUseCase()
    },
    get updateFormFieldGroupUseCase() {
      return resolveUpdateFormFieldGroupUseCase()
    },
    get deleteFormFieldGroupUseCase() {
      return resolveDeleteFormFieldGroupUseCase()
    },
    get reorderFormFieldGroupsUseCase() {
      return resolveReorderFormFieldGroupsUseCase()
    },
    get publishFormConfigUseCase() {
      return resolvePublishFormConfigUseCase()
    },
    get getEffectiveFormUseCase() {
      return resolveGetEffectiveFormUseCase()
    },
  }
}
