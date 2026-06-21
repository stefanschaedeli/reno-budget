"""SQLAlchemy ORM models.

Importing this package registers every model with :class:`app.core.db.Base`
so that Alembic's ``--autogenerate`` (and the test fixtures) see the full
metadata. Add new modules here when you create them.
"""

from app.models.ai import (  # noqa: F401
    AiArtifact,
    AiArtifactStatus,
    AiSession,
    AiSessionStatus,
    AiStep,
)
from app.models.attachment import (  # noqa: F401
    Attachment,
    AttachmentTargetType,
)
from app.models.audit import (  # noqa: F401
    AuditEvent,
)
from app.models.cost import (  # noqa: F401
    BkpCode,
    CostItem,
    CostItemBkpAllocation,
    CostItemPriority,
    CostItemScope,
    CostItemStatus,
    CostItemUnitAllocation,
)
from app.models.lot import (  # noqa: F401
    Lot,
    LotCostItem,
    LotStatus,
)
from app.models.project import (  # noqa: F401
    Project,
    ProjectStatus,
)
from app.models.quote import (  # noqa: F401
    Quote,
    QuoteStatus,
)
from app.models.supplier import (  # noqa: F401
    Supplier,
)
from app.models.tag import (  # noqa: F401
    Tag,
    TagAssignment,
    TagTargetType,
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
