## ADDED Requirements

### Requirement: Staff and admin pages fit every supported device width
Every staff and admin page SHALL lay out without clipped or overflowing
content at each supported viewport width, in both the light and dark
themes. The supported widths are 320, 360, 390, 414, 768, 820, 1024, 1280,
1440 and 1920px.

At every supported width:
- the document SHALL have no horizontal scrollbar;
- the main content area SHALL NOT be wider than its visible width, so
  nothing is hidden by its overflow clipping;
- the top bar SHALL stay a single row.

Wide content (tables, the week board, the invitation board) SHALL scroll
inside its own container instead. Controls in a row (filters, actions,
setting toggles) SHALL wrap or stack rather than push past the edge.

#### Scenario: Organisation configs on a phone
- **WHEN** `/admin/organisation-configs` is viewed at 320px
- **THEN** each setting's title, description and toggle fit within the
  screen, with the toggle wrapping below the text if needed, and nothing is
  clipped

#### Scenario: Audit trail on a phone
- **WHEN** `/admin/audit-trail` is viewed at 390px
- **THEN** the activity filter, the CSV/PDF download buttons and the
  result rows fit within the screen or scroll inside their own container,
  and nothing is clipped

#### Scenario: Device matrix
- **WHEN** every staff and admin route is opened at each supported width
  in both themes
- **THEN** none shows a horizontal page scrollbar, clipped main content,
  or a wrapped top bar
