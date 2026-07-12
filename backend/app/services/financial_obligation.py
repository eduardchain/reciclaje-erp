"""
Service de Obligaciones Financieras (plan F, v2.1 QA-aprobado).

Ciclo completo: crear (con desembolso o desde saldo migrado) → causar
intereses mensualmente (batch manual, patron depreciacion #21) → pagar/recaudar
intereses y capital por separado → cerrar (settle).

Reglas clave:
- La direccion decide el movement type: payable usa obligation_*, receivable
  usa loan_*. El frontend solo conoce las acciones.
- Guard retroactivo (supuesto 5): movimientos de capital con fecha en un
  periodo ya causado → 400 (la causacion quedaria con tramos falsos).
- Guard espejo (gap v2): ANULAR un movimiento de capital fechado en periodo
  ya causado → 400 por la misma razon.
- Anulacion SOLO desde este modulo (patron #67): money_movement.annul()
  bloquea los tipos de obligacion con 422.
- El saldo de arranque de cada mes se RECONSTRUYE desde los MMs confirmados
  (no desde el contador vivo) para que el batch sea correcto aunque corra
  tarde con abonos de meses posteriores ya registrados.
"""
import calendar
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.financial_obligation import FinancialObligation
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.third_party import ThirdParty
from app.models.third_party_category import (
    ThirdPartyCategory,
    ThirdPartyCategoryAssignment,
)
from app.schemas.financial_obligation import (
    AccruePendingRequest,
    AccrueResultResponse,
    FinancialObligationCreate,
    ObligationDirectionSummary,
    ObligationMovementCreate,
    ObligationSummaryResponse,
    PendingAccrualItem,
    PendingAccrualsResponse,
)
from app.services.money_movement import money_movement as money_movement_service
from app.services.obligation_interest import (
    build_capital_events,
    compute_monthly_interest,
)

_BOGOTA_TZ = timezone(timedelta(hours=-5))
ZERO = Decimal("0.00")

# Tipos por direccion — la unica tabla que el resto del service consulta
ACCRUAL_TYPE = {
    "payable": "obligation_interest_accrual",
    "receivable": "loan_interest_accrual",
}
INTEREST_PAYMENT_TYPE = {
    "payable": "obligation_interest_payment",
    "receivable": "loan_interest_collection",
}
CAPITAL_PAYMENT_TYPE = {
    "payable": "obligation_capital_payment",
    "receivable": "loan_capital_collection",
}
DISBURSEMENT_TYPE = {
    "payable": "obligation_disbursement",
    "receivable": "loan_disbursement",
}

# Efecto VIVO (account_sign, tp_sign) por tipo — sitio 6 de la terna de signos
# (#67). Los otros 5 sitios (reports.py ×3, money_movements.py ×2) DEBEN
# espejar estos signos exactamente.
EFFECT_SIGNS = {
    "obligation_disbursement": (1, -1),      # entra el prestamo, les debemos
    "obligation_interest_accrual": (0, -1),  # debemos mas, sin caja
    "obligation_interest_payment": (-1, 1),
    "obligation_capital_payment": (-1, 1),
    "loan_disbursement": (-1, 1),            # sale el prestamo, nos deben
    "loan_interest_accrual": (0, 1),         # nos deben mas, sin caja
    "loan_interest_collection": (1, -1),
    "loan_capital_collection": (1, -1),
}

# Delta de capital por tipo (para reconstruir el saldo de arranque de cada mes)
CAPITAL_DELTA_SIGNS = {
    "obligation_disbursement": 1,
    "obligation_capital_payment": -1,
    "loan_disbursement": 1,
    "loan_capital_collection": -1,
}


# ----------------------------------------------------------------------
# Helpers de periodos ("YYYY-MM")
# ----------------------------------------------------------------------

