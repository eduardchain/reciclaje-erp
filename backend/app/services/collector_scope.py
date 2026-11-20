"""
Alcance de recolector (SAC: Ingrid / Green Loop).

Plan: docs/planes/plan-sac-recolector-alcance.md v1.3 §3, §4 y §5.

Dos piezas:
- la MARCA de un tercero (`third_parties.collector_id`): «este tercero es de
  ESTE recolector»;
- el ALCANCE de un usuario (`user_collector_scopes`): «este usuario solo opera
  lo de ESE recolector».

🔴 Deny-by-default. Un usuario con alcance solo llega a las rutas de
`SCOPED_ENDPOINTS`; cualquier otra le da 403 «Fuera de tu alcance» en
`get_required_org_context`, aunque su rol tenga el permiso. Una ruta nueva queda
CERRADA para el hasta que alguien la agregue aca, con su filtro y su test (T2b
compara este set contra un set literal escrito en el test).

🔴 El alcance lo decide la FILA: no lo apaga el flag ni lo salta el admin
(T16b/T16c). El superusuario no tiene alcance (`deps.py` le hace return temprano
y el endpoint de alcance rechaza ponerselo, N2).
"""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, exists
from sqlalchemy.orm import Session

from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory
from app.models.user import User, UserCollectorScope

# Prefijo de TODO 403 de alcance (N3): los 403 de permisos y de flag dicen otra
# cosa, asi que un test que busca este prefijo no se satisface por otra puerta.
SCOPE_DENIED_PREFIX = "Fuera de tu alcance"

# Mensaje generico de un payload que mezcla lo suyo con lo ajeno (M1): NO nombra
# lo ajeno — su pantalla no lo muestra, el nombre solo le llegaria a quien arma
# UUIDs a mano.
OUT_OF_SCOPE_PAYLOAD = "Hay un tercero fuera de tu alcance en la solicitud"
# Regla 9e (v1.6): una Entrada que SAC liquido y des-liquido con una compra
# viva de un proveedor ajeno. No nombra al proveedor (M1).
# Regla 9f (v1.6/v1.7): la ultima liquidacion de SAC tuvo retenciones o IVA;
# con alcance no se pueden rehacer (S5), y se perderian en silencio.
RELIQUIDATE_TAXES = (
    "Esta Entrada tuvo retenciones o IVA en su liquidación anterior: "
    "la vuelve a liquidar SAC"
)
RELIQUIDATE_FOREIGN_SUPPLIER = (
    "Esta Entrada tiene una compra de un proveedor fuera de tu alcance: "
    "la vuelve a liquidar SAC"
)

_E = "app.api.v1.endpoints."

# §5.2 — la lista blanca, como `módulo.función` del endpoint que atiende la ruta.
# T2 verifica que cada entrada resuelve a sus rutas montadas exactas; T2b, que
# este set es igual al literal del test.
SCOPED_ENDPOINTS: frozenset[str] = frozenset({
    _E + "roles.get_my_permissions",                              # 1
    _E + "materials.list_materials",                              # 2
    _E + "materials.get_material",                                # 3
    _E + "material_kg_profiles.list_material_kg_profiles",        # 4
    _E + "service_tariffs.get_current_tariffs",                   # 5
    _E + "price_lists.get_all_current_prices",                    # 6
    _E + "inbound_orders.list_inbound_orders",                    # 7
    _E + "inbound_orders.get_inbound_order",                      # 8
    _E + "inbound_orders.liquidate_inbound_order",                # 9
    _E + "third_parties.list_third_parties",                      # 10
    _E + "third_parties.list_suppliers",                          # 11
    _E + "third_parties.find_similar_third_parties",              # 12
    _E + "third_parties.list_payable_providers",                  # 13
    _E + "third_parties.get_third_party",                         # 14
    _E + "third_parties.create_third_party",                      # 15
    _E + "third_party_categories.get_flat_categories",            # 15b (v1.5)
    _E + "purchases.list_purchases",                              # 16
    _E + "purchases.get_purchase",                                # 17
    _E + "attachments.list_attachments",                          # 18
    _E + "attachments.download_attachment",                       # 19
    _E + "money_movements.get_by_third_party",                    # 20
    _E + "money_accounts.list_money_accounts",                    # 21
    _E + "money_accounts.get_money_account",                      # 22
    _E + "money_movements.get_by_account",                        # 23
    _E + "money_movements.list_money_movements",                  # 24
    _E + "money_movements.get_movement",                          # 25
    _E + "money_movements.create_supplier_payment",               # 26
    _E + "money_movements.create_advance_payment",                # 27
    _E + "money_movements.create_payment_to_generic",             # 27b
    _E + "money_movements.annul_movement",                        # 28
    _E + "money_movements.download_evidence",                     # 29
    _E + "money_movements.upload_evidence",                       # 30
})

