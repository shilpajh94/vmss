## ADDED Requirements

### Requirement: Page Sections Are Separated by the Standard Section Gap
Every page rendered inside the staff, reception or admin shell SHALL
separate its top-level sections by the standard page-section gap: 16px
below `md`, 24px from `md`. Sections are the page header, the toolbar or
filter row, and each card, board or table. This SHALL hold whether the
page's content is one root element or several sibling elements. No two
top-level sections SHALL touch.

#### Scenario: Admin dashboard cards are spaced
- **WHEN** the admin dashboard renders at 375px
- **THEN** the greeting card, the KPI cards, and the lists below them are
  each separated by 16px, with no two cards touching

#### Scenario: Visits board header, filters, and columns are spaced
- **WHEN** the Visits page renders at 1440px
- **THEN** there is a 24px gap between the page header and the
  search/filter row, and between that row and the status columns

#### Scenario: Create Branch title and form card are spaced
- **WHEN** the Create Branch page renders at any width
- **THEN** the title block and the form card are separated by the
  standard section gap

### Requirement: Page Headers Align With Their Content
A page header rendered inside the shell's padded content area SHALL NOT
add its own horizontal padding. Its left edge SHALL align with the left
edge of the cards and tables beneath it.

#### Scenario: Register Visitor header aligns with the form card
- **WHEN** the Register Visitor page renders at 1440px
- **THEN** the "Register Visitor" title and the registration card start at
  the same horizontal position

### Requirement: Table Status Is Never Hidden Under the Pinned Actions Column
Below `md`, a table's identifying column SHALL wrap its text instead of
forcing the table wider than the screen. The status cell SHALL stay on one
line. The pinned actions column SHALL be visually separated (a divider or
shadow) and SHALL NOT overlap the status cell when the table fits the
viewport.

#### Scenario: Branches table on a phone
- **WHEN** the Branches page renders at 375px with a branch named "QA Form
  Builder Branch"
- **THEN** the name wraps onto two lines, the full "STATUS" header and the
  status pill are visible, and the actions column sits beside them without
  covering them

### Requirement: Form Toggle Fields Align With Neighbouring Fields
A toggle presented as a form field SHALL render like other fields: its
label on top, with the switch and its state text on one row beneath it,
top-aligned with the fields beside it.

#### Scenario: Operational Status on Create Branch
- **WHEN** the Create Branch form renders at 1440px
- **THEN** the "Operational Status" label sits on the same line as the
  "Internal Administration Notes" label, and the switch and "Active /
  Open" text sit on one row beneath it

### Requirement: The Phone Top Bar Names the Current Page
Below `md`, the admin top bar SHALL show the current page's name (the
active breadcrumb item) rather than a generic, truncated product label. It
SHALL show the signed-in user's initials in the avatar.

#### Scenario: Admin top bar on the Branches page at phone width
- **WHEN** an admin opens Branches at 375px
- **THEN** the top bar reads "Branches" (not "Organizat…"), and the avatar
  shows the admin's initials
