"""
Operaciones para ScheduledExpense (Gastos Diferidos Programados).

Flujo:
1. create(): Pago upfront (deferred_funding) + crea ThirdParty prepago auto
2. apply_next(): Cuota mensual (deferred_expense) que aparece en P&L
3. cancel(): Marca cancelado, cuotas previas intactas

Reemplaza DeferredExpense con modelo mas claro:
- Siempre sale dinero de cuenta al crear (deferred_funding)
- Cuotas son deferred_expense (NO tocan cuenta, SI aparecen en P&L)
- ThirdParty auto-creado con is_system_entity=True como prepago
"""
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List
from uuid import UUID

from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.scheduled_expense import ScheduledExpense, ScheduledExpenseApplication
from app.models.expense_category import ExpenseCategory
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.services.money_movement import money_movement as mm_service


class CRUDScheduledExpense:
    """Operaciones CRUD para gastos diferidos programados."""

    def create(
        self,
        db: Session,
        data,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> ScheduledExpense:
        """
        Crear gasto diferido programado.

        1. Valida cuenta + saldo suficiente
        2. Valida categoria
        3. Calcula cuota mensual (floor)
        4. Crea ThirdParty auto: "[Prepago] nombre", is_system_entity=True
        5. Crea MoneyMovement deferred_funding: account(-), third_party(+)
        6. Crea ScheduledExpense
        """
        # 1. Validar cuenta
        account = db.execute(
            select(MoneyAccount).where(
                MoneyAccount.id == data.source_account_id,
                MoneyAccount.organization_id == organization_id,
                MoneyAccount.is_active == True,
            )
        ).scalar_one_or_none()
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuenta de dinero no encontrada",
            )
        if account.current_balance < data.total_amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fondos insuficientes. Disponible: ${account.current_balance}, Requerido: ${data.total_amount}",
            )

        # 2. Validar categoria
        cat = db.execute(
            select(ExpenseCategory).where(
                ExpenseCategory.id == data.expense_category_id,
                ExpenseCategory.organization_id == organization_id,
                ExpenseCategory.is_active == True,
            )
        ).scalar_one_or_none()
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria de gasto no encontrada",
            )

        # 3. Calcular cuota mensual
        monthly = (data.total_amount / data.total_months).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        # 4. Crear ThirdParty auto (prepago)
        prepaid_tp = ThirdParty(
            name=f"[Prepago] {data.name}",
            organization_id=organization_id,
            is_system_entity=True,
            current_balance=Decimal("0"),
            initial_balance=Decimal("0"),
        )
        db.add(prepaid_tp)
        db.flush()

        # 5. Crear MoneyMovement deferred_funding
        funding_movement = mm_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="deferred_funding",
            amount=data.total_amount,
            account_id=data.source_account_id,
            date=datetime.combine(data.start_date, datetime.min.time(), tzinfo=timezone.utc),
            description=f"Pago gasto diferido: {data.name}",
            third_party_id=prepaid_tp.id,
            user_id=user_id,
        )

        # Aplicar efectos: account(-), third_party(+)
        account.current_balance -= data.total_amount
        prepaid_tp.current_balance += data.total_amount

        # 6. Calcular next_application_date
        next_date = self._calc_next_date(data.start_date, data.apply_day)

        # 7. Crear ScheduledExpense
        scheduled = ScheduledExpense(
            organization_id=organization_id,
            name=data.name,
            description=data.description,
            total_amount=data.total_amount,
            monthly_amount=monthly,
            total_months=data.total_months,
            applied_months=0,
            source_account_id=data.source_account_id,
            prepaid_third_party_id=prepaid_tp.id,
            expense_category_id=data.expense_category_id,
            funding_movement_id=funding_movement.id,
            start_date=data.start_date,
            apply_day=data.apply_day,
            next_application_date=next_date,
            status="active",
            created_by=user_id,
        )
        db.add(scheduled)
        db.commit()
        db.refresh(scheduled)
        return scheduled

    def apply_next(
        self,
        db: Session,
        scheduled_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> ScheduledExpenseApplication:
        """
        Aplicar siguiente cuota.

        - Crea MoneyMovement deferred_expense: account=None, third_party(-)
        - Crea ScheduledExpenseApplication
        - Incrementa applied_months
        - Ultima cuota: absorbe residuo, marca completed
        """
        scheduled = self.get(db, scheduled_id, organization_id)

        if scheduled.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede aplicar cuota: gasto en estado '{scheduled.status}'",
            )

        if scheduled.applied_months >= scheduled.total_months:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Todas las cuotas ya fueron aplicadas",
            )

        # Calcular monto
        next_number = scheduled.applied_months + 1
        if next_number == scheduled.total_months:
            applied_so_far = scheduled.monthly_amount * (scheduled.total_months - 1)
            amount = scheduled.total_amount - applied_so_far
        else:
            amount = scheduled.monthly_amount

        now = datetime.now(timezone.utc)
        desc = f"Cuota gasto diferido: {scheduled.name} ({next_number}/{scheduled.total_months})"

        # Obtener prepaid third party
        prepaid_tp = db.get(ThirdParty, scheduled.prepaid_third_party_id)

        # Crear MoneyMovement deferred_expense
        movement = mm_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="deferred_expense",
            amount=amount,
            account_id=None,
            date=now,
            description=desc,
            third_party_id=scheduled.prepaid_third_party_id,
            expense_category_id=scheduled.expense_category_id,
            notes=f"Cuota #{next_number} de '{scheduled.name}'",
            user_id=user_id,
        )

        # Efecto: third_party(-)
        prepaid_tp.current_balance -= amount

        # Crear application
        application = ScheduledExpenseApplication(
            scheduled_expense_id=scheduled.id,
            application_number=next_number,
            amount=amount,
            money_movement_id=movement.id,
            applied_at=now,
            applied_by=user_id,
        )
        db.add(application)

        # Actualizar contadores
        scheduled.applied_months = next_number
        if next_number == scheduled.total_months:
            scheduled.status = "completed"
            scheduled.next_application_date = None
        else:
            # Calcular siguiente fecha
            if scheduled.next_application_date:
                scheduled.next_application_date = scheduled.next_application_date + relativedelta(months=1)
            else:
                scheduled.next_application_date = self._calc_next_date(
                    scheduled.start_date, scheduled.apply_day
                )

        db.commit()
        db.refresh(application)
        return application

    def cancel(
        self,
        db: Session,
        scheduled_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> ScheduledExpense:
        """Cancelar gasto diferido. Cuotas aplicadas permanecen."""
        scheduled = self.get(db, scheduled_id, organization_id)

        if scheduled.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede cancelar: gasto en estado '{scheduled.status}'",
            )

        scheduled.status = "cancelled"
        scheduled.cancelled_at = datetime.now(timezone.utc)
        scheduled.cancelled_by = user_id
        scheduled.next_application_date = None

        db.commit()
        db.refresh(scheduled)
        return scheduled

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(
        self,
        db: Session,
        scheduled_id: UUID,
        organization_id: UUID,
    ) -> ScheduledExpense:
        """Obtener gasto diferido con applications y relaciones."""
        result = db.execute(
            select(ScheduledExpense)
            .options(
                joinedload(ScheduledExpense.applications),
                joinedload(ScheduledExpense.source_account),
                joinedload(ScheduledExpense.prepaid_third_party),
                joinedload(ScheduledExpense.expense_category),
            )
            .where(
                ScheduledExpense.id == scheduled_id,
                ScheduledExpense.organization_id == organization_id,
                ScheduledExpense.is_active == True,
            )
        ).unique().scalar_one_or_none()
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Gasto diferido no encontrado",
            )
        return result

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        status_filter: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ):
        """Listar gastos diferidos con filtro opcional por status."""
        base = select(ScheduledExpense).where(
            ScheduledExpense.organization_id == organization_id,
            ScheduledExpense.is_active == True,
        )
        if status_filter:
            base = base.where(ScheduledExpense.status == status_filter)

        count_q = select(func.count()).select_from(base.subquery())
        total = db.execute(count_q).scalar() or 0

        items = db.execute(
            base.options(
                joinedload(ScheduledExpense.source_account),
                joinedload(ScheduledExpense.prepaid_third_party),
                joinedload(ScheduledExpense.expense_category),
            )
            .order_by(ScheduledExpense.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()

        return items, total

    def get_pending(
        self,
        db: Session,
        organization_id: UUID,
    ) -> List[ScheduledExpense]:
        """Gastos activos con cuotas pendientes."""
        result = db.execute(
            select(ScheduledExpense)
            .options(
                joinedload(ScheduledExpense.source_account),
                joinedload(ScheduledExpense.prepaid_third_party),
                joinedload(ScheduledExpense.expense_category),
            )
            .where(
                ScheduledExpense.organization_id == organization_id,
                ScheduledExpense.is_active == True,
                ScheduledExpense.status == "active",
            )
            .order_by(ScheduledExpense.next_application_date.asc())
        ).unique().scalars().all()
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _calc_next_date(self, start_date: date, apply_day: int) -> date:
        """Calcular la primera fecha de aplicacion."""
        # Si el dia de inicio >= apply_day, la primera cuota es el mes siguiente
        if start_date.day >= apply_day:
            next_month = start_date + relativedelta(months=1)
        else:
            next_month = start_date

        return next_month.replace(day=apply_day)


scheduled_expense = CRUDScheduledExpense()
