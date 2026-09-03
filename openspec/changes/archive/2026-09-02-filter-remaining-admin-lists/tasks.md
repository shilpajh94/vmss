## 1. Branches — Status filter

- [x] 1.1 In `src/presentation/pages/admin-branches/hooks/use-admin-branches.ts`, add `statusFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `filteredBranches` `useMemo` (matching `isActive`), and `clearFilters`/`isFiltering`; return `filteredBranches` in place of the raw list, plus `hasAnyBranches` (raw list length > 0).
- [x] 1.2 In `src/presentation/pages/admin-branches/admin-branches.tsx`, wire "Filters" to `toggleFilterPanel`, add a filter panel with a Status `SelectField` (Active/Inactive), a "Clear filters" action, and distinguish "no branches match these filters" from the existing zero-branches empty state.

## 2. Departments — Branch + Status filters

- [x] 2.1 In `src/presentation/pages/admin-departments/hooks/use-admin-departments.ts`, add `branchFilter`/`statusFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `branchOptions` `useMemo` derived from the loaded departments' `branchId`/`branchName` (deduplicated), a `filteredDepartments` `useMemo` (branch + status, AND semantics), and `clearFilters`/`isFiltering`/`hasAnyDepartments`.
- [x] 2.2 In `src/presentation/pages/admin-departments/admin-departments.tsx`, wire "Filters", add the Branch + Status filter panel, "Clear filters", and the distinct no-matches empty state.

## 3. Buildings — Branch + Status filters

- [x] 3.1 In `src/presentation/pages/admin-buildings/hooks/use-admin-buildings.ts`, add `branchFilter`/`statusFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `branchOptions` `useMemo` derived from the loaded buildings' `branchId`/`branchName`, a `filteredBuildings` `useMemo`, and `clearFilters`/`isFiltering`/`hasAnyBuildings`.
- [x] 3.2 In `src/presentation/pages/admin-buildings/admin-buildings.tsx`, wire "Filters", add the Branch + Status filter panel, "Clear filters", and the distinct no-matches empty state.

## 4. Floors — Building + Access Level + Status filters

- [x] 4.1 In `src/presentation/pages/admin-floors/hooks/use-admin-floors.ts`, add `buildingFilter`/`accessLevelFilter`/`statusFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `filteredFloors` `useMemo` (all three, AND semantics; Building options reuse the already-loaded buildings list, Access Level options are the static `public`/`restricted`/`secure` enum), and `clearFilters`/`isFiltering`/`hasAnyFloors`.
- [x] 4.2 In `src/presentation/pages/admin-floors/admin-floors.tsx`, wire "Filters", add the Building + Access Level + Status filter panel, "Clear filters", and the distinct no-matches empty state.

## 5. Reception Desks — Building + Floor + Status filters

- [x] 5.1 In `src/presentation/pages/admin-reception-desks/hooks/use-admin-reception-desks.ts`, add `buildingFilter`/`floorFilter`/`statusFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, `buildingOptions`/`floorOptions` `useMemo`s derived from the loaded reception desks' `buildingName`/`floorName`, a `filteredReceptionDesks` `useMemo` (all three, AND semantics; Status options are the static `active`/`maintenance`/`inactive` enum), and `clearFilters`/`isFiltering`/`hasAnyReceptionDesks`.
- [x] 5.2 In `src/presentation/pages/admin-reception-desks/admin-reception-desks.tsx`, wire "Filters", add the Building + Floor + Status filter panel, "Clear filters", and the distinct no-matches empty state.

## 6. Security Gates — Building + Gate Type + Security Level filters

- [x] 6.1 In `src/presentation/pages/admin-security-gates/hooks/use-admin-security-gates.ts`, add `buildingFilter`/`gateTypeFilter`/`securityLevelFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `buildingOptions` `useMemo` derived from the loaded gates' `buildingName`, a `filteredSecurityGates` `useMemo` (Gate Type is the static `entry`/`exit`/`both` enum; Security Level maps `highSecurity: boolean` to a "High Security"/"Standard" 2-option filter), and `clearFilters`/`isFiltering`/`hasAnySecurityGates`.
- [x] 6.2 In `src/presentation/pages/admin-security-gates/admin-security-gates.tsx`, wire "Filters", add the Building + Gate Type + Security Level filter panel, "Clear filters", and the distinct no-matches empty state.

## 7. Visitor Categories — Badge Color + NDA Requirement + Escort Requirement filters

- [x] 7.1 In `src/presentation/pages/admin-visitor-categories/hooks/use-admin-visitor-categories.ts`, add `badgeColorFilter`/`ndaRequirementFilter`/`escortRequirementFilter` state, `isFilterPanelOpen`/`toggleFilterPanel`, a `filteredVisitorCategories` `useMemo` (all three static enums, reusing the existing `BADGE_COLOR`/`NDA_REQUIREMENT_LABEL`/`ESCORT_REQUIREMENT_LABEL` label maps from `Components/VisitorCategoriesTable.tsx` for option labels), and `clearFilters`/`isFiltering`/`hasAnyVisitorCategories`.
- [x] 7.2 In `src/presentation/pages/admin-visitor-categories/admin-visitor-categories.tsx`, wire "Filters", add the Badge Color + NDA Requirement + Escort Requirement filter panel, "Clear filters", and the distinct no-matches empty state.

## 8. Verify

- [ ] 8.1 For each of the 7 pages: load it, activate "Filters", confirm the panel shows the right fields each defaulting to "All".
- [ ] 8.2 For each page: select each filter individually and confirm the table narrows correctly; select combinations (where more than one field exists) and confirm AND semantics.
- [ ] 8.3 For each page: pick a filter combination matching zero rows and confirm the page's own "no ... match these filters" message shows, not the zero-records empty state (with its "Add ..." action).
- [ ] 8.4 For each page: activate "Clear filters" and confirm the full list returns and all selects reset to "All".
- [ ] 8.5 Confirm none of the 7 pages issue any new network request as a result of this change (same requests as before, filtering is purely client-side).
