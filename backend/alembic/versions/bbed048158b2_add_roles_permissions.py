"""add roles and permissions system

Revision ID: bbed048158b2
Revises: d29c1bc28dcb
Create Date: 2026-03-13 12:00:00.000000

Sistema de roles y permisos granulares por organizacion.
- Tabla permissions (catalogo global)
- Tabla roles (por organizacion, con is_system_role)
- Tabla role_permissions (junction M:N)
- Migrar organization_members.role (string) → role_id (UUID FK)
- Todos los miembros existentes → rol admin (seguro)
"""
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa
from app.models.base import GUID

# revision identifiers, used by Alembic.
revision: str = "bbed048158b2"
down_revision: Union[str, None] = "d29c1bc28dcb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Catalogo de permisos
PERMISSIONS = [
    ("purchases.view", "Ver Compras", "purchases", "Permite ver listado e historial de compras", 1),
    ("purchases.create", "Crear Compras", "purchases", "Permite crear nuevas compras", 2),
    ("purchases.edit", "Editar Compras", "purchases", "Permite editar compras en estado registrado", 3),
    ("purchases.liquidate", "Liquidar Compras", "purchases", "Permite liquidar compras y asignar precios", 4),
    ("purchases.cancel", "Anular Compras", "purchases", "Permite anular compras", 5),
    ("purchases.view_prices", "Ver Precios en Compras", "purchases", "Permite ver precios y totales", 6),
    ("sales.view", "Ver Ventas", "sales", "Permite ver listado e historial de ventas", 10),
    ("sales.create", "Crear Ventas", "sales", "Permite crear nuevas ventas", 11),
    ("sales.edit", "Editar Ventas", "sales", "Permite editar ventas en estado registrado", 12),
    ("sales.liquidate", "Liquidar Ventas", "sales", "Permite liquidar ventas", 13),
    ("sales.cancel", "Anular Ventas", "sales", "Permite anular ventas", 14),
    ("sales.view_prices", "Ver Precios en Ventas", "sales", "Permite ver precios y totales", 15),
    ("double_entries.view", "Ver Doble Partida", "double_entries", "Permite ver dobles partidas", 20),
    ("double_entries.create", "Crear Doble Partida", "double_entries", "Permite crear dobles partidas", 21),
    ("double_entries.edit", "Editar Doble Partida", "double_entries", "Permite editar dobles partidas", 22),
    ("double_entries.liquidate", "Liquidar Doble Partida", "double_entries", "Permite liquidar dobles partidas", 23),
    ("double_entries.cancel", "Anular Doble Partida", "double_entries", "Permite anular dobles partidas", 24),
    ("inventory.view", "Ver Inventario", "inventory", "Permite ver cantidades en inventario", 30),
    ("inventory.view_values", "Ver Valores de Inventario", "inventory", "Permite ver valorizacion del inventario", 31),
    ("inventory.adjust", "Ajustar Inventario", "inventory", "Permite hacer ajustes de inventario", 32),
    ("inventory.transfer", "Trasladar entre Bodegas", "inventory", "Permite trasladar material entre bodegas", 33),
    ("materials.view", "Ver Materiales", "materials", "Permite ver catalogo de materiales", 40),
    ("materials.create", "Crear Materiales", "materials", "Permite crear nuevos materiales", 41),
    ("materials.edit", "Editar Materiales", "materials", "Permite editar materiales existentes", 42),
    ("materials.delete", "Eliminar Materiales", "materials", "Permite eliminar materiales", 43),
    ("materials.view_prices", "Ver Precios de Materiales", "materials", "Permite ver lista de precios", 44),
    ("materials.edit_prices", "Editar Precios de Materiales", "materials", "Permite modificar lista de precios", 45),
    ("transformations.view", "Ver Transformaciones", "transformations", "Permite ver transformaciones", 50),
    ("transformations.create", "Crear Transformaciones", "transformations", "Permite crear transformaciones de material", 51),
    ("third_parties.view", "Ver Terceros", "third_parties", "Permite ver listado de terceros", 60),
    ("third_parties.create", "Crear Terceros", "third_parties", "Permite crear terceros", 61),
    ("third_parties.edit", "Editar Terceros", "third_parties", "Permite editar terceros", 62),
    ("third_parties.delete", "Eliminar Terceros", "third_parties", "Permite eliminar terceros", 63),
    ("third_parties.view_balance", "Ver Saldos de Terceros", "third_parties", "Permite ver estados de cuenta", 64),
    ("warehouses.view", "Ver Bodegas", "warehouses", "Permite ver bodegas", 70),
    ("warehouses.create", "Crear Bodegas", "warehouses", "Permite crear bodegas", 71),
    ("warehouses.edit", "Editar Bodegas", "warehouses", "Permite editar bodegas", 72),
    ("treasury.view", "Ver Tesoreria Completa", "treasury", "Permite ver todas las cuentas y movimientos", 80),
    ("treasury.view_own", "Ver Solo Mi Caja", "treasury", "Permite ver solo la caja asignada", 81),
    ("treasury.create_movements", "Crear Movimientos", "treasury", "Permite crear movimientos de dinero", 82),
    ("treasury.manage_accounts", "Gestionar Cuentas", "treasury", "Permite crear/editar cuentas de dinero", 83),
    ("treasury.manage_expenses", "Gestionar Gastos", "treasury", "Permite gestionar categorias y gastos", 84),
    ("treasury.manage_fixed_assets", "Gestionar Activos Fijos", "treasury", "Permite gestionar activos fijos", 85),
    ("reports.view", "Ver Reportes", "reports", "Permite ver reportes financieros", 90),
    ("reports.export", "Exportar Reportes", "reports", "Permite exportar reportes a Excel", 91),
    ("admin.manage_users", "Gestionar Usuarios", "admin", "Permite invitar y gestionar usuarios", 100),
    ("admin.manage_roles", "Gestionar Roles", "admin", "Permite crear y editar roles", 101),
    ("admin.view_audit", "Ver Auditoria", "admin", "Permite ver logs de auditoria", 102),
    ("admin.system_config", "Configuracion del Sistema", "admin", "Permite configurar parametros del sistema", 103),
]

