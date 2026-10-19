export const API_ENDPOINTS = {
  CREATE_VISIT_REQUEST: {
    endpoint: "/registrations/walk-in",
    method: "POST",
    hasToken: false,
  },
  TRACK_VISIT_REQUEST: {
    endpoint: "/invitations/track",
    method: "GET",
    hasToken: false,
  },
  REQUEST_VISITOR_OTP: {
    endpoint: "/identity-verification/otp/request",
    method: "POST",
    hasToken: false,
  },
  VERIFY_VISITOR_OTP: {
    endpoint: "/identity-verification/otp/verify",
    method: "POST",
    hasToken: false,
  },
  // Authenticated with the OTP flow's own short-lived proof token, passed as
  // an explicit `Authorization` header by the caller — never the staff
  // session token `hasToken: true` would read from sessionStorage.
  GET_VISITOR_PORTAL_ME: {
    endpoint: "/visitor-portal/me",
    method: "GET",
    hasToken: false,
  },
  STAFF_LOGIN: {
    endpoint: "/auth/login",
    method: "POST",
    hasToken: false,
  },
  START_SSO_LOGIN: {
    endpoint: "/auth/sso/:tenantSlug/login",
    method: "GET",
    hasToken: false,
  },
  SSO_EXCHANGE: {
    endpoint: "/auth/sso/exchange",
    method: "POST",
    hasToken: false,
  },
  LIST_VISIT_REQUESTS: {
    endpoint: "/invitations",
    method: "GET",
    hasToken: true,
  },
  EXPORT_INVITATIONS: {
    endpoint: "/invitations/export",
    method: "GET",
    hasToken: true,
  },
  GET_CURRENT_STAFF_USER: {
    endpoint: "/auth/me",
    method: "GET",
    hasToken: true,
  },
  STAFF_CREATE_VISIT_REQUEST: {
    endpoint: "/invitations",
    method: "POST",
    hasToken: true,
  },
  // Staff-authenticated lookup used to prefill the Register Visitor wizard's
  // Primary Contact fields once the staff member types a known email — no
  // OTP is needed since it runs under the staff session, unlike the visitor
  // self-service GET_VISITOR_PORTAL_ME flow above.
  LOOKUP_STAFF_VISITOR_BY_EMAIL: {
    endpoint: "/invitations/lookup-by-email",
    method: "GET",
    hasToken: true,
  },
  // Same prefill as above, keyed on phone (backend strips it to digits, so
  // any formatting matches; needs >= 7 digits or it 422s).
  LOOKUP_STAFF_VISITOR_BY_PHONE: {
    endpoint: "/invitations/lookup-by-phone",
    method: "GET",
    hasToken: true,
  },
  APPROVE_INVITATION: {
    endpoint: "/invitations/:id/approve",
    method: "POST",
    hasToken: true,
  },
  GET_INVITATION_DETAIL: {
    endpoint: "/invitations/:id",
    method: "GET",
    hasToken: true,
  },
  RESCHEDULE_INVITATION: {
    endpoint: "/invitations/:id/reschedule",
    method: "PATCH",
    hasToken: true,
  },
  EDIT_INVITATION: {
    endpoint: "/invitations/:id/edit",
    method: "PATCH",
    hasToken: true,
  },
  DENY_INVITATION: {
    endpoint: "/invitations/:id/deny",
    method: "PATCH",
    hasToken: true,
  },
  REVERT_INVITATION_APPROVAL: {
    endpoint: "/invitations/:id/revert-approval",
    method: "PATCH",
    hasToken: true,
  },
  CHECK_OUT_INVITATION: {
    endpoint: "/invitations/:id/check-out",
    method: "PATCH",
    hasToken: true,
  },
  APPROVE_INVITATION_STEP: {
    endpoint: "/invitations/:invitationId/approval-steps/:stepId/approve",
    method: "POST",
    hasToken: true,
  },
  REJECT_INVITATION_STEP: {
    endpoint: "/invitations/:invitationId/approval-steps/:stepId/reject",
    method: "POST",
    hasToken: true,
  },
  DELEGATE_INVITATION_STEP: {
    endpoint: "/invitations/:invitationId/approval-steps/:stepId/delegate",
    method: "POST",
    hasToken: true,
  },
  LIST_AUDIT_TRAIL: {
    endpoint: "/audit-trail",
    method: "GET",
    hasToken: true,
  },
  LIST_DASHBOARD_CHECKINS: {
    endpoint: "/admin/dashboard/checkins",
    method: "GET",
    hasToken: true,
  },
  REQUEST_AUDIT_REPORT: {
    endpoint: "/audit-trail/reports",
    method: "POST",
    hasToken: true,
  },
  GET_AUDIT_REPORT: {
    endpoint: "/audit-trail/reports/:jobId",
    method: "GET",
    hasToken: true,
  },
  DOWNLOAD_AUDIT_REPORT: {
    endpoint: "/audit-trail/reports/:jobId/download",
    method: "GET",
    hasToken: true,
  },
  GET_ORGANISATION_CONFIG: {
    endpoint: "/company",
    method: "GET",
    hasToken: true,
  },
  UPDATE_ORGANISATION_CONFIG: {
    endpoint: "/company",
    method: "PUT",
    hasToken: true,
  },
  // Public for the pre-authentication visitor portal, same as LIST_EMPLOYEE_DIRECTORY —
  // the backend already serves this endpoint without auth.
  LIST_BRANCHES: {
    endpoint: "/branches",
    method: "GET",
    hasToken: false,
  },
  CREATE_BRANCH: {
    endpoint: "/branches",
    method: "POST",
    hasToken: true,
  },
  UPDATE_BRANCH: {
    endpoint: "/branches/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_BRANCH: {
    endpoint: "/branches/:id",
    method: "DELETE",
    hasToken: true,
  },
  // Public for the pre-authentication visitor portal, same as LIST_EMPLOYEE_DIRECTORY —
  // the backend already serves this endpoint without auth.
  LIST_DEPARTMENTS: {
    endpoint: "/departments",
    method: "GET",
    hasToken: false,
  },
  CREATE_DEPARTMENT: {
    endpoint: "/departments",
    method: "POST",
    hasToken: true,
  },
  UPDATE_DEPARTMENT: {
    endpoint: "/departments/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_DEPARTMENT: {
    endpoint: "/departments/:id",
    method: "DELETE",
    hasToken: true,
  },
  // Public for the pre-authentication visitor portal, same as LIST_EMPLOYEE_DIRECTORY —
  // the backend already serves this endpoint without auth.
  LIST_BUILDINGS: {
    endpoint: "/buildings",
    method: "GET",
    hasToken: false,
  },
  CREATE_BUILDING: {
    endpoint: "/buildings",
    method: "POST",
    hasToken: true,
  },
  UPDATE_BUILDING: {
    endpoint: "/buildings/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_BUILDING: {
    endpoint: "/buildings/:id",
    method: "DELETE",
    hasToken: true,
  },
  LIST_FLOORS: {
    endpoint: "/floors",
    method: "GET",
    hasToken: true,
  },
  CREATE_FLOOR: {
    endpoint: "/floors",
    method: "POST",
    hasToken: true,
  },
  UPDATE_FLOOR: {
    endpoint: "/floors/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_FLOOR: {
    endpoint: "/floors/:id",
    method: "DELETE",
    hasToken: true,
  },
  GET_ADMIN_DASHBOARD_OVERVIEW: {
    endpoint: "/admin/dashboard/overview",
    method: "GET",
    hasToken: true,
  },
  GET_MY_DASHBOARD_OVERVIEW: {
    endpoint: "/admin/dashboard/my-overview",
    method: "GET",
    hasToken: true,
  },
  GET_DASHBOARD_ANALYTICS: {
    endpoint: "/admin/dashboard/analytics",
    method: "GET",
    hasToken: true,
  },
  GET_MY_DASHBOARD_ANALYTICS: {
    endpoint: "/admin/dashboard/my-analytics",
    method: "GET",
    hasToken: true,
  },
  LIST_HOST_EMPLOYEES: {
    endpoint: "/auth/employees",
    method: "GET",
    hasToken: true,
  },
  // Public host-picker for the pre-authentication visitor portal — a
  // PII-trimmed projection (no email/phone/employeeCode) of LIST_HOST_EMPLOYEES.
  LIST_EMPLOYEE_DIRECTORY: {
    endpoint: "/auth/employees/directory",
    method: "GET",
    hasToken: false,
  },
  SYNC_EMPLOYEES: {
    endpoint: "/auth/employees/sync",
    method: "POST",
    hasToken: true,
  },
  LIST_ROLES: {
    endpoint: "/auth/roles",
    method: "GET",
    hasToken: true,
  },
  CREATE_ROLE: {
    endpoint: "/auth/roles",
    method: "POST",
    hasToken: true,
  },
  LIST_PERMISSIONS: {
    endpoint: "/auth/permissions",
    method: "GET",
    hasToken: true,
  },
  UPDATE_ROLE: {
    endpoint: "/auth/roles/:id",
    method: "PUT",
    hasToken: true,
  },
  RESYNC_ROLE_PERMISSIONS: {
    endpoint: "/auth/roles/resync-permissions",
    method: "POST",
    hasToken: true,
  },
  ASSIGN_HOST_EMPLOYEE_ROLE: {
    endpoint: "/auth/users/:userId/branch-roles",
    method: "POST",
    hasToken: true,
  },
  REVOKE_HOST_EMPLOYEE_ROLE: {
    endpoint: "/auth/users/:userId/branch-roles/:assignmentId",
    method: "DELETE",
    hasToken: true,
  },
  // Kiosks are company-wide: no X-Branch-ID header.
  LIST_KIOSKS: {
    endpoint: "/kiosks",
    method: "GET",
    hasToken: true,
  },
  GET_KIOSK: {
    endpoint: "/kiosks/:id",
    method: "GET",
    hasToken: true,
  },
  CREATE_KIOSK: {
    endpoint: "/kiosks",
    method: "POST",
    hasToken: true,
  },
  UPDATE_KIOSK: {
    endpoint: "/kiosks/:id",
    method: "PUT",
    hasToken: true,
  },
  SET_KIOSK_VISIBILITY: {
    endpoint: "/kiosks/:id/visibility",
    method: "PATCH",
    hasToken: true,
  },
  DELETE_KIOSK: {
    endpoint: "/kiosks/:id",
    method: "DELETE",
    hasToken: true,
  },
  // Registered kiosk / security devices. Reception Desks and Security Gates both
  // read LIST_DEVICES, differing only by the `operatingMode` filter.
  LIST_DEVICES: {
    endpoint: "/devices",
    method: "GET",
    hasToken: true,
  },
  APPROVE_DEVICE: {
    endpoint: "/devices/:id/approve",
    method: "POST",
    hasToken: true,
  },
  ENABLE_DEVICE: {
    endpoint: "/devices/:id/enable",
    method: "POST",
    hasToken: true,
  },
  DISABLE_DEVICE: {
    endpoint: "/devices/:id/disable",
    method: "POST",
    hasToken: true,
  },
  DELETE_DEVICE: {
    endpoint: "/devices/:id",
    method: "DELETE",
    hasToken: true,
  },
  GET_KIOSK_LOCATION_VALIDATION: {
    endpoint: "/admin/settings/kiosk-location-validation",
    method: "GET",
    hasToken: true,
  },
  UPDATE_KIOSK_LOCATION_VALIDATION: {
    endpoint: "/admin/settings/kiosk-location-validation",
    method: "PUT",
    hasToken: true,
  },
  // Public for the pre-authentication visitor portal, same as LIST_EMPLOYEE_DIRECTORY —
  // the backend already serves this endpoint without auth.
  LIST_VISITOR_CATEGORIES: {
    endpoint: "/visitor-categories",
    method: "GET",
    hasToken: false,
  },
  CREATE_VISITOR_CATEGORY: {
    endpoint: "/visitor-categories",
    method: "POST",
    hasToken: true,
  },
  BULK_CREATE_VISITOR_CATEGORIES: {
    endpoint: "/visitor-categories/bulk",
    method: "POST",
    hasToken: true,
  },
  UPDATE_VISITOR_CATEGORY: {
    endpoint: "/visitor-categories/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_VISITOR_CATEGORY: {
    endpoint: "/visitor-categories/:id",
    method: "DELETE",
    hasToken: true,
  },
  LIST_APPROVAL_WORKFLOW_RULES: {
    endpoint: "/approval-workflow-rules",
    method: "GET",
    hasToken: true,
  },
  CREATE_APPROVAL_WORKFLOW_RULE: {
    endpoint: "/approval-workflow-rules",
    method: "POST",
    hasToken: true,
  },
  UPDATE_APPROVAL_WORKFLOW_RULE: {
    endpoint: "/approval-workflow-rules/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_APPROVAL_WORKFLOW_RULE: {
    endpoint: "/approval-workflow-rules/:id",
    method: "DELETE",
    hasToken: true,
  },
  REGISTER_DEVICE: {
    endpoint: "/notifications/devices",
    method: "POST",
    hasToken: true,
  },
  UNREGISTER_DEVICE: {
    endpoint: "/notifications/devices/:fcmToken",
    method: "DELETE",
    hasToken: true,
  },
  LIST_NOTIFICATIONS: {
    endpoint: "/notifications",
    method: "GET",
    hasToken: true,
  },
  NOTIFICATIONS_UNREAD_COUNT: {
    endpoint: "/notifications/unread-count",
    method: "GET",
    hasToken: true,
  },
  MARK_NOTIFICATION_READ: {
    endpoint: "/notifications/:id/read",
    method: "PATCH",
    hasToken: true,
  },
  MARK_ALL_NOTIFICATIONS_READ: {
    endpoint: "/notifications/read-all",
    method: "POST",
    hasToken: true,
  },
  LIST_FORM_STEPS: {
    endpoint: "/form-builder/steps",
    method: "GET",
    hasToken: true,
  },
  CREATE_FORM_STEP: {
    endpoint: "/form-builder/steps",
    method: "POST",
    hasToken: true,
  },
  UPDATE_FORM_STEP: {
    endpoint: "/form-builder/steps/:id",
    method: "PATCH",
    hasToken: true,
  },
  DELETE_FORM_STEP: {
    endpoint: "/form-builder/steps/:id",
    method: "DELETE",
    hasToken: true,
  },
  REORDER_FORM_STEPS: {
    endpoint: "/form-builder/steps/reorder",
    method: "POST",
    hasToken: true,
  },
  LIST_FORM_FIELDS: {
    endpoint: "/form-builder/steps/:stepId/fields",
    method: "GET",
    hasToken: true,
  },
  CREATE_FORM_FIELD: {
    endpoint: "/form-builder/steps/:stepId/fields",
    method: "POST",
    hasToken: true,
  },
  UPDATE_FORM_FIELD: {
    endpoint: "/form-builder/fields/:id",
    method: "PATCH",
    hasToken: true,
  },
  DELETE_FORM_FIELD: {
    endpoint: "/form-builder/fields/:id",
    method: "DELETE",
    hasToken: true,
  },
  REORDER_FORM_FIELDS: {
    endpoint: "/form-builder/steps/:stepId/fields/reorder",
    method: "POST",
    hasToken: true,
  },
  LIST_FORM_FIELD_GROUPS: {
    endpoint: "/form-builder/steps/:stepId/groups",
    method: "GET",
    hasToken: true,
  },
  CREATE_FORM_FIELD_GROUP: {
    endpoint: "/form-builder/steps/:stepId/groups",
    method: "POST",
    hasToken: true,
  },
  UPDATE_FORM_FIELD_GROUP: {
    endpoint: "/form-builder/groups/:id",
    method: "PATCH",
    hasToken: true,
  },
  DELETE_FORM_FIELD_GROUP: {
    endpoint: "/form-builder/groups/:id",
    method: "DELETE",
    hasToken: true,
  },
  REORDER_FORM_FIELD_GROUPS: {
    endpoint: "/form-builder/steps/:stepId/groups/reorder",
    method: "POST",
    hasToken: true,
  },
  PUBLISH_FORM_CONFIG: {
    endpoint: "/form-builder/publish",
    method: "POST",
    hasToken: true,
  },
  GET_EFFECTIVE_FORM: {
    endpoint: "/form-builder/effective",
    method: "GET",
    hasToken: false,
  },
} as const

export type ApiEndpointDefinition = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]
