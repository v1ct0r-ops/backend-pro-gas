"""add volume discount to ventas_revendedor

Revision ID: c7e37aa202f9
Revises: 7b2d77fdad1b
Create Date: 2026-05-02 12:31:32.410063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c7e37aa202f9'
down_revision: Union[str, Sequence[str], None] = '7b2d77fdad1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    return column in inspect(bind).get_columns(table) and \
        any(c['name'] == column for c in inspect(bind).get_columns(table))


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    existing_cols = {c['name'] for c in inspect(bind).get_columns('ventas_revendedor')}

    if 'descuento_pesos_por_kilo' not in existing_cols:
        op.add_column('ventas_revendedor', sa.Column('descuento_pesos_por_kilo', sa.Integer(), nullable=False, server_default='0'))
    if 'monto_descuento_total' not in existing_cols:
        op.add_column('ventas_revendedor', sa.Column('monto_descuento_total', sa.Integer(), nullable=False, server_default='0'))
    if 'total_final' not in existing_cols:
        op.add_column('ventas_revendedor', sa.Column('total_final', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('ventas_revendedor', 'total_final')
    op.drop_column('ventas_revendedor', 'monto_descuento_total')
    op.drop_column('ventas_revendedor', 'descuento_pesos_por_kilo')
