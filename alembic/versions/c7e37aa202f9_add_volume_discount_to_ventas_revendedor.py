"""add volume discount to ventas_revendedor

Revision ID: c7e37aa202f9
Revises: 7b2d77fdad1b
Create Date: 2026-05-02 12:31:32.410063

Behavior:
- If ventas_revendedor does not exist (Neon/fresh env): CREATE TABLE with all columns.
- If ventas_revendedor exists (Docker local): ADD the 3 discount columns only.
- Same dual logic for ventas_revendedor_lineas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = 'c7e37aa202f9'
down_revision: Union[str, Sequence[str], None] = '7b2d77fdad1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    # ── ventas_revendedor ────────────────────────────────────────────────────
    if 'ventas_revendedor' not in tables:
        op.create_table(
            'ventas_revendedor',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('rut_cliente', sa.String(), nullable=False),
            sa.Column('nombre_cliente', sa.String(), nullable=False),
            sa.Column('fecha', sa.DateTime(), nullable=False),
            sa.Column('total_neto', sa.Integer(), nullable=False),
            sa.Column('descuento_pesos_por_kilo', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('monto_descuento_total', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_final', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('total_iva', sa.Integer(), nullable=False),
            sa.Column('total_bruto', sa.Integer(), nullable=False),
            sa.Column('kilos_totales', sa.Float(), nullable=False),
            sa.Column('usuario_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(
            op.f('ix_ventas_revendedor_rut_cliente'),
            'ventas_revendedor', ['rut_cliente'], unique=False,
        )
    else:
        existing = {c['name'] for c in inspector.get_columns('ventas_revendedor')}
        if 'descuento_pesos_por_kilo' not in existing:
            op.add_column('ventas_revendedor', sa.Column('descuento_pesos_por_kilo', sa.Integer(), nullable=False, server_default='0'))
        if 'monto_descuento_total' not in existing:
            op.add_column('ventas_revendedor', sa.Column('monto_descuento_total', sa.Integer(), nullable=False, server_default='0'))
        if 'total_final' not in existing:
            op.add_column('ventas_revendedor', sa.Column('total_final', sa.Integer(), nullable=False, server_default='0'))

    # ── ventas_revendedor_lineas ─────────────────────────────────────────────
    if 'ventas_revendedor_lineas' not in tables:
        op.create_table(
            'ventas_revendedor_lineas',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('venta_id', sa.Integer(), nullable=False),
            sa.Column('producto_id', sa.Integer(), nullable=False),
            sa.Column('cantidad', sa.Integer(), nullable=False),
            sa.Column('precio_unitario_factura', sa.Integer(), nullable=False),
            sa.Column('kilos_linea', sa.Float(), nullable=False),
            sa.Column('descuento_aplicado', sa.Integer(), nullable=True),
            sa.Column('subtotal_neto', sa.Integer(), nullable=False),
            sa.Column('precio_tipo', sa.String(), nullable=False),
            sa.ForeignKeyConstraint(['producto_id'], ['productos_maestro.id']),
            sa.ForeignKeyConstraint(['venta_id'], ['ventas_revendedor.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = inspector.get_table_names()

    if 'ventas_revendedor_lineas' in tables:
        op.drop_table('ventas_revendedor_lineas')
    if 'ventas_revendedor' in tables:
        op.drop_index(op.f('ix_ventas_revendedor_rut_cliente'), table_name='ventas_revendedor')
        op.drop_table('ventas_revendedor')
