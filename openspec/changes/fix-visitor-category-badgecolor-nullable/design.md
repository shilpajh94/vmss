## Context

See proposal.md for the root-cause trace. The fix touches the boundary between two schemas that currently disagree about nullability:

- `VisitorCategoryOutSchema` (wire/parsing schema, `visitor-category-out-schema.ts`) — parses the raw API response and currently rejects a `null` `badgeColor`.
- `VisitorCategorySchema` (domain schema, `visitor-category-schema.ts`) — used as the app-wide `VisitorCategory` type, already declares `badgeColor: z.enum([...]).default("blue")`, i.e. it already models "no color set" by falling back to a default, just never gets the chance to since `toVisitorCategory()` builds the domain object by hand rather than by parsing through `VisitorCategorySchema`.

## Goals / Non-Goals

**Goals:**
- Let the wire schema accept what the backend actually sends (`badgeColor: string | null`).
- Keep every existing consumer of the domain `VisitorCategory` type working unmodified — none of them currently handle a null `badgeColor`, and this change shouldn't require them to.

**Non-Goals:**
- Not deciding what a category with no color should look like in the UI beyond what the domain schema already documents (default to "blue") — that's an existing, already-specified default, not a new design decision.
- Not changing `VisitorCategorySchema` itself — its `.default("blue")` behavior is already correct for the domain type; the gap is only that `toVisitorCategory()` doesn't route through it.

## Decisions

- **Fix at the wire-parsing boundary (`VisitorCategoryOutSchema`), not the domain type**: add `.nullable()` to `badgeColor` there, and in `toVisitorCategory()` map `visitorCategoryOut.badgeColor ?? 'blue'` when constructing the domain object. Alternative considered: change `VisitorCategory`'s own `badgeColor` type to `| null` throughout the app. Rejected — every consumer (admin list swatches, `BadgeColorField`, the visitor/staff wizards) already assumes a concrete color and has no "no color" rendering; propagating `null` through the whole domain type would require touching every consumer for no behavioral benefit, when the domain schema's own already-declared default is the simpler, smaller fix.

## Risks / Trade-offs

- [Risk] A category explicitly re-saved through the admin Edit form will always pick a concrete palette color going forward, so this "seeded with a null badge color" state should only ever affect pre-existing/seed data, not new categories. → No mitigation needed; the default-to-"blue" behavior handles that data as long as it exists.
