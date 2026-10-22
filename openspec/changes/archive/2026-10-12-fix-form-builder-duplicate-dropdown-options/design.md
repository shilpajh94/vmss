## Context

`SelectField` (`src/presentation/components/ui/SelectField.tsx`) unconditionally
renders `<option value="">{placeholder}</option>` before `options`;
`placeholderSelectable` only controls whether that option is disabled. Three
Form Builder call sites pass `placeholderSelectable` *and* an explicit option
with the same label but a sentinel value:

| Call site | Placeholder | Explicit duplicate | Sentinel |
|---|---|---|---|
| `admin-form-builder.tsx` workspace selector | "Tenant Default" | `__default__` | `DEFAULT_WORKSPACE_VALUE` |
| `FieldPropertiesPanel.tsx` condition selector | "Always shown" | `__none__` | `NO_CONDITION_VALUE` |
| `GroupCard.tsx` condition selector | "Always shown" | `__none__` | `NO_CONDITION_VALUE` |

`selectWorkspace` already maps both `''` and `__default__` to "no branch", so
the workspace selector is only cosmetically broken. The condition selectors
compare against `'__none__'` only, so choosing the placeholder (`''`) leaves
the UI in a half-set condition state.

Other `placeholderSelectable` callers (host-employee "All branches", kiosk
"All" filter) use `''` as their "none" value and have no duplicate — they are
the pattern to follow.

## Goals / Non-Goals

**Goals:** one entry per choice in the three dropdowns; "Always shown" reliably
clears the condition.

**Non-Goals:** changing `SelectField`'s API or rendering; touching other
callers; any API/back-end change.

## Decisions

**Use the placeholder as the single "default/none" option, with `''` as its
value.** Remove the explicit `{ value: SENTINEL, label: ... }` option at each of
the three call sites and redefine the sentinels as `''`
(`DEFAULT_WORKSPACE_VALUE = ''`, `NO_CONDITION_VALUE = ''`). Every existing
comparison against the constant keeps working unchanged, and the placeholder —
the only remaining entry with that label — now carries the value the code
checks for. In `selectWorkspace`, the `|| value === ''` branch becomes
redundant and can be collapsed.

Alternatives considered:
- *Drop `placeholderSelectable`/`placeholder` and keep the explicit option.*
  `SelectField` would still render a disabled "Select" entry at the top — a
  different stray option instead of a duplicate.
- *Add a `hidePlaceholder` prop to `SelectField`.* Works, but grows a shared
  component's API to paper over a call-site misuse; the existing callers show
  the intended pattern is "placeholder is the none-choice".
- *Keep `'__none__'` and normalise `''` in `onChange`.* Fixes the functional bug
  but leaves the visual duplicate.

## Risks / Trade-offs

- [A condition saved with `fieldKey: ''` would now read as "Always shown"] →
  Acceptable and arguably correct; both save paths already send `null` when the
  key equals the none value, so no such row should exist.
- [`''` is falsy, unlike `'__none__'`] → Audit the three files for truthiness
  checks on `conditionFieldKey`/`selectedBranchId` during implementation; current
  code uses strict `===`/`!==` against the constant.
