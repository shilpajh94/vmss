## Context

See proposal.md - Why. This capability follows the same admin CRUD layering as `admin-reception-desks`/`admin-security-gates` (`data/` → `infrastructure/` → `presentation/` per `.claude/rules/clean-architecture.md` and `.claude/rules/data-api-layer.md`), but unlike those two it has **no relation to Building, Floor, or Branch** — it's a flat, org-wide policy registry, closer in shape to how `admin-host-employees` lists roles. `AdminSidebar` already reserves the `visitor-categories` nav key, label, and icon (`TagIcon`); `AdminTopBar` reuses its existing hardcoded "Organization Admin" heading, same as every other admin screen. `src/domain/entities/visitor-schema.ts` already has a free-text `visitorCategory: z.string()` field, and the visitor registration wizard (`VisitorFieldsForm.tsx`) has its own hardcoded `VISITOR_CATEGORY_OPTIONS` — neither is touched by this change.

## Goals / Non-Goals

**Goals:**
- Deliver the Visitor Categories Registry (list) and Add/Edit Category pages matching the Figma design (node `203:1780`) and the existing admin CRUD architecture.
- Model Badge Color as a small fixed palette tied to existing theme tokens, matching the four colors shown in the design.
- Faithfully render the design's varied, compound NDA/Escort/Duration values without forcing them into a data model richer than the design justifies.

**Non-Goals:**
- Wiring the visitor registration wizard's category dropdown to this new registry. The wizard keeps its own hardcoded `VISITOR_CATEGORY_OPTIONS` and `Visitor.visitorCategory` stays a free-text field; replacing that with a reference to this registry is a natural follow-up but is out of scope here.
- A structured NDA/escort policy model (e.g. separate `required: enum` + `method: string` fields). The design's own values don't decompose cleanly across categories (e.g. Escort Required shows "No (Self-escort)", "Required (Always)", and "Gate check-in only" — three different shapes), so NDA Required, Escort Required, and Max Duration are each a single optional free-text field, consistent with how Security Gate's Auth Method was handled.
- A general-purpose color-picker component. This introduces one small fixed-palette swatch picker scoped to this feature; a reusable design-system color picker is future work if a second consumer appears.
- Real filtering behind the "Filters" button (matches every existing admin screen).

## Decisions

- **Badge Color as a fixed enum tied to theme tokens**: `VisitorCategorySchema.badgeColor: z.enum(["blue", "orange", "gold", "grey"]).default("blue")`. The four Figma swatches (`#3b82f6`, `#f59e0b`, `#d97706`, `#64748b`) match `--color-info`, `--color-warning`, `--color-vip`, and `--color-text-muted` exactly, so the swatch picker and table badge render using those existing theme classes (`bg-info`, `bg-warning`, `bg-vip`, `bg-text-muted`) rather than hardcoded hex values. Alternative considered: free-text hex input — rejected, the design shows a small closed set of named swatches, not an open color picker.
- **NDA Required, Escort Required, and Max Duration as free text**: each is `z.string().optional()` on `VisitorCategorySchema`, holding the exact display string (e.g. `"Yes (Digital)"`, `"Required (Always)"`, `"8 Hours"`). This avoids inventing a schema shape the design doesn't support uniformly.
- **Escort emphasis is presentational, not a schema field**: the design bolds/reddens "Required (Always)" in the Escort Required column. Rather than adding a boolean flag, `VisitorCategoriesTable` applies emphasis when the stored `escortRequired` string case-insensitively starts with `"required"` — a simple prefix check owned entirely by the table component, with no schema or API impact.
- **No relation fields**: `VisitorCategorySchema` has no `buildingId`/`floorId`/`branchId` — this is a flat top-level entity, so its repository/use cases are simpler than reception-desks/security-gates (no name-lookup joins needed).
- **New endpoints follow the existing REST shape**: `LIST_VISITOR_CATEGORIES`/`CREATE_VISITOR_CATEGORY` at `/visitor-categories`, `UPDATE_/DELETE_VISITOR_CATEGORY` at `/visitor-categories/:id`, all `hasToken: true`.
- **New small swatch-picker UI**: since no color-picker component exists in `src/presentation/components/ui/`, the Add/Edit form gets a small `Components/BadgeColorField.tsx` scoped to this feature (four labeled swatch buttons), rather than reusing `SelectField`'s plain `<select>` for a visually-swatched choice.

## Risks / Trade-offs

- [Free-text NDA/Escort/Duration fields allow inconsistent admin-entered values] → Accepted: the source design itself shows inconsistent shapes across rows, so a rigid schema would misrepresent real usage; a future change can introduce structure once real data reveals a stable pattern.
- [Fixed 4-color palette may not cover every future category] → Contained to `badgeColor`'s enum; extending the palette later is a small, additive schema change.
- [This registry is disconnected from the visitor wizard's `visitorCategory` field] → Explicitly a Non-Goal; two independent sources of "category" values will coexist until a follow-up change unifies them.
