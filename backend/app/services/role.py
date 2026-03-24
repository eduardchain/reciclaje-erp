"""Service para gestion de roles y permisos."""
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.models.permission import Permission
from app.models.role import Role, RolePermission
from app.models.user import OrganizationMember
from app.schemas.role import RoleCreate, RoleUpdate


# ---------------------------------------------------------------------------
# Catalogo de permisos del sistema (~67 permisos, 11 modulos)
# (code, display_name, module, description, sort_order)
# ---------------------------------------------------------------------------

PERMISSIONS_CATALOG = [
    # Compras
    ("purchases.view", "Ver Compras", "purchases", "Permite ver listado e historial de compras", 1),
    ("purchases.create", "Crear Compras", "purchases", "Permite crear nuevas compras", 2),
    ("purchases.edit", "Editar Compras", "purchases", "Permite editar compras en estado registrado", 3),
    ("purchases.liquidate", "Liquidar Compras", "purchases", "Permite liquidar compras y asignar precios", 4),
    ("purchases.cancel", "Anular Compras", "purchases", "Permite anular compras", 5),
    ("purchases.view_prices", "Ver Precios en Compras", "purchases", "Permite ver precios y totales", 6),
    ("purchases.edit_prices", "Editar Precios en Compras", "purchases", "Permite ingresar y modificar precios al crear/editar", 7),

    # Ventas
    ("sales.view", "Ver Ventas", "sales", "Permite ver listado e historial de ventas", 10),
    ("sales.create", "Crear Ventas", "sales", "Permite crear nuevas ventas", 11),
    ("sales.edit", "Editar Ventas", "sales", "Permite editar ventas en estado registrado", 12),
    ("sales.liquidate", "Liquidar Ventas", "sales", "Permite liquidar ventas", 13),
    ("sales.cancel", "Anular Ventas", "sales", "Permite anular ventas", 14),
    ("sales.view_prices", "Ver Precios en Ventas", "sales", "Permite ver precios y totales", 15),
    ("sales.edit_prices", "Editar Precios en Ventas", "sales", "Permite ingresar y modificar precios al crear/editar", 16),
    ("sales.view_profit", "Ver Utilidad en Ventas", "sales", "Permite ver utilidad bruta y neta en ventas", 17),

    # Doble Partida
    ("double_entries.view", "Ver Doble Partida", "double_entries", "Permite ver dobles partidas", 20),
    ("double_entries.create", "Crear Doble Partida", "double_entries", "Permite crear dobles partidas", 21),
    ("double_entries.edit", "Editar Doble Partida", "double_entries", "Permite editar dobles partidas", 22),
    ("double_entries.liquidate", "Liquidar Doble Partida", "double_entries", "Permite liquidar dobles partidas", 23),
    ("double_entries.cancel", "Anular Doble Partida", "double_entries", "Permite anular dobles partidas", 24),
    ("double_entries.view_values", "Ver Valores en Doble Partida", "double_entries", "Permite ver utilidades y margenes", 25),
    ("double_entries.view_profit", "Ver Utilidad en Doble Partida", "double_entries", "Permite ver utilidad y margen en doble partida", 26),

    # Inventario
    ("inventory.view", "Ver Inventario", "inventory", "Permite ver cantidades en inventario", 30),
    ("inventory.view_values", "Ver Valores de Inventario", "inventory", "Permite ver valorizacion del inventario", 31),
    ("inventory.adjust", "Ajustar Inventario", "inventory", "Permite hacer ajustes de inventario", 32),
    ("inventory.transfer", "Trasladar entre Bodegas", "inventory", "Permite trasladar material entre bodegas", 33),
    ("inventory.view_movements", "Ver Movimientos", "inventory", "Permite ver movimientos de inventario", 34),
    ("inventory.view_adjustments", "Ver Ajustes", "inventory", "Permite ver ajustes de inventario", 35),
    ("inventory.view_transit", "Ver En Transito", "inventory", "Permite ver inventario en transito", 36),

    # Materiales
    ("materials.view", "Ver Materiales", "materials", "Permite ver catalogo de materiales", 40),
    ("materials.create", "Crear Materiales", "materials", "Permite crear nuevos materiales", 41),
    ("materials.edit", "Editar Materiales", "materials", "Permite editar materiales existentes", 42),
    ("materials.delete", "Eliminar Materiales", "materials", "Permite eliminar materiales", 43),

    # Transformaciones
    ("transformations.view", "Ver Transformaciones", "transformations", "Permite ver transformaciones", 50),
    ("transformations.create", "Crear Transformaciones", "transformations", "Permite crear transformaciones de material", 51),

    # Terceros
    ("third_parties.view", "Ver Terceros", "third_parties", "Permite ver listado de terceros", 60),
    ("third_parties.create", "Crear Terceros", "third_parties", "Permite crear terceros", 61),
    ("third_parties.edit", "Editar Terceros", "third_parties", "Permite editar terceros", 62),
    ("third_parties.delete", "Eliminar Terceros", "third_parties", "Permite eliminar terceros", 63),
    ("third_parties.view_balance", "Ver Saldos de Terceros", "third_parties", "Permite ver estados de cuenta", 64),

    # Tesoreria
    ("treasury.view_dashboard", "Ver Dashboard Tesoreria", "treasury", "Permite ver dashboard de tesoreria", 80),
    ("treasury.view_movements", "Ver Movimientos", "treasury", "Permite ver movimientos de dinero", 81),
    ("treasury.view_accounts", "Ver Cuentas", "treasury", "Permite ver movimientos por cuenta", 82),
    ("treasury.create_movements", "Crear Movimientos", "treasury", "Permite crear movimientos de dinero", 84),
    ("treasury.manage_fixed_assets", "Gestionar Activos Fijos", "treasury", "Permite gestionar activos fijos", 85),
    ("treasury.view_provisions", "Ver Provisiones", "treasury", "Permite ver provisiones", 86),
    ("treasury.view_liabilities", "Ver Pasivos", "treasury", "Permite ver pasivos", 87),
    ("treasury.view_scheduled", "Ver Gastos Diferidos", "treasury", "Permite ver gastos diferidos", 88),
    ("treasury.view_fixed_assets", "Ver Activos Fijos", "treasury", "Permite ver activos fijos", 89),
    ("treasury.view_statements", "Ver Terceros", "treasury", "Permite ver estados de cuenta de terceros", 90),
    ("treasury.edit_classification", "Editar Clasificacion Gastos", "treasury", "Editar categoria y UN en movimientos de gasto", 92),

    # Reportes
    ("reports.view", "Ver Reportes", "reports", "Permite ver reportes financieros", 100),
    ("reports.export", "Exportar Reportes", "reports", "Permite exportar reportes a Excel", 101),
    ("reports.view_dashboard", "Ver Dashboard", "reports", "Permite ver dashboard de reportes", 102),
    ("reports.view_pnl", "Ver Estado de Resultados", "reports", "Permite ver estado de resultados", 103),
    ("reports.view_cashflow", "Ver Flujo de Caja", "reports", "Permite ver flujo de caja", 104),
    ("reports.view_balance", "Ver Balance General", "reports", "Permite ver balance general", 105),
    ("reports.view_purchases", "Ver Reporte Compras", "reports", "Permite ver reporte de compras", 106),
    ("reports.view_sales", "Ver Reporte Ventas", "reports", "Permite ver reporte de ventas", 107),
    ("reports.view_margins", "Ver Margenes", "reports", "Permite ver analisis de margenes", 108),
    ("reports.view_third_parties", "Ver Saldos Terceros", "reports", "Permite ver saldos de terceros", 109),

    # Configuracion
    ("warehouses.view", "Ver Bodegas", "config", "Permite ver bodegas", 120),
    ("warehouses.create", "Crear Bodegas", "config", "Permite crear bodegas", 121),
    ("warehouses.edit", "Editar Bodegas", "config", "Permite editar bodegas", 122),
    ("treasury.manage_accounts", "Gestionar Cuentas", "config", "Permite crear/editar cuentas de dinero", 123),
    ("config.view_business_units", "Ver Unidades de Negocio", "config", "Permite ver unidades de negocio", 124),
    ("config.manage_business_units", "Gestionar Unidades de Negocio", "config", "Permite crear/editar unidades de negocio", 125),
    ("treasury.manage_expenses", "Gestionar Cat. Gastos", "config", "Permite gestionar categorias de gastos", 126),
    ("materials.view_prices", "Ver Listas de Precios", "config", "Permite ver lista de precios", 127),
    ("materials.edit_prices", "Editar Listas de Precios", "config", "Permite modificar lista de precios", 128),

    # Administracion
    ("admin.manage_users", "Gestionar Usuarios", "admin", "Permite invitar y gestionar usuarios", 200),
    ("admin.manage_roles", "Gestionar Roles", "admin", "Permite crear y editar roles", 201),
    ("admin.view_audit", "Ver Auditoria", "admin", "Permite ver logs de auditoria", 202),
    ("admin.system_config", "Configuracion del Sistema", "admin", "Permite configurar parametros del sistema", 203),
]


