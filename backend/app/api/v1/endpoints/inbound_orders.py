"""Endpoints InboundOrder — Recepcion unificada (SAC E2, plan §4.2).

Router completo gated por flag kg_ledger_enabled (D10). Permisos: reusa los
de compras (D13 — la Recepcion ES la captura de compras/entradas):
purchases.create (POST), purchases.view (GET), purchases.edit (PATCH D18,
David corrige sus capturas), purchases.cancel (annul, Johana).
"""
from collections import defaultdict, deque
from datetime import date, datetime, time as dt_time, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_flag, require_permission
from app.models.inbound_order import InboundOrder
from app.models.user import User
from app.schemas.inbound_order import (
    CONTROL_ONLY_STATUSES,
    InboundAllocationResponse,
    InboundConfirmRequest,
    InboundLiquidateRequest,
    InboundOrderAnnulRequest,
    InboundOrderCreate,
    InboundOrderLineResponse,
    InboundOrderListResponse,
    InboundOrderResponse,
    InboundOrderUpdate,
    InboundPurchaseSummary,
    InboundRetentionDetail,
)
from app.schemas.document_tax import DocumentTaxResponse
from app.services.inbound_order import inbound_order_service
from app.services.collector_scope import (
    RELIQUIDATE_FOREIGN_SUPPLIER,
    RELIQUIDATE_TAXES,
    not_found,
    out_of_scope_payload,
    require_account_in_scope,
    scope_of,
)

router = APIRouter(dependencies=[Depends(require_org_flag("kg_ledger_enabled"))])


def _page_context(db: Session, org_id: UUID, orders: list[InboundOrder]) -> dict:
    """Mapas por pagina para el enrich — mundo willard (C-4), auditoria de
    liquidacion willard (C-5), compras via puente (#93, R2: lookup por pagina,
    JAMAS join en el listado) y nombres de usuarios. 4 queries, cero N+1."""
    order_ids = [o.id for o in orders]
    audit = inbound_order_service.willard_confirm_audit(db, org_id, order_ids)
    worlds = inbound_order_service.willard_worlds_by_order(db, org_id, orders)
    purchases = inbound_order_service.purchases_by_order(db, org_id, order_ids)
    slots, batches = inbound_order_service.purchase_extras(
        db, org_id, [p.id for plist in purchases.values() for p in plist]
    )
    user_ids = set()
    for o in orders:
        user_ids.add(o.created_by)
        if o.annulled_by:
            user_ids.add(o.annulled_by)
        if o.reviewed_by:
            user_ids.add(o.reviewed_by)
        if o.closed_by:
            user_ids.add(o.closed_by)
    for plist in purchases.values():
        for p in plist:
            if p.liquidated_by:
                user_ids.add(p.liquidated_by)
    for liq_by, _liq_at in audit.values():
        if liq_by:
            user_ids.add(liq_by)
    user_ids.discard(None)
    names: dict = {}
    if user_ids:
        rows = db.execute(
            select(User.id, User.full_name, User.email).where(User.id.in_(user_ids))
        ).all()
        names = {uid: (full_name or email) for uid, full_name, email in rows}
    # Documentos de control: UNA consulta para los materiales de la pagina
    # (lookup por pagina, sin N+1), leida al momento (R2).
    control = inbound_order_service.control_material_ids(
        db, org_id, [l.material_id for o in orders for l in o.lines]
    )
    return {
        "audit": audit, "worlds": worlds, "names": names, "purchases": purchases,
        "purchase_slots": slots, "purchase_batches": batches, "control": control,
    }




