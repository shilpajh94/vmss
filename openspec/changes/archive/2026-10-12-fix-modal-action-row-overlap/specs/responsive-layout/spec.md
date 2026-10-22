## MODIFIED Requirements

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
