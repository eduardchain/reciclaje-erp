"""
Servicio de impuestos sobre documentos de venta (CC-013 / Q-41).

UN SOLO PUNTO que aplica y UN SOLO PUNTO que revierte, consumidos por los dos
mundos: la venta normal y la Salida de Plomo. Si esto se escribiera dos veces,
el dia que cambie un signo habria que acordarse de los dos sitios — que es
exactamente la leccion de la terna de signos (#67, #69, #86).

CONSERVACION POR CONSTRUCCION: lo que el cliente deja de deber es exactamente
lo que las entidades tienen a favor, y el IVA que se le cobra de mas es
exactamente lo que se le debe a la DIAN. La suma de los cuatro efectos sobre
terceros da cero, igual que en las retenciones de compra (#75 D9).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_tax import (
    SUBTOTAL_SIGN_ON_PARTY,
    TAX_SIGN_ON_PARTY,
    DocumentTax,
    owner_kind,
)
from app.models.third_party import ThirdParty
from app.services.retention_entities import normalize_entity_name
from app.services.tax_entities import resolve_tax_entity, tax_label


def _require_flag(db: Session, organization_id: UUID) -> None:
    """Guard de bandera (D2, calco del de #75 D9).

    Sin el, una organizacion que no sea SAC podria crear terceros de sistema
    indelebles por API cruda. El payload ausente ni llega acá: el camino sin
    impuestos queda byte a byte.
    """
    from app.utils.org_settings import get_org_setting

    if not get_org_setting(db, organization_id, "kg_ledger_enabled"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Impuestos: modulo no habilitado para esta organizacion",
        )


def apply_taxes(
    db: Session,
    organization_id: UUID,
    taxes_data: List,
    customer: ThirdParty,
    subtotal: Decimal,
    *,
    sale_id: Optional[UUID] = None,
    willard_delivery_id: Optional[UUID] = None,
    purchase_id: Optional[UUID] = None,
) -> Decimal:
    """Aplica los impuestos capturados y devuelve el delta NETO sobre el tercero
    del documento (`customer`: el cliente de una venta o el PROVEEDOR de una
    compra).

    El signo sale de `TAX_SIGN_ON_PARTY[clase de dueno]` y la entidad recibe
    siempre el contrario. El llamador ya aplico el subtotal; esto es ADITIVO.
    """
    owners = [
        k for k, v in (
            ("sale", sale_id),
            ("willard_delivery", willard_delivery_id),
            ("purchase", purchase_id),
        ) if v is not None
    ]
    if not owners:
        raise ValueError("apply_taxes necesita un dueno: sale_id, willard_delivery_id o purchase_id")
    if len(owners) > 1:
        raise ValueError("apply_taxes acepta UN dueno, no varios")
    kind = owners[0]
    signs = TAX_SIGN_ON_PARTY[kind]
    subtotal_sign = SUBTOTAL_SIGN_ON_PARTY[kind]

    _require_flag(db, organization_id)

    # Un tipo que no esta en el mapa de su clase no se admite: hoy una compra
    # solo lleva IVA (sus retenciones viven en purchase_retentions, #75).
    for t in taxes_data:
        if t.tax_type not in signs:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{tax_label(t.tax_type, t.municipality)} no se registra en este "
                    "documento. En una compra solo va el IVA; las retenciones se "
                    "capturan en su bloque."
                ),
            )

    # Una fila por (tipo, municipio): dos IVA sobre el mismo documento es
    # captura duplicada, y en ICA la entidad es por municipio.
    seen: set[tuple[str, Optional[str]]] = set()
    for t in taxes_data:
        key = (t.tax_type, normalize_entity_name(t.municipality) if t.municipality else None)
        if key in seen:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{tax_label(t.tax_type, t.municipality)} viene dos veces en el "
                    "mismo documento. Sume los montos en una sola linea."
                ),
            )
        seen.add(key)

    # "Suma a la factura" = mismo signo que el subtotal sobre el tercero; "se
    # retiene" = el contrario. Asi el guard vale igual para venta y compra.
    added = sum(
        (Decimal(str(t.amount)) for t in taxes_data if signs[t.tax_type] == subtotal_sign),
        Decimal("0"),
    )
    withheld = sum(
        (Decimal(str(t.amount)) for t in taxes_data if signs[t.tax_type] == -subtotal_sign),
        Decimal("0"),
    )
    if withheld >= subtotal + added:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Las retenciones (${withheld}) no pueden igualar ni superar el total "
                f"facturado (${subtotal + added}). Revise los montos de la factura."
            ),
        )

    # D5: la base la deriva el SERVIDOR de lo que realmente facturo. El IVA de
    # este mismo documento es la base de la reteIVA — por eso se calcula antes
    # del loop y no dentro.
    iva_total = sum(
        (Decimal(str(t.amount)) for t in taxes_data if t.tax_type == "iva"),
        Decimal("0"),
    )
    if iva_total == 0 and any(getattr(t, "base_kind", "subtotal") == "iva" for t in taxes_data):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Hay una retencion que se aplica sobre el IVA y esta factura no "
                "tiene IVA. Agregue el IVA o use una tarifa sobre el subtotal."
            ),
        )

    net = Decimal("0")
    for t in taxes_data:
        amount = Decimal(str(t.amount))
        sign = signs[t.tax_type]
        base_amount = iva_total if getattr(t, "base_kind", "subtotal") == "iva" else subtotal
        entity = resolve_tax_entity(db, organization_id, t.tax_type, t.municipality)

        db.add(DocumentTax(
            organization_id=organization_id,
            sale_id=sale_id,
            willard_delivery_id=willard_delivery_id,
            purchase_id=purchase_id,
            third_party_id=entity.id,
            tax_type=t.tax_type,
            municipality=t.municipality.strip() if t.municipality else None,
            concept=t.concept.strip() if t.concept else None,
            rate=t.rate,
            base_amount=base_amount,
            amount=amount,
        ))

        customer.current_balance += sign * amount
        entity.current_balance -= sign * amount
        net += sign * amount

    db.flush()
    return net


def revert_taxes(
    db: Session,
    customer: Optional[ThirdParty],
    *,
    sale_id: Optional[UUID] = None,
    willard_delivery_id: Optional[UUID] = None,
    purchase_id: Optional[UUID] = None,
) -> Decimal:
    """Deshace los impuestos vivos de un documento y devuelve el delta aplicado.

    Estampa `reverted_at` sin borrado fisico, igual que las retenciones de
    compra: el estado de cuenta necesita la fila para emitir su par de eventos
    y el saldo corrido tiene que seguir cerrando contra el saldo vivo (#55).

    ⚠️ Solo toca filas con `reverted_at IS NULL`. Revertir dos veces seria
    devolver el saldo dos veces.
    """
    query = select(DocumentTax).where(DocumentTax.reverted_at.is_(None))
    if sale_id is not None:
        query = query.where(DocumentTax.sale_id == sale_id)
    elif willard_delivery_id is not None:
        query = query.where(DocumentTax.willard_delivery_id == willard_delivery_id)
    elif purchase_id is not None:
        query = query.where(DocumentTax.purchase_id == purchase_id)
    else:
        raise ValueError("revert_taxes necesita un dueno: sale_id, willard_delivery_id o purchase_id")

    # Timestamp de AUDITORIA, no fecha de negocio: responde *cuando exactamente*
    # y nunca se usa para cortar un reporte (regla del reloj unico, #87/#91).
    now = datetime.now(timezone.utc)
    net = Decimal("0")
    for tax in db.execute(query).scalars().all():
        sign = TAX_SIGN_ON_PARTY[owner_kind(tax)][tax.tax_type]
        entity = db.get(ThirdParty, tax.third_party_id)
        if entity is not None:
            entity.current_balance += sign * tax.amount
        if customer is not None:
            customer.current_balance -= sign * tax.amount
        tax.reverted_at = now
        net += sign * tax.amount

    if net:
        db.flush()
    return net