def _enrich(
    db: Session,
    order: InboundOrder,
    kg_by_movement: dict,
    receipt_movements: list,
    warnings: Optional[list[str]] = None,
    ctx: Optional[dict] = None,
) -> InboundOrderResponse:
    """Arma la response con lineas enriquecidas (#54) y kg emitidos por linea.

    El kg de cada linea se matchea por firma (material, cantidad) contra los
    movimientos inbound_receipt vivos (deque — display only)."""
    kg_by_signature: dict = defaultdict(deque)
    for mov in receipt_movements:
        kg = kg_by_movement.get(mov.id)
        if kg is not None:
            kg_by_signature[(mov.material_id, mov.quantity)].append(kg)

    is_purchase_type = order.inbound_type == "purchase"
    control = (ctx or {}).get("control", set())
    lines = []
    total_kg = None
    for line in order.lines:
        kg_lead = None
        lead_pct_applied = None
        lead_label_applied = None
        bucket = kg_by_signature.get((line.material_id, line.quantity))
        if bucket:
            kg_lead, kg_snapshot = bucket.popleft()
            total_kg = (total_kg or 0) + kg_lead
            # D8 (A3 de QA 1): el factor usado sale del snapshot del kg
            # CONFIRMADO de la linea, no de la formula de hoy
            lead_pct_applied = inbound_order_service.applied_lead_percentage(kg_snapshot)
            lead_label_applied = inbound_order_service.applied_lead_label(kg_snapshot)
        # #93: reparto y descuadre por linea (solo tipo compra)
        allocations = []
        allocated_qty = None
        discrepancy = None
        if is_purchase_type:
            allocations = [
                InboundAllocationResponse(
                    id=a.id,
                    third_party_id=a.third_party_id,
                    third_party_name=a.third_party.name if a.third_party else None,
                    # Reparto por compra: el campo se arma A MANO (trampa #95) —
                    # sin esta linea la pantalla no sabria a que compra va
                    purchase_slot=a.purchase_slot,
                    quantity=a.quantity,
                    unit_price=a.unit_price,
                    # Q-15: sin esto la pantalla re-abriria el reparto en modo
                    # unitario aunque se hubiera guardado por total — el campo
                    # no romperia, MENTIRIA (leccion #89)
                    total_price=a.total_price,
                    # Idem para el modo por kg: la pantalla LEE estos dos, no
                    # los re-deriva (el peso es funcion de campos mutables de
                    # la linea — recalcular mostraria un numero distinto al
                    # guardado si la linea se edito despues)
                    price_per_kg=a.price_per_kg,
                    weight_kg_used=a.weight_kg_used,
                    invoice_number=a.invoice_number,
                )
                for a in (line.allocations or [])
            ]
            if allocations or order.status in ("liquidated",):
                allocated_qty = sum((a.quantity for a in allocations), Decimal("0"))
                discrepancy = line.quantity - allocated_qty
        lines.append(
            InboundOrderLineResponse(
                id=line.id,
                material_id=line.material_id,
                material_code=line.material.code if line.material else None,
                material_name=line.material.name if line.material else None,
                material_unit=(line.material.default_unit or "kg") if line.material else "kg",
                quantity=line.quantity,
                unit=line.unit,
                unit_price=line.unit_price,
                unit_cost=line.unit_cost,
                scale_weight_kg=line.scale_weight_kg,
                quality_notes=line.quality_notes,
                kg_lead=kg_lead,
                # plan-sac-factor-willard D8: a mano (trampa #95)
                conversion_option=line.conversion_option,
                lead_percentage_applied=lead_pct_applied,
                lead_factor_label_applied=lead_label_applied,
                reference_unit_price=line.reference_unit_price,
                unallocated_intentional=line.unallocated_intentional,
                allocations=allocations,
                allocated_quantity=allocated_qty,
                discrepancy=discrepancy,
                is_control=line.material_id in control,
            )
        )

    ctx = ctx or {}
    names = ctx.get("names", {})
    bridge_purchases = ctx.get("purchases", {}).get(order.id, [])
    purchase_slots = ctx.get("purchase_slots", {})
    purchase_batches = ctx.get("purchase_batches", {})
    purchase_summaries = [
        InboundPurchaseSummary(
            purchase_id=p.id,
            purchase_number=p.purchase_number,
            purchase_slot=purchase_slots.get(p.id),
            supplier_id=p.supplier_id,
            supplier_name=p.supplier.name if p.supplier else None,
            status=p.status,
            total_amount=float(p.total_amount or 0),
            invoice_number=p.invoice_number,
            # Addendum retenciones #93: solo las VIVAS (reverted_at NULL) —
            # el proveedor quedo acreditado neto; viene por selectinload (R2)
            retentions_total=(
                float(sum(r.amount for r in p.retentions if r.reverted_at is None))
                if any(r.reverted_at is None for r in (p.retentions or []))
                else None
            ),
            # Precarga al re-liquidar (pruebas Daniel): si D20 conserva el
            # reparto, conserva tambien lo que se le colgo encima. Es el lote
            # de la ULTIMA liquidacion (`last_liquidation_batch`, la misma
            # funcion de la regla 9f): una liquidacion posterior sin
            # retenciones lo deja vacio (plan Ingrid v1.7, c1).
            retentions=[
                InboundRetentionDetail(
                    retention_type=r.retention_type,
                    municipality=r.municipality,
                    rate=r.rate,
                    base=r.base,
                    amount=r.amount,
                )
                for r in purchase_batches.get(p.id, ([], []))[0]
            ],
            taxes=[
                DocumentTaxResponse(
                    id=t.id, third_party_id=t.third_party_id, third_party_name=name,
                    tax_type=t.tax_type, municipality=t.municipality,
                    concept=t.concept, rate=t.rate, base_amount=t.base_amount,
                    amount=t.amount, reverted_at=t.reverted_at,
                )
                for t, name in purchase_batches.get(p.id, ([], []))[1]
            ],
        )
        for p in bridge_purchases
    ]

    # Quien liquido — tipo compra: liquidated_by de las compras de la puente
    # (todas nacen del mismo evento D14 — la primera liquidada sirve);
    # willard: created_by del primer kg movement confirmado (auditoria B.2)
    liquidated_by_name = None
    liquidated_at = None
    if is_purchase_type:
        liq_p = next((p for p in bridge_purchases if p.status == "liquidated"), None)
        if liq_p is not None:
            liquidated_by_name = names.get(liq_p.liquidated_by)
            liquidated_at = liq_p.liquidated_at
    else:
        w_audit = ctx.get("audit", {}).get(order.id)
        if w_audit:
            liquidated_by_name = names.get(w_audit[0])
            liquidated_at = w_audit[1]

    return InboundOrderResponse(
        id=order.id,
        order_number=order.order_number,
        inbound_type=order.inbound_type,
        warehouse_id=order.warehouse_id,
        warehouse_name=order.warehouse.name if order.warehouse else None,
        third_party_id=order.third_party_id,
        third_party_name=order.third_party.name if order.third_party else None,
        date=order.date,
        driver_id=order.driver_id,
        driver_name=order.driver.name if order.driver else None,
        vehicle_id=order.vehicle_id,
        vehicle_plate=order.vehicle.plate if order.vehicle else None,
        # Ciclo D: recolector (FK NULL -> relationship None sin query)
        collector_id=order.collector_id,
        collector_name=order.collector.name if order.collector else None,
        willard_distribution_center=order.willard_distribution_center,
        notes=order.notes,
        # Willard: columna propia. Legacy 1:1: la compra derivada. Tipo compra
        # #93: NULL (la factura vive por proveedor en purchases[])
        invoice_number=(
            order.purchase.invoice_number if order.purchase else order.invoice_number
        ),
        remission_number=order.remission_number,
        status=order.status,
        display_status=inbound_order_service.display_status_of(order),
        purchase_id=order.purchase_id,
        purchase_number=order.purchase.purchase_number if order.purchase else None,
        purchase_status=order.purchase.status if order.purchase else None,
        purchases=purchase_summaries,
        discrepancy_adjustments=ctx.get("discrepancies", {}).get(order.id, []),
        reviewed_by_name=names.get(order.reviewed_by),
        reviewed_at=order.reviewed_at,
        willard_world=ctx.get("worlds", {}).get(order.id),
        total_kg_lead=total_kg,
        annulled_reason=order.annulled_reason,
        annulled_at=order.annulled_at,
        created_at=order.created_at,
        created_by_name=names.get(order.created_by),
        liquidated_by_name=liquidated_by_name,
        liquidated_at=liquidated_at,
        liquidated_ts=order.liquidated_ts,
        annulled_by_name=names.get(order.annulled_by),
        # N2 de QA 2: sin lineas no es «solo de control». C1 de la v1.3.1: y
        # solo sin efectos (CONTROL_ONLY_STATUSES); el filtro `control_only`
        # de get_multi espeja este mismo predicado (T26).
        is_control_only=order.status in CONTROL_ONLY_STATUSES
        and bool(order.lines)
        and all(l.material_id in control for l in order.lines),
        closed_at=order.closed_at,
        closed_by_name=names.get(order.closed_by),
        lines=lines,
        warnings=warnings or [],
    )


