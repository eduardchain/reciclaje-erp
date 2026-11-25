"""Servicio de la Salida de control (SAC, plan-sac-documentos-control v1.2 §4.3).

Documento SIN efectos: crear, editar y anular solo escriben
`control_dispatches` y sus lineas. Ningun InventoryMovement, KgLedgerMovement,
MoneyMovement, InventoryAdjustment ni MCH (T13 lo afirma por conteo).

El clasificador es la marca `material_kg_profiles.control_only` (#103 D1: ni la
formula ni la categoria clasifican). La remision sale del MISMO talonario de
las Entradas (Q-75); una repetida se AVISA (D8), nunca se rechaza.
"""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.control_dispatch import ControlDispatch, ControlDispatchLine
from app.models.material import Material
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.schemas.control_dispatch import (
    ControlDispatchCreate,
    ControlDispatchLineCreate,
    ControlDispatchUpdate,
)
from app.services.material_kg_profile import control_material_ids
from app.services.remission_book import duplicate_remission_warning
from app.services.transfer import validate_not_transit_warehouse
from app.utils.advisory_locks import next_number
from app.utils.dates import business_today_noon


# Escalas de las columnas de la linea: Numeric(15,4) y Numeric(15,3). HALF_UP
# porque es la regla de PostgreSQL al guardar (0,00005 -> 0,0001): asi el 422
# sale exactamente cuando la columna guardaria un 0 (O7 de QA 2).
QTY_Q = Decimal("0.0001")
WEIGHT_Q = Decimal("0.001")


