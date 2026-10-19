import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, NamedTuple

from sqlalchemy import Select, exists, func, insert, literal_column, or_, select, update
from sqlalchemy.orm import aliased, selectinload

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.auth.models import AuditLog, Role, User, UserBranchRole
from vmss_api.auth.rbac_catalog import DELEGATION_ONLY_ROLE_NAMES
from vmss_api.core.database import TenantScopedRepository
from vmss_api.core.schemas import BranchScope, SortOrder
from vmss_api.core.tenancy import branch_filter as _core_branch_filter
from vmss_api.invitations.models import (
    Invitation,
    InvitationQRCode,
    InvitationVehicle,
    InvitationVisitor,
)
from vmss_api.org_structure.models import Branch, Building, Department, Floor
from vmss_api.visitors.models import VisitorCategory


class InvitationExportNames(NamedTuple):
    """Display names `list_for_export` joins in alongside each invitation;
    `None` when the invitation has no such reference.
    """

    branch: str | None
    building: str | None
    department: str | None
    host: str | None
    visitor_category: str | None
    checked_in_by: str | None
    checked_out_by: str | None


# Inline literals (not bound params) so Postgres can match the expression to
# the `ix_invitations_primary_contact_phone_digits` functional index.
PHONE_DIGITS_SQL = r"regexp_replace(invitations.primary_contact_phone, '\D', '', 'g')"


def phone_digits(phone: str) -> str:
    """Digits-only form compared by the phone prefill lookup — must stay in
    step with `PHONE_DIGITS_SQL` (and the migration's functional index)."""
    return "".join(ch for ch in phone if ch.isdigit())


def _branch_filter(branch_scope: BranchScope) -> Any | None:
    """`Invitation.branch_id`-bound wrapper around the shared
    `core.tenancy.branch_filter`.
    """
    return _core_branch_filter(Invitation.branch_id, branch_scope)


def _relevant_to_me_filter(user_id: uuid.UUID, default_host_role_id: uuid.UUID) -> Any:
    """specs/invitations/spec.md "Caller Lists Invitations Relevant to
    Themselves via relevantToMe": invitations where `user_id` is (a) the
    invitation's currently resolved host (`Invitation.host_id`) — set either
    at snapshot time for a legacy host-identified `stepOrder` 0 step, or by
    delegating the now-unconditional role-identified ownership step
    (role-based-invitation-workflow; see the `approvals` capability's
    "Delegating the Ownership Step Also Resolves the Invitation's Host") —
    (b) has been delegated any step, regardless of that step's status, (c)
    currently holds — via branch-scoped `UserBranchRole` at the invitation's
    own branch or company-wide — the role of the invitation's current
    pending, role-identified step, AND that step has no delegate assigned,
    AND that role is not delegation-only (`DELEGATION_ONLY_ROLE_NAMES`,
    i.e. `host`), (d) has personally acted on (approved or rejected) any of the
    invitation's steps, regardless of that step's or the invitation's
    current status, or (e) currently holds — via branch-scoped
    `UserBranchRole` at the invitation's own branch or company-wide — the
    tenant's default host role (`default_host_role_id`, resolved by the
    caller via `org_structure.service.get_default_host_role`), regardless of
    the invitation's current step, that step's delegation state, or the
    invitation's own status.

    (c) closes the gap where a valid role-based approver had no way to find
    their pending work short of the unfiltered branch-wide list
    (checkin-approval-workflow-improvements), but — unlike an earlier
    version of this clause — now DOES require that step be undelegated
    (harden-approval-gate-and-narrow-delegate-visibility): once a
    role-identified step is delegated to a specific person, every holder of
    that role other than the delegate (clause (b)), the resolved host
    (clause (a)), or someone who personally acted on a step (clause (d))
    stops seeing the invitation via (c). Clause (e) is the one exception to
    that narrowing: every holder of the tenant's default host role (e.g.
    Reception) keeps permanent visibility into every invitation regardless
    of delegation or status, since that role owns front-office intake for
    the invitation's entire lifecycle — the same permanence clause (d)
    gives an individual actor, granted here to the whole role instead.

    (c) never matches a delegation-only role's step
    (restrict-delegated-invitation-visibility): no holder of such a role may
    act on or be notified about an undelegated step of it
    (`approvals/service.py::_caller_matches_step`,
    `notifications/service.py::notify_step_approver`), so it must not be
    broadcast to all of them here either — an unassigned `host` step is seen
    only via (a), (d) and (e) until someone delegates it.
    (b), (c), (d), and (e) are expressed as (correlated, where needed)
    subqueries against `invitation_approval_steps`/`user_branch_roles`, not
    a per-invitation loop (query-performance.md §2).
    """
    host_or_delegate_or_actor = or_(
        Invitation.host_id == user_id,
        Invitation.id.in_(
            select(InvitationApprovalStep.invitation_id).where(
                InvitationApprovalStep.deleted_at.is_(None),
                InvitationApprovalStep.delegated_to_user_id == user_id,
            )
        ),
        Invitation.id.in_(
            select(InvitationApprovalStep.invitation_id).where(
                InvitationApprovalStep.deleted_at.is_(None),
                InvitationApprovalStep.acted_by_user_id == user_id,
            )
        ),
    )

    # "Current pending step" mirrors
    # `approvals/repository.py::get_current_pending`: the lowest
    # `step_order` still `pending` for that invitation. `current_step` is
    # aliased so this self-referential lookup doesn't collide with the
    # correlated `min_pending_step_order` subquery below.
    current_step = aliased(InvitationApprovalStep)
    min_pending_step_order = (
        select(func.min(InvitationApprovalStep.step_order))
        .where(
            InvitationApprovalStep.invitation_id == current_step.invitation_id,
            InvitationApprovalStep.status == "pending",
            InvitationApprovalStep.deleted_at.is_(None),
        )
        .scalar_subquery()
    )
    current_role_holder = exists(
        select(current_step.id)
        .join(UserBranchRole, UserBranchRole.role_id == current_step.approver_role_id)
        .join(Role, Role.id == current_step.approver_role_id)
        .where(
            current_step.invitation_id == Invitation.id,
            current_step.deleted_at.is_(None),
            current_step.status == "pending",
            current_step.approver_role_id.is_not(None),
            current_step.step_order == min_pending_step_order,
            current_step.delegated_to_user_id.is_(None),
            func.lower(Role.name).not_in(DELEGATION_ONLY_ROLE_NAMES),
            UserBranchRole.user_id == user_id,
            or_(
                UserBranchRole.branch_id == Invitation.branch_id,
                UserBranchRole.branch_id.is_(None),
            ),
        )
    )
    default_host_role_holder = exists(
        select(UserBranchRole.id).where(
            UserBranchRole.user_id == user_id,
            UserBranchRole.role_id == default_host_role_id,
            or_(
                UserBranchRole.branch_id == Invitation.branch_id,
                UserBranchRole.branch_id.is_(None),
            ),
        )
    )
    return or_(host_or_delegate_or_actor, current_role_holder, default_host_role_holder)


