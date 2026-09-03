## Context

`OrganisationConfig` (`src/domain/entities/organisation-config-schema.ts`) has `passBadgeExpiryDuration: z.string().min(1)` as a required field. `HttpOrganisationConfigRepository.update()` (`src/infrastructure/organisation-config-repository.ts`) maps it to `badgeExpiryDurationMinutes` on the `PUT` payload via a fixed `BADGE_EXPIRY_MINUTES_BY_DURATION` lookup, and the whole `form` object (an `OrganisationConfig`) is what `use-admin-organisation-configs.ts`'s `save()` sends on every "Save Configs" click — there's no separate per-field payload.

## Goals / Non-Goals

**Goals:**
- Remove the badge-expiry control from the Organisation Configs page UI.
- Leave the value the backend has stored for badge expiry untouched by this change.

**Non-Goals:**
- Removing `badgeExpiryDurationMinutes` from the backend's `/company` contract, or deciding its long-term fate there — out of scope; a separate proposal if/when the backend contract itself changes.
- Adding badge-expiry configuration anywhere else in the app.

## Decisions

**Keep `passBadgeExpiryDuration` in the domain schema and repository; remove only the UI control.**

`save()` always submits the full form object, and the field is required (`z.string().min(1)`) in both the domain schema and (implicitly, via the fixed lookup) the outgoing payload shape. Dropping the field from the domain type would mean either sending `badgeExpiryDurationMinutes: null` on every save (silently resetting/clearing a value the backend may still rely on) or hand-rolling a partial-payload path — both are backend-contract changes nobody has asked for here.

Instead: `form.passBadgeExpiryDuration` keeps flowing from `get()` → form state → `save()` → `update()` exactly as today; only `VisitorPolicyCard` stops rendering the control and `admin-organisation-configs.tsx` stops wiring `onBadgeExpiryChange`. The admin can no longer see or change the value from this page, and it is saved back unchanged on every "Save Configs" — functionally equivalent to the field not existing from the admin's point of view, with zero risk to the stored value.

**Alternative considered**: strip the field from `OrganisationConfigSchema` and the `PUT` payload entirely. Rejected for this change because it would require a backend-side decision (is the field still required by `/company`? does omitting/nulling it reset badge expiry to a default for every organisation on next save?) that's outside this proposal's scope.

## Risks / Trade-offs

- [Risk] A future change to `update-organisation-config`'s payload construction could accidentally start sending a stale or wrong `passBadgeExpiryDuration` since nothing in the UI exercises that value anymore → Mitigation: the field stays wired through `get()`/`save()` unchanged, so it's still always the last value the backend returned, never a client-invented one.
- [Risk] If the backend ever makes `badgeExpiryDurationMinutes` optional or removes it, this app will keep sending a now-meaningless value on every save → Mitigation: out of scope here; flag as a follow-up when/if the backend contract changes.
