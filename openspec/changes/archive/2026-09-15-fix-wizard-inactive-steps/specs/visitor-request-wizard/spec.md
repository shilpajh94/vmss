## ADDED Requirements

### Requirement: Registration steps reflect the branch's published form-builder configuration
The system SHALL derive the wizard's step list — which steps exist, their order, and their labels — from the branch's published effective form configuration, rather than from a fixed, always-present set of steps. A step the configuration omits (deactivated by an admin, or never enabled for the branch) SHALL NOT appear in the step sidebar and SHALL NOT be reachable by navigation. A step present in the configuration whose key is not one of the wizard's built-in steps (Visitor Info, Visit Info, Carried Items, Vehicle Info, Consent Agreement, Review & Confirm) SHALL still render, using its configured fields, rather than being silently omitted.

#### Scenario: Deactivated step is omitted from the sidebar
- **WHEN** an admin deactivates the "Vehicle Info" step and publishes the change, and a visitor subsequently opens the request wizard for that branch
- **THEN** the step sidebar does not list "Vehicle Info", and the wizard proceeds directly from "Carried Items" to "Consent Agreement"

#### Scenario: Deactivated step cannot be reached by navigation
- **WHEN** the effective configuration omits a step
- **THEN** no sidebar entry, "Next" action, or direct navigation exposed by the wizard leads to that step's content

#### Scenario: Step order follows the published configuration
- **WHEN** the effective configuration lists active steps in an order different from the wizard's historical default order
- **THEN** the sidebar and the step-to-step navigation follow the configuration's order

#### Scenario: A custom step in the configuration renders generically
- **WHEN** the effective configuration includes an active step whose key is not one of the six built-in steps
- **THEN** the wizard renders that step in the sidebar at its configured position and presents its configured fields for input, instead of omitting it

#### Scenario: Reactivating a step restores it
- **WHEN** an admin reactivates a previously deactivated step and publishes the change
- **THEN** the step reappears in the sidebar at its configured position for wizard sessions started after the publish

### Requirement: Step count and progress reflect only the steps present in the configuration
The system SHALL compute the wizard's total step count, current-step position, and "Next"/"Back" transitions from the number of steps actually present in the effective configuration, not from a fixed count.

#### Scenario: Progress indication matches an active step count smaller than the historical default
- **WHEN** the effective configuration has fewer active steps than the wizard's historical six
- **THEN** any step-count or progress indicator (e.g. "Step 2 of 4") reflects the smaller, actual count

### Requirement: Wizard shows a loading state while the effective configuration is being fetched
The system SHALL distinguish "the effective form configuration has not finished loading yet" from "the configuration loaded and a step's field list is genuinely empty," and SHALL NOT render a step list or step content that assumes the latter while the former is still true.

#### Scenario: Sidebar shows a loading state, not an empty or default step list
- **WHEN** the visitor opens the wizard before the effective configuration has finished loading
- **THEN** the sidebar shows a loading indicator rather than an empty step list or the wizard's historical hardcoded default steps

## MODIFIED Requirements

### Requirement: Carried Items step declares security-relevant items without requiring any
The system SHALL let the visitor declare zero or more carried item categories, with an optional free-text description, and SHALL allow progression whether or not any category is selected, when the Carried Items step is present in the effective configuration. The set of available categories SHALL be taken from the step's configured fields; the system SHALL NOT fall back to a hardcoded default category list once the configuration has finished loading, even if that step's configured field list is genuinely empty.

#### Scenario: No items declared is a valid declaration
- **WHEN** the visitor proceeds from the Carried Items step with no category selected
- **THEN** the system allows progression, recording that no items were declared
