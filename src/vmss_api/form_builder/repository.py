import uuid
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from vmss_api.core.database import TenantScopedRepository
from vmss_api.form_builder.models import FormConfigVersion, FormField, FormStep


class FormStepRepository(TenantScopedRepository[FormStep]):
    model = FormStep

    async def list_for_scope(self, branch_id: uuid.UUID | None) -> list[FormStep]:
        stmt = (
            select(FormStep)
            .where(FormStep.branch_id == branch_id, FormStep.deleted_at.is_(None))
            .order_by(FormStep.order_index.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_key(self, branch_id: uuid.UUID | None, key: str) -> FormStep | None:
        stmt = select(FormStep).where(
            FormStep.branch_id == branch_id, FormStep.key == key, FormStep.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_for_scope(self, branch_id: uuid.UUID | None) -> int:
        return await self.count(FormStep.branch_id == branch_id)


class FormFieldRepository(TenantScopedRepository[FormField]):
    model = FormField

    async def list_for_step(self, step_id: uuid.UUID) -> list[FormField]:
        stmt = (
            select(FormField)
            .where(FormField.step_id == step_id, FormField.deleted_at.is_(None))
            .order_by(FormField.order_index.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_for_steps(self, step_ids: Collection[uuid.UUID]) -> list[FormField]:
        """Batched counterpart of `list_for_step` for a whole form's worth of
        steps in one query (query-performance.md §2) — ordered by
        `(step_id, order_index)` so a caller can group by `step_id` and each
        group is already in the same per-step order `list_for_step` returns.
        """
        if not step_ids:
            return []
        stmt = (
            select(FormField)
            .where(FormField.step_id.in_(step_ids), FormField.deleted_at.is_(None))
            .order_by(FormField.step_id, FormField.order_index.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_key(self, step_id: uuid.UUID, key: str) -> FormField | None:
        stmt = select(FormField).where(
            FormField.step_id == step_id, FormField.key == key, FormField.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_key_in_branch(
        self, branch_id: uuid.UUID | None, key: str, *, exclude_step_id: uuid.UUID | None = None
    ) -> FormField | None:
        """specs/form-builder/spec.md "A Custom Field's Key Is Unique Across
        a Branch's Entire Active Form" — every active field on every active
        step of `branch_id`'s form, optionally excluding one step (the
        target step of a `create_field` call, whose own key collision is
        already checked separately by `get_by_key` regardless of the step's
        active state).
        """
        stmt = (
            select(FormField)
            .join(FormStep, FormField.step_id == FormStep.id)
            .where(
                FormStep.branch_id == branch_id,
                FormStep.is_active.is_(True),
                FormStep.deleted_at.is_(None),
                FormField.key == key,
                FormField.is_active.is_(True),
                FormField.deleted_at.is_(None),
            )
        )
        if exclude_step_id is not None:
            stmt = stmt.where(FormField.step_id != exclude_step_id)
        return (await self.session.execute(stmt)).scalars().first()


class FormConfigVersionRepository:
    """Plain (not `TenantScopedRepository`-based) since a `FormConfigVersion`
    is upserted in place per scope, not soft-deleted/paginated like a normal
    tenant-scoped resource.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_scope(self, branch_id: uuid.UUID | None) -> FormConfigVersion | None:
        stmt = select(FormConfigVersion).where(FormConfigVersion.branch_id == branch_id)
        return (await self.session.execute(stmt)).scalar_one_or_none()
