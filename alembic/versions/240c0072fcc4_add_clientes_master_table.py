"""add clientes master table

Revision ID: 240c0072fcc4
Revises: 2062b51e9fd7
Create Date: 2026-06-13 23:58:29.175495

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '240c0072fcc4'
down_revision: Union[str, Sequence[str], None] = '2062b51e9fd7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = inspector.get_table_names()

    if 'clientes' not in existing:
        op.create_table(
            'clientes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('rut', sa.String(), nullable=False),
            sa.Column('nombre', sa.String(), nullable=False),
            sa.Column('email', sa.String(), nullable=True),
            sa.Column('telefono', sa.String(), nullable=True),
            sa.Column('direccion', sa.String(), nullable=True),
            sa.Column('descuento_pesos_por_kilo', sa.Integer(), nullable=False),
            sa.Column('estado', sa.Boolean(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint('descuento_pesos_por_kilo >= 0', name='ck_cliente_descuento_non_negative'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_clientes_rut', 'clientes', ['rut'], unique=True)
        op.create_index('ix_clientes_nombre', 'clientes', ['nombre'], unique=False)
        op.create_index('ix_clientes_estado', 'clientes', ['estado'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_clientes_estado', table_name='clientes')
    op.drop_index('ix_clientes_nombre', table_name='clientes')
    op.drop_index('ix_clientes_rut', table_name='clientes')
    op.drop_table('clientes')
