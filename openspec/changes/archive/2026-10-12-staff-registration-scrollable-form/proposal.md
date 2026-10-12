## Why

On the staff **Register Visitor** page (`/staff/visitors/new`) the whole content region scrolls as one, so moving through a tall step like Visitor Info scrolls the page title, the progress stepper, and the Cancel / Next buttons out of view. Staff lose track of which step they're on, and have to scroll to the very bottom to move on. The form card should scroll on its own, with the page chrome around it staying fixed.

## What Changes

- On desktop widths (`lg` and up, where the sidebar is docked), the page header ("Register Visitor" plus the identity/sign-out block) and the progress stepper stay fixed at the top of the content region.
- The step's form card becomes the only scrolling region, filling the height between the stepper and the action bar.
- The Cancel / Next action bar stays pinned below the form card, visible without scrolling.
- Changing step resets the form card's scroll to the top, so a new step doesn't open part-way down.
- Below `lg`, behaviour stays as it is today: the whole page scrolls and the action bar stays sticky at the bottom. A stacked header and stepper on a phone would otherwise leave only a sliver for the form, which matches how `PageContentLayout` already treats list pages.
- `PageContentLayout` gains an optional pinned `footer` slot so this page reuses the shared fixed-header/scrolling-body layout instead of adding a one-off.

Out of scope (assumption): the public self-service visitor wizard (`/visitor/...`) and the admin create/edit form pages. The report covers only the staff Register Visitor page.

## Capabilities

### New Capabilities
<!-- none -->

### Modified Capabilities
- `staff-visitor-registration`: adds a requirement that, on desktop widths, the page header, stepper, and action bar stay fixed while only the step's form region scrolls.

## Impact

- `src/presentation/components/PageContentLayout.tsx`: new optional `footer` prop. Existing callers pass no footer and are unaffected.
- `src/presentation/pages/staff-visitor-registration/staff-visitor-registration.tsx`: wraps the header/stepper, form card, and action bar in `PageContentLayout`, and resets the form card's scroll on step change.
- No API, data, or dependency changes.
