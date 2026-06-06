"""SQLAlchemy ORM models.

Importing this package registers every model with :class:`app.core.db.Base`
so that Alembic's ``--autogenerate`` (and the test fixtures) see the full
metadata. Add new modules here when you create them.
"""

from app.models.cost import (  # noqa: F401
    BkpCode,
    CostItem,
    CostItemPriority,
    CostItemScope,
    CostItemStatus,
    CostItemUnitAllocation,
)
from app.models.object import (  # noqa: F401
    ContributionMode,
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
    UnitScope,
)
from app.models.user import (  # noqa: F401
    Invitation,
    PasswordResetToken,
    RefreshToken,
    User,
)
