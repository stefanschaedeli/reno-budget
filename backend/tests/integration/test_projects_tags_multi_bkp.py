"""Phase 11A — Project model, Tag uniqueness, polymorphic TagAssignment,
multi-BKP allocations and uncategorised cost items in the timeline.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from decimal import Decimal

import pytest
from app.models.cost import (
    BkpCode,
    CostItem,
    CostItemBkpAllocation,
    CostItemPriority,
    CostItemScope,
    CostItemStatus,
    CostItemUnitAllocation,
)
from app.models.object import (
    ContributionMode,
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
)
from app.models.project import Project, ProjectStatus
from app.models.tag import Tag, TagAssignment, TagTargetType
from app.models.user import User
from app.services.budgets import UNCATEGORISED_BKP_GROUP, compute_timeline
from app.services.rbac import ObjectAccess
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CURRENT_YEAR = _dt.date.today().year


# ---- shared fixtures ---------------------------------------------------------


async def _seed_bkp(session: AsyncSession) -> None:
    session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
            BkpCode(code="E", parent_code=None, level=1, label_de="Inneres", is_seed=True),
            BkpCode(code="E01", parent_code="E", level=2, label_de="Bad", is_seed=True),
        ]
    )
    await session.commit()


async def _mk_user(session: AsyncSession, email: str) -> User:
    from app.core.security import hash_password

    u = User(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password("TestPasswort-9!ABC"),
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u


async def _mk_object(session: AsyncSession, owner: User) -> tuple[Object, list[Unit]]:
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=30,
        contribution_mode=ContributionMode.YEARLY,
        inflation_rate_percent=Decimal("0"),
        initial_reserve_chf=Decimal("0"),
    )
    session.add(obj)
    await session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=600),
        Unit(object_id=obj.id, label="OG", wertquote_permille=400),
    ]
    for u in units:
        session.add(u)
    session.add(
        ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER)
    )
    await session.commit()
    return obj, units


def _owner_access() -> ObjectAccess:
    return ObjectAccess(
        membership_id=uuid.uuid4(), role=ObjectRole.OWNER, allowed_unit_ids=None
    )


async def _add_item(
    session: AsyncSession,
    *,
    obj: Object,
    units: list[Unit],
    bkp: str | None,
    title: str,
    planned: Decimal,
    planned_year: int,
    bkp_allocations: list[tuple[str, int]] | None = None,
    project_id: uuid.UUID | None = None,
) -> CostItem:
    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code=bkp,
        title=title,
        status=CostItemStatus.PLANNED,
        priority=CostItemPriority.MED,
        scope=CostItemScope.SHARED,
        planned_year=planned_year,
        planned_amount_chf=planned,
        project_id=project_id,
    )
    session.add(item)
    await session.flush()
    for u in units:
        session.add(
            CostItemUnitAllocation(
                cost_item_id=item.id,
                unit_id=u.id,
                share_permille=u.wertquote_permille,
            )
        )
    if bkp_allocations:
        for code, perm in bkp_allocations:
            session.add(
                CostItemBkpAllocation(
                    cost_item_id=item.id, bkp_code=code, share_permille=perm
                )
            )
    await session.commit()
    return item


# ---- Timeline math ----------------------------------------------------------


class TestTimelineWithBkpShares:
    async def test_single_bkp_apportions_to_top_group(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "tlsb@example.ch")
        obj, units = await _mk_object(db_session, owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Heizung",
            planned=Decimal("1000.00"),
            planned_year=CURRENT_YEAR + 2,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 2)
        assert row.by_bkp_group["D"].planned_chf == Decimal("1000.00")

    async def test_multi_bkp_split_apportions_amounts(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "tlmb@example.ch")
        obj, units = await _mk_object(db_session, owner)
        # 600/400 split between D and E.
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp=None,  # multi-BKP mode → singleton column NULL
            title="Refit",
            planned=Decimal("1000.00"),
            planned_year=CURRENT_YEAR + 2,
            bkp_allocations=[("D", 600), ("E", 400)],
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 2)
        assert row.by_bkp_group["D"].planned_chf == Decimal("600.00")
        assert row.by_bkp_group["E"].planned_chf == Decimal("400.00")
        # Row total still equals raw planned amount.
        assert row.planned_chf == Decimal("1000.00")

    async def test_null_bkp_lands_in_uncategorised_bucket(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "tlun@example.ch")
        obj, units = await _mk_object(db_session, owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp=None,
            title="Misc",
            planned=Decimal("750.00"),
            planned_year=CURRENT_YEAR + 1,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 1)
        assert UNCATEGORISED_BKP_GROUP in row.by_bkp_group
        assert row.by_bkp_group[UNCATEGORISED_BKP_GROUP].planned_chf == Decimal(
            "750.00"
        )


# ---- Projects ---------------------------------------------------------------


class TestProjects:
    async def test_project_create_and_link_cost_item(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p-cr@example.ch")
        obj, units = await _mk_object(db_session, owner)

        proj = Project(
            object_id=obj.id,
            name="Badsanierung",
            status=ProjectStatus.PLANNED,
            created_by=owner.id,
        )
        db_session.add(proj)
        await db_session.commit()

        item = await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="E01",
            title="Bad-Item",
            planned=Decimal("100.00"),
            planned_year=CURRENT_YEAR + 1,
            project_id=proj.id,
        )
        assert item.project_id == proj.id

    async def test_project_delete_sets_cost_item_project_id_null(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p-del@example.ch")
        obj, units = await _mk_object(db_session, owner)

        proj = Project(
            object_id=obj.id, name="X", status=ProjectStatus.IDEA
        )
        db_session.add(proj)
        await db_session.commit()

        item = await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Y",
            planned=Decimal("50.00"),
            planned_year=CURRENT_YEAR + 1,
            project_id=proj.id,
        )
        item_id = item.id

        await db_session.delete(proj)
        await db_session.commit()

        refreshed = (
            await db_session.execute(select(CostItem).where(CostItem.id == item_id))
        ).scalar_one()
        assert refreshed.project_id is None
        # Cost item itself survives.
        assert refreshed.title == "Y"


# ---- Tags -------------------------------------------------------------------


class TestTags:
    async def test_tag_unique_per_object_key_value(
        self, db_session: AsyncSession
    ) -> None:
        owner = await _mk_user(db_session, "t-u@example.ch")
        obj, _units = await _mk_object(db_session, owner)

        db_session.add(Tag(object_id=obj.id, key="phase", value="A"))
        await db_session.commit()

        db_session.add(Tag(object_id=obj.id, key="phase", value="A"))
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_same_key_value_allowed_in_different_objects(
        self, db_session: AsyncSession
    ) -> None:
        owner1 = await _mk_user(db_session, "t-o1@example.ch")
        owner2 = await _mk_user(db_session, "t-o2@example.ch")
        obj1, _ = await _mk_object(db_session, owner1)
        obj2, _ = await _mk_object(db_session, owner2)

        db_session.add(Tag(object_id=obj1.id, key="phase", value="A"))
        db_session.add(Tag(object_id=obj2.id, key="phase", value="A"))
        await db_session.commit()


class TestTagAssignments:
    async def test_polymorphic_insert_for_project_and_cost_item(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "ta@example.ch")
        obj, units = await _mk_object(db_session, owner)

        proj = Project(object_id=obj.id, name="P", status=ProjectStatus.IDEA)
        db_session.add(proj)
        await db_session.commit()

        item = await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="C",
            planned=Decimal("10.00"),
            planned_year=CURRENT_YEAR + 1,
        )

        tag = Tag(object_id=obj.id, key="quality", value="premium")
        db_session.add(tag)
        await db_session.commit()

        db_session.add(
            TagAssignment(
                tag_id=tag.id,
                target_type=TagTargetType.PROJECT,
                target_id=proj.id,
            )
        )
        db_session.add(
            TagAssignment(
                tag_id=tag.id,
                target_type=TagTargetType.COST_ITEM,
                target_id=item.id,
            )
        )
        await db_session.commit()

        rows = (
            await db_session.execute(
                select(TagAssignment).where(TagAssignment.tag_id == tag.id)
            )
        ).scalars().all()
        target_types = {r.target_type for r in rows}
        assert target_types == {TagTargetType.PROJECT, TagTargetType.COST_ITEM}
