## MODIFIED Requirements

### Requirement: Wizard is reachable from the staff dashboard
The system SHALL render the Register Visitor wizard inside the staff shell (the same sidebar and shared staff top bar as the staff Invitations page), with its own "Register Visitor" title and subtitle as the page's title row. The page SHALL NOT render its own identity or "Sign out" block; those are in the top bar when a staff member activates "My actions" from the dashboard sidebar.

#### Scenario: Staff opens the wizard from the dashboard
- **WHEN** an authenticated staff member activates "My actions" in the dashboard sidebar
- **THEN** the system renders the Register Visitor wizard's "Visitor Info" step inside the staff shell

#### Scenario: Register Visitor uses the shared top bar
- **WHEN** an authenticated staff member opens the Register Visitor wizard at 1440px wide
- **THEN** the shared staff top bar shows their name, role and "Sign out", and the page content starts with the "Register Visitor" title row, with no second identity or "Sign out" block

### Requirement: The wizard's form region scrolls independently of the page header, stepper, and action bar on desktop widths
At desktop widths, where the navigation sidebar is docked, the staff Register Visitor page SHALL keep the staff top bar, its page title row (title and subtitle), the progress stepper, and the Cancel / Next action bar fixed in view. The current step's form region SHALL be the only part of the page that scrolls, filling the vertical space between the stepper and the action bar. When the staff member moves to a different step, the form region SHALL show the top of that step. Below desktop width the whole page SHALL scroll as one, with the action bar kept visible at the bottom of the viewport. On those widths the stacked header and stepper would otherwise leave too little height for the form.

#### Scenario: Scrolling a tall step on desktop keeps the chrome in view
- **WHEN** the staff member is on a step whose fields are taller than the space available at a desktop viewport width and scrolls down within the form
- **THEN** the form fields scroll while the page header, the progress stepper, and the Cancel / Next buttons stay visible and do not move

#### Scenario: Action buttons are reachable without scrolling on desktop
- **WHEN** a step's content is taller than the available space at a desktop viewport width
- **THEN** the Cancel and Next buttons are visible and can be activated without first scrolling to the end of the form

#### Scenario: Short step on desktop shows no scroll
- **WHEN** a step's content fits within the available space at a desktop viewport width
- **THEN** the form region shows no scrollbar and the action bar sits directly below the form area

#### Scenario: Changing step starts the new step at the top
- **WHEN** the staff member has scrolled part-way down a step and moves to another step (via Next, Back, or the stepper)
- **THEN** the form region shows the beginning of the newly displayed step

#### Scenario: Below desktop width the page scrolls as one
- **WHEN** the wizard is shown below desktop width and the content is taller than the viewport
- **THEN** the header, stepper, and form scroll together as one page, and the Cancel / Next action bar stays visible at the bottom of the viewport

#### Scenario: Validation errors remain visible
- **WHEN** the staff member activates Next with a required field missing that is outside the visible part of the form region
- **THEN** the field's validation error can be reached by scrolling the form region, without any part of the form being clipped or unreachable
