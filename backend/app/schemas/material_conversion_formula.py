"""Schemas de MaterialConversionFormula (SAC E1, v0.5 §6.4/§11.1.3/§12.1.2, Anexo D).

`parameters` valida por formula_type con sub-modelos `extra="forbid"` —
imposible persistir parameters vacio, con claves extra o fuera de rango
(invariante 3 del plan E1). Los sub-modelos usan Decimal (precision exacta
en la validacion); el SERVICIO convierte a numeros JSON-nativos al persistir
(mismo racional del fix H1 — el JSONB almacena numeros JSON como en los
ejemplos del Anexo D; el consumidor de E2 convierte Decimal(str(x)) al leer).

Append-only: solo Create y Response, sin Update.
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PrivateAttr, model_validator

FormulaType = Literal[
    "battery_to_lead",
    "drosses_to_lead",
    "scrap_with_terminal_to_lead",
    "custom",
]

def _lowercase_str(v):
    """D6: willard_account_subtype input case-insensitive -> persiste lower."""
    return v.strip().lower() if isinstance(v, str) else v


WillardSubtype = Annotated[Literal["escurrido", "pinza"], BeforeValidator(_lowercase_str)]

# D11c — coherencia formula_type <-> Material.default_unit (Anexo D opera
# battery sobre unidades fisicas; drosses y scrap sobre kg)
EXPECTED_UNIT_BY_FORMULA_TYPE: dict = {
    "battery_to_lead": "unidad",
    "drosses_to_lead": "kg",
    "scrap_with_terminal_to_lead": "kg",
}

# D11d — el subtype discrimina FORMULAS dentro de la cuenta Willard Drosses
# (caso SEC); sobre battery_to_lead multiplicaria vigencias fantasma
SUBTYPE_ALLOWED_FORMULA_TYPES = ("drosses_to_lead", "scrap_with_terminal_to_lead")


class BatteryToLeadParams(BaseModel):
    """kg de plomo equivalente por unidad fisica de bateria."""
    model_config = ConfigDict(extra="forbid")

    kg_lead_per_unit: Decimal = Field(..., gt=0)
    # Opcional: los ejemplos de §11.1.3 y el template §15.2.1 no lo traen
    material_reference: Optional[Literal["07", "08", "1", "2", "3", "4", "5"]] = None


class DrossesToLeadParams(BaseModel):
    """Porcentaje de plomo del dross (0-1]."""
    model_config = ConfigDict(extra="forbid")

    lead_percentage: Decimal = Field(..., gt=0, le=1)


class ScrapWithTerminalParams(BaseModel):
    """Factor de scrap + peso de borne (kg absolutos, v0.5 Anexo D / D6b)."""
    model_config = ConfigDict(extra="forbid")

    scrap_factor: Decimal = Field(..., gt=0, le=1)
    terminal_weight_kg: Decimal = Field(..., ge=0)
    material_reference: Optional[str] = None


PARAMS_MODEL_BY_TYPE = {
    "battery_to_lead": BatteryToLeadParams,
    "drosses_to_lead": DrossesToLeadParams,
    "scrap_with_terminal_to_lead": ScrapWithTerminalParams,
}

FormulaParams = Union[BatteryToLeadParams, DrossesToLeadParams, ScrapWithTerminalParams]


class MaterialConversionFormulaCreate(BaseModel):
    """Crear nueva version de formula (append-only)."""
    material_id: UUID
    formula_type: FormulaType
    parameters: dict
    willard_account_subtype: Optional[WillardSubtype] = None
    notes: Optional[str] = Field(None, max_length=500)

    _parsed_params: Optional[FormulaParams] = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_parameters_by_type(self):
        """Dispatch del schema de parameters segun formula_type (Anexo D)."""
        if self.formula_type == "custom":
            # D11b — el sanitizer AST se implementa cuando se necesite
            raise ValueError("formula_type 'custom' no habilitado en Fase 1")
        params_model = PARAMS_MODEL_BY_TYPE[self.formula_type]
        # ValidationError anidada burbujea como 422 con el detalle del campo
        self._parsed_params = params_model(**(self.parameters or {}))
        return self

    @property
    def canonical_parameters(self) -> dict:
        """Parameters validados como numeros JSON-NATIVOS para el JSONB.

        Racional H1: el write path serializa con json.dumps default — un
        Decimal revienta con 500. El Anexo D almacena numeros JSON; el
        consumidor de E2 convierte con Decimal(str(x)) al leer (exacto).
        """
        dumped = self._parsed_params.model_dump(exclude_none=True)
        return {k: (float(v) if isinstance(v, Decimal) else v) for k, v in dumped.items()}


class MaterialConversionFormulaResponse(BaseModel):
    id: UUID
    organization_id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    material_unit: Optional[str] = None
    formula_type: str
    parameters: dict
    willard_account_subtype: Optional[str] = None
    notes: Optional[str] = None
    created_by: UUID
    created_by_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialConversionFormulaListResponse(BaseModel):
    items: list[MaterialConversionFormulaResponse]
    total: int
