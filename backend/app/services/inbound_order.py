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
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
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
            goes_directly_to_jm=obj_in.goes_directly_to_jm,
            status="confirmed",
            created_by=user_id,
        )
        db.add(order)
        db.flush()

        warnings: list[str] = []
        if is_willard:
            self._apply_willard_effects(
                db, order, obj_in.lines, organization_id, user_id
            )
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
            for l in obj_in.lines:
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

        db.commit()
        db.refresh(order)
        return order, warnings

    # ------------------------------------------------------------------ #
    # Efectos Willard (create + re-apply de edicion D18)                  #
    # ------------------------------------------------------------------ #
    def _apply_willard_effects(
        self,
        db: Session,
        order: InboundOrder,
        lines_in,
        organization_id: UUID,
        user_id: UUID,
    ) -> None:
        material_ids = [l.material_id for l in lines_in]
        worlds = self._load_kg_worlds(db, organization_id, material_ids)
        formulas = self._load_current_formulas(db, organization_id, material_ids)
        today = datetime.now(timezone.utc).date()
        # Cache de cuenta kg por mundo (la sede de baterias es fija: order.warehouse_id)
        account_by_world: dict[str, KgLedgerAccount] = {}

        for line_in in lines_in:
            material = self._validate_material(db, line_in.material_id, organization_id)
            qty = Decimal(str(line_in.quantity))

            # D1/CC-004: el mundo del material rutea la cuenta kg (no un subtipo
            # de encabezado). Un material sin clasificacion Willard no puede
            # recibirse aca — se recibe como Compra regular.
            world = worlds.get(line_in.material_id)
            if world is None or world == "none":
                raise _err(
                    f"El material {material.code} no es de mundo Willard "
                    "(postconsumo/drosses) — clasifiquelo en el maestro de materiales "
                    "o recibalo como Compra regular"
                )
            if world not in account_by_world:
                account_by_world[world] = self._resolve_kg_account_for_world(
                    db, organization_id, world, order.warehouse_id
                )
            account = account_by_world[world]
            kg_source = KG_SOURCE_BY_WORLD[world]
            label = WORLD_LABELS[world]

            formula = formulas.get(line_in.material_id)
            if formula is None:
                raise _err(
                    f"No hay formula de conversion vigente para {material.code} — "
                    "creela primero en el maestro de materiales"
                )
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
        if order.status != "confirmed":
            raise _err(
                f"No se puede anular: la orden esta en estado '{order.status}'",
                status.HTTP_400_BAD_REQUEST,
            )

        warnings: list[str] = []
        if order.inbound_type in WILLARD_INBOUND_TYPES:
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
            # viven en la compra derivada (D7b: doble verdad prohibida)
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
        # (la fecha mueve los eventos kg e inventario)
        needs_reapply = is_willard and bool(
            {"lines", "date"} & set(fields_set.keys())
        )
        if needs_reapply:
            from types import SimpleNamespace
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
        if obj_in.goes_directly_to_jm is not None:
            order.goes_directly_to_jm = obj_in.goes_directly_to_jm

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
        third_party_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InboundOrder], int]:
        q = select(InboundOrder).where(InboundOrder.organization_id == organization_id)
        if inbound_type:
            q = q.where(InboundOrder.inbound_type == inbound_type)
        if status_filter:
            q = q.where(InboundOrder.status == status_filter)
        if third_party_id:
            q = q.where(InboundOrder.third_party_id == third_party_id)
        if date_from:
            q = q.where(InboundOrder.date >= date_from)
        if date_to:
            q = q.where(InboundOrder.date <= date_to)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        orders = db.execute(
            q.options(
                joinedload(InboundOrder.lines).joinedload(InboundOrderLine.material),
                joinedload(InboundOrder.warehouse),
                joinedload(InboundOrder.third_party),
                joinedload(InboundOrder.driver),
                joinedload(InboundOrder.vehicle),
                joinedload(InboundOrder.purchase),
            )
            .order_by(InboundOrder.order_number.desc())
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()
        return list(orders), total

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
