"""
Schemas Pydantic para listas de precios por proveedor (PriceListGroup).

La lista trae TODOS los materiales y el usuario decide a cuales les pone precio
(Hugo, Q-21); un cero es una decision deliberada, no un hueco.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PriceListGroupCreate(BaseModel):
    """Alta de una lista, con el sembrado opcional del dia uno."""
    name: str = Field(..., min_length=1, max_length=100)

    seed_from_general: bool = Field(
        False,
        description=(
            "Copia los precios vigentes de la lista general como punto de partida. "
            "Es la salida de Q-26: sin esto, el dia que se enciende la funcion "
            "ningun proveedor tiene precio sugerido"
        ),
    )
    assign_all_suppliers: bool = Field(
        False,
        description=(
            "Asigna a esta lista todos los proveedores de material que hoy no "
            "pertenecen a ninguna. NO roba proveedores de otra lista"
        ),
    )


class PriceListGroupUpdate(BaseModel):
    """Renombrar o desactivar. Los precios de la lista no se tocan aca."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    is_active: Optional[bool] = None


class PriceListGroupResponse(BaseModel):
    id: UUID
    organization_id: UUID
    name: str
    is_active: bool
    member_count: int = Field(0, description="Proveedores asignados a esta lista")
    priced_material_count: int = Field(
        0, description="Materiales con precio > 0 vigente en esta lista"
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PriceListGroupsResponse(BaseModel):
    items: list[PriceListGroupResponse]


class SupplierMembershipItem(BaseModel):
    """
    Un proveedor y la lista a la que pertenece HOY.

    `current_group_*` alimenta el aviso de la pantalla: un proveedor que ya esta
    en otra lista se muestra con el nombre de esa lista **antes** de guardar. La
    unicidad de D2 es un UNIQUE de base, y chocar contra el en el submit seria
    descubrir el conflicto en el peor momento.
    """
    third_party_id: UUID
    third_party_name: str
    current_group_id: Optional[UUID] = None
    current_group_name: Optional[str] = None


class SupplierMembershipsResponse(BaseModel):
    items: list[SupplierMembershipItem]


class SetMembersRequest(BaseModel):
    """
    Reemplaza el conjunto de proveedores de la lista (D12: la asignacion se hace
    DESDE la lista — "para esta lista son estos, estos y estos proveedores").
    """
    third_party_ids: list[UUID] = Field(default_factory=list)


class SeedResultResponse(BaseModel):
    """Que hizo exactamente el sembrado, para poder decirlo en pantalla."""
    group: PriceListGroupResponse
    seeded_prices: int = Field(0, description="Precios copiados desde la lista general")
    assigned_suppliers: int = Field(0, description="Proveedores asignados a la lista")
    skipped_suppliers: int = Field(
        0, description="Proveedores que ya pertenecian a otra lista y no se tocaron"
    )
