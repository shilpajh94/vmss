import uuid
from datetime import UTC, datetime

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