# Fila 28/30 (H2): los unicos tipos que un usuario con alcance crea, y por eso
# los unicos que anula o a los que les sube evidencia.
OWN_MOVEMENT_TYPES: frozenset[str] = frozenset({
    "payment_to_supplier",
    "advance_payment",
    "payment_to_generic",
})

# Filas 15 y 15b (v1.5): la categoria de conductor con que un usuario con
# alcance crea terceros. UNA sola, por NOMBRE (decision del Coordinador, 20-nov):
# «Empleados» ya existe en produccion (la crea la carga del Sheet, #114) y es
# donde Johana clasifica hoy al conductor de Green Loop. Se compara con
# normalize_entity_name y FALLA CERRADO (#112 D4b): renombrada o desactivada, no
# hay categoria de conductor — nunca «cualquier generic».
SCOPED_CONDUCTOR_CATEGORY = "Empleados"


def scoped_create_categories(db: Session, organization_id: UUID) -> list[ThirdPartyCategory]:
    """UNICA fuente de las categorias con que un usuario con alcance crea un
    tercero: la fila 15b las OFRECE (flat) y la fila 15 las ACEPTA (alta). Con
    dos listas, la pantalla podria ofrecer lo que el servidor rechaza (QA 2).

    Toda categoria ACTIVA de proveedor de material, mas la generic cuyo nombre
    normalizado es «Empleados». Ninguna otra.
    """
    from app.services.retention_entities import normalize_entity_name

    conductor = normalize_entity_name(SCOPED_CONDUCTOR_CATEGORY)
    rows = db.execute(
        select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == organization_id,
            ThirdPartyCategory.is_active.is_(True),
            ThirdPartyCategory.behavior_type.in_(("material_supplier", "generic")),
        )
    ).scalars().all()
    return [
        c for c in rows
        if c.behavior_type == "material_supplier"
        or normalize_entity_name(c.name or "") == conductor
    ]

# §5.7: campos de inventario y costo de SAC que un usuario con alcance no ve.
MATERIAL_HIDDEN_FIELDS: tuple[str, ...] = (
    "current_stock",
    "current_stock_liquidated",
    "current_stock_transit",
    "current_average_cost",
)

# §5.7: la unica tarifa que ve un usuario con alcance.
SCOPED_TARIFF_CODES: frozenset[str] = frozenset({"comision_green_loop"})


def endpoint_key(endpoint) -> str:
    """`módulo.función` del endpoint. Una sola definicion: la usan deps y T2."""
    return f"{endpoint.__module__}.{endpoint.__qualname__}"


def get_scope_row(db: Session, organization_id: UUID, user_id: UUID) -> Optional[UserCollectorScope]:
    """La fila de alcance (a lo sumo una por org y usuario: UNIQUE)."""
    return db.execute(
        select(UserCollectorScope).where(
            UserCollectorScope.organization_id == organization_id,
            UserCollectorScope.user_id == user_id,
        )
    ).scalar_one_or_none()


def scope_of(ctx: Optional[dict]) -> Optional[UUID]:
    """El recolector del alcance del contexto, o None."""
    if not ctx:
        return None
    return ctx.get("collector_scope_id")


def _denied(db: Session, collector_id: UUID, what: str) -> HTTPException:
    collector = db.get(ThirdParty, collector_id)
    name = collector.name if collector else "tu recolector"
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"{SCOPE_DENIED_PREFIX}: {what} (solo puedes operar lo de {name})",
    )


def enforce_route_allowed(db: Session, endpoint, collector_id: UUID) -> None:
    """403 si el endpoint no esta en la lista blanca (deny-by-default)."""
    if endpoint is None or endpoint_key(endpoint) not in SCOPED_ENDPOINTS:
        raise _denied(db, collector_id, "esta pantalla no esta habilitada para tu usuario")


