## ADDED Requirements

### Requirement: Visitor Category and Approval Workflow Rule Lists Support Typed Attribute Filters
`GET /visitor-categories` SHALL accept optional, whitelisted query filters
`badgeColor` (exact match against `VisitorCategory.badge_color`),
`ndaRequirement` (`digital`/`signed_pdf`/`optional`/`none`, matching
`VisitorCategory.nda_requirement`), and `escortRequirement`
(`self_escort`/`access_logs_only`/`always_required`/`gate_check_in_only`,
matching `VisitorCategory.escort_requirement`), each applying no filter
when omitted. `GET /approval-workflow-rules` SHALL accept an optional
`status` filter (`active`/`inactive`, mapped onto
`ApprovalWorkflowRule.is_active`), combinable with its existing
`visitorCategoryId` filter (AND semantics). An unrecognized `ndaRequirement`
or `escortRequirement` value SHALL be rejected with 422, not silently
ignored.

#### Scenario: Filtering visitor categories by badge color
- **WHEN** a caller requests `GET /visitor-categories?badgeColor=amber`
- **THEN** only visitor categories whose `badge_color` is exactly `amber`
  are returned

#### Scenario: Filtering visitor categories by NDA and escort requirement
- **WHEN** a caller requests
  `GET /visitor-categories?ndaRequirement=signed_pdf&escortRequirement=always_required`
- **THEN** only visitor categories matching both fields are returned

#### Scenario: Filtering approval workflow rules by status
- **WHEN** a caller requests `GET /approval-workflow-rules?status=inactive`
- **THEN** only rules with `is_active=false` are returned

#### Scenario: Status filter combines with the existing category filter
- **WHEN** a caller requests
  `GET /approval-workflow-rules?visitorCategoryId=<id>&status=active`
- **THEN** only active rules belonging to that visitor category are returned

#### Scenario: Unrecognized filter value is rejected
- **WHEN** a caller requests `GET /visitor-categories` with `ndaRequirement`
  or `escortRequirement` set to a value outside its whitelisted enum
- **THEN** the request is rejected with 422 and no filtering is applied
