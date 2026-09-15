## MODIFIED Requirements

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

### Requirement: Later steps apply the same rules as the self-service wizard
The system SHALL require the same fields and validation for the Visit Info, Carried Items, Vehicle Info, and Consent Agreement steps as the visitor-request-wizard capability defines for its equivalent steps. For the Carried Items step, the set of available categories SHALL be taken from the step's configured fields, consistent with the visitor-request-wizard capability, and the system SHALL NOT fall back to a hardcoded default category list once the configuration has finished loading, even if that step's configured field list is genuinely empty.

#### Scenario: Missing a required later-step field blocks progression
- **WHEN** the staff member attempts to proceed from Visit Info, Vehicle Info, or Consent Agreement without that step's required fields completed
- **THEN** the system blocks progression and indicates which fields are missing, consistent with the visitor-request-wizard capability's rules

#### Scenario: Carried Items step allows zero items
- **WHEN** the staff member proceeds from the Carried Items step with no category selected
- **THEN** the system allows progression, recording that no items were declared
