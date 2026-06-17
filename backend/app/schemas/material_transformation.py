"""
Schemas Pydantic para MaterialTransformation (Transformacion de Materiales).

La transformacion permite desintegrar un material compuesto en sus componentes.
Ejemplo: Motor 500kg → Cobre 200kg + Hierro 180kg + Aluminio 100kg + Merma 20kg

Validaciones:
- sum(lineas.quantity) + waste_quantity == source_quantity
- source_quantity > 0
- Todas las cantidades de linea > 0
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, model_validator

from app.utils.dates import BusinessDate


# ---------------------------------------------------------------------------
# Schemas de creacion
# ---------------------------------------------------------------------------

class TransformationLineCreate(BaseModel):
    """Linea de destino para una transformacion."""
    destination_material_id: UUID = Field(..., description="Material destino")
    destination_warehouse_id: UUID = Field(..., description="Bodega destino")
    quantity: Decimal = Field(..., gt=0, description="Cantidad resultante")
    unit_cost: Optional[Decimal] = Field(None, gt=0, description="Costo unitario (solo para distribucion manual)")


class MaterialTransformationCreate(BaseModel):
    """Creacion de transformacion de material."""
    source_material_id: UUID = Field(..., description="Material de origen a desintegrar")
    source_warehouse_id: UUID = Field(..., description="Bodega de origen")
    source_quantity: Decimal = Field(..., gt=0, description="Cantidad de material de origen")
    waste_quantity: Decimal = Field(default=Decimal("0"), ge=0, description="Cantidad de merma/desperdicio")
    cost_distribution: str = Field(
        default="average_cost",
        description="Metodo: 'average_cost', 'proportional_weight' o 'manual'"
    )
    lines: list[TransformationLineCreate] = Field(..., min_length=1, description="Lineas de destino (minimo 1)")
    date: BusinessDate = Field(..., description="Fecha de la transformacion")
    reason: str = Field(..., min_length=3, description="Razon de la transformacion")
    notes: Optional[str] = None

    # NOTA: el balance de cantidades (sum(destinos) + merma == origen) NO se valida
    # aqui porque depende de la unidad de medida de los materiales, que este schema
    # no conoce. Se valida en el servicio (`MaterialTransformationService.create`),
    # que tiene acceso a `Material.default_unit`: solo se exige conservacion de masa
    # cuando origen y destinos comparten unidad (ej: kg->kg). Si difieren (ej:
    # desarmar Aire Acondicionado [unidad] en metales [kg]), no aplica.

    @model_validator(mode='after')
    def validate_cost_distribution(self):
        """Validar metodo de distribucion."""
        if self.cost_distribution not in ("average_cost", "proportional_weight", "manual"):
            raise ValueError(f"Metodo de distribucion invalido: {self.cost_distribution}")
        if self.cost_distribution == "manual":
            for i, line in enumerate(self.lines):
                if line.unit_cost is None:
                    raise ValueError(
                        f"Linea {i+1}: unit_cost es obligatorio cuando cost_distribution='manual'"
                    )
        return self


# ---------------------------------------------------------------------------
# Schema de anulacion
# ---------------------------------------------------------------------------

class AnnulTransformationRequest(BaseModel):
    """Solicitud de anulacion de transformacion."""
    reason: str = Field(..., min_length=1, max_length=500, description="Razon de anulacion")


# ---------------------------------------------------------------------------
# Schemas de respuesta
# ---------------------------------------------------------------------------

class TransformationLineResponse(BaseModel):
    """Linea de destino en la respuesta."""
    id: UUID
    destination_material_id: UUID
    destination_material_code: Optional[str] = None
    destination_material_name: Optional[str] = None
    destination_warehouse_id: UUID
    destination_warehouse_name: Optional[str] = None
    quantity: float
    unit_cost: float
    total_cost: float

    model_config = {"from_attributes": True}

    @field_serializer('quantity', 'unit_cost', 'total_cost')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class MaterialTransformationResponse(BaseModel):
    """Respuesta completa de una transformacion de material."""
    id: UUID
    organization_id: UUID
    transformation_number: int
    date: datetime

    # Origen
    source_material_id: UUID
    source_material_code: Optional[str] = None
    source_material_name: Optional[str] = None
    source_warehouse_id: UUID
    source_warehouse_name: Optional[str] = None
    source_quantity: float
    source_unit_cost: float
    source_total_value: float

    # Merma
    waste_quantity: float
    waste_value: float

    # Distribucion
    cost_distribution: str
    value_difference: Optional[float] = None

    # Lineas
    lines: list[TransformationLineResponse] = []

    # Detalles
    reason: str
    notes: Optional[str] = None

    # Estado
    status: str
    annulled_reason: Optional[str] = None
    annulled_at: Optional[datetime] = None
    annulled_by: Optional[UUID] = None

    # Auditoria
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    # Warnings
    warnings: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @field_serializer(
        'source_quantity', 'source_unit_cost', 'source_total_value',
        'waste_quantity', 'waste_value'
    )
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)

    @field_serializer('value_difference')
    def serialize_value_difference(self, value) -> Optional[float]:
        return float(value) if value is not None else None


class PaginatedMaterialTransformationResponse(BaseModel):
    """Respuesta paginada de transformaciones."""
    items: list[MaterialTransformationResponse]
    total: int
    skip: int
    limit: int