def _err(detail: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


class ControlDispatchService:

    def create(
        self, db: Session, obj_in: ControlDispatchCreate, organization_id: UUID, user_id: UUID
    ) -> tuple[ControlDispatch, list[str]]:
        self._validate_not_future(obj_in.date)
        self._validate_warehouse(db, obj_in.warehouse_id, organization_id)
        if obj_in.third_party_id is not None:
            self._validate_third_party(db, obj_in.third_party_id, organization_id)
        self._validate_lines(db, obj_in.lines, organization_id)

        dispatch = ControlDispatch(
            organization_id=organization_id,
            dispatch_number=self._generate_dispatch_number(db, organization_id),
            date=obj_in.date,
            warehouse_id=obj_in.warehouse_id,
            third_party_id=obj_in.third_party_id,
            remission_number=obj_in.remission_number,
            notes=obj_in.notes,
            status="registered",
            created_by=user_id,
        )
        db.add(dispatch)
        db.flush()
        self._replace_lines(db, dispatch, obj_in.lines, organization_id)

        warnings: list[str] = []
        dup = duplicate_remission_warning(
            db, organization_id, obj_in.remission_number, exclude_dispatch_id=dispatch.id
        )
        if dup:
            warnings.append(dup)
        db.commit()
        db.refresh(dispatch)
        return dispatch, warnings

    def update(
        self, db: Session, dispatch_id: UUID, obj_in: ControlDispatchUpdate,
        organization_id: UUID,
    ) -> tuple[ControlDispatch, list[str]]:
        dispatch = self.get(db, dispatch_id, organization_id)
        if dispatch.status != "registered":
            raise _err("La salida de control esta anulada — no se edita", status.HTTP_400_BAD_REQUEST)
        fields = obj_in.model_dump(exclude_unset=True)
        warnings: list[str] = []

        if "date" in fields:
            if obj_in.date is None:
                raise _err("La fecha es obligatoria")
            self._validate_not_future(obj_in.date)
            dispatch.date = obj_in.date
        if "warehouse_id" in fields:
            if obj_in.warehouse_id is None:
                raise _err("La bodega es obligatoria")
            self._validate_warehouse(db, obj_in.warehouse_id, organization_id)
            dispatch.warehouse_id = obj_in.warehouse_id
        if "third_party_id" in fields:
            if obj_in.third_party_id is not None:
                self._validate_third_party(db, obj_in.third_party_id, organization_id)
            dispatch.third_party_id = obj_in.third_party_id
        if "remission_number" in fields:
            # Se cambia, no se borra: la remision es la razon de ser del documento.
            if obj_in.remission_number is None:
                raise _err("La remision es obligatoria: sale del talonario de las Entradas")
            changed = obj_in.remission_number != (dispatch.remission_number or "").strip()
            dispatch.remission_number = obj_in.remission_number
            if changed:
                dup = duplicate_remission_warning(
                    db, organization_id, obj_in.remission_number,
                    exclude_dispatch_id=dispatch.id,
                )
                if dup:
                    warnings.append(dup)
        if "notes" in fields:
            dispatch.notes = obj_in.notes
        if "lines" in fields:
            if not obj_in.lines:
                raise _err("La salida necesita al menos una linea")
            self._validate_lines(db, obj_in.lines, organization_id)
            self._replace_lines(db, dispatch, obj_in.lines, organization_id)

        db.commit()
        db.refresh(dispatch)
        return dispatch, warnings

    def annul(
        self, db: Session, dispatch_id: UUID, reason: str, organization_id: UUID, user_id: UUID
    ) -> ControlDispatch:
        dispatch = self.get(db, dispatch_id, organization_id)
        if dispatch.status == "annulled":
            raise _err("La salida de control ya esta anulada", status.HTTP_400_BAD_REQUEST)
        dispatch.status = "annulled"
        dispatch.annulled_reason = reason
        dispatch.annulled_at = datetime.now(timezone.utc)
        dispatch.annulled_by = user_id
        db.commit()
        db.refresh(dispatch)
        return dispatch

    def get(self, db: Session, dispatch_id: UUID, organization_id: UUID) -> ControlDispatch:
        dispatch = db.execute(
            select(ControlDispatch)
            .options(selectinload(ControlDispatch.lines).selectinload(ControlDispatchLine.material))
            .where(
                ControlDispatch.id == dispatch_id,
                ControlDispatch.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if dispatch is None:
            raise _err("Salida de control no encontrada", status.HTTP_404_NOT_FOUND)
        return dispatch

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[ControlDispatch], int]:
        q = select(ControlDispatch).where(ControlDispatch.organization_id == organization_id)
        if status_filter:
            q = q.where(ControlDispatch.status == status_filter)
        if date_from is not None:
            q = q.where(ControlDispatch.date >= date_from)
        if date_to is not None:
            q = q.where(ControlDispatch.date <= date_to)
        if search and search.strip():
            like = f"%{search.strip()}%"
            # Tercero por EXISTS: la cabecera es nullable y un join duro haria
            # desaparecer las salidas sin tercero (#93 R2).
            tp_match = (
                select(ThirdParty.id)
                .where(ThirdParty.id == ControlDispatch.third_party_id, ThirdParty.name.ilike(like))
                .exists()
            )
            conds = [ControlDispatch.remission_number.ilike(like), tp_match]
            if search.strip().isascii() and search.strip().isdecimal():
                conds.append(ControlDispatch.dispatch_number == int(search.strip()))
            q = q.where(or_(*conds))
        total = db.execute(select(func.count()).select_from(q.subquery())).scalar_one()
        rows = db.execute(
            q.options(selectinload(ControlDispatch.lines).selectinload(ControlDispatchLine.material))
            .order_by(ControlDispatch.date.desc(), ControlDispatch.dispatch_number.desc())
            .offset(skip).limit(limit)
        ).scalars().all()
        return list(rows), total

    # ------------------------------------------------------------------ #
    def _generate_dispatch_number(self, db: Session, organization_id: UUID) -> int:
        """Consecutivo propio de la Salida de control (D7): lock estable +
        MAX+1 en el helper unico (#106). No comparte la secuencia de las
        Entradas: «Entrada #N» no tiene huecos por una salida."""
        return next_number(db, organization_id, "control_dispatch_number")

    def _replace_lines(
        self, db: Session, dispatch: ControlDispatch, lines_in: list[ControlDispatchLineCreate],
        organization_id: UUID,
    ) -> None:
        for old in list(dispatch.lines):
            dispatch.lines.remove(old)
        db.flush()
        for l in lines_in:
            dispatch.lines.append(ControlDispatchLine(
                organization_id=organization_id,
                material_id=l.material_id,
                quantity=l.quantity.quantize(QTY_Q, rounding=ROUND_HALF_UP),
                scale_weight_kg=(
                    l.scale_weight_kg.quantize(WEIGHT_Q, rounding=ROUND_HALF_UP)
                    if l.scale_weight_kg is not None else None
                ),
            ))
        db.flush()

    @staticmethod
    def _validate_lines(
        db: Session, lines_in: list[ControlDispatchLineCreate], organization_id: UUID
    ) -> None:
        seen: set = set()
        materials: dict = {}
        for l in lines_in:
            material = db.get(Material, l.material_id)
            if material is None or material.organization_id != organization_id:
                raise _err("Material no encontrado", status.HTTP_404_NOT_FOUND)
            if not material.is_active:
                raise _err(f"El material {material.code} no esta activo")
            if l.material_id in seen:
                raise _err(f"El material {material.code} aparece en mas de una linea — una fila por material")
            # gt=0 del schema valida ANTES de redondear: 0,00004 pasaba y la
            # columna lo guardaba en 0 -> CHECK -> 500 (O7 de QA 2; #95).
            if l.quantity.quantize(QTY_Q, rounding=ROUND_HALF_UP) <= 0:
                raise _err(
                    f"La cantidad de {material.code} queda en 0 con 4 decimales — revise la cifra"
                )
            if (
                l.scale_weight_kg is not None
                and l.scale_weight_kg.quantize(WEIGHT_Q, rounding=ROUND_HALF_UP) <= 0
            ):
                raise _err(
                    f"El peso de bascula de {material.code} queda en 0 con 3 decimales — revise la cifra"
                )
            seen.add(l.material_id)
            materials[l.material_id] = material
        # O6 de QA 2: el MISMO predicado de la Entrada y de los guards D5.
        control = control_material_ids(db, organization_id, seen)
        not_control = sorted(m.code for mid, m in materials.items() if mid not in control)
        if not_control:
            raise _err(
                f"Solo salen por aqui materiales de control. No lo son: {', '.join(not_control)} "
                "— marquelos en Configuracion > Materiales (kg) o use Ventas"
            )

    @staticmethod
    def _validate_warehouse(db: Session, warehouse_id: UUID, organization_id: UUID) -> Warehouse:
        wh = db.get(Warehouse, warehouse_id)
        if wh is None or wh.organization_id != organization_id:
            raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if not wh.is_active:
            raise _err(f"La bodega '{wh.name}' no esta activa")
        validate_not_transit_warehouse(db, organization_id, wh)
        return wh

    @staticmethod
    def _validate_third_party(db: Session, tp_id: UUID, organization_id: UUID) -> ThirdParty:
        tp = db.get(ThirdParty, tp_id)
        if tp is None or tp.organization_id != organization_id:
            raise _err("Tercero no encontrado", status.HTTP_404_NOT_FOUND)
        if not tp.is_active:
            raise _err(f"El tercero '{tp.name}' no esta activo")
        # O2 de QA 2: una entidad de sistema ([Impuestos], [Retenciones],
        # prepagos) no recibe estibas.
        if tp.is_system_entity:
            raise _err(f"'{tp.name}' es una entidad de sistema — elija otro tercero")
        return tp

    @staticmethod
    def _validate_not_future(value: datetime) -> None:
        if value.date() > business_today_noon().date():
            raise _err("La fecha no puede ser futura")


control_dispatch_service = ControlDispatchService()
