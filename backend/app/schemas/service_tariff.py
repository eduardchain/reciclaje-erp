"""Schemas de ServiceTariff (SAC E1, v0.5 §6.3/§11.1.4/§12.1.3).

Append-only puro (patron decision #35): solo Create y Response — sin Update
(el servicio no expone mutacion; corregir = crear nueva version).
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

TariffCode = Literal[
    "maquila_willard",
    "maquila_intersede_cv_jm",
    "maquila_crisol",
    "flete_willard_bog_baq",
    "flete_willard_planta_planta",
    "abono_planta_por_kg",  # W1: porcion de la maquila que Circunvalar le abona a planta
    "comision_green_loop",  # SAC E2 D7: $100/kg material recolectado en ruta (Johana 2026-07-16)
]

TariffUnit = Literal["per_kg_lead", "per_kg_battery", "per_unit", "per_kg_material"]

# D11a — mapa canonico codigo -> unidad (un error aqui factura mal en E4
# silenciosamente). La UI preselecciona la unidad y el servicio valida coherencia.
CANONICAL_UNIT_BY_CODE: dict = {
    "maquila_willard": "per_kg_lead",
    "maquila_intersede_cv_jm": "per_kg_lead",
    "maquila_crisol": "per_kg_lead",
    "flete_willard_bog_baq": "per_kg_battery",
    "flete_willard_planta_planta": "per_kg_lead",
    "abono_planta_por_kg": "per_kg_lead",
    "comision_green_loop": "per_kg_material",
}


class ServiceTariffCreate(BaseModel):
    """Crear nueva version de tarifa (append-only)."""
    tariff_code: TariffCode
    unit_price_cop: Decimal = Field(..., gt=0, description="Precio unitario COP")
    unit: TariffUnit
    # #93 D11: kg equivalentes por unidad para la base de la comision del
    # recolector ("14 kg por unidad, sea cual sea la unidad" — Hugo). Se
    # versiona JUNTO al precio (mismo acuerdo). Solo comision_green_loop.
    kg_per_unit: Optional[Decimal] = Field(None, gt=0)
    notes: Optional[str] = Field(None, max_length=500)


class ServiceTariffResponse(BaseModel):
    id: UUID
    organization_id: UUID
    tariff_code: str
    unit_price_cop: Decimal
    unit: str
    kg_per_unit: Optional[Decimal] = None
    notes: Optional[str] = None
    created_by: UUID
    created_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceTariffListResponse(BaseModel):
    items: list[ServiceTariffResponse]
    total: int
