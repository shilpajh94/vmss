## ADDED Requirements

### Requirement: Step navigation adapts to narrow viewports
From 768px viewport width upward, the wizard SHALL show its step list as the existing side rail. Below 768px, it SHALL replace the rail with a compact progress header above the step content. The header SHALL show the current step's label, "Step X of N", and a progress bar. It SHALL list the same configured steps, in the same order, as the rail would, and SHALL let the visitor jump back to a completed step. Step content fields SHALL render in a single column below 640px. The Back/Next/Submit actions SHALL stay visible at the bottom of the viewport while the step content scrolls.

#### Scenario: Wizard on a phone
- **WHEN** a visitor opens the registration wizard at 375px wide on a branch configured with 4 steps
- **THEN** no side rail is shown, and a progress header reads "Step 1 of 4" with the current step's label, above single-column fields

#### Scenario: Returning to a completed step on a phone
- **WHEN** the visitor is on step 3 at 375px wide and opens the progress header's step list
- **THEN** steps 1 and 2 are selectable, and choosing one shows that step with its entered data intact

#### Scenario: Actions remain reachable
- **WHEN** a step's content is taller than the phone viewport
- **THEN** the Back/Next (or Submit) buttons stay visible while the fields scroll
