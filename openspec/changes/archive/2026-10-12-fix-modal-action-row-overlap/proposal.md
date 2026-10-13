## Why

In the Create Registration Step modal (admin form builder), the action row
(Cancel / Create Step) covers the bottom of the Step Name input, so the
field is only partly visible. The cause is in the shared `Modal`
component, so every modal has the same defect. It shows most on short
modals whose last body element is an input.

## What Changes

- Fix the shared modal so its pinned action row never covers body
  content when the body fits without scrolling. The normal gap between
  the last body element and the action row must stay visible.
- Keep the current pinned behaviour when the body does scroll: the title
  and action row stay visible while the body scrolls between them, on
  both the phone bottom-sheet layout and the centred `sm`+ layout.
- No change to modal sizes, button styling, or any individual modal's
  content.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `responsive-layout`: the "Modals Fit Small Screens" requirement gains
  the constraint that the pinned title and action rows must never cover
  modal body content.

## Impact

- `src/presentation/components/ui/Modal.tsx`: the only code change.
- Every modal built on `Modal` is affected visually, including
  `ConfirmDialog`, the invitation-board modals, the form-builder modals
  (`CreateStepModal`, `CreateGroupModal`, `AddFieldModal`), and the
  admin floor, branch and visitor-category modals. Each needs a visual
  check, but none needs a code change.
- No API, data, or dependency changes.
