"""acciones remotas sobre equipos (avisos por correo y desinstalaciones en Intune)

Revision ID: b5d2f8c91e37
Revises: a7c3e1f04b2d
Create Date: 2026-11-11 10:45:58.504920

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

JSON = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

# revision identifiers, used by Alembic.
revision: str = 'b5d2f8c91e37'
down_revision: Union[str, None] = 'a7c3e1f04b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    op.create_table('remote_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('device_id', sa.Integer(), nullable=True),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('alert_id', sa.Integer(), nullable=True),
    sa.Column('recipient', sa.String(length=255), nullable=True),
    sa.Column('requested_by', sa.String(length=255), nullable=False),
    sa.Column('requested_at', sa.DateTime(), nullable=False),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('detail', JSON, nullable=True),
    sa.Column('graph_ref', sa.String(length=120), nullable=True),
    sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], name=op.f('fk_remote_actions_alert_id_alerts')),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], name=op.f('fk_remote_actions_device_id_devices')),
    sa.ForeignKeyConstraint(['product_id'], ['software_products.id'], name=op.f('fk_remote_actions_product_id_software_products')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_remote_actions'))
    )
    with op.batch_alter_table('remote_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_remote_actions_alert_id'), ['alert_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_remote_actions_device_id'), ['device_id'], unique=False)
        batch_op.create_index('ix_remote_actions_kind_status', ['kind', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_remote_actions_product_id'), ['product_id'], unique=False)




def downgrade() -> None:

    with op.batch_alter_table('remote_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_remote_actions_product_id'))
        batch_op.drop_index('ix_remote_actions_kind_status')
        batch_op.drop_index(batch_op.f('ix_remote_actions_device_id'))
        batch_op.drop_index(batch_op.f('ix_remote_actions_alert_id'))

    op.drop_table('remote_actions')

