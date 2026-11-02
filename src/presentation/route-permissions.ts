// The permission each admin and staff page requires (design D-W1), keyed by
// page, so the route table in App.tsx (`requires`) and the sidebars that
// hide entries a user can't open read the same code. Each matches what the
// page's main API endpoint enforces.
export const PAGE_PERMISSIONS = {
  adminDashboard: 'invitations:view-all',
  organisationConfigs: 'companies:manage',
  branches: 'branches:manage',
  departments: 'departments:manage',
  buildings: 'buildings:manage',
  floors: 'floors:manage',
  hostEmployees: 'employees:manage',
  receptionDesks: 'desks:manage',
  securityGates: 'gates:manage',
  kiosks: 'kiosks:manage',
  visitorCategories: 'visitor-categories:manage',
  workflows: 'approval-workflow-rules:manage',
  adminInvitations: 'invitations:view-all',
  calendar: 'invitations:view',
  roles: 'roles:manage',
  formBuilder: 'form-builder:manage',
  auditTrail: 'audit-logs:view',
  staffInvitations: 'invitations:view',
  registerVisitor: 'invitations:create',
} as const