# ---------------------------------------------------------------------------
# Roles del sistema con sus permisos
# ---------------------------------------------------------------------------

SYSTEM_ROLES = {
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
            "purchases.view", "purchases.create", "purchases.edit",
            "purchases.liquidate", "purchases.cancel",
            "purchases.view_prices", "purchases.edit_prices",
            "sales.view", "sales.create", "sales.edit",
            "sales.liquidate", "sales.cancel",
            "sales.view_prices", "sales.edit_prices", "sales.view_profit",
            "double_entries.view_values", "double_entries.view_profit",
            "materials.view", "materials.view_prices", "materials.edit_prices",
            "third_parties.view",
            "treasury.view_accounts",
            "treasury.edit_classification",
        ],
    },
    "planillador": {
        "display_name": "Planillador",
        "description": "Doble partida hasta registro (sin liquidar)",
        "permissions": [
            "double_entries.view", "double_entries.create", "double_entries.edit",
            "materials.view", "materials.view_prices",
            "third_parties.view",
        ],
    },
    "admin": {
        "display_name": "Administrador",
        "description": "Acceso completo al sistema",
        "permissions": ["*"],  # Marcador especial: todos los permisos
    },
    "viewer": {
        "display_name": "Solo Lectura",
        "description": "Solo consulta, sin modificaciones",
        "permissions": [
            "purchases.view", "purchases.view_prices",
            "sales.view", "sales.view_prices", "sales.view_profit",
            "double_entries.view", "double_entries.view_values", "double_entries.view_profit",
            "inventory.view", "inventory.view_values",
            "inventory.view_movements", "inventory.view_adjustments", "inventory.view_transit",
            "materials.view", "materials.view_prices",
            "third_parties.view", "third_parties.view_balance",
            "warehouses.view",
            "config.view_business_units",
            "treasury.view_dashboard", "treasury.view_movements", "treasury.view_accounts",
            "treasury.view_provisions", "treasury.view_liabilities",
            "treasury.view_scheduled", "treasury.view_fixed_assets", "treasury.view_statements",
            "reports.view", "reports.export",
            "reports.view_dashboard", "reports.view_pnl", "reports.view_cashflow",
            "reports.view_balance", "reports.view_purchases", "reports.view_sales",
            "reports.view_margins", "reports.view_third_parties",
            "transformations.view",
        ],
    },
}


