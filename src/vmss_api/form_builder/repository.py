import uuid

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

    async def get_by_key(self, step_id: uuid.UUID, key: str) -> FormField | None:
        stmt = select(FormField).where(
            FormField.step_id == step_id, FormField.key == key, FormField.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


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