# Roles del sistema con sus permisos
SYSTEM_ROLES = {
    "admin": {
        "display_name": "Administrador",
        "description": "Acceso completo al sistema",
        "permissions": ["*"],
    },
    "bascula": {
        "display_name": "Bascula",
        "description": "Registro de cantidades sin precios",
        "permissions": [
            "purchases.view", "purchases.create",
            "sales.view", "sales.create",
            "inventory.view",
            "materials.view", "materials.create",
            "third_parties.view", "third_parties.create",
            "warehouses.view", "warehouses.create",
            "transformations.view", "transformations.create",
        ],
    },
    "liquidador": {
        "display_name": "Liquidador",
        "description": "Liquidacion de compras/ventas y caja chica",
        "permissions": [
            "purchases.view", "purchases.liquidate", "purchases.view_prices",
            "sales.view", "sales.liquidate", "sales.view_prices",
            "inventory.view",
            "materials.view", "materials.view_prices", "materials.edit_prices",
            "treasury.view_own", "treasury.create_movements",
        ],
    },
    "planillador": {
        "display_name": "Planillador",
        "description": "Doble partida hasta registro (sin liquidar)",
        "permissions": [
            "double_entries.view", "double_entries.create", "double_entries.edit",
            "inventory.view",
            "materials.view",
        ],
    },
    "viewer": {
        "display_name": "Solo Lectura",
        "description": "Solo consulta, sin modificaciones",
        "permissions": [
            "purchases.view", "purchases.view_prices",
            "sales.view", "sales.view_prices",
            "double_entries.view",
            "inventory.view", "inventory.view_values",
            "materials.view", "materials.view_prices",
            "third_parties.view", "third_parties.view_balance",
            "warehouses.view",
            "treasury.view",
            "reports.view", "reports.export",
            "transformations.view",
        ],
    },
}


