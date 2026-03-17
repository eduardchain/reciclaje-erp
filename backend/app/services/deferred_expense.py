"""
Operaciones para DeferredExpense (Gastos Diferidos).

Metodos:
- create: Crear gasto diferido con calculo de cuota mensual
- get: Obtener detalle con applications
- get_multi: Listar con filtro por status
- get_pending: Listar gastos activos con cuotas pendientes
- apply_next: Aplicar siguiente cuota (genera MoneyMovement)
- cancel: Cancelar gasto (cuotas aplicadas permanecen)
"""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.deferred_expense import DeferredExpense, DeferredApplication
from app.models.expense_category import ExpenseCategory
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.schemas.money_movement import ExpenseCreate, ProvisionExpenseCreate
from app.services.money_movement import money_movement as mm_service


class CRUDDeferredExpense:
    """Operaciones CRUD para gastos diferidos."""

    def create(
        self,
        db: Session,
        data,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> DeferredExpense:
        """
        Crear gasto diferido.

        Calcula monthly_amount = floor(total_amount / total_months, 2).
        La ultima cuota absorbe el residuo para que la suma sea exacta.
        """
        # Validar categoria de gasto
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

        # Validar cuenta o provision segun tipo
        if data.expense_type == "expense":
            account = db.execute(
                select(MoneyAccount).where(
                    MoneyAccount.id == data.account_id,
                    MoneyAccount.organization_id == organization_id,
                    MoneyAccount.is_active == True,
                )
            ).scalar_one_or_none()
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cuenta de dinero no encontrada",
                )
        elif data.expense_type == "provision_expense":
            from app.services.third_party import third_party as tp_service
            provision = db.execute(
                select(ThirdParty).where(
                    ThirdParty.id == data.provision_id,
                    ThirdParty.organization_id == organization_id,
                    ThirdParty.is_active == True,
                )
            ).scalar_one_or_none()
            if not provision or not tp_service.has_behavior_type(db, provision.id, ["provision"]):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Provision no encontrada o no es tipo provision",
                )

        # Calcular cuota mensual (redondeo hacia abajo)
        monthly = (data.total_amount / data.total_months).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )

        deferred = DeferredExpense(
            organization_id=organization_id,
            name=data.name,
            total_amount=data.total_amount,
            monthly_amount=monthly,
            total_months=data.total_months,
            applied_months=0,
            expense_category_id=data.expense_category_id,
            expense_type=data.expense_type,
            account_id=data.account_id if data.expense_type == "expense" else None,
            provision_id=data.provision_id if data.expense_type == "provision_expense" else None,
            description=data.description,
            start_date=data.start_date,
            status="active",
            created_by=user_id,
        )
        db.add(deferred)
        db.commit()
        db.refresh(deferred)
        return deferred

    def get(
        self,
        db: Session,
        deferred_id: UUID,
        organization_id: UUID,
    ) -> DeferredExpense:
        """Obtener gasto diferido con applications."""
        result = db.execute(
            select(DeferredExpense)
            .options(joinedload(DeferredExpense.applications))
            .where(
                DeferredExpense.id == deferred_id,
                DeferredExpense.organization_id == organization_id,
                DeferredExpense.is_active == True,
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
        base = select(DeferredExpense).where(
            DeferredExpense.organization_id == organization_id,
            DeferredExpense.is_active == True,
        )
        if status_filter:
            base = base.where(DeferredExpense.status == status_filter)

        # Total
        count_q = select(func.count()).select_from(base.subquery())
        total = db.execute(count_q).scalar() or 0

        # Items
        items = db.execute(
            base.order_by(DeferredExpense.created_at.desc())
            .offset(skip)
            .limit(limit)
        ).scalars().all()

        return items, total

    def get_pending(
        self,
        db: Session,
        organization_id: UUID,
    ) -> List[DeferredExpense]:
        """Gastos activos con cuotas pendientes, ordenados por start_date ASC."""
        result = db.execute(
            select(DeferredExpense).where(
                DeferredExpense.organization_id == organization_id,
                DeferredExpense.is_active == True,
                DeferredExpense.status == "active",
            ).order_by(DeferredExpense.start_date.asc())
        ).scalars().all()
        return result

    def apply_next(
        self,
        db: Session,
        deferred_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> DeferredApplication:
        """
        Aplicar la siguiente cuota.

        - Valida que el gasto este activo y tenga cuotas pendientes
        - Calcula monto: monthly_amount, o remainder si es la ultima cuota
        - Crea MoneyMovement via money_movement service
        - Crea DeferredApplication
        - Incrementa applied_months
        - Si todas las cuotas aplicadas -> status = 'completed'
        """
        deferred = self.get(db, deferred_id, organization_id)

        if deferred.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede aplicar cuota: gasto en estado '{deferred.status}'",
            )

        if deferred.applied_months >= deferred.total_months:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Todas las cuotas ya fueron aplicadas",
            )

        # Calcular monto de esta cuota
        next_number = deferred.applied_months + 1
        if next_number == deferred.total_months:
            # Ultima cuota: remainder para que sume exacto
            applied_so_far = deferred.monthly_amount * (deferred.total_months - 1)
            amount = deferred.total_amount - applied_so_far
        else:
            amount = deferred.monthly_amount

        # Descripcion para el movimiento
        desc = f"Gasto diferido: {deferred.name} (cuota {next_number}/{deferred.total_months})"

        now = datetime.now(timezone.utc)

        # Crear MoneyMovement segun tipo
        if deferred.expense_type == "expense":
            expense_data = ExpenseCreate(
                amount=amount,
                expense_category_id=deferred.expense_category_id,
                account_id=deferred.account_id,
                description=desc,
                date=now,
                reference_number=None,
                notes=f"Cuota automatica #{next_number} de gasto diferido '{deferred.name}'",
            )
            movement = mm_service.create_expense(db, expense_data, organization_id, user_id)
        else:
            provision_data = ProvisionExpenseCreate(
                provision_id=deferred.provision_id,
                amount=amount,
                expense_category_id=deferred.expense_category_id,
                date=now,
                description=desc,
                reference_number=None,
                notes=f"Cuota automatica #{next_number} de gasto diferido '{deferred.name}'",
            )
            movement = mm_service.create_provision_expense(db, provision_data, organization_id, user_id)

        # Crear application
        application = DeferredApplication(
            deferred_expense_id=deferred.id,
            application_number=next_number,
            amount=amount,
            money_movement_id=movement.id,
            applied_at=now,
            applied_by=user_id,
        )
        db.add(application)

        # Actualizar contadores
        deferred.applied_months = next_number
        if next_number == deferred.total_months:
            deferred.status = "completed"

        db.commit()
        db.refresh(application)
        return application

    def cancel(
        self,
        db: Session,
        deferred_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> DeferredExpense:
        """
        Cancelar gasto diferido.

        Solo cancela si esta activo. Las cuotas ya aplicadas (MoneyMovements)
        permanecen — se anulan manualmente si se desea.
        """
        deferred = self.get(db, deferred_id, organization_id)

        if deferred.status != "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede cancelar: gasto en estado '{deferred.status}'",
            )

        deferred.status = "cancelled"
        deferred.cancelled_at = datetime.now(timezone.utc)
        deferred.cancelled_by = user_id

        db.commit()
        db.refresh(deferred)
        return deferred


deferred_expense = CRUDDeferredExpense()
