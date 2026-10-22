## 1. Shared layout

- [x] 1.1 Add an optional `footer` prop to `PageContentLayout` (`src/presentation/components/PageContentLayout.tsx`), rendered as a `flex-none` sibling after the scrolling region. Markup must be unchanged when `footer` is omitted.
- [x] 1.2 Expose a ref to the scrolling body region (e.g. a `bodyRef` prop) so a caller can reset its scroll position, and update the component's comment to describe the footer slot.

## 2. Register Visitor page

- [x] 2.1 In `staff-visitor-registration.tsx`, wrap the page in `PageContentLayout`: `header` = `RegistrationWorkspaceHeader` + `RegistrationStepper`, children = the form card, `footer` = the Cancel / Next action bar. Keep the `GroupErrorsContext.Provider` as the outermost element.
- [x] 2.2 Drop the form card's `flex-1` (the scroll region now owns the height), add `scrollbar-thin` to the scroll region, and switch the action bar's `md:static md:mx-0 md:px-0 md:pb-0` to `lg:` variants so it stays sticky below `lg`.
- [x] 2.3 Add an effect keyed on `currentStep` that resets the form region to its top: `scrollTop = 0` on the body region from `lg` up, and scrolling the layout root into view below `lg`.

## 3. Verification

- [x] 3.1 Run `npm run lint` and `npm run build`; both clean.
- [x] 3.2 Manually verify at 1920×970 (the reported size): on Visitor Info, scrolling moves only the form card. The header, stepper, and Cancel / Next stay fixed, and the Next button is visible without scrolling.
- [x] 3.3 Verify step changes (Next, Back, and stepper click) open the new step at its top; a short step (e.g. Consent) shows no scrollbar; and a Next with a missing required field leaves the error reachable by scrolling the form.
- [x] 3.4 Verify at 1024×768: the form region keeps usable height. At 768 and 390 widths, the whole page scrolls as before with the action bar sticky at the bottom.
- [x] 3.5 Spot-check one existing `PageContentLayout` list page (e.g. `/admin/buildings`) to confirm it's visually unchanged.