def _period_of(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


def _next_period(period: str) -> str:
    year, month = int(period[:4]), int(period[5:7])
    if month == 12:
        return f"{year + 1}-01"
    return f"{year}-{month + 1:02d}"


def _current_period() -> str:
    """Mes actual en Bogota (consistente con #68) — el batch solo causa meses vencidos."""
    return datetime.now(_BOGOTA_TZ).strftime("%Y-%m")


def _period_start_utc(period: str) -> datetime:
    year, month = int(period[:4]), int(period[5:7])
    return datetime(year, month, 1, tzinfo=timezone.utc)


def _last_day_noon_utc(period: str) -> datetime:
    """Ultimo dia CALENDARIO del periodo a mediodia UTC (BusinessDate, riesgo R4).

    La base 30 es solo la matematica del interes; la fecha contable del MM usa
    el calendario real para que el P&L mensual (#50) lo ubique en el mes correcto.
    """
    year, month = int(period[:4]), int(period[5:7])
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 12, 0, 0, tzinfo=timezone.utc)


class FinancialObligationService:
    """Obligaciones financieras bidireccionales."""

    # ==================================================================
    # Lookups
    # ==================================================================

    def get(
        self, db: Session, obligation_id: UUID, organization_id: UUID
    ) -> FinancialObligation:
        obligation = db.execute(
            select(FinancialObligation)
            .options(joinedload(FinancialObligation.third_party))
            .where(
                FinancialObligation.id == obligation_id,
                FinancialObligation.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not obligation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Obligación financiera no encontrada",
            )
        return obligation

    def get_list(
        self,
        db: Session,
        organization_id: UUID,
        direction: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> list[FinancialObligation]:
        query = (
            select(FinancialObligation)
            .options(joinedload(FinancialObligation.third_party))
            .where(FinancialObligation.organization_id == organization_id)
        )
        if direction:
            query = query.where(FinancialObligation.direction == direction)
        if status_filter:
            query = query.where(FinancialObligation.status == status_filter)
        query = query.order_by(FinancialObligation.created_at.desc())
        return list(db.execute(query).scalars().all())

    def get_statement(
        self, db: Session, obligation_id: UUID, organization_id: UUID
    ) -> list[MoneyMovement]:
        """Movimientos de la obligacion (confirmados y anulados), mas reciente primero."""
        self.get(db, obligation_id, organization_id)  # 404 guard
        return list(
            db.execute(
                select(MoneyMovement)
                .where(
                    MoneyMovement.financial_obligation_id == obligation_id,
                    MoneyMovement.organization_id == organization_id,
                )
                .order_by(
                    MoneyMovement.date.desc(), MoneyMovement.movement_number.desc()
                )
            ).scalars().all()
        )

    # ==================================================================
    # Create
    # ==================================================================

    def _validate_obligation_third_party(
        self, db: Session, third_party_id: UUID, organization_id: UUID
    ) -> ThirdParty:
        """Tercero investor con categoria de Obligaciones Financieras.

        Mismo criterio de _classify_third_party (#31): nombre de categoria
        contiene "obligaci" — asi el saldo cae en investors_obligations /
        investor_receivable en los balances.
        """
        tp = money_movement_service._validate_third_party(
            db, third_party_id, organization_id, require_behavior=["investor"]
        )
        category_names = db.execute(
            select(ThirdPartyCategory.name)
            .join(
                ThirdPartyCategoryAssignment,
                ThirdPartyCategoryAssignment.category_id == ThirdPartyCategory.id,
            )
            .where(ThirdPartyCategoryAssignment.third_party_id == third_party_id)
        ).scalars().all()
        if not any("obligaci" in name.lower() for name in category_names):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El tercero '{tp.name}' no tiene categoría de Obligaciones "
                    "Financieras. Asígnela antes de crear la obligación."
                ),
            )
        return tp

    def create(
        self,
        db: Session,
        data: FinancialObligationCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> FinancialObligation:
        tp = self._validate_obligation_third_party(
            db, data.third_party_id, organization_id
        )

        # 1 tercero = 1 obligacion activa (convencion del cliente)
        existing = db.execute(
            select(FinancialObligation).where(
                FinancialObligation.third_party_id == data.third_party_id,
                FinancialObligation.organization_id == organization_id,
                FinancialObligation.status == "active",
            )
        ).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El tercero '{tp.name}' ya tiene una obligación activa. "
                    "Cambio de tasa = tercero/obligación nueva (convención); "
                    "cierre la actual primero."
                ),
            )

        if data.mode == "disbursement":
            account = money_movement_service._validate_account(
                db, data.disbursement.account_id, organization_id
            )
            capital = data.disbursement.amount
            start_period = data.accrual_start_period or _period_of(
                data.disbursement.date
            )
            disbursement_date = data.disbursement.date
        else:
            # Desde saldo existente (migracion): el saldo del tercero ES el capital
            balance = tp.current_balance or ZERO
            if data.direction == "payable" and balance >= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Para una obligación por pagar el saldo del tercero debe ser "
                        f"negativo (le debemos). Saldo actual: ${balance:,.2f}"
                    ),
                )
            if data.direction == "receivable" and balance <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Para un préstamo por cobrar el saldo del tercero debe ser "
                        f"positivo (nos debe). Saldo actual: ${balance:,.2f}"
                    ),
                )
            account = None
            capital = abs(balance)
            start_period = data.accrual_start_period or _current_period()
            disbursement_date = None

        obligation = FinancialObligation(
            organization_id=organization_id,
            third_party_id=data.third_party_id,
            direction=data.direction,
            monthly_rate=data.monthly_rate,
            capital_balance=capital,
            pending_interest=ZERO,
            accrual_start_period=start_period,
            disbursement_date=disbursement_date,
            status="active",
            notes=data.notes,
            created_by=user_id,
        )
        db.add(obligation)
        db.flush()

        if data.mode == "disbursement":
            movement_type = DISBURSEMENT_TYPE[data.direction]
            label = (
                f"Desembolso recibido de {tp.name} (obligación financiera)"
                if data.direction == "payable"
                else f"Desembolso de préstamo a {tp.name}"
            )
            movement = money_movement_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type=movement_type,
                amount=capital,
                account_id=account.id,
                date=data.disbursement.date,
                description=label,
                third_party_id=tp.id,
                user_id=user_id,
                financial_obligation_id=obligation.id,
            )
            self._apply_effects(movement.movement_type, capital, account, tp)

        db.commit()
        db.refresh(obligation)
        return obligation

    # ==================================================================
    # Efectos (sitio 6 de la terna de signos)
    # ==================================================================

    def _apply_effects(
        self,
        movement_type: str,
        amount: Decimal,
        account: Optional[MoneyAccount],
        tp: Optional[ThirdParty],
        reverse: bool = False,
    ) -> None:
        acc_sign, tp_sign = EFFECT_SIGNS[movement_type]
        factor = -1 if reverse else 1
        if account is not None and acc_sign:
            account.current_balance += acc_sign * amount * factor
        if tp is not None and tp_sign:
            tp.current_balance += tp_sign * amount * factor

    # ==================================================================
    # Guards
    # ==================================================================

    def _get_active(
        self, db: Session, obligation_id: UUID, organization_id: UUID
    ) -> FinancialObligation:
        obligation = self.get(db, obligation_id, organization_id)
        if obligation.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La obligación está cerrada (settled) — no acepta movimientos",
            )
        return obligation

    def _retro_guard(self, obligation: FinancialObligation, date: datetime) -> None:
        """Movimiento de capital en periodo ya causado → 400 (supuesto 5)."""
        if (
            obligation.last_accrued_period
            and _period_of(date) <= obligation.last_accrued_period
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El período {_period_of(date)} ya tiene intereses causados; "
                    "anule la causación para corregir"
                ),
            )

    # ==================================================================
    # Movimientos: capital, intereses, desembolso adicional
    # ==================================================================

    def create_capital_payment(
        self,
        db: Session,
        obligation_id: UUID,
        organization_id: UUID,
        data: ObligationMovementCreate,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """Abono (payable) o recaudo (receivable) de capital."""
        obligation = self._get_active(db, obligation_id, organization_id)
        self._retro_guard(obligation, data.date)
        if data.amount > obligation.capital_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El abono (${data.amount:,.2f}) supera el capital vigente "
                    f"(${obligation.capital_balance:,.2f})"
                ),
            )
        account = money_movement_service._validate_account(
            db, data.account_id, organization_id
        )
        tp = obligation.third_party
        movement_type = CAPITAL_PAYMENT_TYPE[obligation.direction]
        label = (
            f"Abono a capital — {tp.name}"
            if obligation.direction == "payable"
            else f"Recaudo de capital — {tp.name}"
        )
        movement = money_movement_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type=movement_type,
            amount=data.amount,
            account_id=account.id,
            date=data.date,
            description=label,
            third_party_id=tp.id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
            financial_obligation_id=obligation.id,
        )
        self._apply_effects(movement_type, data.amount, account, tp)
        obligation.capital_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_interest_payment(
        self,
        db: Session,
        obligation_id: UUID,
        organization_id: UUID,
        data: ObligationMovementCreate,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """Pago (payable) o recaudo (receivable) de intereses pendientes. Parcial ok."""
        obligation = self._get_active(db, obligation_id, organization_id)
        if data.amount > obligation.pending_interest:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El pago (${data.amount:,.2f}) supera los intereses pendientes "
                    f"(${obligation.pending_interest:,.2f})"
                ),
            )
        account = money_movement_service._validate_account(
            db, data.account_id, organization_id
        )
        tp = obligation.third_party
        movement_type = INTEREST_PAYMENT_TYPE[obligation.direction]
        label = (
            f"Pago de intereses — {tp.name}"
            if obligation.direction == "payable"
            else f"Recaudo de intereses — {tp.name}"
        )
        movement = money_movement_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type=movement_type,
            amount=data.amount,
            account_id=account.id,
            date=data.date,
            description=label,
            third_party_id=tp.id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
            financial_obligation_id=obligation.id,
        )
        self._apply_effects(movement_type, data.amount, account, tp)
        obligation.pending_interest -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_additional_disbursement(
        self,
        db: Session,
        obligation_id: UUID,
        organization_id: UUID,
        data: ObligationMovementCreate,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """Desembolso adicional (supuesto 6): mismo tercero, misma tasa, mas plata."""
        obligation = self._get_active(db, obligation_id, organization_id)
        self._retro_guard(obligation, data.date)
        account = money_movement_service._validate_account(
            db, data.account_id, organization_id
        )
        tp = obligation.third_party
        movement_type = DISBURSEMENT_TYPE[obligation.direction]
        movement = money_movement_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type=movement_type,
            amount=data.amount,
            account_id=account.id,
            date=data.date,
            description=f"Desembolso adicional — {tp.name}",
            third_party_id=tp.id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
            financial_obligation_id=obligation.id,
        )
        self._apply_effects(movement_type, data.amount, account, tp)
        obligation.capital_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def settle(
        self, db: Session, obligation_id: UUID, organization_id: UUID
    ) -> FinancialObligation:
        """Cierre manual — exige capital y pendientes en $0."""
        obligation = self._get_active(db, obligation_id, organization_id)
        if obligation.capital_balance != 0 or obligation.pending_interest != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"No se puede cerrar: capital vigente ${obligation.capital_balance:,.2f}, "
                    f"intereses pendientes ${obligation.pending_interest:,.2f}. "
                    "Ambos deben estar en $0."
                ),
            )
        obligation.status = "settled"
        db.commit()
        db.refresh(obligation)
        return obligation

    # ==================================================================
    # Causacion (batch manual, patron #21)
    # ==================================================================

    def _capital_movements(
        self, db: Session, obligation: FinancialObligation
    ) -> list[MoneyMovement]:
        """MMs confirmados que mueven capital, en orden cronologico."""
        capital_types = [
            DISBURSEMENT_TYPE[obligation.direction],
            CAPITAL_PAYMENT_TYPE[obligation.direction],
        ]
        return list(
            db.execute(
                select(MoneyMovement)
                .where(
                    MoneyMovement.financial_obligation_id == obligation.id,
                    MoneyMovement.movement_type.in_(capital_types),
                    MoneyMovement.status == "confirmed",
                )
                .order_by(MoneyMovement.date.asc())
            ).scalars().all()
        )

    def _initial_capital(
        self, obligation: FinancialObligation, movements: list[MoneyMovement]
    ) -> Decimal:
        """Capital semilla (modo from_balance) reconstruido: contador − Σ deltas.

        Time-independent: los MMs posteriores ya estan restados/sumados en el
        contador, asi que la resta los cancela exactamente.
        """
        total_delta = sum(
            (
                CAPITAL_DELTA_SIGNS[m.movement_type] * m.amount
                for m in movements
            ),
            ZERO,
        )
        return obligation.capital_balance - total_delta

    def _events_for_period(
        self,
        obligation: FinancialObligation,
        movements: list[MoneyMovement],
        initial_capital: Decimal,
        period: str,
    ) -> list[tuple[int, Decimal]]:
        """Eventos de capital del mes: apertura (cierre de M−1) + deltas del mes."""
        start = _period_start_utc(period)
        end = _period_start_utc(_next_period(period))
        opening = initial_capital + sum(
            (
                CAPITAL_DELTA_SIGNS[m.movement_type] * m.amount
                for m in movements
                if m.date < start
            ),
            ZERO,
        )
        day_deltas = [
            (m.date.day, CAPITAL_DELTA_SIGNS[m.movement_type] * m.amount)
            for m in movements
            if start <= m.date < end
        ]
        return build_capital_events(opening, day_deltas)

    def _accrued_periods(
        self, db: Session, obligation: FinancialObligation
    ) -> set[str]:
        rows = db.execute(
            select(MoneyMovement.obligation_period).where(
                MoneyMovement.financial_obligation_id == obligation.id,
                MoneyMovement.movement_type == ACCRUAL_TYPE[obligation.direction],
                MoneyMovement.status == "confirmed",
                MoneyMovement.obligation_period.isnot(None),
            )
        ).scalars().all()
        return set(rows)

    def _pending_items(
        self, db: Session, organization_id: UUID
    ) -> list[tuple[FinancialObligation, PendingAccrualItem]]:
        """Periodos cerrados sin causar, por obligacion activa, con monto calculado.

        Solo periodos VENCIDOS (< mes actual Bogota) — nunca el mes en curso.
        Capital $0 todo el mes → se salta (no genera MM ni aparece en preview).
        """
        current = _current_period()
        obligations = self.get_list(db, organization_id, status_filter="active")
        results: list[tuple[FinancialObligation, PendingAccrualItem]] = []

        for obligation in obligations:
            start = obligation.accrual_start_period
            if obligation.disbursement_date:
                start = max(start, _period_of(obligation.disbursement_date))
            accrued = self._accrued_periods(db, obligation)
            movements = self._capital_movements(db, obligation)
            initial = self._initial_capital(obligation, movements)

            period = start
            while period < current:
                if period not in accrued:
                    events = self._events_for_period(
                        obligation, movements, initial, period
                    )
                    amount, breakdown = compute_monthly_interest(
                        events, obligation.monthly_rate
                    )
                    if amount > 0:
                        results.append(
                            (
                                obligation,
                                PendingAccrualItem(
                                    obligation_id=obligation.id,
                                    third_party_name=obligation.third_party.name,
                                    direction=obligation.direction,
                                    period=period,
                                    amount=amount,
                                    breakdown=breakdown,
                                ),
                            )
                        )
                period = _next_period(period)

        # Orden cronologico global (las causaciones se crean en este orden)
        results.sort(key=lambda pair: (pair[1].period, pair[1].third_party_name))
        return results

    def get_pending_accruals(
        self, db: Session, organization_id: UUID
    ) -> PendingAccrualsResponse:
        items = [item for _, item in self._pending_items(db, organization_id)]
        total_payable = sum(
            (i.amount for i in items if i.direction == "payable"), ZERO
        )
        total_receivable = sum(
            (i.amount for i in items if i.direction == "receivable"), ZERO
        )
        return PendingAccrualsResponse(
            items=items,
            total_payable=total_payable,
            total_receivable=total_receivable,
            has_payable=any(i.direction == "payable" for i in items),
        )

    def accrue_pending(
        self,
        db: Session,
        organization_id: UUID,
        data: AccruePendingRequest,
        user_id: Optional[UUID] = None,
    ) -> AccrueResultResponse:
        """Crear las causaciones pendientes en orden cronologico. Idempotente."""
        pending = self._pending_items(db, organization_id)

        has_payable = any(item.direction == "payable" for _, item in pending)
        if has_payable and not data.expense_category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Hay intereses por pagar pendientes: seleccione la categoría "
                    "de gasto (ej: Intereses)"
                ),
            )
        if data.expense_category_id:
            money_movement_service._validate_expense_category(
                db, data.expense_category_id, organization_id
            )

        created = 0
        total_payable = ZERO
        total_receivable = ZERO
        for obligation, item in pending:
            movement_type = ACCRUAL_TYPE[obligation.direction]
            movement = money_movement_service._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type=movement_type,
                amount=item.amount,
                account_id=None,
                date=_last_day_noon_utc(item.period),
                description=f"Intereses {item.period}: {item.breakdown}",
                third_party_id=obligation.third_party_id,
                expense_category_id=(
                    data.expense_category_id
                    if obligation.direction == "payable"
                    else None
                ),
                user_id=user_id,
                financial_obligation_id=obligation.id,
                obligation_period=item.period,
            )
            self._apply_effects(
                movement_type, item.amount, None, obligation.third_party
            )
            obligation.pending_interest += item.amount
            if (
                obligation.last_accrued_period is None
                or item.period > obligation.last_accrued_period
            ):
                obligation.last_accrued_period = item.period

            created += 1
            if obligation.direction == "payable":
                total_payable += item.amount
            else:
                total_receivable += item.amount

        db.commit()
        return AccrueResultResponse(
            created_count=created,
            total_payable=total_payable,
            total_receivable=total_receivable,
        )

    # ==================================================================
    # Anulacion (solo desde el modulo — Tesoreria directa da 422)
    # ==================================================================

    def annul_movement(
        self,
        db: Session,
        movement_id: UUID,
        organization_id: UUID,
        reason: str,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        movement = db.get(MoneyMovement, movement_id)
        if not movement or movement.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movimiento no encontrado",
            )
        if not movement.financial_obligation_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El movimiento no pertenece a una obligación financiera",
            )
        if movement.status == "annulled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El movimiento ya está anulado",
            )

        obligation = self.get(
            db, movement.financial_obligation_id, organization_id
        )
        if obligation.status != "active":
            # Anular movimientos de una obligacion cerrada dejaria contadores
            # > 0 en una settled (estado imposible) — no hay reopen en v1
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La obligación está cerrada (settled) — sus movimientos no se pueden anular",
            )
        tp = obligation.third_party
        account = (
            db.get(MoneyAccount, movement.account_id)
            if movement.account_id
            else None
        )
        mtype = movement.movement_type
        amount = movement.amount

        if mtype == ACCRUAL_TYPE[obligation.direction]:
            # Anular causacion: revierte pendientes y libera el periodo
            if obligation.pending_interest < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No se puede anular la causación: parte de esos intereses "
                        "ya fue pagada/recaudada. Anule primero los pagos de intereses."
                    ),
                )
            self._apply_effects(mtype, amount, None, tp, reverse=True)
            obligation.pending_interest -= amount
            if movement.obligation_period == obligation.last_accrued_period:
                remaining = self._accrued_periods(db, obligation) - {
                    movement.obligation_period
                }
                obligation.last_accrued_period = max(remaining) if remaining else None

        elif mtype == INTEREST_PAYMENT_TYPE[obligation.direction]:
            # No toca tramos → sin guard de periodo
            self._apply_effects(mtype, amount, account, tp, reverse=True)
            obligation.pending_interest += amount

        elif mtype == CAPITAL_PAYMENT_TYPE[obligation.direction]:
            # Guard espejo del supuesto 5 (gap v2): mismo agujero retroactivo
            # que el guard de creacion, pero por la puerta de atras
            self._retro_guard_annul(obligation, movement)
            self._apply_effects(mtype, amount, account, tp, reverse=True)
            obligation.capital_balance += amount

        elif mtype == DISBURSEMENT_TYPE[obligation.direction]:
            self._retro_guard_annul(obligation, movement)
            # Desembolso inicial: 400 si hay cualquier otro movimiento posterior
            is_initial = (
                obligation.disbursement_date is not None
                and movement.date == obligation.disbursement_date
            )
            if is_initial:
                later = db.execute(
                    select(MoneyMovement.id).where(
                        MoneyMovement.financial_obligation_id == obligation.id,
                        MoneyMovement.status == "confirmed",
                        MoneyMovement.id != movement.id,
                        MoneyMovement.created_at > movement.created_at,
                    ).limit(1)
                ).scalar_one_or_none()
                if later:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            "No se puede anular el desembolso inicial: la obligación "
                            "tiene movimientos posteriores. Anúlelos primero."
                        ),
                    )
            if obligation.capital_balance < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "No se puede anular el desembolso: el capital vigente "
                        f"(${obligation.capital_balance:,.2f}) quedaría negativo"
                    ),
                )
            self._apply_effects(mtype, amount, account, tp, reverse=True)
            obligation.capital_balance -= amount

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El tipo '{mtype}' no corresponde a la dirección de la obligación"
                ),
            )

        now = datetime.now(timezone.utc)
        movement.status = "annulled"
        movement.annulled_at = now
        movement.annulled_by = user_id
        movement.annulled_reason = reason

        db.commit()
        db.refresh(movement)
        return movement

    def _retro_guard_annul(
        self, obligation: FinancialObligation, movement: MoneyMovement
    ) -> None:
        if (
            obligation.last_accrued_period
            and _period_of(movement.date) <= obligation.last_accrued_period
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El período {_period_of(movement.date)} ya tiene intereses "
                    "causados: la causación quedaría con tramos falsos. Anule "
                    "primero las causaciones desde ese período."
                ),
            )

    # ==================================================================
    # Summary (KPIs por direccion)
    # ==================================================================

    def get_summary(
        self, db: Session, organization_id: UUID
    ) -> ObligationSummaryResponse:
        summaries = {}
        current = _current_period()
        for direction in ("payable", "receivable"):
            obligations = [
                o
                for o in self.get_list(
                    db, organization_id, direction=direction, status_filter="active"
                )
            ]
            total_capital = sum((o.capital_balance for o in obligations), ZERO)
            total_pending = sum((o.pending_interest for o in obligations), ZERO)
            if total_capital > 0:
                weighted = (
                    sum(
                        (o.capital_balance * o.monthly_rate for o in obligations),
                        ZERO,
                    )
                    / total_capital
                ).quantize(Decimal("0.01"))
            else:
                weighted = ZERO

            # Proyeccion del mes en curso: eventos registrados hasta hoy,
            # el capital vigente corre hasta el dia 30
            projection = ZERO
            for obligation in obligations:
                movements = self._capital_movements(db, obligation)
                initial = self._initial_capital(obligation, movements)
                events = self._events_for_period(
                    obligation, movements, initial, current
                )
                amount, _ = compute_monthly_interest(
                    events, obligation.monthly_rate
                )
                projection += amount

            summaries[direction] = ObligationDirectionSummary(
                direction=direction,
                count=len(obligations),
                total_capital=total_capital,
                total_pending_interest=total_pending,
                weighted_avg_rate=weighted,
                current_month_projection=projection,
            )

        return ObligationSummaryResponse(
            payable=summaries["payable"], receivable=summaries["receivable"]
        )


# Instancia singleton para uso en endpoints
financial_obligation = FinancialObligationService()
