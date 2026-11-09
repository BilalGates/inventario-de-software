"""detalle de conformidad de Intune en devices

Revision ID: a7c3e1f04b2d
Revises: defceba439ac
Create Date: 2026-11-09 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

revision: str = 'a7c3e1f04b2d'
down_revision: Union[str, None] = 'defceba439ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('devices') as batch_op:
        batch_op.add_column(sa.Column('compliance_details', JSON, nullable=True))
        batch_op.add_column(sa.Column('compliance_checked_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_column('compliance_checked_at')
        batch_op.drop_column('compliance_details')
