# staff-visitor-registration Specification

## Purpose

The staff-visitor-registration capability lets an authenticated staff member register a visitor or a group of visitors on the organization's behalf through a guided multi-step wizard, then submits the request attributed to that staff member.

## Requirements

### Requirement: Wizard requires an authenticated staff session
The system SHALL check for a staff auth token before rendering the Register Visitor wizard, and SHALL redirect to `/staff/login` instead of rendering the wizard when no token is present.

#### Scenario: No token present
- **WHEN** a browser without a staff auth token navigates to the Register Visitor wizard
- **THEN** the system redirects to `/staff/login` and does not render the wizard

#### Scenario: Token present
- **WHEN** a browser with a staff auth token navigates to the Register Visitor wizard
- **THEN** the system renders the wizard's first step, "Visitor Info"

### Requirement: Wizard is reachable from the staff dashboard
The system SHALL render the Register Visitor wizard inside the staff shell (sidebar and workspace header matching the dashboard) when a staff member activates "My actions" from the dashboard sidebar.

#### Scenario: Staff opens the wizard from the dashboard
- **WHEN** an authenticated staff member activates "My actions" in the dashboard sidebar
- **THEN** the system renders the Register Visitor wizard's "Visitor Info" step inside the staff shell

### Requirement: A progress stepper shows the current step, reflecting the branch's published form-builder configuration
The system SHALL display a stepper listing the steps present in the branch's published effective form configuration, in that configuration's order, and SHALL visually mark which step is currently active. A step the configuration omits (deactivated by an admin, or never enabled for the branch) SHALL NOT appear in the stepper and SHALL NOT be reachable by navigation. A step present in the configuration whose key is not one of the wizard's built-in steps (Visitor Info, Visit Info, Carried Items, Vehicle Info, Consent Agreement, Review & Confirm) SHALL still render, using its configured fields, rather than being silently omitted. The stepper's total count and "Next"/"Back" transitions SHALL be computed from the number of steps actually present, not a fixed count of six.

#### Scenario: Stepper reflects current step
- **WHEN** the staff member is on any step of the wizard
- **THEN** the stepper shows the active step names from the effective configuration and highlights the current one

#### Scenario: Deactivated step is omitted from the stepper
- **WHEN** an admin deactivates the "Vehicle Info" step and publishes the change, and a staff member subsequently opens the Register Visitor wizard for that branch
- **THEN** the stepper does not list "Vehicle Info", and the wizard proceeds directly from "Carried Items" to "Consent Agreement"

#### Scenario: Deactivated step cannot be reached by navigation
- **WHEN** the effective configuration omits a step
- **THEN** no stepper entry, "Next" action, or direct navigation exposed by the wizard leads to that step's content

#### Scenario: Step order follows the published configuration
- **WHEN** the effective configuration lists active steps in an order different from the wizard's historical default order
- **THEN** the stepper and the step-to-step navigation follow the configuration's order

#### Scenario: A custom step in the configuration renders generically
- **WHEN** the effective configuration includes an active step whose key is not one of the six built-in steps
- **THEN** the wizard renders that step in the stepper at its configured position and presents its configured fields for input, instead of omitting it

#### Scenario: Progress indication matches an active step count smaller than the historical default
- **WHEN** the effective configuration has fewer active steps than the wizard's historical six
- **THEN** any step-count or progress indicator reflects the smaller, actual count

#### Scenario: Sidebar shows a loading state, not an empty or default step list
- **WHEN** a staff member opens the wizard before the effective configuration has finished loading
- **THEN** the stepper shows a loading indicator rather than an empty step list or the wizard's historical hardcoded default steps

### Requirement: Staff chooses between an individual and a group registration
The system SHALL let the staff member declare whether the registration is for a single visitor or a group, and SHALL show the fields appropriate to that choice on the Visitor Info step.

#### Scenario: Individual registration shows a single contact's fields
- **WHEN** the staff member selects "Individual"
- **THEN** the Visitor Info step shows one set of primary contact fields and no visitor list

#### Scenario: Group registration shows a primary contact and a visitor list
- **WHEN** the staff member selects "Group"
- **THEN** the Visitor Info step shows the primary contact fields plus a list of additional visitors, each addable with their own full name, email, phone, and ID proof type

