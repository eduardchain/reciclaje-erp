"""
Servicio Transfer — traslado intersede en dos pasos (SAC E3.1, plan v1.1).

Flujo: despacho (origen → bodega virtual de transito, CERO kg CERO pesos) →
recepcion confirmada (transito → destino + intersede_send + par de maquila) →
resolucion de discrepancias → anulacion cascade.

Invariante #1 (alcance N-b): los movimientos de DESPACHO/RECEPCION nunca
cambian current_average_cost — salen y entran al mismo unit_cost snapshot
org-wide. La merma bascula se cierra con InventoryAdjustment decrease sobre
el transito (→ adjustment_net del P&L, decision B1 QA), jamas con
incorporate/remove_from_pool. El cascade de anulacion de esos ajustes usa el
annul canonico (#66, reingreso ponderado).

Gating (E10): el router gatea two_step_transfers_enabled; el par de maquila
se gatea INLINE con internal_maquila_enabled (get_org_setting).
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, joinedload

from app.models.exception_task import DiscrepancyTask
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.money_movement import (
    INTERNAL_MAQUILA_MOVEMENT_TYPES,
    MoneyMovement,
)
from app.models.service_tariff import ServiceTariff
from app.models.transfer import Transfer, TransferLine
from app.models.user import User
from app.models.warehouse import Warehouse
from app.schemas.inventory_adjustment import DecreaseCreate, IncreaseCreate
from app.schemas.transfer import (
    TransferDispatchCreate,
    TransferReceiveRequest,
    TransferResolveRequest,
)
from app.utils.org_settings import get_org_setting

MAQUILA_TARIFF_CODE = "maquila_intersede_cv_jm"
MAQUILA_CATEGORY_NAME = "Maquila Intersede"
KG_SOURCE_TYPE = "intersede_send"


def validate_not_transit_warehouse(
    db: Session, organization_id: UUID, warehouse: Warehouse
) -> None:
    """Guard E12/§2.10: bodega de transito solo opera via el 2-pasos.

    is_transit-check PRIMERO (atributo ya cargado, cero BD): las bodegas
    normales — el 100% de prod — salen sin consultar el flag. El flag-check
    despues (mayor-12) mantiene la garantia prod-inerte: sin
    two_step_transfers_enabled el guard cortocircuita aunque la bodega tenga
    is_transit. db.get de la org via identity map = costo ~0.
    """
    if not warehouse.is_transit:
        return
    if not get_org_setting(db, organization_id, "two_step_transfers_enabled"):
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=(
            f"La bodega '{warehouse.name}' es de tránsito intersede: solo opera "
            "a través de traslados dos pasos. Use el módulo de Traslados."
        ),
    )


class TransferService:
    """Traslados dos pasos con tolerancia, kg intersede y maquila."""

    # ================================================================== #
    # Paso 1 — Despacho                                                   #
    # ================================================================== #

    def dispatch(
        self,
        db: Session,
        data: TransferDispatchCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[Transfer, list[str]]:
        """Despacho: fisico origen → transito. CERO kg, CERO pesos."""
        from app.services.material_conversion_formula import (
            material_conversion_formula,
        )

        warnings: list[str] = []

        if data.from_warehouse_id == data.to_warehouse_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sede origen y destino no pueden ser iguales",
            )

        origin = self._validate_warehouse(db, data.from_warehouse_id, organization_id)
        dest = self._validate_warehouse(db, data.to_warehouse_id, organization_id)
        for wh in (origin, dest):
            if wh.is_transit:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{wh.name}' es una bodega de tránsito — no puede ser origen ni destino",
                )

        transit = self._resolve_transit_warehouse(db, organization_id, dest)

        dispatch_date = data.dispatch_date or self._today_noon()
        self._validate_not_future(dispatch_date, "fecha de despacho")

        transfer = Transfer(
            organization_id=organization_id,
            transfer_number=self._generate_transfer_number(db, organization_id),
            from_warehouse_id=origin.id,
            to_warehouse_id=dest.id,
            transit_warehouse_id=transit.id,
            dispatch_date=dispatch_date,
            status="dispatched",
            notes=data.notes,
            created_by=user_id,
        )
        db.add(transfer)
        db.flush()

        # Formulas vigentes en batch (snapshot AL DESPACHO, E7)
        material_ids = [ln.material_id for ln in data.lines]
        wanted = set(material_ids)
        formulas = {
            f.material_id: f
            for f in material_conversion_formula.get_current(db, organization_id)
            if f.material_id in wanted
        }

        for line_in in data.lines:
            material = self._validate_material(db, line_in.material_id, organization_id)
            qty = line_in.quantity_dispatched

            # Warning stock por bodega (#76: avisar, no bloquear)
            stock_origin = self._warehouse_stock(
                db, material.id, origin.id, organization_id
            )
            if stock_origin < qty:
                warnings.append(
                    f"Stock de {material.code} en '{origin.name}' insuficiente: "
                    f"{float(stock_origin):g}, despachando {float(qty):g}"
                )

            formula = formulas.get(material.id)
            snapshot = None
            if formula is not None:
                snapshot = {
                    "formula_id": str(formula.id),
                    "formula_type": formula.formula_type,
                    "parameters": formula.parameters,
                }

            line = TransferLine(
                organization_id=organization_id,
                transfer_id=transfer.id,
                material_id=material.id,
                quantity_dispatched=qty,
                unit_cost=material.current_average_cost.quantize(Decimal("0.01")),
                is_contributor=formula is not None,
                conversion_formula_snapshot=snapshot,
            )
            db.add(line)
            db.flush()

            # Fisico: origen(-) → transito(+) al MISMO unit_cost (invariante 1)
            self._add_movement(
                db, organization_id, material.id, origin.id,
                -qty, line.unit_cost, dispatch_date,
                transfer.id, f"Traslado #{transfer.transfer_number} → {transit.name}",
            )
            self._add_movement(
                db, organization_id, material.id, transit.id,
                qty, line.unit_cost, dispatch_date,
                transfer.id, f"Traslado #{transfer.transfer_number} desde {origin.name}",
            )

        db.commit()
        db.refresh(transfer)
        return transfer, warnings

    # ================================================================== #
    # Paso 2 — Recepcion                                                  #
    # ================================================================== #

    def receive(
        self,
        db: Session,
        transfer_id: UUID,
        data: TransferReceiveRequest,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[Transfer, list[str]]:
        """Recepcion confirmada — atomica (Q-E3.1-b: todo o nada).

        Por linea (E2): dentro de tolerancia y recibido<=despachado → fisico +
        merma decrease + intersede + par; fuera de tolerancia O recibido>
        despachado (N3) → solo fisico capado + DiscrepancyTask (efectos
        retenidos hasta resolve).
        """
        transfer = self._get_or_404(db, transfer_id, organization_id)
        if transfer.status != "dispatched":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se recibe un traslado despachado (estado actual: '{transfer.status}')",
            )

        receipt_date = data.receipt_date or self._today_noon()
        self._validate_not_future(receipt_date, "fecha de recepción")
        if receipt_date.date() < transfer.dispatch_date.date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha de recepción no puede ser anterior al despacho",
            )

        # Recepcion atomica: la request debe cubrir TODAS las lineas
        lines_by_id = {ln.id: ln for ln in transfer.lines}
        req_ids = {rl.transfer_line_id for rl in data.lines}
        if req_ids != set(lines_by_id.keys()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La recepción debe incluir todas las líneas del traslado (recepción parcial no soportada)",
            )

        # Precondiciones fail-fast (mayor-19): 400 legible ANTES de tocar nada
        contributor_lines = [ln for ln in transfer.lines if ln.is_contributor]
        maquila_on = bool(
            get_org_setting(db, organization_id, "internal_maquila_enabled")
        )
        kg_account = None
        tariff = None
        if contributor_lines:
            kg_account = self._get_intersede_account(db, organization_id)
            if maquila_on:
                tariff = self._get_maquila_tariff(db, organization_id)

        tolerance = Decimal(
            str(get_org_setting(db, organization_id, "transfer_tolerance_pct"))
        )

        warnings: list[str] = []
        for rl in data.lines:
            line = lines_by_id[rl.transfer_line_id]
            self._receive_line(
                db=db,
                transfer=transfer,
                line=line,
                quantity_received=rl.quantity_received,
                receipt_date=receipt_date,
                tolerance=tolerance,
                kg_account=kg_account,
                tariff=tariff,
                maquila_on=maquila_on,
                organization_id=organization_id,
                user_id=user_id,
                warnings=warnings,
            )

        transfer.received_date = receipt_date
        transfer.received_by = user_id
        if data.notes:
            transfer.notes = (
                f"{transfer.notes}\n{data.notes}" if transfer.notes else data.notes
            )
        self._recompute_status(transfer)

        db.commit()
        db.refresh(transfer)
        return transfer, warnings

    def _receive_line(
        self,
        db: Session,
        transfer: Transfer,
        line: TransferLine,
        quantity_received: Decimal,
        receipt_date: datetime,
        tolerance: Decimal,
        kg_account: Optional[KgLedgerAccount],
        tariff: Optional[ServiceTariff],
        maquila_on: bool,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        disp = line.quantity_dispatched
        recv = quantity_received
        line.quantity_received = recv

        variance = (abs(recv - disp) / disp).quantize(Decimal("0.0001"))
        over_received = recv > disp
        within = (not over_received) and variance <= tolerance

        # Fisico SIEMPRE entra, capado a lo despachado (N3: el excedente no se
        # inventaria hasta resolver — evitaria transito negativo + maquila
        # sobre kg que el origen nunca despacho)
        entered = min(recv, disp)
        material = db.get(Material, line.material_id)
        if entered > 0:
            self._add_movement(
                db, organization_id, line.material_id, transfer.transit_warehouse_id,
                -entered, line.unit_cost, receipt_date,
                transfer.id,
                f"Recepción traslado #{transfer.transfer_number}",
            )
            self._add_movement(
                db, organization_id, line.material_id, transfer.to_warehouse_id,
                entered, line.unit_cost, receipt_date,
                transfer.id,
                f"Recepción traslado #{transfer.transfer_number}",
            )

        if within:
            # Merma bascula → decrease sobre TRANSITO al avg org-wide (E8/B1):
            # aterriza en adjustment_net del P&L; transito queda en CERO.
            merma = disp - recv
            if merma > 0:
                self._close_transit_with_merma(
                    db, transfer, line, merma, receipt_date,
                    organization_id, user_id, warnings,
                )
            self._emit_line_effects(
                db, transfer, line, effective_qty=recv,
                receipt_date=receipt_date, kg_account=kg_account,
                tariff=tariff, maquila_on=maquila_on,
                organization_id=organization_id, user_id=user_id,
                warnings=warnings,
            )
            line.effects_emitted = True
        else:
            # Retencion: solo fisico entro; kg + par esperan resolucion
            severity = "critical" if recv == 0 else "high"
            if over_received:
                desc = (
                    f"Traslado #{transfer.transfer_number} {material.code}: recibido "
                    f"{float(recv):g} > despachado {float(disp):g} — revisar báscula/origen"
                )
            else:
                desc = (
                    f"Traslado #{transfer.transfer_number} {material.code}: variación "
                    f"{float(variance * 100):g}% supera tolerancia {float(tolerance * 100):g}%"
                )
            task = DiscrepancyTask(
                organization_id=organization_id,
                discrepancy_type="transfer_tolerance",
                severity=severity,
                status="open",
                entity_type="Transfer",
                entity_id=transfer.id,
                description=desc[:500],
                detected_at=datetime.now(timezone.utc),
                warehouse_id=transfer.to_warehouse_id,
                kg_involved=(recv - disp).quantize(Decimal("0.0001")),
            )
            db.add(task)
            db.flush()
            line.discrepancy_task_id = task.id
            warnings.append(desc)

    def _close_transit_with_merma(
        self,
        db: Session,
        transfer: Transfer,
        line: TransferLine,
        merma: Decimal,
        receipt_date: datetime,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        """Decrease hijo en el transito (B1: → adjustment_net, avg intacto)."""
        from app.services.inventory_adjustment import inventory_adjustment

        adjustment, adj_warnings = inventory_adjustment.decrease(
            db,
            DecreaseCreate(
                material_id=line.material_id,
                warehouse_id=transfer.transit_warehouse_id,
                quantity=merma,
                date=receipt_date,
                reason=f"Merma traslado #{transfer.transfer_number}",
            ),
            organization_id,
            user_id=user_id,
            commit=False,
            allow_transit=True,
        )
        adjustment.transfer_id = transfer.id  # FK del cascade de anulacion (C1)
        warnings.extend(adj_warnings)

    def _emit_line_effects(
        self,
        db: Session,
        transfer: Transfer,
        line: TransferLine,
        effective_qty: Decimal,
        receipt_date: datetime,
        kg_account: Optional[KgLedgerAccount],
        tariff: Optional[ServiceTariff],
        maquila_on: bool,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        """Efectos b+c de la linea: intersede_send + par de maquila."""
        if not line.is_contributor:
            return

        # E6 defensivo: contributor sin snapshot (no deberia ocurrir por
        # construccion E7) → retener con task, nunca 400 post-efectos fisicos
        if not line.conversion_formula_snapshot:
            task = DiscrepancyTask(
                organization_id=organization_id,
                discrepancy_type="transfer_formula_missing",
                severity="high",
                status="open",
                entity_type="Transfer",
                entity_id=transfer.id,
                description=(
                    f"Traslado #{transfer.transfer_number}: línea aportante sin "
                    "snapshot de fórmula — kg y maquila retenidos"
                ),
                detected_at=datetime.now(timezone.utc),
                warehouse_id=transfer.to_warehouse_id,
            )
            db.add(task)
            db.flush()
            line.discrepancy_task_id = task.id
            warnings.append(
                f"Línea {line.material_id}: sin fórmula snapshot — kg/maquila retenidos"
            )
            return

        material = db.get(Material, line.material_id)
        kg_equiv = self._kg_from_snapshot(
            line.conversion_formula_snapshot, effective_qty
        )
        line.kg_lead_equivalent = kg_equiv

        # (b) intersede_send — kg POR LINEA (D5/E2), fecha canonica receipt (E11)
        db.add(
            KgLedgerMovement(
                organization_id=organization_id,
                account_id=kg_account.id,
                delta_kg=kg_equiv,
                transaction_date=receipt_date,
                description=(
                    f"Traslado #{transfer.transfer_number} — {material.code} x "
                    f"{float(effective_qty):g} {material.default_unit or 'kg'}"
                ),
                source_type=KG_SOURCE_TYPE,
                source_id=transfer.id,
                conversion_formula_snapshot=line.conversion_formula_snapshot,
                created_by=user_id,
                status="confirmed",
            )
        )

        # (c) par de maquila — inline gate (E10), embudo _create_movement (#83)
        if maquila_on and tariff is not None:
            self._emit_maquila_pair(
                db, transfer, line, material, kg_equiv, tariff,
                receipt_date, organization_id, user_id,
            )

    def _emit_maquila_pair(
        self,
        db: Session,
        transfer: Transfer,
        line: TransferLine,
        material: Material,
        kg_equiv: Decimal,
        tariff: ServiceTariff,
        receipt_date: datetime,
        organization_id: UUID,
        user_id: Optional[UUID],
    ) -> None:
        from app.services.money_movement import money_movement

        amount = (kg_equiv * tariff.unit_price_cop).quantize(Decimal("0.01"))
        if amount <= 0:
            return
        line.maquila_amount = amount

        category = self._get_or_create_maquila_category(db, organization_id)
        desc = (
            f"Maquila intersede traslado #{transfer.transfer_number} — "
            f"{material.code} ({float(kg_equiv):g} kg eq)"
        )

        mm_exp = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_expense",
            amount=amount,
            account_id=None,
            date=receipt_date,
            description=desc,
            user_id=user_id,
            expense_category_id=category.id,
            business_unit_id=material.business_unit_id,
            source_type="transfer",
            source_id=transfer.id,
            tariff_id=tariff.id,
            warehouse_id=transfer.from_warehouse_id,
        )
        mm_inc = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_income",
            amount=amount,
            account_id=None,
            date=receipt_date,
            description=desc,
            user_id=user_id,
            business_unit_id=material.business_unit_id,
            source_type="transfer",
            source_id=transfer.id,
            tariff_id=tariff.id,
            warehouse_id=transfer.to_warehouse_id,
        )
        mm_exp.transfer_pair_id = mm_inc.id
        mm_inc.transfer_pair_id = mm_exp.id

    # ================================================================== #
    # Resolucion de discrepancias                                         #
    # ================================================================== #

    def resolve(
        self,
        db: Session,
        transfer_id: UUID,
        data: TransferResolveRequest,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[Transfer, list[str]]:
        """Resuelve lineas en discrepancia: justify (acepta bascula) o correct
        (arqueo con final_quantity). Emite kg + par con la cantidad final.

        N-a: en held ya entro el fisico capado a quantity_dispatched — aqui
        solo se mueve el DELTA (y el excedente > despachado entra como
        increase en destino a identidad D2).
        """
        transfer = self._get_or_404(db, transfer_id, organization_id)
        if transfer.status != "held_discrepancy":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Solo se resuelven traslados en discrepancia (estado: '{transfer.status}')",
            )

        lines_by_id = {ln.id: ln for ln in transfer.lines}
        maquila_on = bool(
            get_org_setting(db, organization_id, "internal_maquila_enabled")
        )
        warnings: list[str] = []
        now = datetime.now(timezone.utc)
        receipt_date = transfer.received_date or self._today_noon()

        for rl in data.lines:
            line = lines_by_id.get(rl.transfer_line_id)
            if line is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Línea de traslado no encontrada",
                )
            if line.discrepancy_task_id is None or line.effects_emitted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La línea no está en discrepancia",
                )

            if rl.resolution == "correct":
                if rl.final_quantity is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="'correct' requiere final_quantity (arqueo)",
                    )
                final_qty = rl.final_quantity
            else:
                final_qty = line.quantity_received or Decimal("0")

            line.resolved_quantity = final_qty
            disp = line.quantity_dispatched
            entered = min(line.quantity_received or Decimal("0"), disp)
            target_from_transit = min(final_qty, disp)

            # Delta fisico transito→destino (puede ser negativo = devolver)
            delta = target_from_transit - entered
            if delta != 0:
                self._add_movement(
                    db, organization_id, line.material_id,
                    transfer.transit_warehouse_id, -delta, line.unit_cost,
                    receipt_date, transfer.id,
                    f"Resolución traslado #{transfer.transfer_number}",
                )
                self._add_movement(
                    db, organization_id, line.material_id,
                    transfer.to_warehouse_id, delta, line.unit_cost,
                    receipt_date, transfer.id,
                    f"Resolución traslado #{transfer.transfer_number}",
                )

            # Merma residual del transito → decrease (B1)
            merma = disp - target_from_transit
            if merma > 0:
                self._close_transit_with_merma(
                    db, transfer, line, merma, receipt_date,
                    organization_id, user_id, warnings,
                )

            # Excedente sobre lo despachado → increase en DESTINO a identidad
            # D2 (entra al propio avg → adjustment 0, avg intacto)
            excess = final_qty - disp
            if excess > 0:
                self._enter_excess(
                    db, transfer, line, excess, receipt_date,
                    organization_id, user_id, warnings,
                )

            # Efectos kg + par con la cantidad final
            kg_account = None
            tariff = None
            if line.is_contributor:
                kg_account = self._get_intersede_account(db, organization_id)
                if maquila_on:
                    tariff = self._get_maquila_tariff(db, organization_id)
            self._emit_line_effects(
                db, transfer, line, effective_qty=final_qty,
                receipt_date=receipt_date, kg_account=kg_account,
                tariff=tariff, maquila_on=maquila_on,
                organization_id=organization_id, user_id=user_id,
                warnings=warnings,
            )
            line.effects_emitted = True

            # Cerrar la task
            task = db.get(DiscrepancyTask, line.discrepancy_task_id)
            if task is not None and task.status == "open":
                task.status = "justified" if rl.resolution == "justify" else "corrected"
                task.resolved_at = now
                task.resolved_by = user_id
                task.resolution_notes = data.notes
                task.resolution_entity_type = "Transfer"
                task.resolution_entity_id = transfer.id

        self._recompute_status(transfer)
        db.commit()
        db.refresh(transfer)
        return transfer, warnings

    def _enter_excess(
        self,
        db: Session,
        transfer: Transfer,
        line: TransferLine,
        excess: Decimal,
        receipt_date: datetime,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        from app.services.inventory_adjustment import inventory_adjustment

        material = db.get(Material, line.material_id)
        # Identidad D2: entrar al propio avg no mueve el pool. Fallbacks solo
        # para el caso patologico avg=0 (material sin historia de costo).
        avg = material.current_average_cost
        unit_cost = avg if avg > 0 else (
            line.unit_cost if line.unit_cost > 0 else Decimal("0.01")
        )
        adjustment, adj_warnings = inventory_adjustment.increase(
            db,
            IncreaseCreate(
                material_id=line.material_id,
                warehouse_id=transfer.to_warehouse_id,
                quantity=excess,
                unit_cost=unit_cost,
                date=receipt_date,
                reason=f"Excedente traslado #{transfer.transfer_number}",
            ),
            organization_id,
            user_id=user_id,
            commit=False,
        )
        adjustment.transfer_id = transfer.id
        warnings.extend(adj_warnings)

    # ================================================================== #
    # Anulacion (cascade E9/§2.7)                                         #
    # ================================================================== #

    def annul(
        self,
        db: Session,
        transfer_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[Transfer, list[str]]:
        """Cascade reversa en 1 tx. Warn-no-bloquea (#76, desviacion M2
        declarada: material ya vendido → warning, no 400)."""
        transfer = self._get_or_404(db, transfer_id, organization_id)
        if transfer.status == "annulled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El traslado ya está anulado",
            )

        warnings: list[str] = []
        now = datetime.now(timezone.utc)
        today = self._today_noon()

        # 1a. Reversa fisica append-only (#66): espejo de cada movimiento
        movements = db.execute(
            select(InventoryMovement).where(
                InventoryMovement.organization_id == organization_id,
                InventoryMovement.reference_type == "transfer",
                InventoryMovement.reference_id == transfer.id,
            )
        ).scalars().all()
        for mov in movements:
            self._add_movement(
                db, organization_id, mov.material_id, mov.warehouse_id,
                -mov.quantity, mov.unit_cost, today,
                transfer.id,
                f"Anulación traslado #{transfer.transfer_number}: {reason}"[:500],
            )

        # 1b. Anular ajustes hijos (merma/excedente) via el annul canonico #66
        # — localizados por FK transfer_id (C1), jamas por string en reason
        from app.services.inventory_adjustment import inventory_adjustment

        child_adjustments = db.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.organization_id == organization_id,
                InventoryAdjustment.transfer_id == transfer.id,
                InventoryAdjustment.status == "confirmed",
            )
        ).scalars().all()
        for adj in child_adjustments:
            inventory_adjustment.annul(
                db, adj.id,
                f"Anulación traslado #{transfer.transfer_number}: {reason}"[:500],
                organization_id, user_id=user_id, commit=False,
            )

        # 2. Anular kg intersede (filtro source_type — leccion D-02: un
        # movimiento manual con el mismo source_id sobrevive)
        kg_movs = db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_type == KG_SOURCE_TYPE,
                KgLedgerMovement.source_id == transfer.id,
                KgLedgerMovement.status == "confirmed",
            )
        ).scalars().all()
        for mov in kg_movs:
            mov.status = "annulled"
            mov.annulled_reason = reason
            mov.annulled_at = now
            mov.annulled_by = user_id

        # 3. Anular el par de maquila SIN pasar por annul() (E9 — su guard
        # INTERNAL_MAQUILA_MOVEMENT_TYPES lo 422-earia; deadlock ciclo C)
        from app.services.money_movement import money_movement

        pair_movs = db.execute(
            select(MoneyMovement).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.source_type == "transfer",
                MoneyMovement.source_id == transfer.id,
                MoneyMovement.movement_type.in_(INTERNAL_MAQUILA_MOVEMENT_TYPES),
                MoneyMovement.status == "confirmed",
            )
        ).scalars().all()
        for mm in pair_movs:
            money_movement._reverse_effects(db, mm)  # rama pass explicita (inerte)
            mm.status = "annulled"
            mm.annulled_reason = reason
            mm.annulled_at = now
            mm.annulled_by = user_id

        # 4. Cerrar tasks abiertas
        for line in transfer.lines:
            if line.discrepancy_task_id:
                task = db.get(DiscrepancyTask, line.discrepancy_task_id)
                if task is not None and task.status == "open":
                    task.status = "closed"
                    task.resolved_at = now
                    task.resolved_by = user_id
                    task.resolution_notes = f"Traslado anulado: {reason}"[:500]

        # Warnings de stock negativo tras la reversa (M2: vendido → warn)
        db.flush()
        seen_materials: set[UUID] = set()
        for line in transfer.lines:
            if line.material_id in seen_materials:
                continue
            seen_materials.add(line.material_id)
            material = db.get(Material, line.material_id)
            dest_stock = self._warehouse_stock(
                db, line.material_id, transfer.to_warehouse_id, organization_id
            )
            if dest_stock < 0:
                warnings.append(
                    f"El stock de {material.code} en la sede destino queda negativo "
                    f"tras la reversa: {float(dest_stock):g} — probablemente ya se "
                    "vendió o procesó parte del material trasladado"
                )

        transfer.status = "annulled"
        transfer.annulled_reason = reason
        transfer.annulled_at = now
        transfer.annulled_by = user_id

        db.commit()
        db.refresh(transfer)
        return transfer, warnings

    # ================================================================== #
    # Queries                                                             #
    # ================================================================== #

    def get(
        self, db: Session, transfer_id: UUID, organization_id: UUID
    ) -> Transfer:
        return self._get_or_404(db, transfer_id, organization_id, eager=True)

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        status_filter: Optional[str] = None,
        pending_receipt: bool = False,
        from_warehouse_id: Optional[UUID] = None,
        to_warehouse_id: Optional[UUID] = None,
        material_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
        sort: str = "newest",
    ) -> tuple[list[Transfer], int, int]:
        filters = [Transfer.organization_id == organization_id]
        if status_filter:
            filters.append(Transfer.status == status_filter)
        if pending_receipt:
            filters.append(Transfer.status.in_(["dispatched", "held_discrepancy"]))
        if from_warehouse_id:
            filters.append(Transfer.from_warehouse_id == from_warehouse_id)
        if to_warehouse_id:
            filters.append(Transfer.to_warehouse_id == to_warehouse_id)
        if material_id:
            filters.append(
                Transfer.id.in_(
                    select(TransferLine.transfer_id).where(
                        TransferLine.material_id == material_id
                    )
                )
            )
        if date_from:
            filters.append(Transfer.dispatch_date >= date_from)
        if date_to:
            filters.append(Transfer.dispatch_date <= date_to)

        total = db.scalar(select(func.count(Transfer.id)).where(*filters)) or 0
        pending_count = db.scalar(
            select(func.count(Transfer.id)).where(
                Transfer.organization_id == organization_id,
                Transfer.status.in_(["dispatched", "held_discrepancy"]),
            )
        ) or 0

        order = (
            Transfer.dispatch_date.asc()
            if sort == "oldest"
            else Transfer.dispatch_date.desc()
        )
        items = db.execute(
            select(Transfer)
            .options(
                joinedload(Transfer.lines).joinedload(TransferLine.material),
                joinedload(Transfer.from_warehouse),
                joinedload(Transfer.to_warehouse),
                joinedload(Transfer.transit_warehouse),
                joinedload(Transfer.created_by_user),
                joinedload(Transfer.received_by_user),
            )
            .where(*filters)
            .order_by(order, Transfer.transfer_number.desc())
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()

        return list(items), total, pending_count

    # ================================================================== #
    # Helpers                                                             #
    # ================================================================== #

    def _recompute_status(self, transfer: Transfer) -> None:
        """Estado derivado de las lineas (E2)."""
        if transfer.status == "annulled":
            return
        open_discrepancy = any(
            ln.discrepancy_task_id is not None and not ln.effects_emitted
            for ln in transfer.lines
        )
        all_emitted = all(ln.effects_emitted for ln in transfer.lines)
        if open_discrepancy:
            transfer.status = "held_discrepancy"
        elif all_emitted and transfer.received_date is not None:
            transfer.status = "received"

    def _resolve_transit_warehouse(
        self, db: Session, organization_id: UUID, dest: Warehouse
    ) -> Warehouse:
        """Ruteo unico (menor-31): transito con transit_target == destino."""
        transit = db.execute(
            select(Warehouse)
            .where(
                Warehouse.organization_id == organization_id,
                Warehouse.is_transit == True,  # noqa: E712
                Warehouse.is_active == True,  # noqa: E712
                Warehouse.transit_target_warehouse_id == dest.id,
            )
            .order_by(Warehouse.created_at)
        ).scalars().first()
        if transit is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No existe bodega de tránsito que rutee a '{dest.name}'. "
                    "Cree una en Config → Bodegas (marcarla de tránsito y "
                    "apuntarla a la sede destino)."
                ),
            )
        return transit

    def _get_intersede_account(
        self, db: Session, organization_id: UUID
    ) -> KgLedgerAccount:
        account = db.execute(
            select(KgLedgerAccount)
            .where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.account_type == "intersede",
                KgLedgerAccount.is_active == True,  # noqa: E712
            )
            .order_by(KgLedgerAccount.created_at)
        ).scalars().first()
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No existe cuenta kg 'intersede' activa. Créela en Plomo (kg) "
                    "antes de recibir traslados con materiales aportantes."
                ),
            )
        return account

    def _get_maquila_tariff(
        self, db: Session, organization_id: UUID
    ) -> ServiceTariff:
        tariff = db.execute(
            select(ServiceTariff)
            .where(
                ServiceTariff.organization_id == organization_id,
                ServiceTariff.tariff_code == MAQUILA_TARIFF_CODE,
            )
            .order_by(ServiceTariff.created_at.desc(), ServiceTariff.id.desc())
        ).scalars().first()
        if tariff is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No existe tarifa vigente '{MAQUILA_TARIFF_CODE}'. Créela en "
                    "Config → Tarifas antes de recibir traslados con maquila."
                ),
            )
        return tariff

    def _get_or_create_maquila_category(self, db: Session, organization_id: UUID):
        """Categoria sistema (patron #78/#83) — INDIRECTA, reclasificable."""
        from app.models.expense_category import ExpenseCategory
        from app.services.retention_entities import normalize_entity_name

        target = normalize_entity_name(MAQUILA_CATEGORY_NAME)
        candidates = db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.is_system_entity == True,  # noqa: E712
                ExpenseCategory.is_active == True,  # noqa: E712
            )
        ).scalars().all()
        for cat in candidates:
            if normalize_entity_name(cat.name) == target:
                return cat

        cat = ExpenseCategory(
            organization_id=organization_id,
            name=MAQUILA_CATEGORY_NAME,
            description="Maquila intersede causada al recibir traslados dos pasos (SAC)",
            is_direct_expense=False,
            is_system_entity=True,
        )
        db.add(cat)
        db.flush()
        return cat

    @staticmethod
    def _kg_from_snapshot(snapshot: dict, qty: Decimal) -> Decimal:
        """kg equivalente desde el snapshot AL DESPACHO (E7). Espejo de
        inbound_order._compute_kg_lead pero sobre el dict congelado."""
        params = snapshot.get("parameters") or {}
        ftype = snapshot.get("formula_type")
        if ftype == "battery_to_lead":
            factor = Decimal(str(params["kg_lead_per_unit"]))
        elif ftype == "drosses_to_lead":
            factor = Decimal(str(params["lead_percentage"]))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de fórmula '{ftype}' no soportado en traslados",
            )
        return (qty * factor).quantize(Decimal("0.0001"))

    def _add_movement(
        self,
        db: Session,
        organization_id: UUID,
        material_id: UUID,
        warehouse_id: UUID,
        quantity: Decimal,
        unit_cost: Decimal,
        date: datetime,
        transfer_id: UUID,
        notes: str,
    ) -> InventoryMovement:
        movement = InventoryMovement(
            organization_id=organization_id,
            material_id=material_id,
            warehouse_id=warehouse_id,
            movement_type="transfer",
            quantity=quantity,
            unit_cost=unit_cost,
            reference_type="transfer",
            reference_id=transfer_id,
            date=date,
            notes=notes,
        )
        db.add(movement)
        db.flush()
        return movement

    def _warehouse_stock(
        self,
        db: Session,
        material_id: UUID,
        warehouse_id: UUID,
        organization_id: UUID,
    ) -> Decimal:
        result = db.scalar(
            select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
                InventoryMovement.organization_id == organization_id,
                InventoryMovement.material_id == material_id,
                InventoryMovement.warehouse_id == warehouse_id,
            )
        )
        return Decimal(str(result or 0))

    def _validate_warehouse(
        self, db: Session, warehouse_id: UUID, organization_id: UUID
    ) -> Warehouse:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bodega no encontrada",
            )
        if not warehouse.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bodega está inactiva",
            )
        return warehouse

    def _validate_material(
        self, db: Session, material_id: UUID, organization_id: UUID
    ) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado",
            )
        if not material.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Material está inactivo",
            )
        return material

    @staticmethod
    def _today_noon() -> datetime:
        """Hoy a mediodia UTC (convencion BusinessDate del repo)."""
        now = datetime.now(timezone.utc)
        return now.replace(hour=12, minute=0, second=0, microsecond=0)

    @staticmethod
    def _validate_not_future(value: datetime, label: str) -> None:
        # Convencion tz (memoria gotcha_fechas_utc_vs_local): now(utc).date(),
        # NUNCA date.today() local — evita el flake de la franja 00-05 UTC
        if value.date() > datetime.now(timezone.utc).date():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"La {label} no puede ser futura",
            )

    def _generate_transfer_number(self, db: Session, organization_id: UUID) -> int:
        # Advisory lock por org (patron inbound_order._generate_order_number)
        lock_id = hash(str(organization_id)) % (2**63)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        max_number = db.scalar(
            select(func.coalesce(func.max(Transfer.transfer_number), 0)).where(
                Transfer.organization_id == organization_id
            )
        )
        return int(max_number or 0) + 1

    def _get_or_404(
        self,
        db: Session,
        transfer_id: UUID,
        organization_id: UUID,
        eager: bool = False,
    ) -> Transfer:
        if eager:
            transfer = db.execute(
                select(Transfer)
                .options(
                    joinedload(Transfer.lines).joinedload(TransferLine.material),
                    joinedload(Transfer.from_warehouse),
                    joinedload(Transfer.to_warehouse),
                    joinedload(Transfer.transit_warehouse),
                    joinedload(Transfer.created_by_user),
                    joinedload(Transfer.received_by_user),
                )
                .where(Transfer.id == transfer_id)
            ).unique().scalar_one_or_none()
        else:
            transfer = db.get(Transfer, transfer_id)
        if not transfer or transfer.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Traslado no encontrado",
            )
        return transfer


transfer_service = TransferService()
