## 1. Remove the search field from the shared top bar

- [x] 1.1 In `src/presentation/components/AdminTopBar.tsx`, remove the "Search workspace..." box (the `SearchGlyphIcon` + label wrapper) from the top bar's right-hand cluster.
- [x] 1.2 Remove the now-unused `SearchGlyphIcon` import if nothing else in the file uses it.
- [x] 1.3 Confirm the top bar layout (spacing between the notification bell, avatar, and sign-out button) still looks correct with the search box gone, on an admin page that uses `AdminTopBar` (e.g. `/admin/organisation-configs`).

## 2. Verify no other references

- [x] 2.1 Grep the codebase for any other "Search workspace" or workspace-search-specific test/reference and confirm none remain.
