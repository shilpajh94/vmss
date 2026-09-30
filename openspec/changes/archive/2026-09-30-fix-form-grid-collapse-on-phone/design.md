## Context

The four occurrences follow this pattern:

```
<div class="grid grid-cols-1 sm:grid-cols-2 ...">
  ...fields...
  <div class="col-span-2">…</div>
</div>
```

`col-span-2` compiles to `grid-column: span 2 / span 2`. With one
explicit column, the grid adds an implicit track, sized by
`grid-auto-columns: auto`, to satisfy the span. Every auto-placed item
then flows into two columns. The page never overflows (the tracks shrink
to fit), which is why `screenshot-pages.py`'s horizontal-scroll check
passed.

The staff Register Visitor page is unaffected: `PrimaryContactCard`
doesn't span.

## Goals / Non-Goals

**Goals:**
- correct single-column stacking on phones in the two affected components;
- a guard that catches the pattern at lint time, and at runtime in the
  screenshot pass.

**Non-Goals:** redesigning the form layout, or honouring the admin
`width: half|full` field setting inside `CustomFieldsSection`. That
component still stacks custom fields in one column at every width, which
is existing behaviour.

## Decisions

### 1. `col-span-full`, not `sm:col-span-2`
`col-span-full` (`grid-column: 1 / -1`) spans exactly the explicit
columns at every breakpoint: one on a phone, two from `sm`. It keeps
working if a grid later gains `lg:grid-cols-3`. `sm:col-span-2` would also
fix the phone case, but it hard-codes the column count. Rejected.

### 2. Static guard in `npm run lint`
`scripts/check-grid-spans.mjs` follows `check-brand.mjs`'s shape: plain
Node with no dependency, walking `src/**/*.tsx`. It flags any class token
matching `(^|[\s"'`])col-span-([2-9]|1[0-2])\b` that isn't preceded by a
variant (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`, `max-*:`). It also allows a
line containing `grid-span-ok`, for a genuinely fixed multi-column grid.
The message names the file:line and suggests `col-span-full`.

### 3. Runtime guard in the screenshot pass
At the phone width only (375px, where `grid-cols-1` is the active
column count), `screenshot-pages.py` evaluates:

```js
[...document.querySelectorAll('.grid-cols-1')].filter((el) => {
  const tracks = getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean)
  return tracks.length > 1
})
```

Computed `grid-template-columns` includes implicit tracks, so a
`grid-cols-1` grid showing more than one track is exactly this bug. Each
hit prints `IMPLICIT GRID COLUMNS <path> <tag.class>` and fails the run.

Limits: the wizard's Visitor Info step sits behind OTP, and the modal
needs a click, so the script doesn't reach either. The lint guard is the
primary protection for these two. The runtime check covers the page-level
grids the script does reach. Task 3.1 verifies the two components
directly.

## Risks / Trade-offs

- [The lint regex misses a class built by string concatenation] → The
  codebase uses whole literal classes (a Tailwind requirement anyway).
- [A false positive on an intentionally fixed grid] → The `grid-span-ok`
  opt-out on that line.
