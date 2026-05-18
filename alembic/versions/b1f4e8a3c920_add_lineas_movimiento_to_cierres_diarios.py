"""add_lineas_movimiento_to_cierres_diarios

Revision ID: b1f4e8a3c920
Revises: 68605517dcbb
Create Date: 2026-05-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1f4e8a3c920'
down_revision: Union[str, Sequence[str], None] = '68605517dcbb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cierres_diarios', sa.Column('lineas_movimiento', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('cierres_diarios', 'lineas_movimiento')
