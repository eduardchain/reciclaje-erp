"""SAC Ciclo B addendum (Q-12) — flag receptora en bodegas.

Respuesta de Daniel a "por que la recepcion lista Molino/Transito": las bodegas
internas no reciben de terceros. El check vive en la BODEGA (autoservicio —
"que pasa si manana hay otra?"): default TRUE = toda bodega nace receptora,
las internas se desmarcan una vez. Aditiva server_default true -> las 3 orgs
prod quedan byte-identicas (ninguna pantalla prod consume el campo).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column(
            "is_receiving",
            sa.Boolean(),
            nullable=False,
            server_default="true",
            comment="Recibe material de terceros (false = interna: molino/transito)",
        ),
    )


def downgrade() -> None:
    op.drop_column("warehouses", "is_receiving")
