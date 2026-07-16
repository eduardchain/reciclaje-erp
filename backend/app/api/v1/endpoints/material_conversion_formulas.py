"""Endpoints de MaterialConversionFormula (SAC E1, v0.5 §12.1.2).

Append-only: GET (historico) / GET current / POST. Sin PATCH ni DELETE
(invariante 1 del plan E1).
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.material_conversion_formula import (
    MaterialConversionFormulaCreate,
    MaterialConversionFormulaListResponse,
    MaterialConversionFormulaResponse,
)
from app.services.material_conversion_formula import material_conversion_formula

router = APIRouter()


@router.get("", response_model=MaterialConversionFormulaListResponse)
def list_conversion_formulas(
    material_id: Optional[UUID] = Query(None),
    formula_type: Optional[str] = Query(None),
    willard_account_subtype: Optional[str] = Query(None),
    org_context: dict = Depends(require_permission("formulas.view")),
    db: Session = Depends(get_db),
):
    """Historico completo de formulas (mas reciente primero) con filtros."""
    items = material_conversion_formula.get_all(
        db=db,
        organization_id=org_context["organization_id"],
        material_id=material_id,
        formula_type=formula_type,
        willard_account_subtype=willard_account_subtype,
    )
    return MaterialConversionFormulaListResponse(items=items, total=len(items))


@router.get("/current", response_model=MaterialConversionFormulaListResponse)
def get_current_formulas(
    material_id: Optional[UUID] = Query(None),
    org_context: dict = Depends(require_permission("formulas.view")),
    db: Session = Depends(get_db),
):
    """Formula vigente por (material, sub-cuenta) — el caso SEC retorna 2 filas."""
    items = material_conversion_formula.get_current(
        db=db,
        organization_id=org_context["organization_id"],
        material_id=material_id,
    )
    return MaterialConversionFormulaListResponse(items=items, total=len(items))


@router.post(
    "",
    response_model=MaterialConversionFormulaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversion_formula(
    formula_in: MaterialConversionFormulaCreate,
    org_context: dict = Depends(require_permission("formulas.manage")),
    db: Session = Depends(get_db),
):
    """Crear nueva version de formula (append-only — corregir = nueva version)."""
    return material_conversion_formula.create(
        db=db,
        obj_in=formula_in,
        organization_id=org_context["organization_id"],
        user_id=org_context["user_id"],
    )
