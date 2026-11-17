"""Planta como proveedor de maquila (plan-sac-planta-como-proveedor).

UN solo punto de emision para las maquilas entre sedes (D2). Hoy hay cuatro
emisores y cinco conceptos:

- traslado CV -> JM al recibir ($1.500/kg de plomo, #84) — `transfer.py`;
- diferencial del crisol al vender plomo puro ($300/kg, #107) — `willard_delivery.py`;
- reparto de la factura a Willard en los abonos ($1.248 y $566/kg, #100/#109)
  — `willard_delivery.py`;
- retorno de dross al horno ($1.500/kg sobre el plomo, #109) — `crucible_charge.py`.

Sin el setting `plant_third_party_id` (las 7 orgs hoy) se emite el par interno
de siempre: gasto en la sede que paga, ingreso en planta, los dos sin tercero
y sin cuenta, enlazados por `transfer_pair_id`. Byte a byte lo de antes.

Con el setting se emite UN `expense_accrual` a nombre de ese tercero: Johana
lleva a la planta como un proveedor al que le debe las maquilas en pesos
(Q-61, WhatsApp del 13-nov). Inventario y kilos NO cambian: su inventario si
incluye planta y crisol.

Lo que este modulo NO decide: SI se emite. Cada emisor conserva sus gates
(`internal_maquila_enabled`, tipo de salida, sede que factura, tarifa). El
setting cambia la FORMA de la emision, nunca su existencia (D2).
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.money_movement import MoneyMovement
from app.models.third_party import ThirdParty
from app.utils.org_settings import get_org_setting

SETTING_KEY = "plant_third_party_id"
# D3: la deuda con planta vive en el pasivo (#14) o como proveedor de
# servicio (#83, comision del recolector). PLANTA JUAN MINA se cargo Pasivo.
ALLOWED_BEHAVIORS = ["liability", "service_provider"]


def _reject(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


def resolve_plant_third_party(db: Session, organization_id: UUID) -> Optional[ThirdParty]:
    """Tercero planta segun el setting, validado FAIL-CLOSED (D3).

    None si el setting no esta puesto (par interno). Si esta puesto y el
    tercero no sirve -> 422 que nombra el setting y el valor. NUNCA se cae en
    silencio al par: eso perderia la deuda sin aviso (#98 D10, #100 D4d).

    Corre antes de escribir nada del documento: los cuatro flujos hacen un
    solo commit al final (D3), asi que el 422 no deja rastro. Quien mueva un
    commit antes de la emision rompe T9.
    """
    raw = get_org_setting(db, organization_id, SETTING_KEY)
    if raw is None:
        return None
    where = (
        f"El setting {SETTING_KEY} de la organizacion apunta a {raw!r}"
    )
    try:
        tp_id = UUID(str(raw))
    except ValueError:
        raise _reject(f"{where}, que no es el id de un tercero. Corrijalo antes de registrar.")
    tp = db.get(ThirdParty, tp_id)
    if tp is None or tp.organization_id != organization_id:
        raise _reject(f"{where}, que no existe en esta organizacion. Corrijalo antes de registrar.")
    if not tp.is_active:
        raise _reject(f"{where} ({tp.name}), que esta inactivo. Corrijalo antes de registrar.")
    if getattr(tp, "is_system_entity", False):
        raise _reject(f"{where} ({tp.name}), que es una entidad de sistema. Corrijalo antes de registrar.")
    from app.services.third_party import CRUDThirdParty

    if not CRUDThirdParty.has_behavior_type(db, tp.id, ALLOWED_BEHAVIORS):
        raise _reject(
            f"{where} ({tp.name}), que no tiene categoria de Pasivo ni de Proveedor de "
            "servicios. Asignele una antes de registrar."
        )
    return tp


def emit_plant_maquila(
    db: Session,
    *,
    organization_id: UUID,
    amount: Decimal,
    date: datetime,
    description: str,
    user_id: Optional[UUID],
    expense_category_id: Optional[UUID],
    source_type: str,
    source_id: UUID,
    tariff_id: Optional[UUID],
    expense_warehouse_id: Optional[UUID],
    income_warehouse_id: Optional[UUID],
    business_unit_id: Optional[UUID] = None,
) -> list[MoneyMovement]:
    """Emite la maquila: par interno (sin setting) o causado a planta (con setting).

    `expense_warehouse_id` es la sede que paga (la que factura) y
    `income_warehouse_id` la planta. Con el setting solo se usa la primera.
    """
    from app.services.money_movement import money_movement

    plant = resolve_plant_third_party(db, organization_id)
    if plant is not None:
        mm = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="expense_accrual",
            amount=amount,
            account_id=None,
            date=date,
            description=description,
            user_id=user_id,
            third_party_id=plant.id,
            expense_category_id=expense_category_id,
            business_unit_id=business_unit_id,
            source_type=source_type,
            source_id=source_id,
            tariff_id=tariff_id,
            warehouse_id=expense_warehouse_id,
        )
        # O1: _create_movement NO aplica efectos. Mismo patron que la comision
        # del recolector (#83, purchase.py:1837); la reversa es la rama
        # expense_accrual (+=) de money_movement._reverse_effects.
        plant.current_balance -= amount
        return [mm]

    mm_exp = money_movement._create_movement(
        db=db,
        organization_id=organization_id,
        movement_type="internal_maquila_expense",
        amount=amount,
        account_id=None,
        date=date,
        description=description,
        user_id=user_id,
        expense_category_id=expense_category_id,
        business_unit_id=business_unit_id,
        source_type=source_type,
        source_id=source_id,
        tariff_id=tariff_id,
        warehouse_id=expense_warehouse_id,
    )
    mm_inc = money_movement._create_movement(
        db=db,
        organization_id=organization_id,
        movement_type="internal_maquila_income",
        amount=amount,
        account_id=None,
        date=date,
        description=description,
        user_id=user_id,
        business_unit_id=business_unit_id,
        source_type=source_type,
        source_id=source_id,
        tariff_id=tariff_id,
        warehouse_id=income_warehouse_id,
    )
    mm_exp.transfer_pair_id = mm_inc.id
    mm_inc.transfer_pair_id = mm_exp.id
    return [mm_exp, mm_inc]
