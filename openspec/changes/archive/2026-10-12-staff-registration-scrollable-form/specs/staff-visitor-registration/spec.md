## ADDED Requirements

### Requirement: The wizard's form region scrolls independently of the page header, stepper, and action bar on desktop widths
At desktop widths, where the navigation sidebar is docked, the staff Register Visitor page SHALL keep its page header (title, subtitle, and identity/sign-out block), the progress stepper, and the Cancel / Next action bar fixed in view. The current step's form region SHALL be the only part of the page that scrolls, filling the vertical space between the stepper and the action bar. When the staff member moves to a different step, the form region SHALL show the top of that step. Below desktop width the whole page SHALL scroll as one, with the action bar kept visible at the bottom of the viewport. On those widths the stacked header and stepper would otherwise leave too little height for the form.

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
