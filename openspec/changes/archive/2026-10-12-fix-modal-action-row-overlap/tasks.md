## 1. Fix shared modal

- [x] 1.1 In `src/presentation/components/ui/Modal.tsx`, change the action-row sticky offset from `bottom-0` to `-bottom-4` with `sm:-bottom-6` on the `[&>*:last-child:has(>button)]` selector, matching the title row's `-top-4` / `sm:-top-6`
- [x] 1.2 Update the component comment to note why both pinned rows use negative offsets (sticky offsets are measured from the padding-inset edge)

## 2. Verify

- [ ] 2.1 Create Registration Step modal (admin form builder) at 1280px and 375px: Step Name input fully visible, including its bottom border and focus ring, with a gap above the action row
- [ ] 2.2 Long scrolling modals (`AddFieldModal`, `VisitorInfoModal`, `EditInvitationModal`): title and actions stay pinned, nothing scrolls visibly beneath them, and the last body element is fully visible when scrolled to the end
- [ ] 2.3 Spot-check the remaining `Modal` consumers (`ConfirmDialog`, approve/deny/delegate/reschedule invitation modals, `CreateGroupModal`, `FloorModal`, `BranchFormModal`, `BulkAddCategoriesModal`) at both widths
- [x] 2.4 Run `npm run lint` and `npm run build` clean
