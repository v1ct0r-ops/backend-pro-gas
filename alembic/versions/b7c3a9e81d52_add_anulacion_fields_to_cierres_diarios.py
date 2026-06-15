"""add_anulacion_fields_to_cierres_diarios

Revision ID: b7c3a9e81d52
Revises: cd266891a1d2
Create Date: 2026-06-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c3a9e81d52'
down_revision: Union[str, Sequence[str], None] = 'cd266891a1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cierres_diarios', sa.Column('anulado', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('cierres_diarios', sa.Column('anulado_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('cierres_diarios', sa.Column('anulado_por_id', sa.Integer(), nullable=True))
    op.add_column('cierres_diarios', sa.Column('motivo_anulacion', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_cierres_anulado_por',
        'cierres_diarios', 'usuarios',
        ['anulado_por_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_cierres_anulado_por', 'cierres_diarios', type_='foreignkey')
    op.drop_column('cierres_diarios', 'motivo_anulacion')
    op.drop_column('cierres_diarios', 'anulado_por_id')
    op.drop_column('cierres_diarios', 'anulado_at')
    op.drop_column('cierres_diarios', 'anulado')
