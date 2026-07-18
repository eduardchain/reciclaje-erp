"""
Servicio InboundOrder — Recepcion unificada (SAC E2, plan §4.2, D2/D4-D8/D12/D15/D18).

Tipos Willard (postconsumo_baterias, drosses): el material entra al inventario
al costo promedio VIGENTE (identidad D2 — `incorporate_into_pool(liq, avg, qty,
avg)` da adjustment 0 y avg intacto en las 3 ramas) + un KgLedgerMovement por
linea (D5) con la formula de conversion vigente (D6). MCH con transaction_date
= HOY (H1a QA: checkpoint del avg al momento de ESCRIBIR — fecharlo a
order.date re-presentaria cortes historicos, doctrina #61); el
InventoryMovement conserva order.date para la CANTIDAD.

Tipos purchase/ruta: derivan una Purchase(registered) en la MISMA transaccion
via `purchase_service.create(commit=False)` (composabilidad D7). reventa = 422
valor muerto (Johana 2026-07-16: SAC no hace reventa).

Anulacion D8: remocion ponderada (#66) leyendo `line.unit_cost` (snapshot del
avg de entrada); `inbound_reversal` backdateado a `order.date` (doctrina #41:
las ordenes anuladas desaparecen de TODOS los cortes); diferencia →
`annul_cost_adjustment` (8a fuente de la linea P&L, solo lado annul).
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String as SAString, and_, cast, func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.inbound_order import InboundOrder, InboundOrderLine
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_conversion_formula import MaterialConversionFormula
from app.models.material_kg_profile import MaterialKgProfile
from app.models.fleet import Driver, Vehicle
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.schemas.inbound_order import (
    PURCHASE_INBOUND_TYPES,
    WILLARD_INBOUND_TYPES,
    InboundOrderCreate,
    InboundOrderUpdate,
)
from app.schemas.purchase import PurchaseCreate, PurchaseLineCreate
from app.services.inventory_costing import incorporate_into_pool, remove_from_pool
from app.services.material_cost_history import material_cost_history_service
from app.utils.org_settings import get_org_setting

# D1/CC-004: el ruteo de la cuenta kg es POR LINEA segun willard_world del
# material (no por un tipo de encabezado). El inbound_type solo distingue
# willard (efectos propios) de purchase (deriva compra).
KG_SOURCE_BY_WORLD = {
    "postconsumo": "postconsumo_receipt",
    "drosses": "drosses_receipt",
}

WORLD_LABELS = {
    "postconsumo": "Postconsumo baterias",
    "drosses": "Drosses",
}


def _err(detail: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
    return HTTPException(status_code=code, detail=detail)


class InboundOrderService:
    # ------------------------------------------------------------------ #
    # Create                                                              #
    # ------------------------------------------------------------------ #
    def create(
        self,
        db: Session,
        obj_in: InboundOrderCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        warehouse = self._validate_warehouse(db, obj_in.warehouse_id, organization_id)
        third_party = self._validate_third_party(db, obj_in.third_party_id, organization_id)
        if obj_in.driver_id is not None:
            self._validate_org(db, Driver, obj_in.driver_id, organization_id, "Conductor")
        if obj_in.vehicle_id is not None:
            self._validate_org(db, Vehicle, obj_in.vehicle_id, organization_id, "Vehiculo")

        is_willard = obj_in.inbound_type in WILLARD_INBOUND_TYPES

        # D12: centro de distribucion Willard — pertenencia contra settings
        if obj_in.willard_distribution_center is not None:
            if not is_willard:
                raise _err("willard_distribution_center solo aplica a tipos Willard")
            valid_centers = get_org_setting(
                db, organization_id, "willard_distribution_centers"
            ) or []
            if obj_in.willard_distribution_center not in valid_centers:
                raise _err(
                    f"Centro de distribucion '{obj_in.willard_distribution_center}' no "
                    f"configurado — validos: {', '.join(valid_centers)}"
                )

        order = InboundOrder(
            organization_id=organization_id,
            order_number=self._generate_order_number(db, organization_id),
            inbound_type=obj_in.inbound_type,
            warehouse_id=obj_in.warehouse_id,
            third_party_id=obj_in.third_party_id,
            date=obj_in.date,
            driver_id=obj_in.driver_id,
            vehicle_id=obj_in.vehicle_id,
            willard_distribution_center=obj_in.willard_distribution_center,
            # goes_directly_to_jm retirado de la superficie (Ciclo B B4, Q-03) —
            # la columna queda inerte con su server_default
            notes=obj_in.notes,
            # B.2: willard nace "Registrada" (draft) — bandeja de Johana;
            # tipo compra sigue confirmed (su 2-pasos vive en la Purchase derivada)
            status="draft" if is_willard else "confirmed",
            created_by=user_id,
        )
        db.add(order)
        db.flush()

        warnings: list[str] = []
        if is_willard:
            # B.2: capturar != confirmar — el draft valida TODO (fail-fast para
            # David: un draft no puede nacer roto) pero NO mueve nada; los
            # efectos (inventario D2 + kg D5 + MCH H1a) nacen al confirmar
            self._validate_willard_capture(
                db, organization_id, obj_in.warehouse_id,
                obj_in.third_party_id, obj_in.lines,
            )
            self._persist_mirror_lines(db, order, obj_in.lines, organization_id)
        else:
            # D7: derivar Purchase(registered) en la misma transaccion
            vehicle_plate = None
            if obj_in.vehicle_id is not None:
                vehicle_plate = db.get(Vehicle, obj_in.vehicle_id).plate
            purchase_in = PurchaseCreate(
                supplier_id=obj_in.third_party_id,
                date=obj_in.date,
                warehouse_id=obj_in.warehouse_id,  # D11: header fuerza lineas
                vehicle_plate=vehicle_plate,
                lines=[
                    PurchaseLineCreate(
                        material_id=l.material_id,
                        warehouse_id=obj_in.warehouse_id,
                        quantity=l.quantity,
                        unit_price=l.unit_price or Decimal("0"),
                    )
                    for l in obj_in.lines
                ],
            )
            from app.services.purchase import purchase as purchase_service
            purchase, p_warnings = purchase_service.create(
                db,
                obj_in=purchase_in,
                organization_id=organization_id,
                user_id=user_id,
                commit=False,
            )
            order.purchase_id = purchase.id
            warnings.extend(p_warnings)
            # Lineas espejo del inbound (documento de captura)
            self._persist_mirror_lines(db, order, obj_in.lines, organization_id)

        db.commit()
        db.refresh(order)
        return order, warnings

    def _persist_mirror_lines(
        self, db: Session, order: InboundOrder, lines_in, organization_id: UUID
    ) -> None:
        """Lineas espejo del documento de captura — SIN unit_cost (el snapshot
        D8 nace al confirmar, cuando _apply_willard_effects las recrea)."""
        for l in lines_in:
            material = db.get(Material, l.material_id)
            db.add(
                InboundOrderLine(
                    organization_id=organization_id,
                    inbound_order_id=order.id,
                    material_id=l.material_id,
                    quantity=l.quantity,
                    unit=material.default_unit or "kg",
                    unit_price=l.unit_price,
                    scale_weight_kg=l.scale_weight_kg,
                    quality_notes=l.quality_notes,
                )
            )

    # ------------------------------------------------------------------ #
    # Confirmar recepcion Willard (B.2) — los efectos nacen aca           #
    # ------------------------------------------------------------------ #
    def confirm(
        self,
        db: Session,
        order_id: UUID,
        organization_id: UUID,
        user_id: UUID,
    ) -> InboundOrder:
        """Draft -> confirmed: borra las lineas draft y re-aplica via
        _apply_willard_effects (el MISMO camino de efectos del 1-paso previo:
        inventario a identidad D2 + kg ledger D5 + MCH hoy H1a + snapshot de
        formula/avg AL CONFIRMAR — si la formula cambio desde la captura,
        aplica la vigente, #35)."""
        order = self._get_or_404(db, order_id, organization_id)
        if order.inbound_type not in WILLARD_INBOUND_TYPES:
            raise _err(
                "Una recepcion tipo Compra no se confirma aca — su flujo vive "
                "en la compra derivada (liquidela desde Compras)",
                status.HTTP_400_BAD_REQUEST,
            )
        if order.status == "annulled":
            raise _err(
                "La recepcion esta anulada", status.HTTP_400_BAD_REQUEST
            )
        if order.status == "confirmed":
            raise _err(
                "La recepcion ya esta confirmada", status.HTTP_400_BAD_REQUEST
            )

        # Re-validar lo que pudo cambiar entre captura y confirmacion
        self._validate_warehouse(db, order.warehouse_id, organization_id)
        self._validate_third_party(db, order.third_party_id, organization_id)

        # Reconstruir lines_in desde las lineas draft persistidas (patron D18)
        lines_in = [
            SimpleNamespace(
                material_id=l.material_id,
                quantity=l.quantity,
                unit_price=l.unit_price,
                scale_weight_kg=l.scale_weight_kg,
                quality_notes=l.quality_notes,
            )
            for l in order.lines
        ]
        # Borrar las draft — _apply_willard_effects las recrea con unit_cost
        db.query(InboundOrderLine).filter(
            InboundOrderLine.inbound_order_id == order.id
        ).delete(synchronize_session=False)
        db.flush()

        self._apply_willard_effects(db, order, lines_in, organization_id, user_id)
        order.status = "confirmed"
        db.commit()
        db.refresh(order)
        return order

    # ------------------------------------------------------------------ #
    # Validacion de captura Willard (B.2) — camino UNICO                  #
    # ------------------------------------------------------------------ #
    def _validate_willard_capture(
        self,
        db: Session,
        organization_id: UUID,
        warehouse_id: UUID,
        third_party_id: UUID,
        lines_in,
    ) -> tuple[dict, dict, dict]:
        """Validaciones Willard — corren al CAPTURAR (fail-fast: un draft no
        puede nacer roto) y al CONFIRMAR (via _apply_willard_effects, que las
        consume — B.2 W2: una sola implementacion, cero divergencia).

        Retorna (worlds, formulas, account_by_world) para que apply no
        re-consulte.
        """
        material_ids = [l.material_id for l in lines_in]
        worlds = self._load_kg_worlds(db, organization_id, material_ids)

        # Ciclo B (B2): homogeneidad de mundo — una recepcion Willard es de UN
        # solo mundo; camion mixto = DOS recepciones (Q-10, decision Daniel).
        real_worlds = {
            w for w in (worlds.get(mid) for mid in material_ids)
            if w and w != "none"
        }
        if len(real_worlds) > 1:
            raise _err(
                "Una recepcion Willard es de un solo mundo (drosses o postconsumo) "
                "— separe el camion en dos recepciones"
            )

        # Ciclo B (B2): drosses van SIEMPRE a la planta (Q-03/Q-05). Solo valida
        # si la org configuro willard_sede_drosses (None = compat, no valida).
        if real_worlds == {"drosses"}:
            jm_id = get_org_setting(db, organization_id, "willard_sede_drosses")
            if jm_id is not None and str(warehouse_id) != str(jm_id):
                jm_wh = db.get(Warehouse, UUID(str(jm_id)))
                jm_name = jm_wh.name if jm_wh else "la bodega configurada"
                raise _err(
                    f"Los drosses se reciben en la planta ({jm_name}) — "
                    "seleccione esa bodega"
                )

        # Cache de cuenta kg por mundo (la sede de baterias es fija: warehouse_id)
        account_by_world: dict[str, KgLedgerAccount] = {}

        # Ciclo B addendum (feedback Daniel): el tercero de una recepcion
        # Willard ES el titular de la cuenta kg (fijo en UI; aca defensa) —
        # la cuenta esta amarrada a su tercero por CHECK del modelo
        if real_worlds:
            world0 = next(iter(real_worlds))
            account0 = self._resolve_kg_account_for_world(
                db, organization_id, world0, warehouse_id
            )
            account_by_world[world0] = account0
            if account0.third_party_id and third_party_id != account0.third_party_id:
                titular = db.get(ThirdParty, account0.third_party_id)
                raise _err(
                    "El tercero de una recepcion Willard es el titular de la "
                    f"cuenta kg ({titular.name if titular else 'configurado en la cuenta'})"
                )

        formulas = self._load_current_formulas(db, organization_id, material_ids)

        # Per-linea: material activo, mundo Willard, formula vigente
        for line_in in lines_in:
            material = self._validate_material(db, line_in.material_id, organization_id)
            world = worlds.get(line_in.material_id)
            # D1/CC-004: el mundo del material rutea la cuenta kg. Un material
            # sin clasificacion Willard se recibe como Compra regular.
            if world is None or world == "none":
                raise _err(
                    f"El material {material.code} no es de mundo Willard "
                    "(postconsumo/drosses) — clasifiquelo en el maestro de materiales "
                    "o recibalo como Compra regular"
                )
            if world not in account_by_world:
                account_by_world[world] = self._resolve_kg_account_for_world(
                    db, organization_id, world, warehouse_id
                )
            if formulas.get(line_in.material_id) is None:
                raise _err(
                    f"No hay formula de conversion vigente para {material.code} — "
                    "creela primero en el maestro de materiales"
                )

        return worlds, formulas, account_by_world

    # ------------------------------------------------------------------ #
    # Efectos Willard (confirm B.2 + re-apply de edicion D18)             #
    # ------------------------------------------------------------------ #
    def _apply_willard_effects(
        self,
        db: Session,
        order: InboundOrder,
        lines_in,
        organization_id: UUID,
        user_id: UUID,
    ) -> None:
        # B.2 (W2): la validacion es el MISMO camino que la captura — aca se
        # re-valida (formula/cuenta/material pueden cambiar entre captura y
        # confirmacion) y se consumen los datos cargados
        worlds, formulas, account_by_world = self._validate_willard_capture(
            db, organization_id, order.warehouse_id, order.third_party_id, lines_in
        )
        today = datetime.now(timezone.utc).date()

        for line_in in lines_in:
            material = self._validate_material(db, line_in.material_id, organization_id)
            qty = Decimal(str(line_in.quantity))
            world = worlds[line_in.material_id]
            account = account_by_world[world]
            kg_source = KG_SOURCE_BY_WORLD[world]
            label = WORLD_LABELS[world]
            formula = formulas[line_in.material_id]
            delta_kg = self._compute_kg_lead(formula, qty)

            # D2: entrada a identidad — adjustment 0 y avg intacto por construccion
            old_liq = material.current_stock_liquidated
            avg = material.current_average_cost
            new_avg, _adj = incorporate_into_pool(
                liquidated=old_liq, avg_cost=avg, quantity=qty, unit_cost=avg
            )
            material.current_average_cost = new_avg
            material.current_stock_liquidated = old_liq + qty
            material.current_stock += qty

            line = InboundOrderLine(
                organization_id=organization_id,
                inbound_order_id=order.id,
                material_id=line_in.material_id,
                quantity=qty,
                unit=material.default_unit or "kg",
                unit_price=line_in.unit_price,
                unit_cost=avg.quantize(Decimal("0.01")),  # snapshot D8
                scale_weight_kg=line_in.scale_weight_kg,
                quality_notes=line_in.quality_notes,
            )
            db.add(line)

            movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line_in.material_id,
                warehouse_id=order.warehouse_id,
                movement_type="inbound_receipt",
                quantity=qty,
                unit_cost=avg.quantize(Decimal("0.01")),  # espejo del snapshot D8
                reference_type="inbound",
                reference_id=order.id,
                date=order.date,  # la CANTIDAD si vive en la fecha de negocio (D4)
                notes=f"Recepcion {label} #{order.order_number}",
            )
            db.add(movement)
            db.flush()

            # H1a QA: checkpoint del avg al momento de ESCRIBIR (HOY) — nunca
            # backdatear (re-presentaria cortes historicos, doctrina #61)
            material_cost_history_service.record_cost_change(
                db=db,
                material=material,
                previous_cost=avg,
                previous_stock=old_liq,
                new_cost=new_avg,
                new_stock=material.current_stock_liquidated,
                source_type="inbound_receipt",
                source_id=order.id,
                organization_id=organization_id,
                transaction_date=today,
            )

            # D5: un KgLedgerMovement POR LINEA con snapshot de formula propio
            db.add(
                KgLedgerMovement(
                    organization_id=organization_id,
                    account_id=account.id,
                    delta_kg=delta_kg,
                    transaction_date=order.date,
                    description=(
                        f"Recepcion {label} #{order.order_number} — "
                        f"{material.code} x {qty:g} {material.default_unit or 'kg'}"
                    ),
                    source_type=kg_source,
                    source_id=order.id,
                    inventory_movement_id=movement.id,
                    conversion_formula_snapshot={
                        "formula_id": str(formula.id),
                        "formula_type": formula.formula_type,
                        "parameters": formula.parameters,
                    },
                    created_by=user_id,
                    status="confirmed",
                )
            )

    # ------------------------------------------------------------------ #
    # Reversa Willard (annul + revert de edicion D18)                     #
    # ------------------------------------------------------------------ #
    def _revert_willard_effects(
        self,
        db: Session,
        order: InboundOrder,
        organization_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> tuple[Decimal, list[str]]:
        """Remocion ponderada (#66) al snapshot line.unit_cost + anulacion de
        los kg movements (#48). Retorna (diferencia_total, warnings)."""
        warnings: list[str] = []
        total_adjustment = Decimal("0")
        today = datetime.now(timezone.utc).date()

        for line in order.lines:
            material = db.get(Material, line.material_id)
            qty = line.quantity
            old_liq = material.current_stock_liquidated
            old_avg = material.current_average_cost

            new_avg, adj = remove_from_pool(
                liquidated=old_liq,
                avg_cost=old_avg,
                quantity=qty,
                unit_cost=line.unit_cost or Decimal("0"),
            )
            material.current_average_cost = new_avg
            material.current_stock_liquidated = old_liq - qty
            material.current_stock -= qty
            total_adjustment += adj

            # MCH SIEMPRE (append-only #66) — HOY (H1a)
            material_cost_history_service.record_cost_change(
                db=db,
                material=material,
                previous_cost=old_avg,
                previous_stock=old_liq,
                new_cost=new_avg,
                new_stock=old_liq - qty,
                source_type="inbound_annulment",
                source_id=order.id,
                organization_id=organization_id,
                transaction_date=today,
            )

            # Reversal backdateado a order.date (doctrina #41: la orden anulada
            # desaparece de TODOS los cortes — receipt y reversal se cancelan)
            db.add(
                InventoryMovement(
                    organization_id=organization_id,
                    material_id=line.material_id,
                    warehouse_id=order.warehouse_id,
                    movement_type="inbound_reversal",
                    quantity=-qty,
                    unit_cost=line.unit_cost or Decimal("0"),
                    reference_type="inbound",
                    reference_id=order.id,
                    date=order.date,
                    notes=f"Reversa recepcion #{order.order_number}: {reason}",
                )
            )

            if material.current_stock_liquidated < 0:
                warnings.append(
                    f"El stock liquidado de {material.code} queda negativo tras la "
                    f"reversa: {float(material.current_stock_liquidated):g} "
                    f"{material.default_unit or 'kg'}"
                )

        # Anular los kg movements de la orden (#48)
        kg_movs = db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id == order.id,
                KgLedgerMovement.status == "confirmed",
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for mov in kg_movs:
            mov.status = "annulled"
            mov.annulled_reason = reason
            mov.annulled_by = user_id
            mov.annulled_at = now

        return total_adjustment, warnings

    # ------------------------------------------------------------------ #
    # Annul (D8)                                                          #
    # ------------------------------------------------------------------ #
    def annul(
        self,
        db: Session,
        order_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        order = self._get_or_404(db, order_id, organization_id)
        # B.2: draft y confirmed son anulables (draft = solo status, sin reversa)
        if order.status == "annulled":
            raise _err(
                "No se puede anular: la orden ya esta anulada",
                status.HTTP_400_BAD_REQUEST,
            )

        warnings: list[str] = []
        if order.inbound_type in WILLARD_INBOUND_TYPES:
            # B.2: un draft no movio nada — anular es solo status + auditoria
            if order.status == "confirmed":
                total_adj, warnings = self._revert_willard_effects(
                    db, order, organization_id, user_id, reason
                )
                order.annul_cost_adjustment = total_adj
        elif order.purchase_id is not None:
            from app.services.purchase import purchase as purchase_service
            purchase = order.purchase
            if purchase.status == "liquidated":
                raise _err(
                    f"Cancele primero la compra #{purchase.purchase_number} "
                    "(esta liquidada — la anulacion de la orden solo cubre compras registradas)",
                    status.HTTP_400_BAD_REQUEST,
                )
            if purchase.status == "registered":
                _, p_warnings = purchase_service.cancel(
                    db,
                    purchase_id=purchase.id,
                    organization_id=organization_id,
                    user_id=user_id,
                    commit=False,
                    from_inbound=True,
                )
                warnings.extend(p_warnings)

        order.status = "annulled"
        order.annulled_reason = reason
        order.annulled_at = datetime.now(timezone.utc)
        order.annulled_by = user_id

        db.commit()
        db.refresh(order)
        return order, warnings

    # ------------------------------------------------------------------ #
    # Update (D18)                                                        #
    # ------------------------------------------------------------------ #
    def update(
        self,
        db: Session,
        order_id: UUID,
        obj_in: InboundOrderUpdate,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        order = self._get_or_404(db, order_id, organization_id)
        if order.status == "annulled":
            # D18: anuladas no se editan — como si no existieran para el PATCH
            raise _err("Orden no encontrada", status.HTTP_404_NOT_FOUND)

        is_willard = order.inbound_type in WILLARD_INBOUND_TYPES
        fields_set = obj_in.model_dump(exclude_unset=True)

        if not is_willard:
            # Tipos purchase: solo cabecera sin efectos — las lineas y la fecha
            # viven en la compra derivada (D7b: doble verdad prohibida).
            # notes NO se bloquea: es la nota de la CAPTURA (la compra tiene la suya)
            blocked = {"lines", "date", "willard_distribution_center"}
            offending = blocked & set(fields_set.keys())
            if offending:
                pn = order.purchase.purchase_number if order.purchase else "?"
                raise _err(
                    f"En ordenes tipo compra, {', '.join(sorted(offending))} se edita "
                    f"en la compra derivada #{pn} (modulo de compras)"
                )
        else:
            if obj_in.willard_distribution_center is not None:
                valid_centers = get_org_setting(
                    db, organization_id, "willard_distribution_centers"
                ) or []
                if obj_in.willard_distribution_center not in valid_centers:
                    raise _err(
                        f"Centro de distribucion '{obj_in.willard_distribution_center}' "
                        f"no configurado — validos: {', '.join(valid_centers)}"
                    )

        if obj_in.driver_id is not None:
            self._validate_org(db, Driver, obj_in.driver_id, organization_id, "Conductor")
        if obj_in.vehicle_id is not None:
            self._validate_org(db, Vehicle, obj_in.vehicle_id, organization_id, "Vehiculo")

        warnings: list[str] = []
        # Revert-and-reapply Willard cuando cambian lineas o fecha
        # (la fecha mueve los eventos kg e inventario) — SOLO confirmadas;
        # un draft (B.2) no tiene efectos que revertir
        willard_body_changed = is_willard and bool(
            {"lines", "date"} & set(fields_set.keys())
        )
        needs_reapply = willard_body_changed and order.status == "confirmed"
        if willard_body_changed and not needs_reapply:
            # B.2: edicion simple del draft — validar la captura nueva y
            # reemplazar las lineas espejo, cero movimientos
            if obj_in.date is not None:
                order.date = obj_in.date
            if obj_in.lines is not None:
                self._validate_willard_capture(
                    db, organization_id, order.warehouse_id,
                    order.third_party_id, obj_in.lines,
                )
                db.query(InboundOrderLine).filter(
                    InboundOrderLine.inbound_order_id == order.id
                ).delete(synchronize_session=False)
                db.flush()
                self._persist_mirror_lines(db, order, obj_in.lines, organization_id)
        if needs_reapply:
            old_lines = [
                SimpleNamespace(
                    material_id=l.material_id,
                    quantity=l.quantity,
                    unit_price=l.unit_price,
                    scale_weight_kg=l.scale_weight_kg,
                    quality_notes=l.quality_notes,
                )
                for l in order.lines
            ]
            revert_adj, rev_warnings = self._revert_willard_effects(
                db, order, organization_id, user_id,
                reason=f"Edicion de orden #{order.order_number}",
            )
            warnings.extend(rev_warnings)
            if revert_adj != 0:
                # Micro-gap documentado (informe E2): la diferencia se conserva
                # en el header y entra al P&L solo si la orden se anula despues
                order.annul_cost_adjustment += revert_adj
                warnings.append(
                    f"La edicion dejo una diferencia de costo de ${revert_adj} "
                    "(pool negativo al editar) — se reconocera en P&L al anular la orden"
                )

            # Borrar lineas viejas y re-aplicar (nuevo avg de entrada, HOY)
            db.query(InboundOrderLine).filter(
                InboundOrderLine.inbound_order_id == order.id
            ).delete(synchronize_session=False)
            db.flush()

            if obj_in.date is not None:
                order.date = obj_in.date

            new_lines = obj_in.lines if obj_in.lines is not None else old_lines
            self._apply_willard_effects(db, order, new_lines, organization_id, user_id)

        # Cabecera sin efectos
        if obj_in.driver_id is not None:
            order.driver_id = obj_in.driver_id
        if obj_in.vehicle_id is not None:
            order.vehicle_id = obj_in.vehicle_id
        if obj_in.willard_distribution_center is not None:
            order.willard_distribution_center = obj_in.willard_distribution_center
        if "notes" in fields_set:
            # None explicito borra la nota (exclude_unset distingue ausente de null)
            order.notes = obj_in.notes

        db.commit()
        db.refresh(order)
        return order, warnings

    # ------------------------------------------------------------------ #
    # Lectura                                                             #
    # ------------------------------------------------------------------ #
    def get(self, db: Session, order_id: UUID, organization_id: UUID) -> InboundOrder:
        return self._get_or_404(db, order_id, organization_id)

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        inbound_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        display_status: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "newest",
        willard_world: Optional[str] = None,
        warehouse_id: Optional[UUID] = None,
        third_party_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InboundOrder], int]:
        from app.models.purchase import Purchase

        q = select(InboundOrder).where(InboundOrder.organization_id == organization_id)
        if inbound_type:
            q = q.where(InboundOrder.inbound_type == inbound_type)
        if status_filter:
            q = q.where(InboundOrder.status == status_filter)

        # Ciclo C (C-1): estado DERIVADO unico — espejo SQL de display_status_of
        # (test de paridad filtro==campo). Anulada gana: orden anulada O compra
        # cancelada (incl. cancelada post-liquidacion desde Compras, #63).
        if display_status:
            q = q.outerjoin(Purchase, InboundOrder.purchase_id == Purchase.id)
            is_willard = InboundOrder.inbound_type.in_(WILLARD_INBOUND_TYPES)
            # NULL-safe (three-valued logic): para willard el outer join deja
            # Purchase.* en NULL — negar un OR con NULL descartaria esas filas.
            purchase_cancelled = and_(
                Purchase.id.is_not(None), Purchase.status == "cancelled"
            )
            not_annulled = and_(
                InboundOrder.status != "annulled",
                or_(Purchase.id.is_(None), Purchase.status != "cancelled"),
            )
            if display_status == "annulled":
                q = q.where(
                    or_(InboundOrder.status == "annulled", purchase_cancelled)
                )
            elif display_status == "registered":
                q = q.where(
                    not_annulled,
                    or_(
                        and_(is_willard, InboundOrder.status == "draft"),
                        Purchase.status == "registered",
                    ),
                )
            elif display_status == "liquidated":
                q = q.where(
                    not_annulled,
                    or_(
                        and_(is_willard, InboundOrder.status == "confirmed"),
                        Purchase.status == "liquidated",
                    ),
                )

        # Ciclo C (C-2): buscador — #, placa, conductor, tercero, material
        if search and search.strip():
            like = f"%{search.strip()}%"
            material_match = (
                select(InboundOrderLine.id)
                .join(Material, InboundOrderLine.material_id == Material.id)
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    or_(Material.code.ilike(like), Material.name.ilike(like)),
                )
                .exists()
            )
            q = (
                q.outerjoin(Driver, InboundOrder.driver_id == Driver.id)
                .outerjoin(Vehicle, InboundOrder.vehicle_id == Vehicle.id)
                .join(ThirdParty, InboundOrder.third_party_id == ThirdParty.id)
                .where(
                    or_(
                        cast(InboundOrder.order_number, SAString).ilike(like),
                        Vehicle.plate.ilike(like),
                        Driver.name.ilike(like),
                        ThirdParty.name.ilike(like),
                        material_match,
                    )
                )
            )

        # Ciclo C (filtros pruebas Daniel): mundo willard — EXISTS sobre lineas
        # con perfil de ese mundo. Restringido a tipo willard: un material
        # "ambos canales" (Q-04, world+compra_regular) NO debe traer compras.
        if willard_world:
            world_match = (
                select(InboundOrderLine.id)
                .join(
                    MaterialKgProfile,
                    InboundOrderLine.material_id == MaterialKgProfile.material_id,
                )
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    MaterialKgProfile.organization_id == organization_id,
                    MaterialKgProfile.willard_world == willard_world,
                )
                .exists()
            )
            q = q.where(
                InboundOrder.inbound_type.in_(WILLARD_INBOUND_TYPES), world_match
            )
        if warehouse_id:
            q = q.where(InboundOrder.warehouse_id == warehouse_id)
        if third_party_id:
            q = q.where(InboundOrder.third_party_id == third_party_id)
        if date_from:
            q = q.where(InboundOrder.date >= date_from)
        if date_to:
            q = q.where(InboundOrder.date <= date_to)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        # Ciclo C (C-3): oldest = FIFO para la bandeja de Johana
        order_clause = (
            InboundOrder.created_at.asc()
            if sort == "oldest"
            else InboundOrder.order_number.desc()
        )
        orders = db.execute(
            q.options(
                joinedload(InboundOrder.lines).joinedload(InboundOrderLine.material),
                joinedload(InboundOrder.warehouse),
                joinedload(InboundOrder.third_party),
                joinedload(InboundOrder.driver),
                joinedload(InboundOrder.vehicle),
                joinedload(InboundOrder.purchase),
            )
            .order_by(order_clause)
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()
        return list(orders), total

    @staticmethod
    def display_status_of(order: InboundOrder) -> str:
        """Ciclo C (C-1): estado UNICO visible — el usuario nunca ve el estado
        tecnico de la orden vs el de la compra. Espejo Python del filtro SQL
        de get_multi (test de paridad los amarra)."""
        if order.status == "annulled":
            return "annulled"
        if order.inbound_type in WILLARD_INBOUND_TYPES:
            return "registered" if order.status == "draft" else "liquidated"
        p = order.purchase
        if p is None:
            return "registered"  # defensivo: derivada ausente
        if p.status == "cancelled":
            return "annulled"
        if p.status == "liquidated":
            return "liquidated"
        return "registered"

    def willard_confirm_audit(
        self, db: Session, organization_id: UUID, order_ids: list[UUID]
    ) -> dict[UUID, tuple[UUID, datetime]]:
        """Ciclo C (C-5): quien liquido una willard = created_by del primer
        KgLedgerMovement confirmado (decision de auditoria B.2)."""
        if not order_ids:
            return {}
        rows = db.execute(
            select(
                KgLedgerMovement.source_id,
                KgLedgerMovement.created_by,
                KgLedgerMovement.created_at,
            )
            .where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id.in_(order_ids),
                KgLedgerMovement.status == "confirmed",
            )
            .order_by(KgLedgerMovement.created_at.asc())
        ).all()
        audit: dict[UUID, tuple[UUID, datetime]] = {}
        for source_id, created_by, created_at in rows:
            audit.setdefault(source_id, (created_by, created_at))
        return audit

    def willard_worlds_by_order(
        self, db: Session, organization_id: UUID, orders: list[InboundOrder]
    ) -> dict[UUID, str]:
        """Ciclo C (C-4): mundo de la orden willard (homogeneo por construccion
        B2) — perfil del material de la primera linea. 1 query por pagina."""
        material_ids = {
            line.material_id
            for o in orders
            if o.inbound_type in WILLARD_INBOUND_TYPES
            for line in o.lines
        }
        if not material_ids:
            return {}
        rows = db.execute(
            select(MaterialKgProfile.material_id, MaterialKgProfile.willard_world).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(material_ids),
            )
        ).all()
        world_by_material = {mid: w for mid, w in rows if w and w != "none"}
        result: dict[UUID, str] = {}
        for o in orders:
            if o.inbound_type not in WILLARD_INBOUND_TYPES:
                continue
            for line in o.lines:
                world = world_by_material.get(line.material_id)
                if world:
                    result[o.id] = world
                    break
        return result

    def kg_deltas_by_movement(
        self, db: Session, organization_id: UUID, order_ids: list[UUID]
    ) -> dict[UUID, Decimal]:
        """Mapa inventory_movement_id -> delta_kg (confirmed) para enriquecer lineas."""
        if not order_ids:
            return {}
        rows = db.execute(
            select(
                KgLedgerMovement.inventory_movement_id,
                KgLedgerMovement.delta_kg,
            ).where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id.in_(order_ids),
                KgLedgerMovement.status == "confirmed",
                KgLedgerMovement.inventory_movement_id.is_not(None),
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    def receipt_movements(
        self, db: Session, organization_id: UUID, order_id: UUID
    ) -> list[InventoryMovement]:
        """Movimientos inbound_receipt vivos de la orden, en orden de creacion
        (paralelo a lines por construccion — mismo loop)."""
        return list(db.execute(
            select(InventoryMovement).where(
                InventoryMovement.organization_id == organization_id,
                InventoryMovement.reference_type == "inbound",
                InventoryMovement.reference_id == order_id,
                InventoryMovement.movement_type == "inbound_receipt",
            ).order_by(InventoryMovement.created_at)
        ).scalars().all())

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _get_or_404(self, db: Session, order_id: UUID, organization_id: UUID) -> InboundOrder:
        order = db.execute(
            select(InboundOrder)
            .options(
                joinedload(InboundOrder.lines).joinedload(InboundOrderLine.material),
                joinedload(InboundOrder.warehouse),
                joinedload(InboundOrder.third_party),
                joinedload(InboundOrder.driver),
                joinedload(InboundOrder.vehicle),
                joinedload(InboundOrder.purchase),
            )
            .where(
                InboundOrder.id == order_id,
                InboundOrder.organization_id == organization_id,
            )
        ).unique().scalar_one_or_none()
        if order is None:
            raise _err("Orden no encontrada", status.HTTP_404_NOT_FOUND)
        return order

    def _resolve_kg_account_for_world(
        self, db: Session, organization_id: UUID, world: str, warehouse_id: UUID
    ) -> KgLedgerAccount:
        """D1: postconsumo -> (willard_baterias, sede); drosses ->
        (willard_drosses, org-wide)."""
        if world == "postconsumo":
            acc_type, wh_filter = "willard_baterias", warehouse_id
        else:  # drosses
            acc_type, wh_filter = "willard_drosses", None
        q = select(KgLedgerAccount).where(
            KgLedgerAccount.organization_id == organization_id,
            KgLedgerAccount.account_type == acc_type,
            KgLedgerAccount.is_active.is_(True),
            KgLedgerAccount.warehouse_id == wh_filter
            if wh_filter is not None
            else KgLedgerAccount.warehouse_id.is_(None),
        )
        account = db.execute(q).scalar_one_or_none()
        if account is None:
            scope = "para esta sede" if wh_filter is not None else "org-wide"
            raise _err(
                f"No existe cuenta kg activa '{acc_type}' {scope} — "
                "cree primero la cuenta kg en Plomo (kg)"
            )
        return account

    def _load_kg_worlds(
        self, db: Session, organization_id: UUID, material_ids: list[UUID]
    ) -> dict:
        """willard_world por material (los materiales sin perfil no aparecen)."""
        if not material_ids:
            return {}
        rows = db.execute(
            select(
                MaterialKgProfile.material_id, MaterialKgProfile.willard_world
            ).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(material_ids),
            )
        ).all()
        return {mid: world for mid, world in rows}

    def _load_current_formulas(
        self, db: Session, organization_id: UUID, material_ids: list[UUID]
    ) -> dict:
        """Formulas vigentes por material — DISTINCT ON con tiebreaker id."""
        rows = db.execute(
            select(MaterialConversionFormula)
            .distinct(MaterialConversionFormula.material_id)
            .where(
                MaterialConversionFormula.organization_id == organization_id,
                MaterialConversionFormula.material_id.in_(material_ids),
            )
            .order_by(
                MaterialConversionFormula.material_id,
                MaterialConversionFormula.created_at.desc(),
                MaterialConversionFormula.id.desc(),
            )
        ).scalars().all()
        return {f.material_id: f for f in rows}

    @staticmethod
    def _compute_kg_lead(formula: MaterialConversionFormula, qty: Decimal) -> Decimal:
        """delta_kg = qty x kg_lead_per_unit (baterias) / kg x lead_percentage
        (drosses). Params viven como numeros JSON -> Decimal(str())."""
        params = formula.parameters or {}
        if formula.formula_type == "battery_to_lead":
            factor = Decimal(str(params["kg_lead_per_unit"]))
        elif formula.formula_type == "drosses_to_lead":
            factor = Decimal(str(params["lead_percentage"]))
        else:
            raise _err(
                f"Tipo de formula '{formula.formula_type}' no soportado en recepcion"
            )
        return (qty * factor).quantize(Decimal("0.0001"))

    def _generate_order_number(self, db: Session, organization_id: UUID) -> int:
        # Advisory lock por org (patron _generate_purchase_number)
        lock_id = hash(str(organization_id)) % (2**63)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        max_number = db.execute(
            select(func.max(InboundOrder.order_number)).where(
                InboundOrder.organization_id == organization_id
            )
        ).scalar_one_or_none()
        return (max_number or 0) + 1

    def _validate_material(self, db: Session, material_id: UUID, organization_id: UUID) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise _err("Material no encontrado", status.HTTP_404_NOT_FOUND)
        if not material.is_active:
            raise _err(
                f"El material '{material.code}' esta inactivo", status.HTTP_400_BAD_REQUEST
            )
        return material

    def _validate_warehouse(self, db: Session, warehouse_id: UUID, organization_id: UUID) -> Warehouse:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.organization_id != organization_id:
            raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if not warehouse.is_active:
            raise _err("La bodega esta inactiva", status.HTTP_400_BAD_REQUEST)
        # Q-12 (feedback Daniel): las bodegas internas (molino/transito) no
        # reciben de terceros — el frontend las filtra; aca defensa
        if not warehouse.is_receiving:
            raise _err(
                f"La bodega '{warehouse.name}' es interna (no recibe material "
                "de terceros) — marquela como receptora en Configuracion si aplica"
            )
        return warehouse

    def _validate_third_party(self, db: Session, tp_id: UUID, organization_id: UUID) -> ThirdParty:
        tp = db.get(ThirdParty, tp_id)
        if not tp or tp.organization_id != organization_id:
            raise _err("Tercero no encontrado", status.HTTP_404_NOT_FOUND)
        if not tp.is_active:
            raise _err(f"El tercero '{tp.name}' esta inactivo", status.HTTP_400_BAD_REQUEST)
        return tp

    @staticmethod
    def _validate_org(db: Session, model, obj_id: UUID, organization_id: UUID, label: str):
        obj = db.get(model, obj_id)
        if not obj or obj.organization_id != organization_id:
            raise _err(f"{label} no encontrado", status.HTTP_404_NOT_FOUND)
        return obj


inbound_order_service = InboundOrderService()
