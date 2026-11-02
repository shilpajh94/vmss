import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from vmss_api.approvals.models import InvitationApprovalStep
from vmss_api.core.database import TenantScopedRepository


class InvitationApprovalStepRepository(TenantScopedRepository[InvitationApprovalStep]):
    model = InvitationApprovalStep

    async def list_for_invitation(self, invitation_id: uuid.UUID) -> list[InvitationApprovalStep]:
        stmt = (
            select(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .order_by(InvitationApprovalStep.step_order.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_invitations(
        self, invitation_ids: list[uuid.UUID]
    ) -> list[InvitationApprovalStep]:
        """Every live step of several invitations in one query, ordered by
        invitation then `step_order` — the list view's batch counterpart of
        `get_current_pending` + `count_for_invitation` (query-performance.md
        §2: never one query per row)."""
        if not invitation_ids:
            return []
        stmt = (
            select(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id.in_(invitation_ids),
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .order_by(InvitationApprovalStep.invitation_id, InvitationApprovalStep.step_order)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_current_pending(self, invitation_id: uuid.UUID) -> InvitationApprovalStep | None:
        """The single step with the lowest `step_order` still `pending` for
        this invitation — the only step actionable at any given time (specs/
        approvals/spec.md "Steps Are Approved in Strict Order").
        """
        stmt = (
            select(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.status == "pending",
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .order_by(InvitationApprovalStep.step_order.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_for_invitation(self, invitation_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def has_pending_for_invitation(self, invitation_id: uuid.UUID) -> bool:
        """Backs the blanket approve endpoint's "still has a workflow step to
        go through?" guard (design.md Decision 3) — an `EXISTS`-style check,
        not a full count. Deliberately checks for a `pending` step, not
        merely "any step at all": once every snapshotted step has been
        approved, `approvals.service.approve_step`'s own finalization call
        into `approve_invitation` (design.md Decision 2) must be able to
        proceed, even though the invitation still has (all-approved) step
        rows — checking "any step exists" here would wrongly 409 that
        internal call too.
        """
        stmt = (
            select(InvitationApprovalStep.id)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.status == "pending",
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none() is not None

    async def get_first_step(self, invitation_id: uuid.UUID) -> InvitationApprovalStep | None:
        """The step with the lowest `step_order` for this invitation — the
        host-nomination step, whichever step that turns out to be: the
        synthetic `step_order` 0 placeholder when the category had no active
        rules at submission time, or the category's own first configured
        rule otherwise (`invitations/service.py::_build_approval_steps`).
        `step_order` is no longer assumed to start at a literal `0`, so
        callers needing "is this the host-nomination step?" (`approvals/
        service.py::delegate_step`) compare against this instead of a
        hardcoded value.
        """
        stmt = (
            select(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .order_by(InvitationApprovalStep.step_order.asc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_step_order(
        self, invitation_id: uuid.UUID, step_order: int
    ) -> InvitationApprovalStep | None:
        """Looks up an invitation's step by its `step_order` rather than its
        id — used to find the host-identified `stepOrder` 0 step when
        validating a delegation request (`approvals/service.py::delegate_step`).
        """
        stmt = select(InvitationApprovalStep).where(
            InvitationApprovalStep.invitation_id == invitation_id,
            InvitationApprovalStep.step_order == step_order,
            InvitationApprovalStep.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_for_invitation(
        self, invitation_id: uuid.UUID, step_id: uuid.UUID
    ) -> InvitationApprovalStep | None:
        """A step id that exists but belongs to a different invitation is
        treated the same as an unknown step id (specs/approvals/spec.md) —
        both filters are in the same `WHERE`, not checked separately.
        """
        stmt = select(InvitationApprovalStep).where(
            InvitationApprovalStep.id == step_id,
            InvitationApprovalStep.invitation_id == invitation_id,
            InvitationApprovalStep.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def add_steps(self, steps: list[InvitationApprovalStep]) -> None:
        """One `session.add_all` per submission's whole snapshot — never a
        per-row `session.add()` loop (query-performance.md §3).
        """
        self.session.add_all(steps)

    async def approve_if_pending(
        self, step_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> InvitationApprovalStep | None:
        """Atomic conditional transition, same race-safety rationale as
        `InvitationRepository.approve_if_submitted` — two concurrent approve
        requests for the same step can't both pass a status check and both
        advance the workflow.
        """
        stmt = (
            update(InvitationApprovalStep)
            .where(InvitationApprovalStep.id == step_id, InvitationApprovalStep.status == "pending")
            .values(status="approved", acted_by_user_id=user_id, acted_at=datetime.now(UTC))
            .returning(InvitationApprovalStep)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def reject_if_pending(
        self, step_id: uuid.UUID, *, user_id: uuid.UUID
    ) -> InvitationApprovalStep | None:
        stmt = (
            update(InvitationApprovalStep)
            .where(InvitationApprovalStep.id == step_id, InvitationApprovalStep.status == "pending")
            .values(status="rejected", acted_by_user_id=user_id, acted_at=datetime.now(UTC))
            .returning(InvitationApprovalStep)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def delegate_if_eligible(
        self,
        step_id: uuid.UUID,
        *,
        delegated_to_user_id: uuid.UUID,
        delegated_by_user_id: uuid.UUID,
        expected_current_delegate_id: uuid.UUID | None = None,
    ) -> InvitationApprovalStep | None:
        """Atomic conditional transition, same race-safety rationale as
        `approve_if_pending`: the `WHERE` clause is a compare-and-swap on
        the step's *current* delegate (`expected_current_delegate_id` —
        `None` for "not yet delegated", the first-delegation case) as well
        as its `pending` status, so two concurrent delegate/re-delegate
        requests for the same step can't both pass the caller's
        authorization check (evaluated against the delegate value read just
        before this call) and both silently record a delegation — the
        loser's CAS fails and it observes `None`. `None` also covers "no
        longer pending" — the caller (`approvals/service.py::delegate_step`)
        treats either case as 409.
        """
        stmt = (
            update(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.id == step_id,
                InvitationApprovalStep.status == "pending",
                InvitationApprovalStep.delegated_to_user_id.is_(None)
                if expected_current_delegate_id is None
                else InvitationApprovalStep.delegated_to_user_id == expected_current_delegate_id,
            )
            .values(
                delegated_to_user_id=delegated_to_user_id,
                delegated_by_user_id=delegated_by_user_id,
                delegated_at=datetime.now(UTC),
            )
            .returning(InvitationApprovalStep)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_clock(
        self,
        step_id: uuid.UUID,
        *,
        escalates_at: datetime | None,
        auto_approves_at: datetime | None,
    ) -> None:
        """Sets a newly-current step's `escalates_at`/`auto_approves_at` —
        called with values computed in Python from the step's own
        snapshotted minute values (`approvals/service.py::approve_step`),
        when the step before it is approved (specs/approvals/spec.md "A
        later step's timestamps are set when it becomes current").
        """
        stmt = (
            update(InvitationApprovalStep)
            .where(InvitationApprovalStep.id == step_id)
            .values(escalates_at=escalates_at, auto_approves_at=auto_approves_at)
        )
        await self.session.execute(stmt)

    async def reset_all_for_invitation(self, invitation_id: uuid.UUID) -> None:
        """Puts every non-deleted step of `invitation_id` back to `pending`
        with no actor, delegation, or clock — one bulk `UPDATE`, not a
        per-step loop (query-performance.md §3). Backs an approval revert
        (add-invitation-approval-revert/design.md Decision 5); the caller
        then re-activates the first step's clock. Step order, approver
        identity, and the snapshotted minute values are left untouched.
        Returns the number of steps reset (0 for an invitation with no
        workflow).
        """
        stmt = (
            update(InvitationApprovalStep)
            .where(
                InvitationApprovalStep.invitation_id == invitation_id,
                InvitationApprovalStep.deleted_at.is_(None),
            )
            .values(
                status="pending",
                acted_by_user_id=None,
                acted_at=None,
                delegated_to_user_id=None,
                delegated_by_user_id=None,
                delegated_at=None,
                escalates_at=None,
                auto_approves_at=None,
            )
        )
        await self.session.execute(stmt)

    async def activate_current_pending(
        self, invitation_id: uuid.UUID
    ) -> InvitationApprovalStep | None:
        """Starts the clock on the invitation's current pending step (lowest
        `step_order` still `pending`): its `escalates_at`/`auto_approves_at`
        are computed from its own snapshotted minute values relative to
        *now* (specs/approvals/spec.md "A later step's timestamps are set
        when it becomes current"). Shared by `approvals/service.py::
        approve_step` (the next step after an approval) and `invitations/
        service.py::revert_invitation_approval` (step 1 again after a
        reset) — it lives here rather than in either service because
        `approvals.service` already imports `invitations.service`. Returns
        the activated step, or `None` if nothing is pending, so the caller
        can push its approver *after* commit.
        """
        step = await self.get_current_pending(invitation_id)
        if step is None:
            return None
        now = datetime.now(UTC)
        await self.set_clock(
            step.id,
            escalates_at=(
                now + timedelta(minutes=step.escalation_minutes)
                if step.escalation_minutes is not None
                else None
            ),
            auto_approves_at=(
                now + timedelta(minutes=step.auto_approve_minutes)
                if step.auto_approve_minutes is not None
                else None
            ),
        )
        return step