def relevant_to_me_clause(user_id: uuid.UUID, default_host_role_id: uuid.UUID) -> Any:
    """Public handle on the `relevantToMe` predicate for other features — the
    personal dashboard counts over exactly this set so it can never disagree
    with `GET /invitations?relevantToMe=true` (staff-lifecycle-emails-and-
    dashboard-landing design.md D6).
    """
    return _relevant_to_me_filter(user_id, default_host_role_id)


def _list_filters(
    *,
    branch_scope: BranchScope | None,
    relevant_to_user_id: uuid.UUID | None,
    default_host_role_id: uuid.UUID | None,
    status: str | None,
    registration_type: str | None,
    source: str | None,
    search: str | None,
    purpose_of_visit: str | None,
) -> list[Any]:
    """The one filter set `GET /invitations` and `GET /invitations/export`
    share, so the two can't drift (add-invitation-export/design.md
    Decision 2). The branch scope and the `relevantToMe` predicate are
    ANDed when both are given: the list passes exactly one, the export
    always passes its `invitations:export` branch scope and adds
    `relevantToMe` on top.
    """
    filters: list[Any] = []
    if branch_scope is not None:
        branch_filter = _branch_filter(branch_scope)
        if branch_filter is not None:
            filters.append(branch_filter)
    if relevant_to_user_id is not None:
        assert default_host_role_id is not None
        filters.append(_relevant_to_me_filter(relevant_to_user_id, default_host_role_id))
    if status is not None:
        filters.append(Invitation.status == status)
    if registration_type is not None:
        filters.append(Invitation.registration_type == registration_type)
    if source is not None:
        filters.append(Invitation.source == source)
    if purpose_of_visit is not None:
        filters.append(Invitation.purpose_of_visit == purpose_of_visit)
    if search is not None:
        pattern = f"%{search}%"
        filters.append(
            or_(
                Invitation.primary_contact_full_name.ilike(pattern),
                Invitation.tracking_id.ilike(pattern),
            )
        )
    return filters


# add-invitation-export/design.md Decision 3: an export's date range (and
# its sort order) applies to the timestamp matching its `status` filter, or
# to `created_at` when no status is given.
_EXPORT_DATE_COLUMNS: dict[str | None, Any] = {
    "submitted": Invitation.submitted_at,
    "approved": Invitation.approved_at,
    "denied": Invitation.denied_at,
    "checked_in": Invitation.checked_in_at,
    "checked_out": Invitation.checked_out_at,
    "archived": Invitation.archived_at,
    None: Invitation.created_at,
}