#### Scenario: Group registration requires at least one visitor in the list
- **WHEN** the staff member attempts to proceed from a Group registration with zero visitors added to the list
- **THEN** the system blocks progression and indicates at least one visitor must be added

### Requirement: Primary contact details are required before proceeding
The system SHALL require full name, email address, phone number, and a visitor category for the primary contact, and SHALL require a preferred contact method (email or SMS) and an ID proof type, before the Visitor Info step can be completed.

#### Scenario: Missing a required primary contact field blocks progression
- **WHEN** the staff member attempts to proceed without full name, email, phone, visitor category, preferred contact method, or ID proof type filled in for the primary contact
- **THEN** the system blocks progression and indicates which fields are missing

### Requirement: The primary contact's visitor category is submitted as the invitation's category
The system SHALL submit the primary contact's selected visitor category as the invitation-level visitor category, identified by that category's id, since the backend associates one visitor category with an invitation as a whole rather than per visitor.

#### Scenario: Submission includes the invitation's visitor category
- **WHEN** the staff member submits the registration
- **THEN** the submitted request includes the primary contact's selected visitor category's id as the invitation's visitor category

### Requirement: ID proof can optionally be uploaded for each visitor
The system SHALL let the staff member attach an image or PDF as ID proof for the primary contact and for each additional visitor in a group registration. The system SHALL reject files that are not PNG, JPG, or PDF, or that exceed 5MB.

#### Scenario: Valid ID document is accepted
- **WHEN** the staff member selects a PNG, JPG, or PDF file under 5MB as ID proof for a visitor
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Oversized or unsupported file is rejected
- **WHEN** the staff member selects a file over 5MB or with an unsupported type as ID proof
- **THEN** the system rejects the file and explains why, without associating it with the visitor's entry

### Requirement: Added group visitors appear in an editable list
The system SHALL show every visitor added to a group registration in a list displaying each visitor's position, full name, email or phone, and ID proof type, with actions to edit or remove that visitor.

#### Scenario: Added visitor appears in the list
- **WHEN** the staff member submits the "Add to List" form with valid visitor details
- **THEN** the new visitor appears as a new row in the visitor list and the add-visitor form is cleared

#### Scenario: Visitor is removed from the list
- **WHEN** the staff member removes a visitor from the list
- **THEN** that visitor no longer appears in the list or in the submitted registration

### Requirement: Later steps apply the same rules as the self-service wizard
The system SHALL require the same fields and validation for the Visit Info, Carried Items, Vehicle Info, and Consent Agreement steps as the visitor-request-wizard capability defines for its equivalent steps. For the Carried Items step, the set of available categories SHALL be taken from the step's configured fields, consistent with the visitor-request-wizard capability, and the system SHALL NOT fall back to a hardcoded default category list once the configuration has finished loading, even if that step's configured field list is genuinely empty.

#### Scenario: Missing a required later-step field blocks progression
- **WHEN** the staff member attempts to proceed from Visit Info, Vehicle Info, or Consent Agreement without that step's required fields completed
- **THEN** the system blocks progression and indicates which fields are missing, consistent with the visitor-request-wizard capability's rules

#### Scenario: Carried Items step allows zero items
- **WHEN** the staff member proceeds from the Carried Items step with no category selected
- **THEN** the system allows progression, recording that no items were declared

### Requirement: Review step summarizes the request before submission
The system SHALL present a summary of every prior step's entered data — registration type, primary contact and any additional visitors, visit info, carried items, vehicles, and consent state — on the Review & Confirm step, and SHALL only submit the request when the staff member explicitly confirms.

#### Scenario: Review shows entered data
- **WHEN** the staff member reaches the Review & Confirm step
- **THEN** the summary reflects the registration type, all visitor entries, visit info, carried items, vehicles, and consent state entered in the prior steps

#### Scenario: Staff can return to an earlier step from review
- **WHEN** the staff member chooses to go back from the Review & Confirm step
- **THEN** the system returns to the previous step with all previously entered data intact

### Requirement: Submission is attributed to the authenticated staff member
The system SHALL submit a staff-initiated registration through an authenticated request so the resulting visit request records which staff member created it.

#### Scenario: Successful submission
- **WHEN** the staff member confirms submission and the request is accepted
- **THEN** the system shows a confirmation containing a tracking reference, and the created visit request is attributed to the submitting staff member

