"""
Schemas de DocumentTax — IVA y retenciones de lo que SAC factura (CC-013 / Q-41).

DATA-GATED (D2, patron #75 D9): el payload ausente deja el camino actual byte a
byte. Eso no es solo comodidad — es la no-regresion de las otras seis
organizaciones, porque a ellas nunca les llega.
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentTaxCreate(BaseModel):
    """Un impuesto capturado al liquidar.

    El sistema REGISTRA lo que Siigo emitio (D1): el monto viene del payload y
    el `rate` es informativo — el numero editado es la verdad, igual que en las
    retenciones de compra (#79 F1).

    D5 — LA BASE SE DECLARA, NO SE ASUME, y el que la CALCULA es el servidor.
    El cliente manda `base_kind` ("sobre que se aplica") y el servidor deriva el
    monto de la base de lo que realmente facturo. Dos razones:

    1. Una reteIVA va sobre el IVA y una retefuente sobre el subtotal. Guardar
       la reteIVA como "2,85 % del subtotal" da el numero correcto SOLO mientras
       el IVA sea 19 %, y queda mal en silencio el dia que cambie.
    2. En una Salida tipo ABONO la base es la maquila mas el flete, que salen de
       las tarifas vigentes AL LIQUIDAR — la pantalla no las conoce todavia. Si
       la base viajara desde el cliente, ahi tendria que adivinarla, y una
       adivinanza persistida en un campo de auditoria es peor que no tenerlo.

    El MONTO si viene del payload y es la verdad (#79 F1): el sistema REGISTRA
    lo que Siigo emitio (D1).
    """
    model_config = ConfigDict(extra="forbid")

    tax_type: Literal["iva", "retefuente", "reteiva", "ica"]
    municipality: Optional[str] = Field(None, min_length=1, max_length=60)
    concept: Optional[str] = Field(
        None, max_length=60,
        description="Venta de bien vs servicio — las facturas muestran 2,5 % y 4 % del MISMO cliente",
    )
    rate: Optional[Decimal] = Field(None, gt=0, description="Tasa informativa con la que se precalculo")
    base_kind: Literal["subtotal", "iva"] = Field(
        "subtotal",
        description="Sobre que se aplica la tasa. El servidor deriva el monto de la base (D5)",
    )
    amount: Decimal = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_municipality(self):
        """ICA es POR MUNICIPIO (una entidad por municipio, #75 H4)."""
        if self.tax_type == "ica":
            if not (self.municipality and self.municipality.strip()):
                raise ValueError(
                    "municipality es obligatorio en ICA (una entidad por municipio)"
                )
        elif self.municipality is not None:
            raise ValueError("municipality solo aplica a ICA")
        return self


class DocumentTaxResponse(BaseModel):
    """Impuesto persistido (detalle de venta o de Salida de Plomo)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    third_party_id: UUID
    third_party_name: Optional[str] = None
    tax_type: str
    municipality: Optional[str] = None
    concept: Optional[str] = None
    rate: Optional[Decimal] = None
    base_amount: Decimal
    amount: Decimal
    reverted_at: Optional[datetime] = None
