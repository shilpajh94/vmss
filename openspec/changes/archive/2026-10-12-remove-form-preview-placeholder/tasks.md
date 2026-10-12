## 1. Remove the placeholder

- [x] 1.1 Delete the disabled "Form Preview" `<button>` (`disabled`, `title="Coming soon"`) from the heading row in `src/presentation/pages/admin-form-builder/admin-form-builder.tsx`
- [x] 1.2 Confirm the heading row still wraps cleanly with only the workspace selector, "Create Registration Step", and "Publish Changes", on both mobile and desktop widths

## 2. Verify

- [x] 2.1 Run `npm run lint` and `npm run build` (includes `tsc -b`); both pass
- [x] 2.2 Open `/admin/form-builder` in the running app and confirm no "Form Preview" button appears, and that creating and publishing steps still work
- [x] 2.3 Run `openspec validate remove-form-preview-placeholder --strict`
