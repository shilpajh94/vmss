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
  LIST_RECEPTION_DESKS: {
    endpoint: "/reception-desks",
    method: "GET",
    hasToken: true,
  },
  CREATE_RECEPTION_DESK: {
    endpoint: "/reception-desks",
    method: "POST",
    hasToken: true,
  },
  UPDATE_RECEPTION_DESK: {
    endpoint: "/reception-desks/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_RECEPTION_DESK: {
    endpoint: "/reception-desks/:id",
    method: "DELETE",
    hasToken: true,
  },
  LIST_SECURITY_GATES: {
    endpoint: "/security-gates",
    method: "GET",
    hasToken: true,
  },
  CREATE_SECURITY_GATE: {
    endpoint: "/security-gates",
    method: "POST",
    hasToken: true,
  },
  UPDATE_SECURITY_GATE: {
    endpoint: "/security-gates/:id",
    method: "PUT",
    hasToken: true,
  },
  DELETE_SECURITY_GATE: {
    endpoint: "/security-gates/:id",
    method: "DELETE",
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
} as const

export type ApiEndpointDefinition = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]
