# responsive-layout Specification

## Purpose
Defines the viewport range every page of the web portal must support, and
how shared layout patterns adapt across phone, tablet, and desktop widths.
The patterns covered are page containers, form grids, data tables, kanban
boards, modals, headers/filters, and touch controls.

## Requirements

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
with its count, where each count is the server's total for that status
(not the number of cards loaded). The status selector SHALL stay visible
while the selected column's cards are scrolled. At `lg` and wider the
columns SHALL remain side by side. Switching columns SHALL NOT refetch
data already loaded or reset filters; the newly shown column SHALL keep
whatever pages it had already loaded.

#### Scenario: Staff board on a phone
- **WHEN** the staff dashboard's invitation board is opened at 375px wide
- **THEN** a status selector with each column's label and total count is
  shown, one column's cards are listed full-width beneath it, and
  selecting a different status shows that column's cards

#### Scenario: Status selector stays visible while scrolling on a phone
- **WHEN** a staff member at 375px wide scrolls down through the selected
  column's cards
- **THEN** the status selector, including the active status and its
  count, stays visible above the cards

#### Scenario: Board on desktop
- **WHEN** the same board is opened at 1280px wide
- **THEN** all status columns render side by side as before

### Requirement: Modals Fit Small Screens
Every modal and confirmation dialog SHALL fit within the viewport at 360px
wide. On phone it SHALL span the full width, minus a small margin or as a
bottom sheet, and its height SHALL NOT exceed the viewport. Its body
SHALL scroll internally while its title and primary/secondary actions
remain visible. The pinned title and action rows SHALL NOT cover any part
of the modal body. When the body fits without scrolling, every body
element, including the full border of its last input, SHALL be visible
with the normal spacing above the action row. Multi-column content inside
a modal (e.g. visitor info, edit invitation) SHALL stack to one column on
phone.

#### Scenario: Visitor info modal on a phone
- **WHEN** a reception user opens the visitor info modal at 375px wide
- **THEN** the modal fills the width, its detail fields render in one
  column, its content scrolls inside the modal, and its close and action
  buttons stay visible

#### Scenario: Short modal whose body ends with an input
- **WHEN** an admin opens the Create Registration Step modal on desktop
  (1280px wide) or on a phone (375px wide)
- **THEN** the Step Name input is fully visible, including its bottom
  border and focus ring, with visible spacing between it and the
  Cancel / Create Step row

#### Scenario: Long modal body scrolled to the end
- **WHEN** a modal's body is taller than the available height and the user
  scrolls it to the bottom
- **THEN** the last body element is fully visible above the pinned action
  row, and the title and action rows remain visible throughout the scroll

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

### Requirement: Paged List Pagination Stays Visible Below the Data
On every paged staff or admin list page (a table with a
`Showing A-B of N` footer and Previous/Next controls), from `lg` (1024px)
up:
- the pagination footer SHALL sit directly below the scrolling data
  region, outside it;
- the footer SHALL stay visible without scrolling, whatever the number
  of rows;
- only the rows SHALL scroll;
- when the rows are scrolled to the end, the last row and the data
  container's bottom edge SHALL sit fully above the footer;
- the page itself SHALL NOT scroll vertically because of the rows.

Below `lg`, the whole page SHALL scroll as one, and the pagination footer
SHALL follow the last row.

While the list is loading for the first time, has failed, or is empty,
the footer SHALL NOT be shown.

#### Scenario: Full page of rows on a laptop screen
- **WHEN** the employees list shows 20 rows at 1280×720
- **THEN** the `Showing 1-20 of N` text and the Previous/Next buttons
  are fully inside the window without scrolling, and the page itself
  does not scroll

#### Scenario: Scrolling the rows keeps the footer in place
- **WHEN** the user scrolls the rows of a paged list to the end at
  1440×900
- **THEN** the pagination footer stays in the same position and the last
  row ends above it

#### Scenario: Short list
- **WHEN** a paged list has three rows at 1440×900
- **THEN** the pagination footer is directly below the third row, not
  pushed to the bottom of the window

#### Scenario: Phone width
- **WHEN** a paged list with 20 rows is viewed at 390px wide
- **THEN** the page scrolls as a whole and the pagination footer follows
  the last row

#### Scenario: Workflows list
- **WHEN** the approval workflows list shows a full page at 1280×720
- **THEN** its `Showing A-B of N workflows` footer and Previous/Next
  buttons are visible without scrolling

### Requirement: The Public Portal Footer Is Compact
The footer shared by the public pages (visitor portal, visitor request,
tracking, not-found and route error pages) SHALL take only the height
its content needs:
- From 1024px wide upward, the logo, tagline and copyright line SHALL sit
  on one row, with the policy links and support contact on the same row,
  and the footer SHALL be no taller than 88px when its content fits on
  one row.
- Below 1024px the blocks SHALL stack, with no more than 16px of vertical
  padding above and below the footer content.
- The footer logo SHALL stay 28px tall. The tagline, the copyright line,
  and any configured Privacy Policy, Terms of Service and support contact
  links SHALL still be shown.
- Links SHALL keep the touch target sizes required by "Controls Are
  Touch-Operable".

#### Scenario: Error page footer on a full-HD desktop
- **WHEN** the "Something went wrong" page renders in a viewport 1920px
  wide and about 866px tall
- **THEN** the footer is no taller than 88px and shows the logo, tagline
  and copyright line on one row

#### Scenario: Landing page footer with all links configured
- **WHEN** the visitor portal landing page renders at 1440px wide with the
  privacy, terms and support settings all configured
- **THEN** the footer shows the brand block and all three links on one row,
  no taller than 88px

#### Scenario: Footer on a phone
- **WHEN** any public page renders at 360px wide
- **THEN** the footer blocks are stacked, nothing overflows horizontally,
  and the footer's vertical padding is no more than 16px at the top and
  bottom
