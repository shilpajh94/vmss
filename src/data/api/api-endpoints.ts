export const API_ENDPOINTS = {
  CREATE_VISIT_REQUEST: {
    endpoint: "/visit-requests",
    method: "POST",
    hasToken: false,
  },
  UPLOAD_VISITOR_DOCUMENT: {
    endpoint: "/uploads/visitor-documents",
    method: "POST",
    hasToken: false,
  },
  TRACK_VISIT_REQUEST: {
    endpoint: "/visit-requests/track",
    method: "GET",
    hasToken: false,
  },
  REQUEST_VISITOR_OTP: {
    endpoint: "/visitor-otp/request",
    method: "POST",
    hasToken: false,
  },
  VERIFY_VISITOR_OTP: {
    endpoint: "/visitor-otp/verify",
    method: "POST",
    hasToken: false,
  },
  INITIATE_STAFF_SSO: {
    endpoint: "/staff-auth/sso/initiate",
    method: "POST",
    hasToken: false,
  },
  LIST_VISIT_REQUESTS: {
    endpoint: "/visit-requests",
    method: "GET",
    hasToken: true,
  },
  GET_CURRENT_STAFF_USER: {
    endpoint: "/staff-auth/me",
    method: "GET",
    hasToken: true,
  },
  STAFF_CREATE_VISIT_REQUEST: {
    endpoint: "/staff/visit-requests",
    method: "POST",
    hasToken: true,
  },
  LIST_AUDIT_TRAIL: {
    endpoint: "/staff/audit-trail",
    method: "GET",
    hasToken: true,
  },
  GET_ORGANISATION_CONFIG: {
    endpoint: "/organisation-config",
    method: "GET",
    hasToken: true,
  },
  UPDATE_ORGANISATION_CONFIG: {
    endpoint: "/organisation-config",
    method: "PUT",
    hasToken: true,
  },
  UPLOAD_ORGANISATION_LOGO: {
    endpoint: "/uploads/organisation-logo",
    method: "POST",
    hasToken: true,
  },
  LIST_BRANCHES: {
    endpoint: "/branches",
    method: "GET",
    hasToken: true,
  },
  CREATE_BRANCH: {
    endpoint: "/branches",
    method: "POST",
    hasToken: true,
  },
  UPDATE_BRANCH: {
    endpoint: "/branches",
    method: "PUT",
    hasToken: true,
  },
  DELETE_BRANCH: {
    endpoint: "/branches",
    method: "DELETE",
    hasToken: true,
  },
  LIST_DEPARTMENTS: {
    endpoint: "/departments",
    method: "GET",
    hasToken: true,
  },
  CREATE_DEPARTMENT: {
    endpoint: "/departments",
    method: "POST",
    hasToken: true,
  },
  UPDATE_DEPARTMENT: {
    endpoint: "/departments",
    method: "PUT",
    hasToken: true,
  },
  DELETE_DEPARTMENT: {
    endpoint: "/departments",
    method: "DELETE",
    hasToken: true,
  },
  LIST_BUILDINGS: {
    endpoint: "/buildings",
    method: "GET",
    hasToken: true,
  },
  CREATE_BUILDING: {
    endpoint: "/buildings",
    method: "POST",
    hasToken: true,
  },
  UPDATE_BUILDING: {
    endpoint: "/buildings",
    method: "PUT",
    hasToken: true,
  },
  DELETE_BUILDING: {
    endpoint: "/buildings",
    method: "DELETE",
    hasToken: true,
  },
} as const

export type ApiEndpointDefinition = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]
