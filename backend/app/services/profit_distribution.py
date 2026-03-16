"""Servicio para repartición de utilidades a socios."""
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.models.profit_distribution import ProfitDistribution, ProfitDistributionLine
from app.models.third_party import ThirdParty
from app.services.money_movement import money_movement
from app.schemas.profit_distribution import (
    AvailableProfitResponse,
    PartnerResponse,
    ProfitDistributionCreate,
    ProfitDistributionLineResponse,
    ProfitDistributionResponse,
)
from app.services.reports import ReportService


class ProfitDistributionService:
    """Gestión de repartición de utilidades."""

    def __init__(self):
        self._report_service = ReportService()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def calculate_accumulated_profit(self, db: Session, organization_id: UUID) -> Decimal:
        """Utilidad neta acumulada histórica (P&L sin filtro de fechas)."""
        r = self._report_service._calculate_profit(db, organization_id)
        return r["net_profit"]

    def calculate_distributed_profit(self, db: Session, organization_id: UUID) -> Decimal:
        """Total de utilidades ya distribuidas."""
        val = db.scalar(
            select(func.coalesce(func.sum(ProfitDistributionLine.amount), 0))
            .select_from(ProfitDistributionLine)
            .join(ProfitDistribution, ProfitDistributionLine.distribution_id == ProfitDistribution.id)
            .where(ProfitDistribution.organization_id == organization_id)
        )
        return Decimal(str(val))

    def get_available(self, db: Session, organization_id: UUID) -> AvailableProfitResponse:
        """Retorna utilidad acumulada, distribuida y disponible."""
        accumulated = self.calculate_accumulated_profit(db, organization_id)
        distributed = self.calculate_distributed_profit(db, organization_id)
        return AvailableProfitResponse(
            accumulated_profit=float(accumulated),
            distributed_profit=float(distributed),
            available_profit=float(accumulated - distributed),
        )

    def get_partners(self, db: Session, organization_id: UUID) -> list[PartnerResponse]:
        """Lista de socios (investor_type='socio') con saldo actual."""
        partners = db.execute(
            select(ThirdParty).where(
                ThirdParty.organization_id == organization_id,
                ThirdParty.is_investor == True,
                ThirdParty.investor_type == "socio",
                ThirdParty.is_active == True,
            ).order_by(ThirdParty.name)
        ).scalars().all()
        return [
            PartnerResponse(
                id=p.id,
                name=p.name,
                current_balance=float(p.current_balance),
            )
            for p in partners
        ]

    def list_distributions(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """Historial de reparticiones con paginación."""
        base = select(ProfitDistribution).where(
            ProfitDistribution.organization_id == organization_id,
        ).order_by(ProfitDistribution.date.desc(), ProfitDistribution.created_at.desc())

        total = db.scalar(
            select(func.count()).select_from(
                base.subquery()
            )
        )

        distributions = db.execute(
            base.options(
                joinedload(ProfitDistribution.lines).joinedload(ProfitDistributionLine.third_party)
            ).offset(skip).limit(limit)
        ).unique().scalars().all()

        items = [self._to_response(d) for d in distributions]
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    # ------------------------------------------------------------------
    # Crear distribución
    # ------------------------------------------------------------------

    def create_distribution(
        self,
        db: Session,
        data: ProfitDistributionCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> ProfitDistributionResponse:
        """Crea repartición: distribution + lines + MoneyMovements + actualiza saldos."""
        # Validar socios
        total_amount = Decimal("0")
        validated_lines = []

        for line in data.lines:
            tp = db.get(ThirdParty, line.third_party_id)
            if not tp or tp.organization_id != organization_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Tercero no encontrado: {line.third_party_id}",
                )
            if not tp.is_investor or tp.investor_type != "socio":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"'{tp.name}' no es socio (investor_type='socio')",
                )
            validated_lines.append((tp, line.amount))
            total_amount += line.amount

        # Crear distribución
        distribution = ProfitDistribution(
            date=data.date,
            total_amount=total_amount,
            notes=data.notes,
            created_by=user_id,
            organization_id=organization_id,
        )
        db.add(distribution)
        db.flush()  # Obtener distribution.id

        # Crear líneas + MoneyMovements
        for tp, amount in validated_lines:
            # Crear MoneyMovement usando helper (genera movement_number)
            movement = money_movement._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="profit_distribution",
                amount=amount,
                account_id=None,
                date=data.date,
                description=f"Repartición de Utilidades - {tp.name}",
                third_party_id=tp.id,
                user_id=user_id,
            )

            # Actualizar saldo del socio (le debemos más)
            tp.current_balance -= amount

            # Crear línea de distribución
            dist_line = ProfitDistributionLine(
                distribution_id=distribution.id,
                third_party_id=tp.id,
                amount=amount,
                money_movement_id=movement.id,
            )
            db.add(dist_line)

        db.commit()
        db.refresh(distribution)

        # Cargar relaciones para response
        distribution = db.execute(
            select(ProfitDistribution)
            .options(
                joinedload(ProfitDistribution.lines).joinedload(ProfitDistributionLine.third_party)
            )
            .where(ProfitDistribution.id == distribution.id)
        ).unique().scalar_one()

        return self._to_response(distribution)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_response(d: ProfitDistribution) -> ProfitDistributionResponse:
        return ProfitDistributionResponse(
            id=d.id,
            date=d.date,
            total_amount=float(d.total_amount),
            notes=d.notes,
            created_by=d.created_by,
            created_at=d.created_at,
            lines=[
                ProfitDistributionLineResponse(
                    id=line.id,
                    third_party_id=line.third_party_id,
                    third_party_name=line.third_party.name if line.third_party else "N/A",
                    amount=float(line.amount),
                    money_movement_id=line.money_movement_id,
                )
                for line in d.lines
            ],
        )


profit_distribution_service = ProfitDistributionService()
