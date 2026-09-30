# visitor-request-wizard Specification

## Purpose

The visitor-request-wizard capability lets a visitor submit everything a host organization needs to issue a visitor pass — who is visiting, why, what they're carrying, and what they consent to — across a guided multi-step form, and tells them whether it was accepted.

## Requirements

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

### Requirement: Wizard is reachable from the landing page's request entry point
The system SHALL render the visitor request wizard only after a visitor has successfully completed OTP verification (directly, or by activating "Start a new request" on the return-visit history screen), pre-filled with the registration type and contact captured during verification. When the verified visitor has a non-null prefill profile, the wizard SHALL also pre-fill that profile's full name, email, phone, preferred contact method, and ID-proof type for the primary contact. The wizard SHALL NOT render directly from the landing page's "Request Visit" action, and SHALL NOT pre-fill the ID-proof document image or profile photo from a prior visit.

#### Scenario: Visitor reaches the wizard from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page and successfully completes OTP verification
- **THEN** the first step of the visitor request wizard ("Visitor Info") renders, with registration type and the verified contact's mobile number or email already filled in

#### Scenario: Wizard does not render before verification
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders, and the visitor request wizard does not render until verification succeeds

#### Scenario: Returning visitor's wizard is pre-filled from their profile
- **WHEN** a returning visitor starts a new request from the return-visit history screen and their prefill profile is not null
- **THEN** the wizard's Visitor Info step renders with full name, email, phone, preferred contact method, and ID-proof type already filled in for the primary contact, while the ID-proof document image and profile photo remain unfilled and must be provided fresh

#### Scenario: First-time visitor's wizard has no profile prefill
- **WHEN** a visitor is verified and the history lookup's prefill profile is null
- **THEN** the wizard renders with only registration type and contact pre-filled, matching the wizard's existing first-time-visitor behavior

### Requirement: Visitor chooses between an individual and a group registration
The system SHALL let the visitor declare whether the request is for a single visitor or a group, and SHALL show the fields appropriate to that choice.

#### Scenario: Individual registration shows a single visitor's fields
- **WHEN** the visitor selects "Individual"
- **THEN** the form shows one set of fields for full name, email, phone, address, visitor category, preferred contact method, ID proof, and profile image

#### Scenario: Group registration shows a primary contact and a visitor list
- **WHEN** the visitor selects "Group"
- **THEN** the form shows primary contact fields plus a list of additional visitors, each addable with their own full name, email, phone, address, visitor category, ID proof, and profile image

#### Scenario: Group registration requires at least one visitor in the list
- **WHEN** the visitor attempts to proceed from a Group registration with zero visitors added to the list
- **THEN** the system blocks progression and indicates at least one visitor must be added

### Requirement: Visitor Info step requires core contact and address details
The system SHALL require full name, email, phone number, address, visitor category, and ID proof type before the Visitor Info step can be completed, for the individual visitor or for the primary contact and every added group visitor.

#### Scenario: Missing a required contact field blocks progression
- **WHEN** the visitor attempts to proceed without full name, email, phone, address, visitor category, or ID proof type filled in
- **THEN** the system blocks progression and indicates which fields are missing

### Requirement: ID proof and profile image can optionally be uploaded as supporting documents
The system SHALL let the visitor attach an image or PDF as ID proof, and separately an image as a profile photo, for themselves (individual) or for any visitor in the list (group). The system SHALL reject files that are not PNG, JPG, or PDF, or that exceed 5MB, for either upload.

#### Scenario: Valid ID document is accepted
- **WHEN** the visitor selects a PNG, JPG, or PDF file under 5MB as ID proof
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Valid profile image is accepted
- **WHEN** the visitor selects a PNG or JPG file under 5MB as a profile image
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Oversized or unsupported file is rejected
- **WHEN** the visitor selects a file over 5MB or with an unsupported type for either ID proof or profile image
- **THEN** the system rejects the file and explains why, without associating it with the visitor's entry

### Requirement: Visit Info step requires visit-planning details
The system SHALL require purpose of visit, host name or email, preferred visit date, preferred visit time, expected duration, location, building, and department to visit before the Visit Info step can be completed. Additional notes are optional.

#### Scenario: Missing a required visit-planning field blocks progression
- **WHEN** the visitor attempts to proceed without purpose, host, date, time, duration, location, building, or department filled in
- **THEN** the system blocks progression and indicates which fields are missing

