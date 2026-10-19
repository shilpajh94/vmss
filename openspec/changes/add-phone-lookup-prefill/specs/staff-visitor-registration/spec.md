## ADDED Requirements

### Requirement: Primary contact is prefilled from a phone lookup
The system SHALL, when the staff member has entered a primary contact phone number containing at least 7 digits, look up the most recent matching visitor via `GET /invitations/lookup-by-phone` (sending the phone as typed) and prefill the primary contact from the result. The lookup SHALL be debounced and SHALL NOT be issued on every keystroke, SHALL NOT be re-issued for an unchanged phone value, and SHALL be skipped while the phone has fewer than 7 digits or more than 50 characters. A response is applied only if the phone value it was issued for is still the current one.

#### Scenario: Known phone prefills the form
- **WHEN** the staff member enters a phone with at least 7 digits that matches a prior visitor
- **THEN** full name, email, preferred contact method, visitor category, ID proof type and photo from the match are filled into the primary contact fields that are still empty, and the staff member is told an existing visitor was found

#### Scenario: Short phone does not trigger a lookup
- **WHEN** the phone field contains fewer than 7 digits
- **THEN** no lookup request is sent

#### Scenario: No match leaves the form untouched
- **WHEN** the lookup returns `data: null`
- **THEN** the form is unchanged and no error is shown

#### Scenario: Lookup failure leaves the form untouched
- **WHEN** the lookup fails (including a 422 or network error)
- **THEN** the form is unchanged and no error is shown

#### Scenario: Phone-only prior registration
- **WHEN** the match has a null email
- **THEN** the email field is left as it was and the other matched fields are still prefilled

#### Scenario: ID proof document not returned
- **WHEN** the match has a null `idProofUrl`
- **THEN** no ID proof file is prefilled and the upload control stays empty

### Requirement: Lookup prefill never overwrites staff-entered values
The system SHALL apply a lookup match (by phone or by email) only to primary contact fields that are currently empty, and SHALL NOT replace a value the staff member has already entered or a previously prefilled file.

#### Scenario: Typed name is preserved
- **WHEN** the staff member has typed a full name and then a lookup returns a different name
- **THEN** the typed full name is kept and only the still-empty fields are filled

#### Scenario: Typed email is preserved by phone lookup
- **WHEN** the staff member has entered an email and a phone lookup returns a different email
- **THEN** the entered email is kept
