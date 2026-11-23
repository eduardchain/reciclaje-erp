"""Cuentas restringidas por usuario (plan cuentas-restringidas v1.2).

Un miembro puede tener cuentas de dinero asignadas (`user_account_assignments`).
Este modulo es el UNICO dueño de la regla "que cuentas puede ver y mover":

- `accounts_for(db, ctx)`: el conjunto permitido. `None` = todas.
  · con alcance de recolector (#129): las asignadas, y vacio = NINGUNA;
  · rol admin de sistema (o superusuario): `None` (D1 de Daniel: la asignacion
    a un admin no restringe nada; la pantalla de Usuarios lo avisa);
  · sin asignaciones: `None`.
- Lecturas: `account_visible` y `account_filter_clause`, construidos sobre el
  mismo predicado (#111: un solo selector, por delegacion).
- Escrituras: un listener `before_flush` (§2.1). En la transaccion de un usuario
  restringido, toda fila de `MoneyAccount` o `MoneyMovement` que se inserta,
  modifica (con cambios netos) o borra tiene que ser de una cuenta permitida; si
  no, 403 que nombra la cuenta. Un movimiento con `account_id` NULL pasa siempre
  (D3). El usuario lo deja `get_required_org_context` en `db.info`; sin el
  (scripts, seeds, servicios llamados directo) el listener no hace nada (T11).

Por que en el flush y no llamada por llamada: las reversas escriben
`current_balance` directo en 7 funciones (annul de tesoreria, obligaciones,
3 de activos fijos, cancel de compra y de venta), mas la evidencia, la
clasificacion y la edicion de cuentas. El flush ve toda escritura, tambien la de
un camino que se escriba mañana. Precedente de listener sobre Session: #106.
"""
from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import event, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement

ACTOR_KEY = "account_actor"
ALLOWED_KEY = "account_allowed"

#: Valor de `source` en el estado de cuenta por tercero para el evento de un
#: movimiento cuya cuenta el usuario no puede ver (C3): sale como texto, sin
#: enlace a un detalle que le daria 404.
RESTRICTED_SOURCE = "money_movement_restricted"


# ---------------------------------------------------------------------------
# El predicado
# ---------------------------------------------------------------------------