@dataclass(frozen=True)
class InvitationExportCriteria:
    """`GET /invitations/export`'s filters as plain values. `starts_at`/
    `ends_before` are the half-open UTC bounds the service derives from the
    tenant-local `dateFrom`/`dateTo` calendar dates.
    """

    branch_scope: BranchScope
    relevant_to_user_id: uuid.UUID | None
    default_host_role_id: uuid.UUID | None
    status: str | None
    registration_type: str | None
    source: str | None
    search: str | None
    purpose_of_visit: str | None
    starts_at: datetime | None
    ends_before: datetime | None


def _export_filters(criteria: InvitationExportCriteria) -> list[Any]:
    filters = _list_filters(
        branch_scope=criteria.branch_scope,
        relevant_to_user_id=criteria.relevant_to_user_id,
        default_host_role_id=criteria.default_host_role_id,
        status=criteria.status,
        registration_type=criteria.registration_type,
        source=criteria.source,
        search=criteria.search,
        purpose_of_visit=criteria.purpose_of_visit,
    )
    column = _EXPORT_DATE_COLUMNS[criteria.status]
    if criteria.starts_at is not None:
        filters.append(column >= criteria.starts_at)
    if criteria.ends_before is not None:
        filters.append(column < criteria.ends_before)
    return filters


def _order_clause(column: Any, sort_order: SortOrder) -> Any:
    return column.desc() if sort_order == SortOrder.desc else column.asc()


# add-invitation-lifecycle-actions/design.md Decision 1: statuses eligible
# for reschedule (before check-in) vs. the "active visit" statuses extend
# and badge issuance operate on.
_RESCHEDULABLE_STATUSES = ("submitted", "approved")
_ACTIVE_STATUSES = ("approved", "checked_in")
# add-qr-checkin-security/design.md "checkInStatus cycles indefinitely":
# once an invitation is validly approved, `status` mirrors whichever of
# these three a QR/tracking-ID check-in transition last set it to — a
# re-entry scan must not be blocked just because `status` currently reads
# `checked_out` from an earlier cycle. `check_in_status` (not `status`)
# is what actually decides entry-vs-exit for the QR gate; this tuple only
# excludes an invitation that was never validly approved (`submitted`/
# `denied`).
_QR_ENTRY_ELIGIBLE_STATUSES = ("approved", "checked_in", "checked_out")


def _reschedule_values(preferred_visit_date: Any, preferred_visit_time: Any) -> dict[str, Any]:
    """Every `SET` in one Postgres `UPDATE` reads the pre-update row, so the
    `previous_*` columns reliably capture the immediately-prior schedule
    (`add-reschedule-history/design.md`).
    """
    return {
        "previous_preferred_visit_date": Invitation.preferred_visit_date,
        "previous_preferred_visit_time": Invitation.preferred_visit_time,
        "preferred_visit_date": preferred_visit_date,
        "preferred_visit_time": preferred_visit_time,
        "rescheduled_at": datetime.now(UTC),
        "reschedule_count": Invitation.reschedule_count + 1,
    }


