## ADDED Requirements

### Requirement: Staff Lifecycle Update Email Carries Event-Specific Content
The system SHALL render a "Staff lifecycle update" notification type for
the responsible staff of an invitation that was denied, had its approval
reverted, or was rescheduled. It SHALL follow every general rule in "Each
Notification Type Carries Accurate, Type-Specific Content":

- absent rows are omitted;
- the copy names the actual visitor, tracking ID and actor;
- the subject line equals the heading.

It SHALL use the same branded template, plain-text fallback and greeting
rules as every other notification type. Each event SHALL render as follows:

| Event | Tone | Pill | Heading | Sections, in order |
|---|---|---|---|---|
| Denied | danger (red) | Visit denied | {Visitor}'s visit request was denied | Lead naming the visitor and who denied it; red "Reason given" callout; Visit details plus visitor name; portal next step quoting the tracking ID |
| Approval reverted | pending (amber) | Approval withdrawn | Approval withdrawn for {Visitor}'s visit | Lead naming the visitor and who withdrew it; amber "Reason given" callout; note that the visitor's pass will not admit them until the request is approved again; Visit details plus visitor name; portal next step quoting the tracking ID |
| Rescheduled | info (blue) | Rescheduled | {Visitor}'s visit has been rescheduled | Lead naming the visitor and who rescheduled it; Visit details (showing the new date and time) plus visitor name; note that the visit is back awaiting approval when its status is `submitted`; portal next step quoting the tracking ID |

"Who did it" SHALL be the acting staff member's full name. It SHALL be
"a staff member" when that account no longer exists by the time the email
is sent, and SHALL never be a raw user id. The staff email
SHALL NOT include the visitor's identity-document number, photo or QR pass.
The visitor's phone and email SHALL be included as detail rows when present,
as they are in the point-of-contact email.

#### Scenario: Staff revert email shows the internal reason
- **WHEN** a staff lifecycle email is rendered for an approval revert of
  visitor "Meera Krishnan", reverted by "Anil Kumar" with reason "Host on
  leave that day"
- **THEN** the pill reads "Approval withdrawn" in the amber tone, the lead
  names Meera Krishnan and Anil Kumar, and an amber "Reason given" callout
  reads "Host on leave that day"

#### Scenario: Staff denial email renders in the red theme
- **WHEN** a staff lifecycle email is rendered for a denial with reason
  "Visitor not on the expected list"
- **THEN** its pill reads "Visit denied" in the danger tone and the reason
  appears in a red "Reason given" callout

#### Scenario: Staff reschedule email shows the new date
- **WHEN** a staff lifecycle email is rendered for an invitation
  rescheduled to 2026-10-22 at 14:00
- **THEN** the date-and-time row reads "Thu, 22 Oct 2026 · 2:00 PM"

#### Scenario: Staff email never carries the QR pass
- **WHEN** a staff lifecycle email is rendered for an approved invitation
  that has an issued QR pass
- **THEN** the email contains no QR image and no QR pass block

#### Scenario: Subject matches heading
- **WHEN** a staff lifecycle email is rendered for any of the three events
- **THEN** its subject line equals its rendered heading text