### Requirement: Carried Items step declares security-relevant items without requiring any
The system SHALL let the visitor declare zero or more carried item categories, with an optional free-text description, and SHALL allow progression whether or not any category is selected, when the Carried Items step is present in the effective configuration. The set of available categories SHALL be taken from the step's configured fields; the system SHALL NOT fall back to a hardcoded default category list once the configuration has finished loading, even if that step's configured field list is genuinely empty.

#### Scenario: No items declared is a valid declaration
- **WHEN** the visitor proceeds from the Carried Items step with no category selected
- **THEN** the system allows progression, recording that no items were declared

### Requirement: Vehicle Info step records zero or more vehicles
The system SHALL let the visitor add zero or more vehicles, each requiring vehicle type, license plate, make/model, and color when added, and SHALL allow progression with an empty vehicle list.

#### Scenario: Adding a vehicle requires its details
- **WHEN** the visitor attempts to add a vehicle without vehicle type, license plate, make/model, or color filled in
- **THEN** the system blocks adding that vehicle and indicates which fields are missing

#### Scenario: No vehicles declared is valid
- **WHEN** the visitor proceeds from the Vehicle Info step with no vehicle added
- **THEN** the system allows progression

### Requirement: Consent Agreement step requires all three acknowledgements
The system SHALL require the visitor to check all three consent acknowledgements (terms & conditions, personal data use, safety guidelines) before the Consent Agreement step can be completed.

#### Scenario: Unchecked consent blocks progression
- **WHEN** the visitor attempts to proceed with any of the three consent checkboxes unchecked
- **THEN** the system blocks progression

### Requirement: Review step summarizes the request before submission
The system SHALL present a summary of every prior step's entered data on the final step, and SHALL only submit the request when the visitor explicitly confirms.

#### Scenario: Review shows entered data
- **WHEN** the visitor reaches the Review & Confirm step
- **THEN** the summary reflects the visitor info (including address, visitor category, and profile image), visit info (including location and building), carried items, vehicles, and consent state entered in the prior steps

#### Scenario: Visitor can return to an earlier step from review
- **WHEN** the visitor chooses to go back from the Review & Confirm step
- **THEN** the system returns to the previous step with all previously entered data intact

### Requirement: The primary contact's visitor category is submitted as the invitation's category
The system SHALL submit the primary contact's selected visitor category as the invitation-level visitor category, identified by that category's id, since the backend associates one visitor category with an invitation as a whole rather than per visitor.

#### Scenario: Submission includes the invitation's visitor category
- **WHEN** the visitor confirms submission
- **THEN** the submitted request includes the primary contact's selected visitor category's id as the invitation's visitor category

### Requirement: Submission reports success with a tracking reference
The system SHALL, on successful submission, show the visitor a confirmation containing a tracking reference for the request.

#### Scenario: Successful submission
- **WHEN** the visitor confirms submission and the request is accepted
- **THEN** the system shows a confirmation screen containing a tracking reference for the submitted request

### Requirement: Submission failure is reported without losing entered data
The system SHALL, when submission fails, show the visitor an error and SHALL preserve all entered data so the visitor can retry without re-entering it.

#### Scenario: Submission fails
- **WHEN** the visitor confirms submission and the request is rejected or the submission cannot be completed
- **THEN** the system shows an error message, remains on the Review & Confirm step, and retains all previously entered data for a retry