#### Scenario: Submission failure is reported without losing entered data
- **WHEN** the staff member confirms submission and the request is rejected or cannot be completed
- **THEN** the system shows an error message, remains on the Review & Confirm step, and retains all previously entered data for a retry

### Requirement: Submission outcome also triggers a notification
The system SHALL, in addition to the existing confirmation or inline error, trigger a success notification when a staff-initiated registration is submitted successfully, and an error notification when submission fails.

#### Scenario: Successful submission
- **WHEN** the staff member confirms submission and the request is accepted
- **THEN** the system shows the confirmation with a tracking reference and also triggers a success notification

#### Scenario: Submission failure
- **WHEN** the staff member confirms submission and the request is rejected or cannot be completed
- **THEN** the system shows the inline error message on the Review & Confirm step and also triggers an error notification

### Requirement: Staff can cancel the wizard
The system SHALL, when the staff member activates "Cancel" from the wizard, discard any unsaved entries and return to the staff dashboard without submitting a request.

#### Scenario: Staff cancels registration
- **WHEN** the staff member activates "Cancel" on any step of the wizard
- **THEN** the system returns to the staff dashboard and no visit request is submitted

### Requirement: Every step in the progress stepper stays visible and reachable regardless of viewport width or zoom level
The stepper SHALL keep every active step (however many the branch's
published form configuration includes) visible and directly reachable at
any browser zoom level or viewport width, without relying on an
undiscoverable horizontal scroll as the only way to reach a step past the
visible edge. If the stepper cannot fit every step on one row at the
current width, it SHALL either wrap steps onto additional rows, switch to
a more compact per-step presentation, or provide a visible scroll
affordance (not a bare, easy-to-miss scrollbar) indicating more steps exist
off-screen.

#### Scenario: A branch with many steps stays fully visible at reduced zoom
- **WHEN** a branch's published form configuration has enough active steps
  that their combined width would exceed a fixed-width row at the current
  browser zoom level
- **THEN** every step remains visible (via wrapping, a compact
  presentation, or a discoverable scroll affordance) rather than being
  clipped behind an unindicated horizontal scroll

#### Scenario: All steps remain individually reachable
- **WHEN** the wizard renders at any viewport width or browser zoom level
- **THEN** the user can navigate to any active step via the stepper without
  needing to guess that off-screen content exists

### Requirement: Submission confirmation reflects the server's confirmed primary contact name
The system SHALL, after a successful submission (`POST /invitations`), look up the invitation's public tracking record using the returned tracking reference and display that record's primary contact name on the confirmation screen as the confirmed name of record for the request. A failure of that lookup SHALL NOT be treated as a submission failure — the confirmation screen still shows the tracking reference regardless. This wizard has no pre-submit lookup to detect whether the typed primary contact matches a prior invitation, so this confirmed-name display is the only place the staff member can see that the backend silently overwrote the typed name with the name on file for a matched contact.

#### Scenario: Confirmed name differs from what staff typed
- **WHEN** the staff member submits a primary contact whose email (or, when no email is submitted, phone) matches a prior invitation under a different name, the request is accepted, and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen shows the primary contact name from that lookup, which may differ from the name the staff member typed

#### Scenario: Confirmed name matches a first-time contact
- **WHEN** the staff member submits a primary contact that matches no prior invitation, the request is accepted, and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen shows the primary contact name from that lookup, matching what the staff member typed

### Requirement: Staff Registration Renders a Published Configuration That Is Older Than the Client or Contains Unknown Field Types
The staff Register Visitor form SHALL render the published form
configuration even when it lacks keys added after it was published, or
contains a field whose type the client doesn't support. Missing keys
SHALL take their defaults: a field's `hideLabel` is `false`, and a
group's `visibilityCondition` is absent. A field of an unsupported type
SHALL be omitted from rendering, the step count and the submission.
Every other field and step SHALL render as configured.

#### Scenario: Register Visitor with an old default form
- **WHEN** a staff user opens Register Visitor and the effective
  configuration lacks `hideLabel` and `visibilityCondition` keys and
  contains a `signature_pad` field
- **THEN** the stepper lists the configured steps, the visitor-info step
  renders its supported fields, and no load error is shown