def _enrich_one(db: Session, order: InboundOrder, org_id: UUID, warnings=None) -> InboundOrderResponse:
    kg_map = inbound_order_service.kg_deltas_by_movement(db, org_id, [order.id])
    movs = inbound_order_service.receipt_movements(db, org_id, order.id)
    ctx = _page_context(db, org_id, [order])
    # Los ajustes de descuadre SOLO en el detalle (una query; el listado no los
    # muestra y ahi seria una query por pagina sin uso)
    ctx["discrepancies"] = {
        order.id: inbound_order_service.discrepancy_adjustments(db, org_id, order.id)
    }
    return _enrich(db, order, kg_map, movs, warnings, ctx)


@router.post("", response_model=InboundOrderResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    order_in: InboundOrderCreate,
    org_context: dict = Depends(require_permission("purchases.create")),
    db: Session = Depends(get_db),
):
    """Captura unica en patio — efectos atomicos segun tipo (D2/D5/D7)."""
    order, warnings = inbound_order_service.create(
        db,
        obj_in=order_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


def _require_order_in_scope(order, org_context: dict) -> None:
    """Fila 8: con alcance, una Entrada de otro recolector (o sin recolector)
    da 404 — no revela que existe (§5.3)."""
    scope = scope_of(org_context)
    if scope is not None and order.collector_id != scope:
        raise not_found("Entrada")


def _scoped_liquidation_payload(
    db: Session, order_id: UUID, payload: InboundLiquidateRequest, org_context: dict
) -> InboundLiquidateRequest:
    """Fila 9: reglas de la liquidacion para un usuario con alcance de
    recolector. TODO se valida antes de que el servicio escriba (D14 de #93):
    un rechazo no deja nada.

    - La Entrada es de su recolector (404).
    - Todo proveedor del reparto es de su recolector (422 generico, M1).
    - Toda cuenta de contado esta asignada (403).
    - Sin retenciones ni IVA (422, S5).
    - Comision (S6/D-a): el tercero es su recolector y el monto lo fija el
      servidor; si no viene, la causa igual. Otro tercero u otro monto -> 422.
    - Sin descuadre (9g, v1.10): lo valida el servicio con
      `require_full_allocation`, sobre el mismo calculo del descuadre.
    """
    from decimal import Decimal
    from app.models.third_party import ThirdParty
    from app.schemas.inbound_order import InboundCollectorCommission

    org_id = org_context["organization_id"]
    scope = scope_of(org_context)
    order = inbound_order_service.get(db, order_id, org_id)
    _require_order_in_scope(order, org_context)

    # 9e (v1.6): una Entrada que SAC liquido y des-liquido. Toda compra VIVA
    # del puente tiene que ser de su recolector. Si no, cambiar ese proveedor
    # por uno suyo en la misma compra pasaria la regla del reparto y el
    # servicio cancelaria la compra ajena (R6 de #122), un documento que ella
    # ni puede abrir. Las canceladas no cuentan: son historia que SAC ya
    # corrigio (P48). En la primera liquidacion el puente esta vacio.
    from app.models.inbound_order import InboundOrderPurchase
    from app.models.purchase import Purchase
    live = db.execute(
        select(Purchase.id, Purchase.supplier_id)
        .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
        .where(InboundOrderPurchase.inbound_order_id == order.id,
               Purchase.status != "cancelled")
    ).all()
    live_suppliers = {sid for _pid, sid in live}
    if live_suppliers:
        live_marks = dict(db.execute(
            select(ThirdParty.id, ThirdParty.collector_id)
            .where(ThirdParty.id.in_(live_suppliers))
        ).all())
        if any(live_marks.get(s) != scope for s in live_suppliers):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=RELIQUIDATE_FOREIGN_SUPPLIER,
            )
    # 9f (v1.7): el lote de la ULTIMA liquidacion de alguna compra viva trae
    # retenciones o IVA. Con alcance no se pueden rehacer (S5) y se perderian
    # en silencio. Misma funcion que la precarga: una liquidacion posterior
    # de SAC sin retenciones deja el lote vacio y la Entrada vuelve a ser suya.
    if live:
        batches = inbound_order_service.last_liquidation_batch(
            db, org_id, [pid for pid, _sid in live])
        if any(rets or taxes for rets, taxes in batches.values()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=RELIQUIDATE_TAXES,
            )

    tp_ids = {a.third_party_id for line in payload.lines for a in line.allocations}
    tp_ids |= {b.third_party_id for b in (payload.supplier_payments or [])}
    if tp_ids:
        marks = dict(db.execute(
            select(ThirdParty.id, ThirdParty.collector_id).where(ThirdParty.id.in_(tp_ids))
        ).all())
        if any(marks.get(t) != scope for t in tp_ids):
            raise out_of_scope_payload()

    for block in payload.supplier_payments or []:
        require_account_in_scope(db, org_context, block.account_id)

    if payload.supplier_retentions or payload.purchase_taxes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Con tu usuario la liquidacion va sin retenciones ni IVA: si la compra los lleva, la liquida SAC",
        )

    expected = inbound_order_service.suggested_collector_commission(db, order, org_id)
    cc = payload.collector_commission
    if cc is not None:
        if cc.third_party_id != scope or Decimal(str(cc.amount)) != expected:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La comision del recolector la calcula el sistema (tarifa x lo pesado): no se puede cambiar",
            )
    forced = (
        InboundCollectorCommission(third_party_id=scope, amount=expected)
        if expected > 0 else None
    )
    return payload.model_copy(update={"collector_commission": forced})


