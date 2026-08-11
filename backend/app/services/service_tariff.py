"""Servicio de ServiceTariff (SAC E1, v0.5 §6.3/§12.1.3, plan §4.3).

Append-only puro (patron PriceList, decision #35): create + lecturas.
Sin update/delete — corregir una tarifa = crear una nueva version; la
vigente es max(created_at, id) por tariff_code.
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service_tariff import ServiceTariff
from app.models.user import User
from app.schemas.service_tariff import (
    CANONICAL_UNIT_BY_CODE,
    ServiceTariffCreate,
    ServiceTariffResponse,
)


class ServiceTariffService:
    """Tarifas de servicio append-only con consulta de vigentes."""

    def create(
        self,
        db: Session,
        obj_in: ServiceTariffCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> ServiceTariff:
        # D11a — coherencia tariff_code <-> unit: un error aqui factura mal
        # en E4 silenciosamente (la tarifa se aplica sobre la base equivocada)
        canonical = CANONICAL_UNIT_BY_CODE[obj_in.tariff_code]
        if obj_in.unit != canonical:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La tarifa '{obj_in.tariff_code}' se cobra {canonical}, "
                f"no {obj_in.unit}",
            )

        # #93 D11: kg_per_unit solo tiene sentido en comision_green_loop (la
        # base de la comision mezcla kg y unidades — "14 kg por unidad")
        if obj_in.kg_per_unit is not None and obj_in.tariff_code != "comision_green_loop":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="kg_per_unit solo aplica a la tarifa comision_green_loop",
            )

        db_obj = ServiceTariff(
            organization_id=organization_id,
            tariff_code=obj_in.tariff_code,
            unit_price_cop=obj_in.unit_price_cop,
            unit=obj_in.unit,
            kg_per_unit=obj_in.kg_per_unit,
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
        tariff_code: Optional[str] = None,
    ) -> list[ServiceTariffResponse]:
        """Historico completo (mas reciente primero), filtro opcional por codigo."""
        query = (
            select(ServiceTariff, User.full_name.label("created_by_name"))
            .outerjoin(User, ServiceTariff.created_by == User.id)
            .where(ServiceTariff.organization_id == organization_id)
        )
        if tariff_code:
            query = query.where(ServiceTariff.tariff_code == tariff_code)
        query = query.order_by(ServiceTariff.created_at.desc(), ServiceTariff.id.desc())

        return [self._to_response(row) for row in db.execute(query).all()]

    def get_current(
        self,
        db: Session,
        organization_id: UUID,
    ) -> list[ServiceTariffResponse]:
        """Tarifa vigente por codigo (DISTINCT ON).

        Tiebreaker `id DESC`: func.now() de PG es transaction-scoped y empata
        en cargas batch (ej. template S4) — invariante 2 del plan (determinista).
        """
        query = (
            select(ServiceTariff, User.full_name.label("created_by_name"))
            .outerjoin(User, ServiceTariff.created_by == User.id)
            .where(ServiceTariff.organization_id == organization_id)
            .distinct(ServiceTariff.tariff_code)
            .order_by(
                ServiceTariff.tariff_code,
                ServiceTariff.created_at.desc(),
                ServiceTariff.id.desc(),
            )
        )
        return [self._to_response(row) for row in db.execute(query).all()]

    @staticmethod
    def _to_response(row) -> ServiceTariffResponse:
        tariff = row[0]
        resp = ServiceTariffResponse.model_validate(tariff)
        resp.created_by_name = row.created_by_name
        return resp


service_tariff = ServiceTariffService()
