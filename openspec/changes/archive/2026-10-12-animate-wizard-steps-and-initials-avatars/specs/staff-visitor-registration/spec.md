## ADDED Requirements

### Requirement: Moving between steps is animated
When the staff member moves to another step of the Register Visitor wizard, the stepper SHALL animate the change. On a forward move, the connector between the step left and the step entered SHALL fill toward the new step, and the step left SHALL change to a completed state that shows a checkmark instead of its number. On a backward move, the connectors and completed states SHALL reverse. The step content SHALL enter from the right on a forward move and from the left on a backward move. The full transition SHALL take no more than about 300ms. Inputs SHALL be usable as soon as the new step is shown, without waiting for the animation to finish. When the user's system requests reduced motion, the stepper state and step content SHALL change instantly, with no movement.

#### Scenario: Advancing to the next step
- **WHEN** the staff member completes Visitor Info and activates Next
- **THEN** the connector from step 1 to step 2 fills toward step 2, step 1 shows a checkmark, step 2 becomes active, and the Visit Details content slides in from the right

#### Scenario: Going back to an earlier step
- **WHEN** the staff member is on step 3 and selects step 1 in the stepper
- **THEN** the connectors after step 1 un-fill, step 1 becomes active again, and its content slides in from the left with the previously entered data intact

#### Scenario: Validation failure does not animate
- **WHEN** the staff member activates Next with a required field missing
- **THEN** the stepper and content stay on the current step, with no transition played

#### Scenario: Reduced motion is requested
- **WHEN** the operating system's reduced-motion preference is on and the staff member activates Next
- **THEN** the next step is shown immediately with no sliding or filling animation, and the stepper shows the same completed/active states