@router.get("", response_model=InboundOrderListResponse)
def list_inbound_orders(
    inbound_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status", pattern="^(draft|reviewed|liquidated|confirmed|closed|annulled)$"),
    display_status: Optional[str] = Query(
        None,
        pattern="^(registered|reviewed|liquidated|closed|annulled)$",
        description="#93 D4: estado unico columna-driven",
    ),
    search: Optional[str] = Query(None, max_length=100),
    sort: str = Query(
        "newest",
        pattern="^(newest|oldest|remission_asc|remission_desc)$",
        description="remission_*: orden natural de la remision sobre TODA la lista (plan columna Remision)",
    ),
    willard_world: Optional[str] = Query(None, pattern="^(postconsumo|drosses)$"),
    control_only: Optional[bool] = Query(
        None,
        description="Documentos de control v1.3: true = solo de control y sin efectos (el campo is_control_only); false = el resto",
    ),
    warehouse_id: Optional[UUID] = Query(None),
    third_party_id: Optional[UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    org_context: dict = Depends(require_permission("purchases.view")),
    db: Session = Depends(get_db),
):
    org_id = org_context["organization_id"]
    orders, total = inbound_order_service.get_multi(
        db,
        organization_id=org_id,
        # Alcance de recolector (fila 7): se FUERZA su recolector.
        collector_id=scope_of(org_context),
        inbound_type=inbound_type,
        status_filter=status_filter,
        display_status=display_status,
        search=search,
        sort=sort,
        willard_world=willard_world,
        control_only=control_only,
        warehouse_id=warehouse_id,
        third_party_id=third_party_id,
        date_from=datetime.combine(date_from, dt_time.min, tzinfo=timezone.utc) if date_from else None,
        date_to=datetime.combine(date_to, dt_time.max, tzinfo=timezone.utc) if date_to else None,
        skip=skip,
        limit=limit,
    )
    kg_map = inbound_order_service.kg_deltas_by_movement(db, org_id, [o.id for o in orders])
    ctx = _page_context(db, org_id, list(orders))
    items = []
    for o in orders:
        movs = inbound_order_service.receipt_movements(db, org_id, o.id)
        items.append(_enrich(db, o, kg_map, movs, None, ctx))
    return InboundOrderListResponse(items=items, total=total)


@router.get("/{order_id}", response_model=InboundOrderResponse)
def get_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.view")),
    db: Session = Depends(get_db),
):
    order = inbound_order_service.get(db, order_id, org_context["organization_id"])
    _require_order_in_scope(order, org_context)
    resp = _enrich_one(db, order, org_context["organization_id"])
    # Ciclo D (pruebas Daniel): costo de recoleccion en la cara financiera —
    # solo detalle (patron #63, sin N+1 en listados). #93: la comision vive
    # POR ENTRADA (source_id=orden, purchase_id NULL) y la legacy #83 tambien
    # estampaba source_id=orden — una sola query por FUENTE cubre ambas.
    from decimal import Decimal as _Dec
    from sqlalchemy import func as _func, select as _select
    from app.models.money_movement import MoneyMovement as _MM
    cc = db.execute(
        _select(_func.coalesce(_func.sum(_MM.amount), 0)).where(
            _MM.organization_id == org_context["organization_id"],
            _MM.movement_type == "expense_accrual",
            _MM.source_type == "collector_commission",
            _MM.source_id == order.id,
            _MM.status == "confirmed",
        )
    ).scalar_one()
    cc = _Dec(str(cc or 0))
    resp.collector_commission_total = float(cc) if cc > 0 else None
    return resp


