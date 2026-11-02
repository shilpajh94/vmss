## MODIFIED Requirements

### Requirement: Step navigation adapts to narrow viewports
From 1024px viewport width upward, the wizard SHALL show its step list inside the navy panel on the left of the split-screen layout. The panel holds the back action and logo above the steps and the copyright line below them. Completed steps SHALL show a cyan marker and SHALL be selectable. The current step SHALL be highlighted. Upcoming steps SHALL be dimmed and not selectable.

Below 1024px, the wizard SHALL show the navy top strip and a compact progress header above the step content. The header SHALL show:
- the current step's label;
- "Step X of N";
- a progress bar.

It SHALL list the same configured steps, in the same order, as the panel would, and SHALL let the visitor jump back to a completed step.

Step content fields SHALL render in a single column below 640px. The Back/Next/Submit actions SHALL stay visible at the bottom of the form panel while the step content scrolls.

#### Scenario: Wizard on a laptop
- **WHEN** a visitor opens the registration wizard at 1440×900 on a branch configured with 4 steps
- **THEN** the navy panel on the left lists the 4 steps with step 1 highlighted, and the step's fields are in the form panel on the right

#### Scenario: Wizard on a phone
- **WHEN** a visitor opens the registration wizard at 375px wide on a branch configured with 4 steps
- **THEN** no step panel is shown, and a progress header reads "Step 1 of 4" with the current step's label, above single-column fields

#### Scenario: Returning to a completed step on a phone
- **WHEN** the visitor is on step 3 at 375px wide and opens the progress header's step list
- **THEN** steps 1 and 2 are selectable, and choosing one shows that step with its entered data intact

#### Scenario: Actions remain reachable
- **WHEN** a step's content is taller than the viewport
- **THEN** the Back/Next (or Submit) buttons stay visible while the fields scroll