class InvitationRepository(TenantScopedRepository[Invitation]):
    model = Invitation

    def _with_children(self) -> Select[tuple[Invitation]]:
        """Every read path below eventually serializes `visitors`/`vehicles`
        (`InvitationTrackingOut`), so both are eager-loaded here rather than
        left to the `lazy="raise"` relationships on `Invitation` to blow up
        at response-serialization time (query-performance.md §1).
        """
        return select(Invitation).options(
            selectinload(Invitation.visitors), selectinload(Invitation.vehicles)
        )

    async def get_with_children(self, id_: uuid.UUID) -> Invitation | None:
        stmt = self._with_children().where(Invitation.id == id_, Invitation.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_location(
        self,
        *,
        branch_id: uuid.UUID,
        department_id: uuid.UUID | None,
        building_id: uuid.UUID | None = None,
    ) -> tuple[Branch, Department | None, Building | None]:
        """Resolves an invitation's branch and, when it has a
        `department_id` on file, that department's building via
        `Department.floor_id -> Floor.building_id` — one query with outer
        joins, mirroring `auth/repository.py::list_employees_page`'s
        established cross-package join pattern. `invitations` has no ORM
        `relationship()` onto `org_structure` models (same convention as
        `auth.models.User.department_id`), so this is an explicit join, not
        a `selectinload`/`joinedload` option (query-performance.md §1).

        `deleted_at` is deliberately not filtered on any of the three
        tables here: an invitation shows the branch/department/building it
        actually resolved to at the time, even if one of them has since
        been soft-deleted, rather than silently going blank.

        `branch_id` is a required, FK-enforced column, so the branch row
        is always found — `department_id` is optional and, when `None`,
        the join condition below evaluates to `Department.id IS NULL`,
        correctly yielding no `Department`/`Building` match.
        """
        stmt = (
            select(Branch, Department, Building)
            .select_from(Branch)
            .outerjoin(Department, Department.id == department_id)
            .outerjoin(Floor, Department.floor_id == Floor.id)
            .outerjoin(
                Building,
                Building.id == building_id
                if building_id is not None
                else Floor.building_id == Building.id,
            )
            .where(Branch.id == branch_id)
        )
        row = (await self.session.execute(stmt)).first()
        assert row is not None, f"Invitation references a nonexistent branch {branch_id}"
        branch, department, building = row
        return branch, department, building

    async def approve_if_submitted(
        self, id_: uuid.UUID, *, expires_at: datetime | None = None
    ) -> Invitation | None:
        """Atomic conditional transition: the `UPDATE` only affects a row
        that is still `submitted`, so two concurrent approval requests for
        the same invitation can't both transition it and both dispatch an
        approval notification — a plain read-then-write has no such
        guarantee (see codebase-review-and-e2e-scenario-test/design.md).
        Returns the updated row if this call performed the transition,
        `None` if the invitation was already approved (or lost the race to
        a concurrent call) — the caller treats `None` as "not currently
        submitted", the same 409 the sequential already-approved case
        already raises.

        `expires_at`, when given, overwrites the creation-time TTL with the
        end of the approved visit day (`service.py::_end_of_visit_day_utc`)
        — omitted (`None`) when the invitation has no `preferred_visit_date`
        to align to, leaving the existing value untouched.
        """
        values: dict[str, Any] = {"status": "approved", "approved_at": datetime.now(UTC)}
        if expires_at is not None:
            values["expires_at"] = expires_at
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "submitted")
            .values(**values)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revert_approval_if_eligible(
        self, id_: uuid.UUID, *, user_id: uuid.UUID, reason: str
    ) -> Invitation | None:
        """Atomic conditional `approved` -> `submitted` transition, same
        shape as `approve_if_submitted`. `check_in_status = 'unused'` is
        checked in the same `WHERE` because `status` and `check_in_status`
        are written by different paths — this is the only place a race
        with a concurrent check-in can be closed (add-invitation-approval-
        revert/design.md Decision 2). `None` means "not eligible", which
        the caller turns into a 409.
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status == "approved",
                Invitation.check_in_status == "unused",
            )
            .values(
                status="submitted",
                approved_at=None,
                approval_reverted_at=datetime.now(UTC),
                approval_reverted_by_user_id=user_id,
                approval_revert_reason=reason,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def deny_if_submitted(self, id_: uuid.UUID, *, reason: str) -> Invitation | None:
        """Atomic conditional transition, same shape as `approve_if_submitted`
        — see spec.md "A Submitted Invitation Can Be Denied With a Reason".
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "submitted")
            .values(status="denied", denial_reason=reason, denied_at=datetime.now(UTC))
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_in_if_eligible(
        self, id_: uuid.UUID, *, user_id: uuid.UUID | None, device_pk: uuid.UUID | None = None
    ) -> Invitation | None:
        """Gated on `check_in_status` (not `status` alone), same cycling
        rule as `check_in_by_qr_if_eligible` (allow-multiple-checkins):
        `unused`/`checked_out` are both "currently outside" and admitted,
        `checked_in` is rejected. `status` must still show the invitation
        was validly approved at some point (`approved`/`checked_in`/
        `checked_out` — never `submitted`/`denied`). Both conditions are
        checked in the same atomic `UPDATE` so a concurrent
        override/check-in/check-out can't race past a read-then-write gap,
        the way `approve_if_submitted`'s docstring already explains for the
        approve case. Writing `check_in_status` here (previously left
        untouched by this path) is what closes the cross-path gap where a
        visitor checked in via this endpoint could still be re-admitted
        through the QR endpoint, whose own gate reads `check_in_status`,
        not `status`.

        `user_id` is `None` for the public, tracking-ID-keyed check-in path
        (spec.md "An Approved Invitation Can Be Publicly Checked In By
        Tracking ID") — `checked_in_by_user_id` is nullable at the model
        level for exactly this case.
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.check_in_status.in_(("unused", "checked_out")),
                Invitation.status.in_(_QR_ENTRY_ELIGIBLE_STATUSES),
                Invitation.watchlist_flagged.is_(False),
            )
            .values(
                status="checked_in",
                check_in_status="checked_in",
                checked_in_at=datetime.now(UTC),
                checked_in_by_user_id=user_id,
                check_in_device_id=device_pk,
                check_out_device_id=None,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_in_by_qr_if_eligible(
        self, id_: uuid.UUID, *, today_local: date, device_pk: uuid.UUID | None = None
    ) -> Invitation | None:
        """The `unused`/`checked_out` -> `checked_in` transition driven by
        a QR scan (spec.md "QR Check-In Drives a Cycling
        Checked-In/Checked-Out Lifecycle" / "QR Check-In Enforces
        Invitation Expiry on Every Entry"). `unused` and `checked_out` are
        both "currently outside" — a visitor may have multiple entry
        points during one visit (e.g. leaving for lunch and returning), so
        this admits from either, not just the very first entry
        (design.md "checkInStatus cycles indefinitely; checked_out is not
        terminal"). Every eligibility condition — approved, not
        watchlist-flagged, currently outside, not before the scheduled
        visit date, not expired — is folded into the one atomic `UPDATE`'s
        `WHERE` clause, same race-safety reasoning as `check_in_if_eligible`
        above. `today_local` is the caller's already-resolved tenant-local
        calendar date (qr-checkin-scheduling-photo-email/design.md Decision
        3) — computed once per call, not re-derived per row. Mirrors the
        transition into `status` too, in the same statement, so the
        existing tracking-ID/staff check-in paths and anything reading
        `status` (the "who's inside" emergency report) see a QR-driven
        check-in exactly like any other (design.md "check_in_status kept
        parallel to status, not merged"). There is no authenticated actor
        on this path, so `checked_in_by_user_id` is left at its default
        (`None`).
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.check_in_status.in_(("unused", "checked_out")),
                Invitation.status.in_(_QR_ENTRY_ELIGIBLE_STATUSES),
                Invitation.watchlist_flagged.is_(False),
                or_(
                    Invitation.preferred_visit_date.is_(None),
                    Invitation.preferred_visit_date <= today_local,
                ),
                Invitation.expires_at > datetime.now(UTC),
            )
            .values(
                check_in_status="checked_in",
                status="checked_in",
                checked_in_at=datetime.now(UTC),
                check_in_device_id=device_pk,
                check_out_device_id=None,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_out_by_qr_if_eligible(
        self, id_: uuid.UUID, *, device_pk: uuid.UUID | None = None
    ) -> Invitation | None:
        """The `checked_in` -> `checked_out` transition driven by a second
        scan of the same QR token — deliberately not subject to the expiry
        check `check_in_by_qr_if_eligible` applies on entry (spec.md "QR
        Check-In Enforces Invitation Expiry on Entry Only").
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.check_in_status == "checked_in")
            .values(
                check_in_status="checked_out",
                status="checked_out",
                checked_out_at=datetime.now(UTC),
                checked_out_automatically=False,
                check_out_device_id=device_pk,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def check_out_if_checked_in(
        self, id_: uuid.UUID, *, user_id: uuid.UUID, device_pk: uuid.UUID | None = None
    ) -> Invitation | None:
        """Also writes `check_in_status="checked_out"` (allow-multiple-
        checkins) — this path previously left `check_in_status` untouched,
        so a visitor checked in via `check_in_if_eligible` and checked out
        here would leave `check_in_status` stuck wherever it was, breaking
        both the QR endpoint's own gate (which reads `check_in_status`, not
        `status`) and this same re-entry path's own gate above. Gate
        (`status == "checked_in"`) unchanged.
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "checked_in")
            .values(
                status="checked_out",
                check_in_status="checked_out",
                checked_out_at=datetime.now(UTC),
                checked_out_by_user_id=user_id,
                checked_out_automatically=False,
                check_out_device_id=device_pk,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def auto_check_out_expired(self, *, now: datetime) -> list[uuid.UUID]:
        """Visit-lifecycle sweep (auto-checkout-and-archive-no-shows): closes
        every check-in whose `expires_at` has passed. Matches either status
        column so a legacy row where only one says `checked_in` is still
        closed, and writes both. `checked_out_at` is the expiry, not `now` —
        the real exit time is unknown and sweep lag shouldn't inflate the
        visit (design.md D3). The conditional `WHERE` is what makes a
        redelivered or concurrent sweep a no-op for rows already closed
        (design.md D2).
        """
        stmt = (
            update(Invitation)
            .where(
                or_(
                    Invitation.status == "checked_in",
                    Invitation.check_in_status == "checked_in",
                ),
                Invitation.expires_at <= now,
                Invitation.deleted_at.is_(None),
            )
            .values(
                status="checked_out",
                check_in_status="checked_out",
                checked_out_at=Invitation.expires_at,
                checked_out_automatically=True,
            )
            .returning(Invitation.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def archive_expired_no_shows(self, *, now: datetime) -> list[uuid.UUID]:
        """Visit-lifecycle sweep: an approved invitation never checked in by
        the end of its (possibly extended) `expires_at` becomes `archived`.
        `submitted` rows are deliberately left alone (design.md Non-Goals).
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.status == "approved",
                Invitation.check_in_status == "unused",
                Invitation.expires_at <= now,
                Invitation.deleted_at.is_(None),
            )
            .values(status="archived", archived_at=now)
            .returning(Invitation.id)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def record_system_audit(
        self, invitation_ids: list[uuid.UUID], *, action: str, diff: dict[str, Any]
    ) -> None:
        """Bulk audit rows with no actor, written in the caller's transaction
        so a sweep transition can't commit without its audit entry (design.md
        D2) — unlike `auth/audit.py::record_audit_log`, which opens its own
        session because it runs after a request's session has closed.
        """
        if not invitation_ids:
            return
        await self.session.execute(
            insert(AuditLog),
            [
                {
                    "id": uuid.uuid4(),
                    "actor_user_id": None,
                    "action": action,
                    "entity_type": "invitation",
                    "entity_id": invitation_id,
                    "diff": diff,
                }
                for invitation_id in invitation_ids
            ],
        )

    async def edit_if_eligible(
        self,
        id_: uuid.UUID,
        *,
        allowed_statuses: tuple[str, ...] = _RESCHEDULABLE_STATUSES,
        **changes: Any,
    ) -> Invitation | None:
        """Atomic conditional `UPDATE` backing `PATCH /invitations/{id}/edit`
        (role-based-invitation-workflow), same eligible-status pattern as
        `reschedule_if_eligible`/`extend_if_eligible`. `changes` is whatever
        subset of columns the caller actually supplied — the service layer
        (`invitations/service.py::edit_invitation`) never calls this with an
        empty `changes`, so there is always at least one column in `values()`.
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status.in_(allowed_statuses))
            .values(**changes)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_host_if_exists(
        self, id_: uuid.UUID, *, host_id: uuid.UUID, host_name_or_email: str
    ) -> Invitation | None:
        """Resolves the invitation's host once its ownership step's
        delegation succeeds (`approvals/service.py::delegate_step`,
        role-based-invitation-workflow) — no status guard, since delegation
        can happen while the invitation is still `submitted` regardless of
        which lifecycle stage the ownership step itself is in, and
        re-delegating an already-resolved host must still be able to
        overwrite the prior one.
        """
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_)
            .values(host_id=host_id, host_name_or_email=host_name_or_email)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reschedule_if_eligible(
        self,
        id_: uuid.UUID,
        *,
        preferred_visit_date: Any,
        preferred_visit_time: Any,
        expires_at: datetime | None = None,
    ) -> Invitation | None:
        """`previous_preferred_visit_date`/`_time` are set from
        `Invitation.preferred_visit_date`/`_time` in the same `UPDATE` that
        overwrites those columns — every `SET` clause in one Postgres
        `UPDATE` reads the pre-update row, so this reliably captures the
        immediately-prior schedule rather than the just-written new one
        (`add-reschedule-history/design.md`).

        `expires_at`, when given, realigns expiry to the end of the new
        visit day the same way `approve_if_submitted` does at initial
        approval — the service always supplies it, for `submitted` and
        `approved` alike.
        """
        values = _reschedule_values(preferred_visit_date, preferred_visit_time)
        if expires_at is not None:
            values["expires_at"] = expires_at
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status.in_(_RESCHEDULABLE_STATUSES))
            .values(**values)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reschedule_archived_if_eligible(
        self,
        id_: uuid.UUID,
        *,
        preferred_visit_date: Any,
        preferred_visit_time: Any,
        expires_at: datetime,
    ) -> Invitation | None:
        """The only way out of `archived` (auto-checkout-and-archive-no-shows
        design.md D6): same reschedule-history `SET`s as
        `reschedule_if_eligible`, plus a return to `submitted` with
        `approved_at` cleared, so the visit is reviewed again for its new
        date. `archived_at` is left as history.
        """
        values = _reschedule_values(preferred_visit_date, preferred_visit_time)
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.status == "archived")
            .values(**values, expires_at=expires_at, status="submitted", approved_at=None)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def extend_if_eligible(
        self, id_: uuid.UUID, *, new_expires_at: datetime
    ) -> Invitation | None:
        """The new-expiry-must-be-later check is folded into the `WHERE`
        clause too (`Invitation.expires_at < new_expires_at`), not just
        validated by the caller — so a concurrent extend to a later value
        can't be silently clobbered by a stale, earlier one that started
        first but committed second.
        """
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status.in_(_ACTIVE_STATUSES),
                Invitation.expires_at < new_expires_at,
            )
            .values(expires_at=new_expires_at)
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def issue_badge_if_eligible(
        self, id_: uuid.UUID, *, badge_number: str, badge_storage_key: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(
                Invitation.id == id_,
                Invitation.status.in_(_ACTIVE_STATUSES),
                Invitation.badge_number.is_(None),
            )
            .values(
                badge_number=badge_number,
                badge_storage_key=badge_storage_key,
                badge_issued_at=datetime.now(UTC),
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reprint_badge_if_issued(
        self, id_: uuid.UUID, *, badge_storage_key: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.badge_number.is_not(None))
            .values(
                badge_storage_key=badge_storage_key,
                badge_reprint_count=Invitation.badge_reprint_count + 1,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def override_watchlist_if_flagged(
        self, id_: uuid.UUID, *, user_id: uuid.UUID, reason: str
    ) -> Invitation | None:
        stmt = (
            update(Invitation)
            .where(Invitation.id == id_, Invitation.watchlist_flagged.is_(True))
            .values(
                watchlist_flagged=False,
                watchlist_override_at=datetime.now(UTC),
                watchlist_override_by_user_id=user_id,
                watchlist_override_reason=reason,
            )
            .returning(Invitation)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_badge_number(self, badge_number: str) -> Invitation | None:
        """Backs `_generate_unique_badge_number`'s retry-against-uniqueness
        loop (design.md Decision 4) — same shape as tracking-id generation.
        """
        stmt = select(Invitation).where(Invitation.badge_number == badge_number)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_tracking_id(self, tracking_id: str) -> Invitation | None:
        stmt = self._with_children().where(
            Invitation.tracking_id == tracking_id, Invitation.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_checkin_code(self, code: str) -> Invitation | None:
        stmt = self._with_children().where(
            Invitation.checkin_code == code, Invitation.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_primary_contact_email(self, email: str) -> list[Invitation]:
        """Backs the email-based tracking lookup (spec.md "Public Lookup by
        Email Is Rate-Limited and Minimally Revealing") — no eager-load of
        children here, since that endpoint only ever returns tracking id +
        status, never visitor/vehicle detail.
        """
        stmt = select(Invitation).where(
            Invitation.primary_contact_email == email, Invitation.deleted_at.is_(None)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_latest_by_primary_contact_email(self, email: str) -> Invitation | None:
        """Backs the returning-primary-contact name/email lock
        (`dedupe-repeat-visitor-registrations/design.md` Decision 2) — a
        single `ORDER BY ... LIMIT 1` rather than fetching every prior
        invitation via `list_by_primary_contact_email` and filtering in
        Python, since this runs on every invitation creation.
        """
        stmt = (
            select(Invitation)
            .where(Invitation.primary_contact_email == email, Invitation.deleted_at.is_(None))
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_by_primary_contact_phone(self, phone: str) -> Invitation | None:
        """The phone-fallback counterpart to
        `get_latest_by_primary_contact_email` — only ever consulted when the
        new request has no primary contact email at all (design.md
        Decision 5)."""
        stmt = (
            select(Invitation)
            .where(Invitation.primary_contact_phone == phone, Invitation.deleted_at.is_(None))
            .order_by(Invitation.created_at.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_for_prefill_by_email(
        self, email: str, branch_scope: BranchScope
    ) -> Invitation | None:
        """Backs the staff `lookup-by-email` prefill endpoint
        (`add-invitation-lookup-by-email/design.md`) — a separate method
        from `get_latest_by_primary_contact_email` since that one's
        case-sensitive, branch-unscoped matching is deliberate for the
        create-time dedupe lock it backs, and this endpoint needs different
        semantics: case-insensitive, and scoped to the caller's authorized
        branches.
        """
        filters = [func.lower(Invitation.primary_contact_email) == email.lower()]
        filters.append(Invitation.deleted_at.is_(None))
        branch_filter = _branch_filter(branch_scope)
        if branch_filter is not None:
            filters.append(branch_filter)
        stmt = select(Invitation).where(*filters).order_by(Invitation.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_latest_for_prefill_by_phone(
        self, phone_digits_value: str, branch_scope: BranchScope
    ) -> Invitation | None:
        """Phone counterpart of `get_latest_for_prefill_by_email`, comparing
        digits only (`reception-phone-prefill-lookup/design.md`); the
        expression matches the `ix_invitations_primary_contact_phone_digits`
        functional index.
        """
        filters = [
            literal_column(PHONE_DIGITS_SQL) == phone_digits_value,
            Invitation.primary_contact_phone.is_not(None),
            Invitation.deleted_at.is_(None),
        ]
        branch_filter = _branch_filter(branch_scope)
        if branch_filter is not None:
            filters.append(branch_filter)
        stmt = select(Invitation).where(*filters).order_by(Invitation.created_at.desc()).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_page(
        self,
        *,
        branch_scope: BranchScope | None,
        relevant_to_user_id: uuid.UUID | None = None,
        default_host_role_id: uuid.UUID | None = None,
        status: str | None,
        registration_type: str | None,
        source: str | None,
        search: str | None,
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: SortOrder,
        purpose_of_visit: str | None = None,
    ) -> tuple[list[Invitation], int]:
        """Backs `GET /invitations` (design.md Decision 2) — deliberately no
        `selectinload` of visitors/vehicles here (unlike `_with_children`
        above), since `InvitationListItemOut` doesn't serialize either.

        `relevant_to_user_id`, when given, replaces the branch-scoped filter
        entirely with the caller's personal host/delegate worklist
        (specs/invitations/spec.md "Caller Lists Invitations Relevant to
        Themselves via relevantToMe") — `branch_scope` is ignored in that
        case, per invitation-relevant-to-me-and-delegation/design.md
        "relevantToMe is implemented as a distinct query path, not a
        require_branch_scope variant". `default_host_role_id` is required
        whenever `relevant_to_user_id` is given (the caller resolves it via
        `org_structure.service.get_default_host_role` — see
        harden-approval-gate-and-narrow-delegate-visibility/design.md
        Decision 1) and is otherwise ignored.
        """
        column = {"submitted_at": Invitation.submitted_at, "created_at": Invitation.created_at}[
            sort_by
        ]
        if relevant_to_user_id is not None:
            branch_scope = None
        else:
            assert branch_scope is not None
        filters = _list_filters(
            branch_scope=branch_scope,
            relevant_to_user_id=relevant_to_user_id,
            default_host_role_id=default_host_role_id,
            status=status,
            registration_type=registration_type,
            source=source,
            search=search,
            purpose_of_visit=purpose_of_visit,
        )
        return await super().paginate(
            page=page,
            page_size=page_size,
            order_by=_order_clause(column, sort_order),
            filters=filters,
        )

    async def count_export_rows(
        self,
        criteria: InvitationExportCriteria,
    ) -> int:
        """Visitor rows `GET /invitations/export` would produce — one per
        invitation (its primary contact) plus one per co-visitor — counted
        before anything is loaded, so an over-cap export is rejected without
        doing the work (add-invitation-export/design.md Decision 1).
        """
        conditions = (Invitation.deleted_at.is_(None), *_export_filters(criteria))
        invitation_count = select(func.count()).select_from(Invitation).where(*conditions)
        visitor_count = (
            select(func.count())
            .select_from(InvitationVisitor)
            .join(Invitation, Invitation.id == InvitationVisitor.invitation_id)
            .where(*conditions)
        )
        stmt = select(invitation_count.scalar_subquery() + visitor_count.scalar_subquery())
        return int((await self.session.execute(stmt)).scalar_one())

    async def list_for_export(
        self,
        criteria: InvitationExportCriteria,
    ) -> list[tuple[Invitation, InvitationExportNames]]:
        """Every matching invitation with its co-visitors and vehicles
        eager-loaded and its branch/building/department/host/visitor-category
        and check-in/out staff display names joined in the same query — no
        per-row lookup (query-performance.md §1-2). Newest first by the
        status-matched timestamp (design.md Decision 3).
        """
        column = _EXPORT_DATE_COLUMNS[criteria.status]
        host = aliased(User)
        checked_in_by = aliased(User)
        checked_out_by = aliased(User)
        stmt = (
            select(
                Invitation,
                Branch.name,
                Building.name,
                Department.name,
                host.full_name,
                VisitorCategory.name,
                checked_in_by.full_name,
                checked_out_by.full_name,
            )
            .outerjoin(Branch, Branch.id == Invitation.branch_id)
            .outerjoin(Building, Building.id == Invitation.building_id)
            .outerjoin(Department, Department.id == Invitation.department_id)
            .outerjoin(host, host.id == Invitation.host_id)
            .outerjoin(VisitorCategory, VisitorCategory.id == Invitation.visitor_category_id)
            .outerjoin(checked_in_by, checked_in_by.id == Invitation.checked_in_by_user_id)
            .outerjoin(checked_out_by, checked_out_by.id == Invitation.checked_out_by_user_id)
            .options(selectinload(Invitation.visitors), selectinload(Invitation.vehicles))
            .where(Invitation.deleted_at.is_(None), *_export_filters(criteria))
            .order_by(column.desc().nulls_last(), Invitation.id)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            (
                invitation,
                InvitationExportNames(
                    branch=branch,
                    building=building,
                    department=department,
                    host=host_name,
                    visitor_category=category,
                    checked_in_by=checked_in_name,
                    checked_out_by=checked_out_name,
                ),
            )
            for (
                invitation,
                branch,
                building,
                department,
                host_name,
                category,
                checked_in_name,
                checked_out_name,
            ) in rows
        ]

    async def is_relevant_to(
        self, id_: uuid.UUID, *, user_id: uuid.UUID, default_host_role_id: uuid.UUID
    ) -> bool:
        """Single-row form of `list_page`'s `relevantToMe` predicate, so the
        detail endpoint's participant check can never drift from the worklist
        (restrict-delegated-invitation-visibility/design.md Decision 3).
        """
        stmt = select(
            exists().where(
                Invitation.id == id_,
                Invitation.deleted_at.is_(None),
                _relevant_to_me_filter(user_id, default_host_role_id),
            )
        )
        return bool((await self.session.execute(stmt)).scalar())

    async def get_qr_code(self, invitation_id: uuid.UUID) -> InvitationQRCode | None:
        stmt = select(InvitationQRCode).where(InvitationQRCode.invitation_id == invitation_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_qr_code(self, qr_code: InvitationQRCode) -> None:
        self.session.add(qr_code)

    def add_visitors(self, visitors: list[InvitationVisitor]) -> None:
        """One `session.add_all` for every co-visitor row from a single
        submission — never a per-row `session.add()`/query loop
        (query-performance.md §3).
        """
        self.session.add_all(visitors)

    def add_vehicles(self, vehicles: list[InvitationVehicle]) -> None:
        self.session.add_all(vehicles)