### Requirement: Returning visitor's primary contact full name is locked after prefill
The system SHALL render the primary contact's "Full Name" field as read-only for the remainder of the wizard whenever it was pre-filled from a returning visitor's profile (visitor-return-history's prefill), since the invitation-creation API silently discards any edit to that field for a contact it matches by email (or, when no email is submitted, by phone) against a prior invitation. This lock applies only to the primary contact; it SHALL NOT apply to a first-time visitor with no prefill profile, and SHALL NOT apply to any additional visitor added to a group registration.

#### Scenario: Returning primary contact's name field is read-only
- **WHEN** the wizard's initial data includes a pre-filled full name for the primary contact from a returning visitor's profile
- **THEN** the "Full Name" field for the primary contact renders read-only and does not accept edits

#### Scenario: First-time visitor's name field stays editable
- **WHEN** the visitor is verified with no prior visits and the history lookup's prefill profile is null
- **THEN** the primary contact's "Full Name" field renders as a normal editable field

#### Scenario: Additional group visitor's name field is never locked
- **WHEN** the primary contact's full name is locked because their profile was pre-filled
- **THEN** every additional visitor added to the group registration still has a normal editable "Full Name" field

### Requirement: Submission confirmation reflects the server's confirmed primary contact name
The system SHALL, after a successful submission (`POST /registrations/walk-in`), look up the invitation's public tracking record using the returned tracking reference and display that record's primary contact name on the confirmation screen as the confirmed name of record for the request, rather than assuming the value the wizard submitted was retained unchanged. A failure of that lookup SHALL NOT be treated as a submission failure — the confirmation screen still shows the tracking reference regardless.

#### Scenario: Confirmation shows the tracking record's confirmed name
- **WHEN** a visit request is submitted successfully and the subsequent tracking lookup succeeds
- **THEN** the confirmation screen displays the primary contact name from that lookup, alongside the tracking reference

#### Scenario: Confirmed-name lookup failure doesn't affect the confirmation
- **WHEN** a visit request is submitted successfully but the subsequent tracking lookup fails
- **THEN** the confirmation screen still shows the tracking reference, without the confirmed-name display and without showing an error

### Requirement: Step navigation adapts to narrow viewports
From 768px viewport width upward, the wizard SHALL show its step list as the existing side rail. Below 768px, it SHALL replace the rail with a compact progress header above the step content. The header SHALL show the current step's label, "Step X of N", and a progress bar. It SHALL list the same configured steps, in the same order, as the rail would, and SHALL let the visitor jump back to a completed step. Step content fields SHALL render in a single column below 640px. The Back/Next/Submit actions SHALL stay visible at the bottom of the viewport while the step content scrolls.

#### Scenario: Wizard on a phone
- **WHEN** a visitor opens the registration wizard at 375px wide on a branch configured with 4 steps
- **THEN** no side rail is shown, and a progress header reads "Step 1 of 4" with the current step's label, above single-column fields

#### Scenario: Returning to a completed step on a phone
- **WHEN** the visitor is on step 3 at 375px wide and opens the progress header's step list
- **THEN** steps 1 and 2 are selectable, and choosing one shows that step with its entered data intact

#### Scenario: Actions remain reachable
- **WHEN** a step's content is taller than the phone viewport
- **THEN** the Back/Next (or Submit) buttons stay visible while the fields scroll

### Requirement: The Wizard Renders a Published Configuration That Is Older Than the Client or Contains Unknown Field Types
The wizard SHALL render the published form configuration even when it
lacks keys added to the field or group shape after it was published, or
contains a field whose type the client doesn't support. A missing field
`hideLabel` SHALL be treated as `false`. A missing group
`visibilityCondition` SHALL be treated as absent (no condition). A field
of an unsupported type SHALL be omitted: it SHALL NOT render, SHALL NOT
affect the step count, and SHALL NOT be submitted. Every other field and
step SHALL render as configured. The "Something went wrong loading the
registration form" state SHALL be reserved for a failed request or a
response that isn't a form configuration at all.

#### Scenario: Old default form with a removed field type
- **WHEN** the effective configuration's fields lack `hideLabel`, its
  groups lack `visibilityCondition`, and one field has type
  `signature_pad`
- **THEN** the wizard shows its steps with "Step 1 of N" (N being the
  number of configured steps), every supported field renders with its
  label visible, and the `signature_pad` field is not shown

### Requirement: Wizard Fields Stack in One Column on Narrow Screens
Below the `sm` breakpoint (640px), every field of a wizard step SHALL
occupy the full width of the step's card, one field per row, whether or
not the step has admin-authored custom fields. No field SHALL be laid out
beside another at those widths. No label or input SHALL be narrowed below
the card's content width. From `sm` upward, the step's two-column layout
SHALL be unchanged, and admin-authored custom fields SHALL span the full
row.

#### Scenario: Visitor Info on a phone with a custom field
- **WHEN** the Visitor Info step renders at 375px wide and the published
  form includes an admin-authored field such as the "Terms & Conditions"
  consent checkbox
- **THEN** Full Name, Email Address, Phone Number, Visitor Category,
  Preferred Contact Method, ID Proof Type, Upload ID, Profile Image, and
  the custom field each render full-width, one per row, with their labels
  on a single line where they fit and their inputs showing the full
  placeholder

#### Scenario: Two columns from the sm breakpoint
- **WHEN** the same step renders at 768px wide
- **THEN** the system fields render two per row as before, and the custom
  fields section spans the whole row beneath them