def _as_uuid(value) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def accounts_for(db: Session, ctx: dict) -> Optional[list[UUID]]:
    """Cuentas que el usuario puede ver y mover. `None` = todas.

    Con alcance de recolector: las asignadas, y lista vacia = NINGUNA aunque el
    rol sea admin. Sin alcance: admin (o superusuario) = `None` SIN consultar;
    sin asignaciones = `None`; con asignaciones = esas."""
    from app.services.organization import get_user_account_assignments

    if ctx.get("collector_scope_id") is not None:
        return list(set(get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"])))
    if ctx["is_admin"]:
        return None
    assigned = get_user_account_assignments(db, ctx["user_id"], ctx["organization_id"])
    return assigned if assigned else None


def account_visible(db: Session, ctx: dict, account_id) -> bool:
    """Una cuenta NULL siempre es visible (D3); si no, tiene que estar en el conjunto."""
    if account_id is None:
        return True
    allowed = accounts_for(db, ctx)
    return allowed is None or _as_uuid(account_id) in {_as_uuid(a) for a in allowed}


def account_filter_clause(allowed: Optional[Iterable]):
    """Clausula SQL para `MoneyMovement`: cuenta permitida o NULL (D3/C3).
    `None` = sin restriccion (devuelve None: el llamador no agrega nada)."""
    if allowed is None:
        return None
    return or_(MoneyMovement.account_id.in_(list(allowed)), MoneyMovement.account_id.is_(None))


# ---------------------------------------------------------------------------
# El usuario de la transaccion
# ---------------------------------------------------------------------------

def register_actor(db: Session, ctx: dict) -> None:
    """Lo llama `get_required_org_context`: deja el usuario del request en la
    sesion (una por request) y descarta un conjunto calculado antes."""
    db.info[ACTOR_KEY] = {
        "organization_id": ctx["organization_id"],
        "user_id": ctx["user_id"],
        "is_admin": ctx["is_admin"],
        "collector_scope_id": ctx.get("collector_scope_id"),
    }
    db.info.pop(ALLOWED_KEY, None)


def _allowed_for_session(session: Session) -> Optional[set[UUID]]:
    """El conjunto permitido del usuario de la sesion, calculado UNA vez por
    sesion (nunca a nivel de modulo: P13) y solo cuando un flush toca dinero."""
    if ALLOWED_KEY in session.info:
        return session.info[ALLOWED_KEY]
    with session.no_autoflush:
        allowed = accounts_for(session, session.info[ACTOR_KEY])
    result = None if allowed is None else {_as_uuid(a) for a in allowed}
    session.info[ALLOWED_KEY] = result
    return result


# ---------------------------------------------------------------------------
# El listener
# ---------------------------------------------------------------------------

def _by_relationship(movement: MoneyMovement) -> list[tuple[Optional[UUID], Optional[str]]]:
    """Las cuentas que entran o salen por la relacion `account` (added y deleted de
    su historia, que no dispara cargas). Una cuenta agregada sin id es nueva: corta (D6)."""
    out: list[tuple[Optional[UUID], Optional[str]]] = []
    hist = sa_inspect(movement).attrs.account.history
    for account in list(hist.added or ()) + list(hist.deleted or ()):
        if account is None:
            continue
        if account.id is None:
            out.append((None, account.name or "nueva"))
        else:
            out.append((_as_uuid(account.id), None))
    return out


def _touched(session: Session) -> list[tuple[Optional[UUID], Optional[str]]]:
    """(cuenta, nombre si la cuenta es nueva) de cada fila de dinero del flush.

    | Fila           | Insert       | Update (solo con cambios netos) | Delete       |
    | MoneyMovement  | account_id   | la cuenta VIEJA y la NUEVA      | account_id   |
    | MoneyAccount   | id (nueva)   | id                              | id           |

    En un MoneyMovement se mira ademas la relacion `account` (PC1 de QA 2): la FK
    `account_id` se sincroniza DENTRO del flush, despues de before_flush, asi que
    `MoneyMovement(account=K3)` llega aca con `account_id` None, y `mov.account = K3`
    llega con la cuenta vieja. Sin esto, asignar por la relacion pasaba sin mirar.
    """
    out: list[tuple[Optional[UUID], Optional[str]]] = []
    with session.no_autoflush:
        for obj in session.new:
            if isinstance(obj, MoneyMovement):
                if obj.account_id is not None:
                    out.append((_as_uuid(obj.account_id), None))
                out.extend(_by_relationship(obj))
            elif isinstance(obj, MoneyAccount):
                # Una cuenta nueva nunca esta en el conjunto (D6).
                out.append((None, obj.name or "nueva"))
        for obj in session.dirty:
            if not isinstance(obj, (MoneyMovement, MoneyAccount)):
                continue
            if not session.is_modified(obj, include_collections=False):
                continue
            if isinstance(obj, MoneyMovement):
                values = [obj.account_id]
                hist = sa_inspect(obj).attrs.account_id.history
                if hist.has_changes():
                    # La cuenta VIEJA: la historia la tiene solo si el valor se
                    # cargo antes de cambiarlo; la BD la tiene siempre, porque
                    # el flush todavia no corrio (C4).
                    values += list(hist.deleted or ())
                    values.append(session.execute(
                        select(MoneyMovement.account_id).where(MoneyMovement.id == obj.id)
                    ).scalar_one_or_none())
                for value in values:
                    if value is not None:
                        out.append((_as_uuid(value), None))
                out.extend(_by_relationship(obj))
            else:
                out.append((_as_uuid(obj.id), None))
        for obj in session.deleted:
            if isinstance(obj, MoneyMovement):
                if obj.account_id is not None:
                    out.append((_as_uuid(obj.account_id), None))
            elif isinstance(obj, MoneyAccount):
                out.append((_as_uuid(obj.id), None))
    return out


def _forbidden(session: Session, account_id: Optional[UUID], new_name: Optional[str]) -> HTTPException:
    if account_id is None:
        detail = (f"No tienes acceso a la cuenta «{new_name}»: un usuario con cuentas "
                  "asignadas no crea cuentas")
    else:
        # El nombre GUARDADO, de la base y no del objeto de la sesion: en un PATCH
        # de la cuenta el objeto ya trae el nombre nuevo que el usuario intenta
        # ponerle, y el mensaje tiene que nombrar la cuenta que el conoce.
        with session.no_autoflush:
            name = session.execute(
                select(MoneyAccount.name).where(MoneyAccount.id == account_id)
            ).scalar_one_or_none()
        detail = f"No tienes acceso a la cuenta «{name or account_id}»"
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


@event.listens_for(Session, "before_flush")
def _guard_account_writes(session: Session, flush_context, instances) -> None:
    if ACTOR_KEY not in session.info:
        return
    touched = _touched(session)
    if not touched:
        return
    allowed = _allowed_for_session(session)
    if allowed is None:
        return
    for account_id, new_name in touched:
        if account_id is None or account_id not in allowed:
            raise _forbidden(session, account_id, new_name)
