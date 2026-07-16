"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema. Все изменения — вверх по версии (add_column, create_table, и т.д.)."""
    ${upgrades if upgrades else "    pass"}


def downgrade() -> None:
    """Downgrade schema. Откат изменений, выполненных в upgrade(). Всегда проверяйте обратимость."""
    ${downgrades if downgrades else "    pass"}