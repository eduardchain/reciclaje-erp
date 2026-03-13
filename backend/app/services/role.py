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
# Catalogo de permisos del sistema (~45 permisos, 11 modulos)
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

    # Ventas
    ("sales.view", "Ver Ventas", "sales", "Permite ver listado e historial de ventas", 10),
    ("sales.create", "Crear Ventas", "sales", "Permite crear nuevas ventas", 11),
    ("sales.edit", "Editar Ventas", "sales", "Permite editar ventas en estado registrado", 12),
    ("sales.liquidate", "Liquidar Ventas", "sales", "Permite liquidar ventas", 13),
    ("sales.cancel", "Anular Ventas", "sales", "Permite anular ventas", 14),
    ("sales.view_prices", "Ver Precios en Ventas", "sales", "Permite ver precios y totales", 15),

    # Doble Partida
    ("double_entries.view", "Ver Doble Partida", "double_entries", "Permite ver dobles partidas", 20),
    ("double_entries.create", "Crear Doble Partida", "double_entries", "Permite crear dobles partidas", 21),
    ("double_entries.edit", "Editar Doble Partida", "double_entries", "Permite editar dobles partidas", 22),
    ("double_entries.liquidate", "Liquidar Doble Partida", "double_entries", "Permite liquidar dobles partidas", 23),
    ("double_entries.cancel", "Anular Doble Partida", "double_entries", "Permite anular dobles partidas", 24),

    # Inventario
    ("inventory.view", "Ver Inventario", "inventory", "Permite ver cantidades en inventario", 30),
    ("inventory.view_values", "Ver Valores de Inventario", "inventory", "Permite ver valorizacion del inventario", 31),
    ("inventory.adjust", "Ajustar Inventario", "inventory", "Permite hacer ajustes de inventario", 32),
    ("inventory.transfer", "Trasladar entre Bodegas", "inventory", "Permite trasladar material entre bodegas", 33),

    # Materiales
    ("materials.view", "Ver Materiales", "materials", "Permite ver catalogo de materiales", 40),
    ("materials.create", "Crear Materiales", "materials", "Permite crear nuevos materiales", 41),
    ("materials.edit", "Editar Materiales", "materials", "Permite editar materiales existentes", 42),
    ("materials.delete", "Eliminar Materiales", "materials", "Permite eliminar materiales", 43),
    ("materials.view_prices", "Ver Precios de Materiales", "materials", "Permite ver lista de precios", 44),
    ("materials.edit_prices", "Editar Precios de Materiales", "materials", "Permite modificar lista de precios", 45),

    # Transformaciones
    ("transformations.view", "Ver Transformaciones", "transformations", "Permite ver transformaciones", 50),
    ("transformations.create", "Crear Transformaciones", "transformations", "Permite crear transformaciones de material", 51),

    # Terceros
    ("third_parties.view", "Ver Terceros", "third_parties", "Permite ver listado de terceros", 60),
    ("third_parties.create", "Crear Terceros", "third_parties", "Permite crear terceros", 61),
    ("third_parties.edit", "Editar Terceros", "third_parties", "Permite editar terceros", 62),
    ("third_parties.delete", "Eliminar Terceros", "third_parties", "Permite eliminar terceros", 63),
    ("third_parties.view_balance", "Ver Saldos de Terceros", "third_parties", "Permite ver estados de cuenta", 64),

    # Bodegas
    ("warehouses.view", "Ver Bodegas", "warehouses", "Permite ver bodegas", 70),
    ("warehouses.create", "Crear Bodegas", "warehouses", "Permite crear bodegas", 71),
    ("warehouses.edit", "Editar Bodegas", "warehouses", "Permite editar bodegas", 72),

    # Tesoreria
    ("treasury.view", "Ver Tesoreria Completa", "treasury", "Permite ver todas las cuentas y movimientos", 80),
    ("treasury.view_own", "Ver Solo Mi Caja", "treasury", "Permite ver solo la caja asignada", 81),
    ("treasury.create_movements", "Crear Movimientos", "treasury", "Permite crear movimientos de dinero", 82),
    ("treasury.manage_accounts", "Gestionar Cuentas", "treasury", "Permite crear/editar cuentas de dinero", 83),
    ("treasury.manage_expenses", "Gestionar Gastos", "treasury", "Permite gestionar categorias y gastos", 84),
    ("treasury.manage_fixed_assets", "Gestionar Activos Fijos", "treasury", "Permite gestionar activos fijos", 85),

    # Reportes
    ("reports.view", "Ver Reportes", "reports", "Permite ver reportes financieros", 90),
    ("reports.export", "Exportar Reportes", "reports", "Permite exportar reportes a Excel", 91),

    # Administracion
    ("admin.manage_users", "Gestionar Usuarios", "admin", "Permite invitar y gestionar usuarios", 100),
    ("admin.manage_roles", "Gestionar Roles", "admin", "Permite crear y editar roles", 101),
    ("admin.view_audit", "Ver Auditoria", "admin", "Permite ver logs de auditoria", 102),
    ("admin.system_config", "Configuracion del Sistema", "admin", "Permite configurar parametros del sistema", 103),
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


MODULE_DISPLAY_NAMES = {
    "purchases": "Compras",
    "sales": "Ventas",
    "double_entries": "Doble Partida",
    "inventory": "Inventario",
    "materials": "Materiales",
    "transformations": "Transformaciones",
    "third_parties": "Terceros",
    "warehouses": "Bodegas",
    "treasury": "Tesoreria",
    "reports": "Reportes",
    "admin": "Administracion",
}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RoleService:
    """Service para gestion de roles y permisos."""

    def seed_permissions(self, db: Session) -> int:
        """Poblar tabla de permisos si esta vacia. Retorna cantidad creada."""
        existing = db.query(Permission).count()
        if existing > 0:
            return 0

        created = 0
        for code, display_name, module, description, sort_order in PERMISSIONS_CATALOG:
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
        self, db: Session, role_id: UUID, organization_id: UUID
    ) -> bool:
        """Eliminar un rol (solo si no es del sistema y no tiene usuarios)."""
        role = self.get_role_by_id(db, role_id, organization_id)
        if not role:
            return False

        if role.is_system_role:
            raise ValueError("No se puede eliminar un rol del sistema")

        member_count = db.query(OrganizationMember).filter(
            OrganizationMember.role_id == role_id,
        ).count()
        if member_count > 0:
            raise ValueError(
                f"No se puede eliminar: hay {member_count} usuario(s) con este rol"
            )

        db.delete(role)
        db.commit()
        return True

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
