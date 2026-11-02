## MODIFIED Requirements

### Requirement: Every staff and admin surface follows the theme
In the dark theme, page backgrounds, cards, tables, modals, dropdowns, form
fields, toasts, the top bar and charts on staff and admin pages SHALL use
the dark token values. No surface SHALL remain a fixed light colour.

- Text SHALL meet WCAG AA contrast against its background: 4.5:1 for body
  text, 3:1 for large text and for UI component boundaries. This includes
  small numerals such as step numbers and count badges.
- Dashboard charts SHALL re-colour when the theme changes, without a
  reload.
- The sidebar keeps its existing dark navy styling in both themes.
- The open option list of every native dropdown (filter bars, form selects,
  branch pickers) SHALL use a dark surface with theme text colour. It SHALL
  never open as a light panel or with text that does not meet 4.5:1 against
  it.
- A control, pill, icon tile or inset panel placed on a card or modal SHALL
  be the same colour as that card or lighter in the dark theme. It SHALL
  NOT be darker than the card it sits on (no near-black "hole").
- A sticky or bottom action bar SHALL share the colour of the surface
  directly behind it, so it shows no band of a different colour against the
  page.

#### Scenario: Modal in dark mode
- **WHEN** a dark-theme admin opens the "Add Floor" modal
- **THEN** the modal, its fields and its buttons use dark surfaces with
  readable text, and no white panel appears

#### Scenario: Charts follow a theme switch
- **WHEN** an admin on the dashboard switches from Light to Dark
- **THEN** the chart gridlines, axis text and tooltip surface switch to
  their dark colours without a reload

#### Scenario: Filter dropdown opens dark
- **WHEN** a dark-theme reception user on `/staff/invitations` opens the
  "All statuses" filter
- **THEN** the option list has a dark background and every option
  (Requested, Approved, Checked-in, Checked-out, Denied, Archived) is
  readable at 4.5:1 or better

#### Scenario: Form select opens dark
- **WHEN** a dark-theme admin on `/admin/branches/new` opens the Country
  select
- **THEN** the option list has a dark background and readable options

#### Scenario: No dark holes on Form Builder cards
- **WHEN** a dark-theme admin views `/admin/form-builder`
- **THEN** each step card's "Edit Fields" button and step icon tile are no
  darker than the card behind them

#### Scenario: Register Visitor action bar blends in
- **WHEN** a dark-theme host views `/staff/visitors/new` at desktop width
- **THEN** the Cancel / Next bar sits on the same colour as the page around
  it, with only its top divider separating it

#### Scenario: Step numbers are readable
- **WHEN** a user in either theme views the Register Visitor stepper
- **THEN** the numbers of the steps not yet reached meet 4.5:1 contrast
  against their circle

#### Scenario: Live switch matches a fresh load
- **WHEN** a user on any staff or admin page switches from Light to Dark
- **THEN** every element's colours equal those of the same page loaded
  fresh in the dark theme