@router.patch("/{order_id}", response_model=InboundOrderResponse)
def update_inbound_order(
    order_id: UUID,
    order_in: InboundOrderUpdate,
    org_context: dict = Depends(require_permission("purchases.edit")),
    db: Session = Depends(get_db),
):
    """Edicion D18: Willard = revert-and-reapply; tipos compra = solo cabecera
    sin efectos (las lineas viven en la compra derivada)."""
    order, warnings = inbound_order_service.update(
        db,
        order_id=order_id,
        obj_in=order_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


@router.post("/{order_id}/confirm", response_model=InboundOrderResponse)
def confirm_inbound_order(
    order_id: UUID,
    body: Optional[InboundConfirmRequest] = Body(None),
    org_context: dict = Depends(require_permission("purchases.liquidate")),
    db: Session = Depends(get_db),
):
    """B.2 + Q-16: reviewed -> confirmed — los efectos (inventario D2 + kg D5 +
    MCH H1a) nacen aca, por el MISMO camino del 1-paso previo. Solo tipos
    Willard (una orden tipo compra se confirma liquidando su compra derivada).
    Desde Q-16 el paso previo es la REVISION, no la captura.

    Cuerpo OPCIONAL (plan-sac-factor-willard D3): el factor de Willard
    escogido por material. Sin cuerpo = el defecto, como antes."""
    order = inbound_order_service.confirm(
        db,
        order_id=order_id,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
        conversion_options=body.conversion_options if body else None,
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"])


@router.post("/{order_id}/review", response_model=InboundOrderResponse)
def review_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.review")),
    db: Session = Depends(get_db),
):
    """#93 D10 + Q-16: draft -> reviewed, en AMBOS tipos — certifica las
    cantidades pesadas; en compra habilita liquidar, en Willard confirmar.
    Es donde el peso de bascula se vuelve obligatorio (Q-13).
    Permiso propio purchases.review."""
    order = inbound_order_service.review(
        db,
        order_id=order_id,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"])


@router.post("/{order_id}/liquidate", response_model=InboundOrderResponse)
def liquidate_inbound_order(
    order_id: UUID,
    payload: InboundLiquidateRequest,
    org_context: dict = Depends(require_permission("purchases.liquidate")),
    db: Session = Depends(get_db),
):
    """#93 D14: liquidacion ATOMICA — el reparto asigna cada linea a N
    proveedores, nacen y se liquidan N compras en una transaccion, el
    descuadre se ajusta al precio de referencia (D6/D7) y la comision del
    recolector se causa una vez por entrada (D11). Todo el evento en el dia
    de la liquidacion (D21)."""
    scoped = scope_of(org_context) is not None
    if scoped:
        payload = _scoped_liquidation_payload(db, order_id, payload, org_context)
    order, warnings = inbound_order_service.liquidate(
        db,
        order_id=order_id,
        payload=payload,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
        # 9g (plan Ingrid v1.10): con alcance, sin descuadre.
        require_full_allocation=scoped,
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


@router.post("/{order_id}/close", response_model=InboundOrderResponse)
def close_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.liquidate")),
    db: Session = Depends(get_db),
):
    """Documentos de control §4.2: cierre SIN VALOR de una Entrada con todos
    sus materiales de control — estado terminal propio, cero efectos. Fuera de
    SCOPED_ENDPOINTS a proposito (#129): Ingrid no la ve."""
    order = inbound_order_service.close(
        db,
        order_id=order_id,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"])


@router.post("/{order_id}/reopen", response_model=InboundOrderResponse)
def reopen_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.cancel")),
    db: Session = Depends(get_db),
):
    """R6 (D3): deshace un cierre sin valor por error, sin anular (anular
    romperia el consecutivo). Vuelve al estado de antes del cierre."""
    order = inbound_order_service.reopen(
        db,
        order_id=order_id,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"])


@router.post("/{order_id}/unliquidate", response_model=InboundOrderResponse)
def unliquidate_inbound_order(
    order_id: UUID,
    org_context: dict = Depends(require_permission("purchases.cancel")),
    db: Session = Depends(get_db),
):
    """#93 D20: revierte la liquidacion completa (N compras -> registradas,
    ajustes y comision anulados) y vuelve a 'revisada' CONSERVANDO el reparto
    — sin quemar consecutivos. Nunca bloquea (#76)."""
    order, warnings = inbound_order_service.unliquidate(
        db,
        order_id=order_id,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)


@router.post("/{order_id}/annul", response_model=InboundOrderResponse)
def annul_inbound_order(
    order_id: UUID,
    annul_in: InboundOrderAnnulRequest,
    org_context: dict = Depends(require_permission("purchases.cancel")),
    db: Session = Depends(get_db),
):
    """Anulacion D8: remocion ponderada + kg movements anulados + reversal
    backdateado; tipos compra cancelan la derivada registered en el mismo acto."""
    order, warnings = inbound_order_service.annul(
        db,
        order_id=order_id,
        reason=annul_in.reason,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
    order = inbound_order_service.get(db, order.id, org_context["organization_id"])
    return _enrich_one(db, order, org_context["organization_id"], warnings)
