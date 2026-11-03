## Purpose

Defines the visitor badge card that reception prints for a checked-in visitor: its ID-card layout and its QR code, which replaces the barcode of the reference design and is scannable by the badge scan page.

## ADDED Requirements

### Requirement: Badge card layout
The system SHALL render the visitor badge as an ID card with a coloured header reading "VISITOR ID CARD", the visitor's photo, and labelled rows for Name, Purpose and Meet To, with a QR code in the footer area.

#### Scenario: Card shows visit details
- **WHEN** reception prints a badge for a visit with name "Smith Murphy", purpose "Meeting" and host "Brown Walsh"
- **THEN** the card shows those values beside the labels Name, Purpose and Meet To, with the visitor's photo and the header text

#### Scenario: Optional value missing
- **WHEN** the purpose or host is not available for the visit
- **THEN** the row still renders with a placeholder dash and the card is still printable

### Requirement: QR code replaces barcode
The system SHALL show a QR code, and no barcode, on the badge, encoding exactly the signed badge token issued by the backend for that print or reprint.

#### Scenario: QR encodes the issued token
- **WHEN** a badge is printed
- **THEN** scanning the QR yields the issued token, and the badge scan page accepts it for check-out or re-entry

#### Scenario: Reprint invalidates the old QR
- **WHEN** a badge is reprinted
- **THEN** the card shows the QR for the new token, and the earlier badge's QR is rejected by the scan page

### Requirement: Browser print output
The system SHALL print only the badge card, at a fixed ID-card size, from the browser print dialog, without page chrome.

#### Scenario: Print dialog
- **WHEN** reception confirms a print or reprint
- **THEN** the browser print dialog opens showing only the badge card

#### Scenario: Print rules unchanged
- **WHEN** the visit lacks verified ID, a photo or approval, or the reprint reason is missing
- **THEN** no badge card is shown or printed and the existing specific error or validation message is displayed

### Requirement: Token handling
The system SHALL NOT log or persist the badge token beyond the lifetime of the print action.

#### Scenario: Token not stored
- **WHEN** the print dialog closes
- **THEN** the token is no longer held in application state or browser storage