MODULE_DISPLAY_NAMES = {
    "purchases": "Compras",
    "sales": "Ventas",
    "double_entries": "Doble Partida",
    "inventory": "Inventario",
    "materials": "Materiales",
    "transformations": "Transformaciones",
    "third_parties": "Terceros",
    "treasury": "Tesoreria",
    "reports": "Reportes",
    "config": "Configuracion",
    "admin": "Administracion",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RoleService:
    """Service para gestion de roles y permisos."""

    def seed_permissions(self, db: Session) -> int:
        """Poblar tabla de permisos. Crea solo los que no existen (upsert por code). Retorna cantidad creada."""
        existing_codes = {p.code for p in db.query(Permission.code).all()}

        created = 0
        for code, display_name, module, description, sort_order in PERMISSIONS_CATALOG:
            if code in existing_codes:
                continue
            perm = Permission(
                code=code,
                display_name=display_name,
                module=module,
                description=description,
                sort_order=sort_order,
            )
            db.add(perm)
            created += 1

        db.flush()
        return created

    def create_system_roles_for_org(self, db: Session, organization_id: UUID) -> list[Role]:
        """Crear los 5 roles del sistema para una organizacion."""
        all_permissions = {p.code: p for p in db.query(Permission).all()}

        created_roles = []
        for name, config in SYSTEM_ROLES.items():
            # Verificar si ya existe
            existing = db.query(Role).filter(
                Role.organization_id == organization_id,
                Role.name == name,
            ).first()
            if existing:
                continue

            role = Role(
                organization_id=organization_id,
                name=name,
                display_name=config["display_name"],
                description=config["description"],
                is_system_role=True,
            )
            db.add(role)
            db.flush()

            # Asignar permisos
            if "*" in config["permissions"]:
                for perm in all_permissions.values():
                    db.add(RolePermission(role_id=role.id, permission_id=perm.id))
            else:
                for perm_code in config["permissions"]:
                    if perm_code in all_permissions:
                        db.add(RolePermission(
                            role_id=role.id,
                            permission_id=all_permissions[perm_code].id,
                        ))

            created_roles.append(role)

        db.flush()
        return created_roles

    def get_admin_role_for_org(self, db: Session, organization_id: UUID) -> Optional[Role]:
        """Obtener el rol admin del sistema para una organizacion."""
        return db.query(Role).filter(
            Role.organization_id == organization_id,
            Role.name == "admin",
            Role.is_system_role == True,
        ).first()

    def get_all_permissions(self, db: Session) -> list[Permission]:
        """Obtener todos los permisos ordenados."""
        return db.query(Permission).order_by(Permission.sort_order).all()

    def get_permissions_by_module(self, db: Session) -> list[dict]:
        """Obtener permisos agrupados por modulo para UI."""
        permissions = self.get_all_permissions(db)

        modules: dict = {}
        for perm in permissions:
            if perm.module not in modules:
                modules[perm.module] = {
                    "module": perm.module,
                    "module_display": MODULE_DISPLAY_NAMES.get(perm.module, perm.module),
                    "permissions": [],
                }
            modules[perm.module]["permissions"].append(perm)

        return list(modules.values())

    def get_roles_by_org(self, db: Session, organization_id: UUID) -> list[dict]:
        """Obtener roles de una organizacion con conteos."""
        roles = db.query(Role).options(
            joinedload(Role.permissions),
        ).filter(
            Role.organization_id == organization_id,
        ).order_by(Role.is_system_role.desc(), Role.name).all()

        result = []
        for role in roles:
            member_count = db.query(func.count(OrganizationMember.id)).filter(
                OrganizationMember.role_id == role.id,
            ).scalar()
            result.append({
                "id": role.id,
                "name": role.name,
                "display_name": role.display_name,
                "description": role.description,
                "is_system_role": role.is_system_role,
                "permission_count": len(role.permissions),
                "member_count": member_count or 0,
            })

        return result

    def get_role_by_id(
        self, db: Session, role_id: UUID, organization_id: UUID
    ) -> Optional[Role]:
        """Obtener un rol por ID con permisos cargados."""
        return db.query(Role).options(
            joinedload(Role.permissions).joinedload(RolePermission.permission),
        ).filter(
            Role.id == role_id,
            Role.organization_id == organization_id,
        ).first()

    def create_role(
        self, db: Session, organization_id: UUID, role_in: RoleCreate
    ) -> Role:
        """Crear un rol personalizado."""
        existing = db.query(Role).filter(
            Role.organization_id == organization_id,
            Role.name == role_in.name,
        ).first()
        if existing:
            raise ValueError(f"Ya existe un rol con el nombre '{role_in.name}'")

        role = Role(
            organization_id=organization_id,
            name=role_in.name,
            display_name=role_in.display_name,
            description=role_in.description,
            is_system_role=False,
        )
        db.add(role)
        db.flush()

        if role_in.permission_codes:
            permissions = db.query(Permission).filter(
                Permission.code.in_(role_in.permission_codes),
            ).all()
            for perm in permissions:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

        db.commit()
        db.refresh(role)
        return role

    def update_role(
        self, db: Session, role_id: UUID, organization_id: UUID, role_in: RoleUpdate
    ) -> Optional[Role]:
        """Actualizar un rol (display_name, description, permisos)."""
        role = self.get_role_by_id(db, role_id, organization_id)
        if not role:
            return None

        if role_in.display_name is not None:
            role.display_name = role_in.display_name
        if role_in.description is not None:
            role.description = role_in.description

        if role_in.permission_codes is not None:
            # Reemplazar permisos
            db.query(RolePermission).filter(RolePermission.role_id == role_id).delete()
            permissions = db.query(Permission).filter(
                Permission.code.in_(role_in.permission_codes),
            ).all()
            for perm in permissions:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))

        db.commit()
        db.refresh(role)
        return role

    def delete_role(
        self, db: Session, role_id: UUID, organization_id: UUID,
        reassign_to: UUID | None = None,
    ) -> bool:
        """Eliminar un rol. Si tiene usuarios, requiere reassign_to."""
        role = self.get_role_by_id(db, role_id, organization_id)
        if not role:
            return False

        if role.is_system_role:
            raise ValueError("No se puede eliminar un rol del sistema")

        members = db.query(OrganizationMember).filter(
            OrganizationMember.role_id == role_id,
        ).all()

        if members and not reassign_to:
            raise ValueError(
                f"No se puede eliminar: hay {len(members)} usuario(s) con este rol. "
                "Debe reasignarlos a otro rol."
            )

        if members and reassign_to:
            if reassign_to == role_id:
                raise ValueError("No se puede reasignar al mismo rol que se elimina")

            # Verificar que rol destino existe y es de la org
            target_role = self.get_role_by_id(db, reassign_to, organization_id)
            if not target_role:
                raise ValueError("Rol de destino no encontrado en esta organizacion")

            for member in members:
                member.role_id = reassign_to
            db.flush()

        db.delete(role)
        db.commit()
        return True

    def get_all_permission_codes(self, db: Session) -> set[str]:
        """Retorna todos los codigos de permisos del catalogo."""
        return {p.code for p in db.query(Permission.code).all()}

    def get_user_permissions(
        self, db: Session, user_id: UUID, organization_id: UUID
    ) -> tuple[Optional[Role], set[str]]:
        """
        Obtener rol y set de permisos de un usuario en una organizacion.
        Retorna (role, permissions_set). Si admin, retorna todos los permisos.
        """
        member = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        ).first()

        if not member:
            return None, set()

        role = db.query(Role).options(
            joinedload(Role.permissions).joinedload(RolePermission.permission),
        ).filter(Role.id == member.role_id).first()

        if not role:
            return None, set()

        # Admin tiene todos los permisos
        if role.name == "admin" and role.is_system_role:
            all_codes = {p.code for p in db.query(Permission.code).all()}
            return role, all_codes

        perms = {rp.permission.code for rp in role.permissions}
        return role, perms

    def assign_role_to_user(
        self, db: Session, user_id: UUID, organization_id: UUID, role_id: UUID
    ) -> bool:
        """Asignar un rol a un usuario en una organizacion."""
        member = db.query(OrganizationMember).filter(
            OrganizationMember.user_id == user_id,
            OrganizationMember.organization_id == organization_id,
        ).first()

        if not member:
            return False

        # Verificar que el rol pertenece a la organizacion
        role = db.query(Role).filter(
            Role.id == role_id,
            Role.organization_id == organization_id,
        ).first()

        if not role:
            return False

        member.role_id = role_id
        db.commit()
        return True


role_service = RoleService()
