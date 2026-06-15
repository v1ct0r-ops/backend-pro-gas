"""add indexes for pagination ordering

Revision ID: 2062b51e9fd7
Revises: 63b609a19722
Create Date: 2026-06-13 21:29:21.489632

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2062b51e9fd7'
down_revision: Union[str, Sequence[str], None] = '63b609a19722'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_medias_cargas_fecha", "medias_cargas", ["fecha"], unique=False)
    op.create_index("ix_bitacora_llamadas_fecha_hora", "bitacora_llamadas", ["fecha_hora"], unique=False)
    op.create_index("ix_cierres_diarios_fecha", "cierres_diarios", ["fecha"], unique=False)
    op.create_index("ix_ventas_revendedor_fecha", "ventas_revendedor", ["fecha"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ventas_revendedor_fecha", table_name="ventas_revendedor")
    op.drop_index("ix_cierres_diarios_fecha", table_name="cierres_diarios")
    op.drop_index("ix_bitacora_llamadas_fecha_hora", table_name="bitacora_llamadas")
    op.drop_index("ix_medias_cargas_fecha", table_name="medias_cargas")