def upgrade() -> None:
    # 1. Crear tabla permissions
    permissions_table = op.create_table(
        "permissions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_permissions_code", "permissions", ["code"])
    op.create_index("ix_permissions_module", "permissions", ["module"])

    # 2. Crear tabla roles
    op.create_table(
        "roles",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_system_role", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_role_org_name"),
    )
    op.create_index("ix_roles_organization_id", "roles", ["organization_id"])

    # 3. Crear tabla role_permissions
    op.create_table(
        "role_permissions",
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("permission_id", GUID(), sa.ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    # 4. Seed permisos
    conn = op.get_bind()
    perm_ids = {}
    for code, display_name, module, description, sort_order in PERMISSIONS:
        perm_id = str(uuid4())
        perm_ids[code] = perm_id
        conn.execute(
            sa.text(
                "INSERT INTO permissions (id, code, display_name, module, description, sort_order) "
                "VALUES (:id, :code, :display_name, :module, :description, :sort_order)"
            ),
            {
                "id": perm_id,
                "code": code,
                "display_name": display_name,
                "module": module,
                "description": description,
                "sort_order": sort_order,
            },
        )

    # 5. Para cada organizacion existente: crear system roles + asignar permisos
    orgs = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    all_perm_codes = list(perm_ids.keys())

    org_admin_roles = {}  # org_id → admin_role_id

    for (org_id,) in orgs:
        for role_name, config in SYSTEM_ROLES.items():
            role_id = str(uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO roles (id, organization_id, name, display_name, description, is_system_role) "
                    "VALUES (:id, :org_id, :name, :display_name, :description, true)"
                ),
                {
                    "id": role_id,
                    "org_id": org_id,
                    "name": role_name,
                    "display_name": config["display_name"],
                    "description": config["description"],
                },
            )

            if role_name == "admin":
                org_admin_roles[org_id] = role_id

            # Asignar permisos
            if "*" in config["permissions"]:
                codes_to_assign = all_perm_codes
            else:
                codes_to_assign = config["permissions"]

            for perm_code in codes_to_assign:
                if perm_code in perm_ids:
                    conn.execute(
                        sa.text(
                            "INSERT INTO role_permissions (role_id, permission_id) "
                            "VALUES (:role_id, :perm_id)"
                        ),
                        {"role_id": role_id, "perm_id": perm_ids[perm_code]},
                    )

    # 6. Agregar columna role_id (nullable) a organization_members
    op.add_column(
        "organization_members",
        sa.Column("role_id", GUID(), nullable=True),
    )

    # 7. Data migration: ALL existing members → admin role
    for (org_id,) in orgs:
        admin_role_id = org_admin_roles.get(org_id)
        if admin_role_id:
            conn.execute(
                sa.text(
                    "UPDATE organization_members SET role_id = :role_id "
                    "WHERE organization_id = :org_id"
                ),
                {"role_id": admin_role_id, "org_id": org_id},
            )

    # 8. ALTER role_id → NOT NULL
    op.alter_column("organization_members", "role_id", nullable=False)

    # 9. Agregar FK + index
    op.create_foreign_key(
        "fk_org_members_role_id",
        "organization_members",
        "roles",
        ["role_id"],
        ["id"],
    )
    op.create_index("ix_org_members_role_id", "organization_members", ["role_id"])

    # 10. DROP columna role (string) si existe
    try:
        op.drop_column("organization_members", "role")
    except Exception:
        pass  # Puede que no exista si ya se elimino


def downgrade() -> None:
    # Re-agregar columna role string
    op.add_column(
        "organization_members",
        sa.Column("role", sa.String(50), nullable=True),
    )

    # Map role_id → role name string
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE organization_members om "
            "SET role = r.name "
            "FROM roles r "
            "WHERE om.role_id = r.id"
        )
    )
    op.alter_column("organization_members", "role", nullable=False)

    # Drop FK, index, column
    op.drop_index("ix_org_members_role_id", "organization_members")
    op.drop_constraint("fk_org_members_role_id", "organization_members", type_="foreignkey")
    op.drop_column("organization_members", "role_id")

    # Drop tables in order
    op.drop_table("role_permissions")
    op.drop_table("roles")
    op.drop_index("ix_permissions_module", "permissions")
    op.drop_index("ix_permissions_code", "permissions")
    op.drop_table("permissions")
