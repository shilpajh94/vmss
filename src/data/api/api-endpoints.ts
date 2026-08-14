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
} as const

export type ApiEndpointDefinition = (typeof API_ENDPOINTS)[keyof typeof API_ENDPOINTS]
