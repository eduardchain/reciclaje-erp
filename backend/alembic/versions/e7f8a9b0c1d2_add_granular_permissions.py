"""Agregar 16 permisos granulares para sub-tabs

Revision ID: e7f8a9b0c1d2
Revises: f7a3c9e21b04
Create Date: 2026-03-13

"""
from typing import Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "f7a3c9e21b04"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

# 16 nuevos permisos granulares
NEW_PERMISSIONS = [
    # Treasury granulares
    ("treasury.view_provisions", "Ver Provisiones", "treasury", "Permite ver provisiones", 86),
    ("treasury.view_liabilities", "Ver Pasivos", "treasury", "Permite ver pasivos laborales", 87),
    ("treasury.view_scheduled", "Ver Gastos Diferidos", "treasury", "Permite ver gastos diferidos", 88),
    ("treasury.view_fixed_assets", "Ver Activos Fijos", "treasury", "Permite ver activos fijos", 89),
    ("treasury.view_statements", "Ver Estados de Cuenta", "treasury", "Permite ver estados de cuenta de terceros", 90),
    # Inventory granulares
    ("inventory.view_movements", "Ver Movimientos", "inventory", "Permite ver movimientos de inventario", 34),
    ("inventory.view_adjustments", "Ver Ajustes", "inventory", "Permite ver ajustes de inventario", 35),
    ("inventory.view_transit", "Ver En Transito", "inventory", "Permite ver inventario en transito", 36),
    # Reports granulares
    ("reports.view_dashboard", "Ver Dashboard", "reports", "Permite ver dashboard de reportes", 92),
    ("reports.view_pnl", "Ver Estado de Resultados", "reports", "Permite ver estado de resultados", 93),
    ("reports.view_cashflow", "Ver Flujo de Caja", "reports", "Permite ver flujo de caja", 94),
    ("reports.view_balance", "Ver Balance General", "reports", "Permite ver balance general", 95),
    ("reports.view_purchases", "Ver Reporte Compras", "reports", "Permite ver reporte de compras", 96),
    ("reports.view_sales", "Ver Reporte Ventas", "reports", "Permite ver reporte de ventas", 97),
    ("reports.view_margins", "Ver Margenes", "reports", "Permite ver analisis de margenes", 98),
    ("reports.view_third_parties", "Ver Saldos Terceros", "reports", "Permite ver saldos de terceros", 99),
]


def upgrade() -> None:
    """Insertar 16 permisos granulares y asignar a viewer de cada org."""
    conn = op.get_bind()

    # 1. Insertar permisos que no existan
    new_codes = [p[0] for p in NEW_PERMISSIONS]
    existing = conn.execute(
        sa.text("SELECT code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    existing_codes = {row[0] for row in existing}

    for code, display_name, module, description, sort_order in NEW_PERMISSIONS:
        if code not in existing_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                    "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
                ),
                {
                    "id": str(uuid4()),
                    "code": code,
                    "display_name": display_name,
                    "module": module,
                    "description": description,
                    "sort_order": sort_order,
                },
            )

    # 2. Obtener IDs de los 16 permisos
    perms = conn.execute(
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)"),
        {"codes": new_codes},
    ).fetchall()
    perm_map = {row[1]: row[0] for row in perms}

    # 3. Asignar a todos los roles viewer del sistema (todos los granulares)
    viewer_roles = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = 'viewer' AND is_system_role = true"
        )
    ).fetchall()

    for role_row in viewer_roles:
        role_id = role_row[0]
        for code in new_codes:
            if code in perm_map:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                    ),
                    {"role_id": role_id, "perm_id": perm_map[code]},
                )

    # 4. Asignar a liquidador: inventory.view_movements + todos los reports granulares
    liquidador_codes = [
        "inventory.view_movements",
        "reports.view_pnl", "reports.view_cashflow", "reports.view_balance",
        "reports.view_purchases", "reports.view_sales", "reports.view_margins",
        "reports.view_third_parties",
    ]
    liquidador_roles = conn.execute(
        sa.text(
            "SELECT id FROM roles WHERE name = 'liquidador' AND is_system_role = true"
        )
    ).fetchall()

    for role_row in liquidador_roles:
        role_id = role_row[0]
        for code in liquidador_codes:
            if code in perm_map:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :perm_id) ON CONFLICT DO NOTHING"
                    ),
                    {"role_id": role_id, "perm_id": perm_map[code]},
                )


def downgrade() -> None:
    """Quitar 16 permisos granulares."""
    conn = op.get_bind()

    codes = [p[0] for p in NEW_PERMISSIONS]

    # Quitar asignaciones
    perms = conn.execute(
        sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)"),
        {"codes": codes},
    ).fetchall()
    perm_ids = [row[0] for row in perms]

    if perm_ids:
        conn.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id = ANY(:perm_ids)"
            ),
            {"perm_ids": perm_ids},
        )
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = ANY(:perm_ids)"),
            {"perm_ids": perm_ids},
        )