def deny_if_collector_scoped(db: Session, organization_id: UUID, user: User) -> None:
    """§5.0 (H4): las rutas de miembros de la org no pasan por
    `get_required_org_context`; se cierran con esta llamada al entrar. Va
    tambien en las que ya exigen admin: un admin con fila de alcance tampoco
    administra (T16c)."""
    if user.is_superuser:
        return
    row = get_scope_row(db, organization_id, user.id)
    if row is not None:
        raise _denied(db, row.collector_id, "la administracion de miembros no esta habilitada para tu usuario")


# ---------------------------------------------------------------------------
# Predicados de alcance
# ---------------------------------------------------------------------------

def in_scope(tp: Optional[ThirdParty], collector_id: UUID) -> bool:
    """`alc(tp)`: el tercero lleva la marca del recolector del alcance."""
    return tp is not None and tp.collector_id == collector_id


def not_found(label: str = "Recurso") -> HTTPException:
    """404 para un objeto que existe pero esta fuera del alcance (§5.3)."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} no encontrado")


def out_of_scope_payload() -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=OUT_OF_SCOPE_PAYLOAD)


def require_tp_in_scope(db: Session, third_party_id: UUID, collector_id: UUID, label: str = "Tercero") -> ThirdParty:
    """404 si el tercero no existe o no es del alcance."""
    tp = db.get(ThirdParty, third_party_id)
    if not in_scope(tp, collector_id):
        raise not_found(label)
    return tp


def allowed_account_ids(db: Session, ctx: dict) -> set[UUID]:
    """`cta(k)` con alcance: lista vacia = NINGUNA (fail-closed). Sin alcance no
    se usa esta funcion: el comportamiento de hoy (vacia = todas) no cambia
    (decision 1 de Daniel, ciclo propio)."""
    from app.services.organization import get_user_account_assignments
    return set(get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"]))


def require_account_in_scope(db: Session, ctx: dict, account_id: Optional[UUID]) -> None:
    """403 «No tienes acceso a esta cuenta» si la cuenta no esta asignada (§5.3)."""
    if account_id is None or account_id not in allowed_account_ids(db, ctx):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes acceso a esta cuenta")


def accounts_for(db: Session, ctx: dict) -> Optional[list[UUID]]:
    """Cuentas que ve el usuario. Con alcance: las asignadas, y lista vacia =
    NINGUNA aunque el rol sea admin. Sin alcance: el comportamiento de hoy
    (admin o sin asignaciones = None = todas)."""
    if scope_of(ctx) is not None:
        return list(allowed_account_ids(db, ctx))
    if ctx["is_admin"]:
        return None
    from app.services.organization import get_user_account_assignments
    assigned = get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"])
    return assigned if assigned else None


def movement_visible(db: Session, ctx: dict, movement) -> bool:
    """Filas 24, 25 y 29: `cta(account)` o (`account IS NULL` y `alc(tp)`)."""
    scope = scope_of(ctx)
    if movement.account_id is not None:
        return movement.account_id in allowed_account_ids(db, ctx)
    return in_scope(movement.third_party, scope)


def movement_owned(db: Session, ctx: dict, movement) -> bool:
    """Filas 28 y 30 (H2): las cuatro condiciones a la vez. Asi no anula ni le
    cambia la evidencia a un traslado o a un pago que hizo Johana desde su caja."""
    scope = scope_of(ctx)
    return (
        movement.movement_type in OWN_MOVEMENT_TYPES
        and movement.transfer_pair_id is None
        and movement.account_id is not None
        and movement.account_id in allowed_account_ids(db, ctx)
        and in_scope(movement.third_party, scope)
    )


# ---------------------------------------------------------------------------
# Reglas de la marca (§3) y del alcance (§4)
# ---------------------------------------------------------------------------

def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def validate_collector(db: Session, organization_id: UUID, collector_id: UUID) -> ThirdParty:
    """El recolector es de la org, esta activo y es service_provider (#32/#83)."""
    from app.services.third_party import third_party as tp_service
    collector = db.get(ThirdParty, collector_id)
    if collector is None or collector.organization_id != organization_id:
        raise _unprocessable("El recolector no existe en esta organizacion")
    if not collector.is_active:
        raise _unprocessable(f"El recolector '{collector.name}' esta inactivo")
    if not tp_service.has_behavior_type(db, collector.id, ["service_provider"]):
        raise _unprocessable(
            f"El recolector '{collector.name}' debe tener una categoria con comportamiento "
            "'Proveedor de Servicios'"
        )
    if collector.collector_id is not None:
        raise _unprocessable(
            f"'{collector.name}' tiene a su vez un recolector: un recolector no puede estar marcado"
        )
    return collector


def validate_collector_mark(
    db: Session,
    organization_id: UUID,
    third_party_id: Optional[UUID],
    collector_id: UUID,
) -> ThirdParty:
    """§3: reglas de la marca. 422 que nombra el motivo.

    `third_party_id` es None al crear (el tercero aun no existe).
    """
    from app.utils.org_settings import get_org_setting
    if not get_org_setting(db, organization_id, "kg_ledger_enabled"):
        raise _unprocessable("La marca de recolector no esta habilitada para esta organizacion")
    if third_party_id is not None and collector_id == third_party_id:
        raise _unprocessable("Un tercero no puede ser su propio recolector")
    collector = validate_collector(db, organization_id, collector_id)
    if third_party_id is not None:
        is_collector_of_others = db.execute(
            select(exists().where(ThirdParty.collector_id == third_party_id))
        ).scalar()
        if is_collector_of_others:
            raise _unprocessable(
                "Este tercero es recolector de otros terceros: no se le puede poner recolector"
            )
    return collector


def validate_scope_target(
    db: Session,
    organization_id: UUID,
    target_user: User,
    target_is_admin: bool,
    collector_id: UUID,
) -> ThirdParty:
    """§4: a quien se le puede poner alcance."""
    from app.utils.org_settings import get_org_setting
    if not get_org_setting(db, organization_id, "kg_ledger_enabled"):
        raise _unprocessable("El alcance de recolector no esta habilitado para esta organizacion")
    if target_user.is_superuser:
        # N2: deps le hace return temprano al superusuario; la fila nunca
        # restringiria nada, y no se escribe un alcance que no restringe.
        raise _unprocessable("No se le puede poner alcance de recolector a un superusuario")
    if target_is_admin:
        raise _unprocessable(
            "No se le puede poner alcance de recolector a un administrador de la organizacion"
        )
    return validate_collector(db, organization_id, collector_id)


def _join_names(names: list[str]) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " y " + names[-1]


def unmarked_supplier_warnings(
    db: Session,
    organization_id: UUID,
    collector_id: Optional[UUID],
    supplier_ids: Iterable[UUID],
) -> list[str]:
    """D-E2(b) (Daniel, 20-nov ~14:25; plan v1.8 §5.6): quien liquida una
    Entrada con recolector y reparte a un proveedor sin ESA marca recibe un
    aviso en la respuesta. Avisa, no bloquea (#17/#76).

    Solo si el recolector tiene al menos un usuario activo con alcance: sin
    el, nadie deja de ver nada y el aviso seria ruido. Un aviso por
    proveedor, ordenados por nombre, y el texto dice que hacer."""
    supplier_ids = set(supplier_ids)
    if collector_id is None or not supplier_ids:
        return []
    users = db.execute(
        select(User.full_name, User.email)
        .join(UserCollectorScope, UserCollectorScope.user_id == User.id)
        .where(
            UserCollectorScope.organization_id == organization_id,
            UserCollectorScope.collector_id == collector_id,
            User.is_active.is_(True),
        )
    ).all()
    if not users:
        return []
    names = sorted((full_name or email) for full_name, email in users)
    plural = len(names) > 1
    who = _join_names(names)
    collector = db.get(ThirdParty, collector_id)
    cname = collector.name if collector is not None else "su recolector"
    rows = db.execute(
        select(ThirdParty.name, ThirdParty.collector_id)
        .where(ThirdParty.id.in_(supplier_ids))
    ).all()
    return [
        f"El proveedor {name} no tiene la marca de {cname}: {who} "
        f"{'verán' if plural else 'verá'} esta compra en la Entrada, pero no "
        f"{'podrán' if plural else 'podrá'} abrirla. Si es de {cname}, "
        "márcalo en Terceros → Recolector."
        for name, mark in sorted(rows, key=lambda r: r[0])
        if mark != collector_id
    ]


def collector_names(db: Session, ids: Iterable[Optional[UUID]]) -> dict[UUID, str]:
    """Nombres de recolectores en UNA consulta (lookup por pagina, sin N+1)."""
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    rows = db.execute(select(ThirdParty.id, ThirdParty.name).where(ThirdParty.id.in_(wanted))).all()
    return {r.id: r.name for r in rows}
