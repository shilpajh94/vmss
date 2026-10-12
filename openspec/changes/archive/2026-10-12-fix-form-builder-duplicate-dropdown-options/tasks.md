## 1. Workspace selector

- [x] 1.1 In `hooks/use-admin-form-builder.ts`, set `DEFAULT_WORKSPACE_VALUE = ''` and simplify `selectWorkspace` to `value === DEFAULT_WORKSPACE_VALUE ? undefined : value`
- [x] 1.2 In `admin-form-builder.tsx`, remove the explicit `{ value: DEFAULT_WORKSPACE_VALUE, label: 'Tenant Default' }` option so options are only the branches (keep `placeholder="Tenant Default"` + `placeholderSelectable`)

## 2. Conditional-visibility selectors

- [x] 2.1 In `Components/FieldPropertiesPanel.tsx`, set `NO_CONDITION_VALUE = ''` and remove the explicit `{ value: NO_CONDITION_VALUE, label: 'Always shown' }` option
- [x] 2.2 In `Components/GroupCard.tsx`, make the same two changes
- [x] 2.3 Audit both files for truthiness checks on `conditionFieldKey` that would behave differently now that the none value is falsy

## 3. Verify

- [x] 3.1 `npm run lint` and `npm run build` (tsc) pass
- [x] 3.2 Manual: `/admin/form-builder` dropdown shows "Tenant Default" once then each branch; switching branch → Tenant Default reloads default steps
- [x] 3.3 Manual: field and group "Show this … when:" dropdowns show "Always shown" once; selecting it on an element with a condition hides operator/value inputs and saves with no condition
