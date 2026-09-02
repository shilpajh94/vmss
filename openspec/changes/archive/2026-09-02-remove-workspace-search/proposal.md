## Why

The Admin top bar's "Search workspace..." field is a non-functional placeholder — typing into it does nothing, per the existing spec ("Top bar search and notification affordances are presented but not yet functional"). It takes up top-bar space and signals a capability that doesn't exist, so it should be removed rather than left as dead UI until a real search feature is built.

## What Changes

- Remove the "Search workspace..." field (icon + input box) from the shared Admin top bar (`AdminTopBar.tsx`), which renders on every admin page.
- The notification indicator next to it (now a working notification bell, not a placeholder) is unaffected and stays.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `admin-organisation-configs`: the "Top bar search and notification affordances are presented but not yet functional" requirement is narrowed — the workspace search field is removed entirely rather than left as an inert placeholder. The notification affordance's own behavior is unchanged by this proposal.

## Impact

- `src/presentation/components/AdminTopBar.tsx` — shared component rendered by all ~23 admin pages; removing the search box here removes it everywhere in one place.
- No API, schema, or use-case changes — this is presentation-only.
