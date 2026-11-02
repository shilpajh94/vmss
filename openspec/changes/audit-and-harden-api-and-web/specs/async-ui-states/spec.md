## ADDED Requirements

### Requirement: Server Validation and Conflict Messages Reach the User
When a create, update or delete request fails with a 4xx response whose
envelope carries a human-readable message (for example a duplicate code
409, or a 422 naming the invalid field), the toast or inline error SHALL
show that message. A generic "Something went wrong" message SHALL be used
only when the response carries no usable message, or for network and 5xx
failures. Field-level errors SHALL be shown next to the field they name
when the form displays that field.

#### Scenario: Duplicate branch code
- **WHEN** an admin saves a branch whose code already exists and the API
  responds 409 with a message about the duplicate code
- **THEN** that message is shown, and the form keeps the entered values

#### Scenario: Server error without a message
- **WHEN** a save fails with a 500 response
- **THEN** a generic failure message is shown
