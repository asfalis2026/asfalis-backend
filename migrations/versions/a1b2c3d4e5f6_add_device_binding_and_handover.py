"""add_device_binding_and_handover

Revision ID: a1b2c3d4e5f6
Revises: 49fa15f2d45d
Create Date: 2026-03-03 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '49fa15f2d45d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_device_bindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('device_imei', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', name='uq_user_device_binding_user_id')
    )

    op.create_table(
        'handset_change_requests',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('old_device_imei', sa.String(length=64), nullable=True),
        sa.Column('new_device_imei', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('eligible_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index('ix_handset_change_user_status', 'handset_change_requests', ['user_id', 'status'])


def downgrade():
    op.drop_index('ix_handset_change_user_status', table_name='handset_change_requests')
    op.drop_table('handset_change_requests')
    op.drop_table('user_device_bindings')
