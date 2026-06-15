"""add_anulacion_fields_to_medias_cargas

Revision ID: cd266891a1d2
Revises: 240c0072fcc4
Create Date: 2026-06-14 21:03:07.426918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd266891a1d2'
down_revision: Union[str, Sequence[str], None] = '240c0072fcc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('medias_cargas', sa.Column('anulada', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('medias_cargas', sa.Column('anulada_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('medias_cargas', sa.Column('anulado_por_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_medias_cargas_anulado_por_usuarios',
        'medias_cargas', 'usuarios',
        ['anulado_por_id'], ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    op.drop_constraint('fk_medias_cargas_anulado_por_usuarios', 'medias_cargas', type_='foreignkey')
    op.drop_column('medias_cargas', 'anulado_por_id')
    op.drop_column('medias_cargas', 'anulada_at')
    op.drop_column('medias_cargas', 'anulada')
