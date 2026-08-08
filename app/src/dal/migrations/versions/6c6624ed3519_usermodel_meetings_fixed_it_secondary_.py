"""UserModel.meetings fixed it secondary tabel on meeting_participants_table

Revision ID: 6c6624ed3519
Revises: 91983037ff5d
Create Date: 2026-08-02 19:17:12.811041

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c6624ed3519'
down_revision: Union[str, Sequence[str], None] = '91983037ff5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
