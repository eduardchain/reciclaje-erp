"""Servicio de MaterialConversionFormula (SAC E1, v0.5 §6.4/§12.1.2, plan §4.4).

Append-only puro (patron PriceList, decision #35). La vigente es
max(created_at, id) por material_id (un factor por material — el subtipo
escurrido/pinza se elimino, CC-001: son materiales distintos).
"""
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.material import Material
from app.models.material_conversion_formula import MaterialConversionFormula
from app.models.user import User
from app.schemas.material_conversion_formula import (
    EXPECTED_UNIT_BY_FORMULA_TYPE,
    DrossesToLeadParams,
    _json_native,
    MaterialConversionFormulaCreate,
    MaterialConversionFormulaResponse,
)


FACTOR_KEYS = ("label", "alternatives")


class MaterialConversionFormulaService:
    """Formulas de conversion append-only con consulta de vigentes."""

    def create(
        self,
        db: Session,
        obj_in: MaterialConversionFormulaCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> MaterialConversionFormulaResponse:
        material = db.execute(
            select(Material).where(
                Material.id == obj_in.material_id,
                Material.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not material:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Material no encontrado en esta organizacion",
            )

        # D11c — coherencia formula_type <-> Material.default_unit: una formula
        # de baterias sobre un material en kg produce kg-equivalentes absurdos
        expected_unit = EXPECTED_UNIT_BY_FORMULA_TYPE[obj_in.formula_type]
        actual_unit = (material.default_unit or "kg").strip().lower()
        if actual_unit != expected_unit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"La formula '{obj_in.formula_type}' aplica a materiales en "
                f"'{expected_unit}' — {material.code} esta en '{actual_unit}'. "
                f"Corrige la unidad del material o el tipo de formula",
            )

        parameters = self._carry_over_factors(db, obj_in, organization_id)

        db_obj = MaterialConversionFormula(
            organization_id=organization_id,
            material_id=obj_in.material_id,
            formula_type=obj_in.formula_type,
            parameters=parameters,
            notes=obj_in.notes,
            created_by=user_id,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return self._enrich(db_obj, material, None)

    def _carry_over_factors(
        self,
        db: Session,
        obj_in: MaterialConversionFormulaCreate,
        organization_id: UUID,
    ) -> dict:
        """D2 de plan-sac-factor-willard: ningun escritor borra la lista sin querer.

        FormulasPage y el seeder arman `{lead_percentage}` solo. Si el cuerpo NO
        trae `label`/`alternatives` (clave ausente) y la vigente si, se copian
        de la vigente; para quitarlos hay que mandarlos en null explicito (que
        `exclude_none` no deja llegar al JSONB). La copia se re-valida entera:
        si choca (el defecto nuevo es igual a una alternativa), 422."""
        parameters = obj_in.canonical_parameters
        if obj_in.formula_type != "drosses_to_lead":
            return parameters
        missing = [k for k in FACTOR_KEYS if k not in obj_in.params_fields_set]
        if not missing:
            return parameters
        current = self.get_current(db, organization_id, obj_in.material_id)
        if not current or current[0].formula_type != "drosses_to_lead":
            return parameters
        carried = {k: current[0].parameters[k] for k in missing if k in (current[0].parameters or {})}
        if not carried:
            return parameters
        merged = {**parameters, **carried}
        try:
            reparsed = DrossesToLeadParams(**merged)
        except ValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "La version nueva choca con los factores de Willard que tiene la "
                    "vigente y que se conservan al no mandarlos: "
                    + "; ".join(err["msg"] for err in e.errors())
                    + ". Edite la lista de factores en el mismo cambio."
                ),
            )
        return _json_native(reparsed.model_dump(exclude_none=True))

    def get_all(
        self,
        db: Session,
        organization_id: UUID,
        material_id: Optional[UUID] = None,
        formula_type: Optional[str] = None,
    ) -> list[MaterialConversionFormulaResponse]:
        """Historico completo (mas reciente primero) con filtros opcionales."""
        query = self._joined_query(organization_id)
        if material_id:
            query = query.where(MaterialConversionFormula.material_id == material_id)
        if formula_type:
            query = query.where(MaterialConversionFormula.formula_type == formula_type)
        query = query.order_by(
            MaterialConversionFormula.created_at.desc(),
            MaterialConversionFormula.id.desc(),
        )
        return [
            self._enrich(row[0], row[1], row.created_by_name)
            for row in db.execute(query).all()
        ]

    def get_current(
        self,
        db: Session,
        organization_id: UUID,
        material_id: Optional[UUID] = None,
    ) -> list[MaterialConversionFormulaResponse]:
        """Formula vigente por material — DISTINCT ON con tiebreaker id."""
        query = (
            self._joined_query(organization_id)
            .distinct(MaterialConversionFormula.material_id)
            .order_by(
                MaterialConversionFormula.material_id,
                MaterialConversionFormula.created_at.desc(),
                MaterialConversionFormula.id.desc(),
            )
        )
        if material_id:
            query = query.where(MaterialConversionFormula.material_id == material_id)
        return [
            self._enrich(row[0], row[1], row.created_by_name)
            for row in db.execute(query).all()
        ]

    @staticmethod
    def _joined_query(organization_id: UUID):
        return (
            select(
                MaterialConversionFormula,
                Material,
                User.full_name.label("created_by_name"),
            )
            .join(Material, MaterialConversionFormula.material_id == Material.id)
            .outerjoin(User, MaterialConversionFormula.created_by == User.id)
            .where(MaterialConversionFormula.organization_id == organization_id)
        )

    @staticmethod
    def _enrich(
        formula: MaterialConversionFormula,
        material: Optional[Material],
        created_by_name: Optional[str],
    ) -> MaterialConversionFormulaResponse:
        resp = MaterialConversionFormulaResponse.model_validate(formula)
        if material is not None:
            resp.material_code = material.code
            resp.material_name = material.name
            resp.material_unit = material.default_unit or "kg"
        resp.created_by_name = created_by_name
        return resp


material_conversion_formula = MaterialConversionFormulaService()
