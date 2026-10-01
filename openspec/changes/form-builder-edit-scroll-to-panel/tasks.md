## 1. Implementation

- [x] 1.1 In the step editor hook, expose a way to distinguish explicit selection (e.g. a scroll-request counter incremented by `selectField`, not by the initial auto-select)
- [x] 1.2 Add a ref wrapper around `FieldPropertiesPanel` in `admin-form-builder-step-editor.tsx`
- [x] 1.3 On explicit select, scroll the wrapper into view after render (smooth, `start`; `auto` under prefers-reduced-motion)

## 2. Verification

- [x] 2.1 Manually verify: narrow width, click Edit on a top field → panel scrolls into view
- [x] 2.2 Manually verify: wide width, list scrolled, Edit on lower field → panel visible
- [x] 2.3 Verify no scroll on step load, and no movement when panel already at top (scrollTop unchanged when it is already at the top of the view)
- [x] 2.4 Run lint and type-check
