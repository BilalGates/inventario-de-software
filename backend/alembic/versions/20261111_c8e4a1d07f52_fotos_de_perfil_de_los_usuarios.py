"""fotos de perfil de los usuarios

Revision ID: c8e4a1d07f52
Revises: b5d2f8c91e37
Create Date: 2026-11-11 12:32:35.365422

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8e4a1d07f52'
down_revision: Union[str, None] = 'b5d2f8c91e37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo', sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column('photo_type', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('photo_checked_at', sa.DateTime(), nullable=True))




def downgrade() -> None:

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('photo_checked_at')
        batch_op.drop_column('photo_type')
        batch_op.drop_column('photo')


