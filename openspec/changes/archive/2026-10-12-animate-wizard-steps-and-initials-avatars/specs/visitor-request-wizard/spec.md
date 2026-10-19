## ADDED Requirements

### Requirement: Moving between steps is animated
When the visitor moves to another step of the registration wizard, the step indicator SHALL animate the change. In the desktop side rail, the step left on a forward move SHALL change to a completed state that shows a checkmark instead of its number, and a vertical connector between it and the next step SHALL fill downward. On phone widths the progress bar SHALL animate its width to the new value. Backward moves SHALL reverse these changes. The step content SHALL enter from the right on a forward move and from the left on a backward move. The transition SHALL take no more than about 300ms, and SHALL NOT delay input on the new step. When the user's system requests reduced motion, all of this SHALL happen instantly, with no movement.

#### Scenario: Advancing on desktop
- **WHEN** a visitor at desktop width completes Visitor Info and activates Next
- **THEN** step 1 in the side rail shows a checkmark, the connector to step 2 fills downward, step 2 becomes active, and the next step's content slides in from the right

#### Scenario: Advancing on a phone
- **WHEN** a visitor at 375px wide on a 4-step configuration activates Next on step 1
- **THEN** the progress bar animates from 25% to 50%, the header reads "Step 2 of 4", and the content slides in from the right

#### Scenario: Returning to a completed step
- **WHEN** the visitor on step 3 selects step 1
- **THEN** the indicator reverses to show step 1 active, and its content slides in from the left with entered data intact

#### Scenario: Reduced motion is requested
- **WHEN** the operating system's reduced-motion preference is on and the visitor moves to another step
- **THEN** the indicator and content update immediately, with no sliding, filling, or width animation
