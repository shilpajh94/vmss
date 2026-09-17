## MODIFIED Requirements

### Requirement: Wizard is reachable from the landing page's request entry point
The system SHALL render the visitor request wizard only after a visitor has successfully completed OTP verification (directly, or by activating "Start a new request" on the return-visit history screen), pre-filled with the registration type and contact captured during verification. When the verified visitor has a non-null prefill profile, the wizard SHALL also pre-fill that profile's full name, email, phone, preferred contact method, and ID-proof type for the primary contact, and SHALL make the profile's ID-proof document image and profile photo, when present, available for reuse as described in "ID proof and profile image can optionally be uploaded as supporting documents". The wizard SHALL NOT render directly from the landing page's "Request Visit" action.

#### Scenario: Visitor reaches the wizard from the landing page
- **WHEN** a visitor activates "Request Visit" on the landing page and successfully completes OTP verification
- **THEN** the first step of the visitor request wizard ("Visitor Info") renders, with registration type and the verified contact's mobile number or email already filled in

#### Scenario: Wizard does not render before verification
- **WHEN** a visitor activates "Request Visit" on the landing page
- **THEN** the OTP-request screen renders, and the visitor request wizard does not render until verification succeeds

#### Scenario: Returning visitor's wizard is pre-filled from their profile
- **WHEN** a returning visitor starts a new request from the return-visit history screen and their prefill profile is not null
- **THEN** the wizard's Visitor Info step renders with full name, email, phone, preferred contact method, and ID-proof type already filled in for the primary contact, and with the primary contact's ID-proof document image and profile photo available for reuse wherever the prefill profile includes them

#### Scenario: First-time visitor's wizard has no profile prefill
- **WHEN** a visitor is verified and the history lookup's prefill profile is null
- **THEN** the wizard renders with only registration type and contact pre-filled, matching the wizard's existing first-time-visitor behavior

### Requirement: ID proof and profile image can optionally be uploaded as supporting documents
The system SHALL let the visitor attach an image or PDF as ID proof, and separately an image as a profile photo, for themselves (individual) or for any visitor in the list (group). The system SHALL reject files that are not PNG, JPG, or PDF, or that exceed 5MB, for either upload.

For the primary contact only, when the wizard's initial data includes an existing ID-proof document image URL and/or profile photo URL from a returning visitor's prefill profile, the system SHALL present that existing file (as a thumbnail or document preview) with a choice to keep it or replace it, instead of an empty upload control. Keeping the existing file SHALL satisfy that field's upload requirement without the visitor selecting a new file. Choosing to replace it SHALL revert that field to the normal fresh-upload control, subject to the same PNG/JPG/PDF and 5MB constraints. This existing-file choice applies only to the primary contact; additional group visitors and first-time visitors (no prefill profile, or a prefill profile without that URL) always see the normal fresh-upload control.

#### Scenario: Valid ID document is accepted
- **WHEN** the visitor selects a PNG, JPG, or PDF file under 5MB as ID proof
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Valid profile image is accepted
- **WHEN** the visitor selects a PNG or JPG file under 5MB as a profile image
- **THEN** the system accepts the file and associates it with that visitor's entry

#### Scenario: Oversized or unsupported file is rejected
- **WHEN** the visitor selects a file over 5MB or with an unsupported type for either ID proof or profile image
- **THEN** the system rejects the file and explains why, without associating it with the visitor's entry

#### Scenario: Returning visitor's primary contact sees an existing-file preview
- **WHEN** the primary contact's prefill profile includes an ID-proof document image URL or a profile photo URL
- **THEN** the corresponding field renders a preview of that existing file with "Keep existing" and "Replace" actions instead of an empty upload control

#### Scenario: Visitor keeps the existing file
- **WHEN** the visitor takes no action, or explicitly chooses "Keep existing", on a field showing an existing-file preview
- **THEN** the system treats that field's upload requirement as satisfied using the existing file, without requiring a new selection, and submits that same file's content with the request

#### Scenario: Visitor replaces the existing file
- **WHEN** the visitor chooses "Replace" on a field showing an existing-file preview
- **THEN** the field reverts to the normal fresh-upload control, and the visitor must select a new PNG/JPG/PDF file under 5MB to satisfy that field's upload requirement

#### Scenario: Additional group visitor never sees an existing-file preview
- **WHEN** the visitor adds an additional visitor to a group registration
- **THEN** that visitor's ID-proof field always renders the normal fresh-upload control, regardless of the primary contact's prefill profile
