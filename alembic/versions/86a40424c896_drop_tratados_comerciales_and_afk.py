"""drop_tratados_comerciales_and_afk

Revision ID: 86a40424c896
Revises: c7e37aa202f9
Create Date: 2026-05-02 15:46:00.798113

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision: str = '86a40424c896'
down_revision: Union[str, Sequence[str], None] = 'c7e37aa202f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. Archivar datos de tratados_comerciales antes de eliminar la tabla.
    #    Si la tabla no existe, omitir silenciosamente.
    tables = inspector.get_table_names()

    if 'ventas_revendedor_lineas' in tables:
        # Eliminar FK tratado_id solo si la columna existe
        cols = {c['name'] for c in inspector.get_columns('ventas_revendedor_lineas')}
        if 'tratado_id' in cols:
            # Buscar el nombre real del constraint en pg_constraint (no asumir naming convention)
            fk_name_row = bind.execute(text("""
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'ventas_revendedor_lineas'::regclass
                  AND contype = 'f'
                  AND conname LIKE '%tratado_id%'
                LIMIT 1
            """)).fetchone()
            if fk_name_row:
                op.drop_constraint(fk_name_row[0], 'ventas_revendedor_lineas', type_='foreignkey')
            op.drop_column('ventas_revendedor_lineas', 'tratado_id')

    if 'tratados_comerciales' in tables:
        # Crear tabla de respaldo antes de destruir
        bind.execute(text("""
            CREATE TABLE IF NOT EXISTS tratados_comerciales_backup AS
            SELECT *, NOW() AS backup_timestamp FROM tratados_comerciales
        """))
        idx_names = {i['name'] for i in inspector.get_indexes('tratados_comerciales')}
        if 'ix_tratados_comerciales_rut_cliente' in idx_names:
            op.drop_index('ix_tratados_comerciales_rut_cliente', table_name='tratados_comerciales')
        op.drop_table('tratados_comerciales')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('tratados_comerciales',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('rut_cliente', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('nombre_cliente', sa.VARCHAR(), autoincrement=False, nullable=False),
    sa.Column('formato_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('admin_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('descuento_por_kilo', sa.DOUBLE_PRECISION(precision=53), autoincrement=False, nullable=False),
    sa.Column('vigente', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.ForeignKeyConstraint(['admin_id'], ['usuarios.id'], name=op.f('tratados_comerciales_admin_id_fkey')),
    sa.ForeignKeyConstraint(['formato_id'], ['productos_maestro.id'], name=op.f('tratados_comerciales_formato_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('tratados_comerciales_pkey'))
    )
    op.create_index(op.f('ix_tratados_comerciales_rut_cliente'), 'tratados_comerciales', ['rut_cliente'], unique=False)
    op.add_column('ventas_revendedor_lineas', sa.Column('tratado_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(op.f('ventas_revendedor_lineas_tratado_id_fkey'), 'ventas_revendedor_lineas', 'tratados_comerciales', ['tratado_id'], ['id'])
