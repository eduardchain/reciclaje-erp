"""Servicio de LeadMarketPrice (CC-014, Q-B).

Append-only puro (patron ServiceTariff / PriceList #35): create + lecturas,
sin update ni delete. La vigente es la de mayor `effective_date`, con
`created_at DESC, id DESC` como desempate — el desempate por id es obligatorio
porque `now()` de PG es transaccional y empata en cargas batch.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.lead_market_price import LeadMarketPrice
from app.models.user import User
from app.schemas.lead_market_price import (
    LeadMarketPriceCreate,
    LeadMarketPriceResponse,
)

# Orden canonico de vigencia, en UN solo sitio: lo usan get_current,
# get_current_as_of y el historico. Si se escribe dos veces, se desincronizan.
_CURRENT_ORDER = (
    LeadMarketPrice.effective_date.desc(),
    LeadMarketPrice.created_at.desc(),
    LeadMarketPrice.id.desc(),
)


class LeadMarketPriceService:
    """Precio de mercado del plomo, append-only con vigencia por fecha de negocio."""

    def create(
        self,
        db: Session,
        obj_in: LeadMarketPriceCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> LeadMarketPrice:
        db_obj = LeadMarketPrice(
            organization_id=organization_id,
            price_per_kg=obj_in.price_per_kg,
            effective_date=obj_in.effective_date,
            notes=obj_in.notes,
            created_by=user_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get_all(
        self,
        db: Session,
        organization_id: UUID,
    ) -> list[LeadMarketPriceResponse]:
        """Historico completo, el vigente primero."""
        query = (
            select(LeadMarketPrice, User.full_name.label("created_by_name"))
            .outerjoin(User, LeadMarketPrice.created_by == User.id)
            .where(LeadMarketPrice.organization_id == organization_id)
            .order_by(*_CURRENT_ORDER)
        )
        return [self._to_response(row) for row in db.execute(query).all()]

    def get_current(
        self,
        db: Session,
        organization_id: UUID,
        cutoff_dt: Optional[datetime] = None,
    ) -> Optional[LeadMarketPrice]:
        """El precio vigente, opcionalmente a una fecha de corte.

        `cutoff_dt` son las 00:00 del dia SIGUIENTE al corte (es lo que arma
        el balance) y se compara con `<`, igual que el resto de los saldos
        as-of. Como `effective_date` se guarda a mediodia UTC, un precio
        fechado el dia del corte entra.
        """
        query = (
            select(LeadMarketPrice)
            .where(LeadMarketPrice.organization_id == organization_id)
            .order_by(*_CURRENT_ORDER)
            .limit(1)
        )
        if cutoff_dt is not None:
            query = query.where(LeadMarketPrice.effective_date < cutoff_dt)
        return db.execute(query).scalars().first()

    def get_current_response(
        self,
        db: Session,
        organization_id: UUID,
    ) -> Optional[LeadMarketPriceResponse]:
        """El vigente con el nombre de quien lo cargo (para la pantalla)."""
        query = (
            select(LeadMarketPrice, User.full_name.label("created_by_name"))
            .outerjoin(User, LeadMarketPrice.created_by == User.id)
            .where(LeadMarketPrice.organization_id == organization_id)
            .order_by(*_CURRENT_ORDER)
            .limit(1)
        )
        row = db.execute(query).first()
        return self._to_response(row) if row else None

    @staticmethod
    def _to_response(row) -> LeadMarketPriceResponse:
        price = row[0]
        resp = LeadMarketPriceResponse.model_validate(price)
        resp.created_by_name = row.created_by_name
        return resp


lead_market_price = LeadMarketPriceService()
