## Purpose

Defines the viewport range every page of the web portal must support, and
how shared layout patterns adapt across phone, tablet, and desktop widths.
The patterns covered are page containers, form grids, data tables, kanban
boards, modals, headers/filters, and touch controls.

## ADDED Requirements

### Requirement: Every Page Is Usable From 360px Wide Upward
The system SHALL render every route, public, staff, reception, and admin,
fully usable at any viewport width from 360px upward, in both portrait
and landscape. Fully usable means all content can be read, and every
control and navigation item can be reached and operated, with no
horizontal scroll of the outer page. Layout SHALL adapt at these
breakpoints:
- phone: below 640px;
- `sm`: 640px and up;
- `md` (tablet): 768px and up;
- `lg` (desktop): 1024px and up.

At `lg` and wider, each page SHALL keep its current desktop layout.

#### Scenario: Phone portrait
- **WHEN** any page is opened at 360×740
- **THEN** no content is clipped or overlaps, all actions are reachable,
  and the document has no horizontal scrollbar

#### Scenario: Tablet
- **WHEN** any page is opened at 768×1024 or 1024×768
- **THEN** the page uses the tablet layout defined by the rules below, with
  no horizontal page scroll

#### Scenario: Desktop unchanged
- **WHEN** any page is opened at 1440×900
- **THEN** it renders with the same layout as before this change

### Requirement: Page Containers and Form Grids Are Fluid
Page content containers SHALL NOT use fixed pixel widths that exceed the
viewport. They SHALL fill the available width, up to their current
desktop width as a maximum. Page padding SHALL shrink on smaller screens:
16px on phone, 24px on tablet, 32px on desktop. Multi-column form grids
SHALL render one column on phone, at most two columns from `md`, and
their full desktop column count from `lg`.

#### Scenario: Admin create/edit form on a phone
- **WHEN** an admin opens any create/edit form (branch, building, floor,
  department, desk, gate, kiosk, employee, visitor category, workflow,
  role) at 375px wide
- **THEN** the form fills the width with 16px side padding, its fields
  stack in one column, and its Save/Cancel actions are visible without
  horizontal scrolling

#### Scenario: Form grid on a tablet
- **WHEN** a form with a 3- or 4-column desktop grid is viewed at 800px
  wide
- **THEN** its fields render in at most two columns

### Requirement: Page Headers, Actions, and Filters Wrap Instead of Overflowing
A page's title row, primary/secondary action buttons, search box, and
filter dropdowns SHALL wrap or stack onto multiple rows when the viewport
is too narrow to hold them on one line. On phone, the search box and
each filter SHALL take the full width. Breadcrumbs and long titles SHALL
truncate with an ellipsis rather than push content off-screen.

#### Scenario: List page toolbar on a phone
- **WHEN** a list page with a search box, two filters, and an "Add" button
  is viewed at 375px wide
- **THEN** the search box and filters stack full-width, the Add button
  stays visible, and nothing extends past the right edge

### Requirement: Data Tables Scroll Within Their Container and Keep Actions Reachable
Every data table SHALL scroll horizontally inside its own bordered
container when its columns exceed the available width, so the page itself
never scrolls sideways. Below `md`, each table SHALL hide its non-essential
columns. Its identifying column (e.g. name/tracking ID), its status column
if it has one, and its row-actions column SHALL remain visible. The
row-actions column SHALL remain reachable without scrolling the table.
Pagination controls SHALL wrap and stay operable at 360px.

#### Scenario: Branches table on a phone
- **WHEN** the branches list is viewed at 375px wide
- **THEN** the branch name, status, and actions columns are visible, other
  columns are hidden, and the row actions can be tapped without scrolling
  the table

#### Scenario: Wide table on a tablet
- **WHEN** a table whose columns are wider than 768px is viewed at 768px
- **THEN** the table scrolls horizontally within its container while the
  rest of the page stays fixed in width

### Requirement: Invitation Boards Show One Status Column at a Time Below Desktop
Below `lg`, the staff and reception invitation (kanban) boards SHALL
display one status column at a time. The column shown SHALL be chosen by
a status selector (tabs or segmented control) that lists every column
with its count. At `lg` and wider the columns SHALL remain side by side.
Switching columns SHALL NOT refetch data or reset filters.

#### Scenario: Staff board on a phone
- **WHEN** the staff dashboard's invitation board is opened at 375px wide
- **THEN** a status selector with each column's label and count is shown,
  one column's cards are listed full-width beneath it, and selecting a
  different status shows that column's cards

#### Scenario: Board on desktop
- **WHEN** the same board is opened at 1280px wide
- **THEN** all status columns render side by side as before

### Requirement: Modals Fit Small Screens
Every modal and confirmation dialog SHALL fit within the viewport at 360px
wide. On phone it SHALL span the full width, minus a small margin or as a
bottom sheet, and its height SHALL NOT exceed the viewport. Its body
SHALL scroll internally while its title and primary/secondary actions
remain visible. Multi-column content inside a modal (e.g. visitor info,
edit invitation) SHALL stack to one column on phone.

#### Scenario: Visitor info modal on a phone
- **WHEN** a reception user opens the visitor info modal at 375px wide
- **THEN** the modal fills the width, its detail fields render in one
  column, its content scrolls inside the modal, and its close and action
  buttons stay visible

### Requirement: Controls Are Touch-Operable
On viewports below `lg`, every interactive control SHALL have a tap target
of at least 40×40 CSS pixels. Buttons, icon buttons, checkboxes, toggles,
row actions, and pagination controls are all included. Any action
revealed only on hover SHALL also be reachable by tap. Drag-and-drop
interactions SHALL work with touch input as well as a mouse. For
form-builder step, field, and option reordering this is a press-and-hold
drag. For the invitation board, where HTML drag-and-drop has no touch
support, it is an equivalent tap button on the card.

#### Scenario: Hover-only row action on a tablet
- **WHEN** a row action that appears on hover at desktop is viewed on a
  touch tablet
- **THEN** the action is visible or reachable with a single tap

#### Scenario: Moving a board card without drag-and-drop
- **WHEN** a staff user on a touch device below `lg` views a requested
  invitation card that could be dragged onto the Approved or Denied column
  on desktop
- **THEN** the card shows "Approve" and "Deny" buttons that perform the same
  action as dropping it on that column (deny still asks for a reason)

#### Scenario: Reordering form fields by touch
- **WHEN** an admin long-presses and drags a field's handle in the form
  builder on a touch device
- **THEN** the field is reordered the same way a mouse drag would reorder it

### Requirement: Public Portal Pages Adapt to Phone Screens
The public header, footer, landing page, tracking page, and OTP screens
SHALL adapt to phone widths:
- header side padding SHALL shrink to 16px;
- footer columns SHALL stack;
- hero and card content SHALL render in a single column;
- any fixed-width panel SHALL become full-width.

Text inputs SHALL use a font size of at least 16px on phone, so that
mobile browsers do not auto-zoom on focus.

#### Scenario: Track page on a phone
- **WHEN** a visitor opens the track-request page at 360px wide
- **THEN** the lookup form and status panel render full-width in one
  column, and focusing the input does not zoom the page
