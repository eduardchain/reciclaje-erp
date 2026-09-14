"""
Documentos de crisol (#107 D2/D3) — el 4º "ítem" que Hugo pidió en Salidas de
Plomo (28-ago :377: "te faltaría hacer un ítem ahí que sería salida a crisoles").

Dos documentos sobre la cuenta intersede (la deuda de planta con Circunvalar es
UNA, con dos etapas — Johana: "intersede = horno grande + crisol"):

    charge        traslado a crisoles     horno −kg / crisol +kg   sin pesos
    dross_return  retorno de dross        crisol −kg / horno +kg   par de maquila
                                                                   ($1.500/kg, Johana:
                                                                   "generan una nueva maquila")

Ninguno mueve inventario ni deuda: el neto sobre intersede es CERO por
construccion (dos movimientos de la misma cuenta, signos opuestos). Es control
de donde esta el plomo (Hugo: "los saldos no va a afectar sino el del traslado
que haces de un horno a otro horno"). Las conversiones fisicas (crudo -> puro +
dross; dross -> crudo) siguen siendo transformaciones manuales (D6).

`discharge` (cierre de refinacion de la spec) queda reservado: el schema lo
rechaza y el servicio tambien, por si alguien entra sin schema.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_kg_profile import MaterialKgProfile
from app.models.money_movement import MoneyMovement
from app.models.plant_process import CrucibleCharge
from app.models.service_tariff import ServiceTariff
from app.models.warehouse import Warehouse
from app.schemas.crucible_charge import CrucibleChargeCreate
from app.services.kg_ledger import STAGE_LABELS, add_kg_movement, kg_ledger_service
from app.utils.advisory_locks import lock_sequences, next_number
from app.utils.dates import business_today_noon
from app.utils.org_settings import get_org_setting

KG_SOURCE_TYPE = "crucible_charge"
# La "nueva maquila" del dross que vuelve al horno es la misma maquila interna
# del traslado (Johana 3-sep, fila 10: un mismo kg puede causarla mas de una vez).
DROSS_TARIFF_CODE = "maquila_intersede_cv_jm"
EVENT_LABELS = {"charge": "Traslado a crisoles", "dross_return": "Retorno de dross al horno"}
# (etapa que baja, etapa que sube)
STAGE_FLOW = {"charge": ("horno", "crisol"), "dross_return": ("crisol", "horno")}


def _err(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


class CrucibleChargeService:
    """Un solo paso (registrar) y anular: no hay revisor en salidas (Hugo 28-ago)
    y aqui ni siquiera hay pesos que certificar."""

    # ================================================================== #
    # Crear                                                               #
    # ================================================================== #
    def create(
        self,
        db: Session,
        data: CrucibleChargeCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[CrucibleCharge, list[str]]:
        if data.event_type not in STAGE_FLOW:
            raise _err(
                f"Evento '{data.event_type}' reservado: el crisol no se cierra, baja al "
                "vender plomo puro y al devolver dross.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        self._validate_plant(db, organization_id, warehouse)
        material = self._validate_material(db, data.material_id, organization_id)
        if data.event_type == "charge":
            self._require_crudo(db, material, organization_id)
        self._validate_not_future(data.date)
        account = self._intersede_account(db, organization_id)

        warnings: list[str] = []
        down, up = STAGE_FLOW[data.event_type]
        balances = kg_ledger_service.intersede_stage_balances(db, organization_id)
        after = balances[down] - data.quantity_kg
        if after < 0:
            # Avisa, no bloquea (#17/#76): el saldo negativo es valido en toda la
            # app; lo que importa es que el usuario lo VEA (lección #100 D4d).
            hint = (
                " Registre primero el Traslado a crisoles."
                if down == "crisol"
                else " Revise los traslados recibidos en planta."
            )
            warnings.append(
                f"La etapa {STAGE_LABELS[down]} de intersede queda en "
                f"{float(after):g} kg tras este documento.{hint}"
            )

        # Declaracion anticipada de locks (#106 D4): el retorno numera el
        # documento (rango 14) y DESPUES el par (movement, rango 30).
        if data.event_type == "dross_return":
            lock_sequences(db, organization_id, "crucible_number", "movement_number")
        charge = CrucibleCharge(
            organization_id=organization_id,
            charge_number=self._generate_charge_number(db, organization_id),
            event_type=data.event_type,
            date=data.date,
            quantity_kg=data.quantity_kg,
            material_id=material.id,
            warehouse_id=warehouse.id,
            notes=data.notes,
            status="confirmed",
            created_by=user_id,
        )
        db.add(charge)
        db.flush()

        desc = (
            f"{EVENT_LABELS[data.event_type]} — {charge.label} — "
            f"{material.code} x {float(data.quantity_kg):g} kg plomo"
        )
        for stage, sign in ((down, -1), (up, 1)):
            add_kg_movement(
                db,
                organization_id=organization_id,
                account=account,
                delta_kg=sign * data.quantity_kg,
                transaction_date=data.date,
                description=desc,
                source_type=KG_SOURCE_TYPE,
                source_id=charge.id,
                stage=stage,
                created_by=user_id,
            )
        if data.event_type == "dross_return":
            self._emit_dross_pair(db, charge, material, organization_id, user_id, warnings)

        db.commit()
        db.refresh(charge)
        return charge, warnings

    # ================================================================== #
    # Anular                                                              #
    # ================================================================== #
    def annul(
        self,
        db: Session,
        charge_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> CrucibleCharge:
        """Reversa por `(source_type, source_id)`, patron de la Salida: los dos
        movimientos kg y, si hubo, el par de maquila. No valida (#99): un
        documento viejo tiene que poder anularse aunque hoy no pasara el guard."""
        charge = self._get_or_404(db, charge_id, organization_id)
        if charge.status == "annulled":
            raise _err("El documento de crisol ya esta anulado.")
        now = datetime.now(tz=None).astimezone()
        note = f"Anulacion de documento de crisol — {charge.label}: {reason}"
        for mv in db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.source_type == KG_SOURCE_TYPE,
                KgLedgerMovement.source_id == charge.id,
                KgLedgerMovement.status == "confirmed",
            )
        ).scalars().all():
            mv.status = "annulled"
            mv.annulled_reason = note
            mv.annulled_at = now
            mv.annulled_by = user_id
        for mm in db.execute(
            select(MoneyMovement).where(
                MoneyMovement.source_type == KG_SOURCE_TYPE,
                MoneyMovement.source_id == charge.id,
                MoneyMovement.status == "confirmed",
            )
        ).scalars().all():
            mm.status = "annulled"
            mm.annulled_at = now
            mm.annulled_by = user_id
            mm.annulled_reason = note
        charge.maquila_amount = Decimal("0")
        charge.status = "annulled"
        charge.annulled_reason = reason
        charge.annulled_at = now
        charge.annulled_by = user_id
        db.commit()
        db.refresh(charge)
        return charge

    # ================================================================== #
    # Lectura                                                             #
    # ================================================================== #
    def list_charges(
        self,
        db: Session,
        organization_id: UUID,
        event_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[CrucibleCharge], int]:
        filters = [CrucibleCharge.organization_id == organization_id]
        if event_type:
            filters.append(CrucibleCharge.event_type == event_type)
        if status_filter:
            filters.append(CrucibleCharge.status == status_filter)
        total = db.execute(
            select(func.count()).select_from(CrucibleCharge).where(*filters)
        ).scalar_one()
        rows = db.execute(
            select(CrucibleCharge)
            .options(joinedload(CrucibleCharge.material), joinedload(CrucibleCharge.warehouse))
            .where(*filters)
            .order_by(CrucibleCharge.date.desc(), CrucibleCharge.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).scalars().all()
        return rows, total

    def _get_or_404(self, db: Session, charge_id: UUID, organization_id: UUID) -> CrucibleCharge:
        charge = db.execute(
            select(CrucibleCharge)
            .options(joinedload(CrucibleCharge.material), joinedload(CrucibleCharge.warehouse))
            .where(
                CrucibleCharge.id == charge_id,
                CrucibleCharge.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if charge is None:
            raise _err("Documento de crisol no encontrado", status.HTTP_404_NOT_FOUND)
        return charge

    # ================================================================== #
    # Efectos                                                             #
    # ================================================================== #
    def _emit_dross_pair(
        self,
        db: Session,
        charge: CrucibleCharge,
        material: Material,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        """
        Johana (3-sep, fila 10): el dross del crisol "vuelve al horno grande y
        genera una nueva maquila". Par `internal_maquila_expense` (sede que
        factura) / `internal_maquila_income` (planta) por kg × tarifa del horno,
        categoria "Maquila Intersede" — la MISMA del traslado, porque es la misma
        maquila cobrada otra vez. Gate por FLAG (G6): con `internal_maquila_enabled`
        apagado los kg se mueven igual y no hay par. Sin tarifa o sin sede de
        facturacion, los kg tambien se mueven y se avisa (D4d de #100).
        """
        charge.maquila_amount = Decimal("0")
        if not get_org_setting(db, organization_id, "internal_maquila_enabled"):
            return
        raw = get_org_setting(db, organization_id, "willard_sede_facturacion")
        billing_wh = UUID(str(raw)) if raw else None
        if billing_wh is None:
            warnings.append(
                "Sin sede de facturacion configurada: el dross volvio al horno sin "
                "causar la maquila del reproceso. Definala en la configuracion de la "
                "organizacion."
            )
            return
        tariff = db.execute(
            select(ServiceTariff)
            .where(
                ServiceTariff.organization_id == organization_id,
                ServiceTariff.tariff_code == DROSS_TARIFF_CODE,
            )
            .order_by(ServiceTariff.created_at.desc(), ServiceTariff.id.desc())
            .limit(1)
        ).scalar_one_or_none()
        if tariff is None:
            warnings.append(
                f"Sin tarifa vigente '{DROSS_TARIFF_CODE}': el dross volvio al horno sin "
                "causar la maquila del reproceso. Configurela en Config → Tarifas."
            )
            return
        amount = (charge.quantity_kg * tariff.unit_price_cop).quantize(Decimal("0.01"))
        if amount <= 0:
            return
        from app.services.money_movement import money_movement
        from app.services.transfer import TransferService

        category = TransferService()._get_or_create_maquila_category(db, organization_id)
        desc = (
            f"Maquila reproceso dross — {charge.label} — "
            f"{material.code} ({float(charge.quantity_kg):g} kg plomo)"
        )
        mm_exp = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_expense",
            amount=amount,
            account_id=None,
            date=charge.date,
            description=desc,
            user_id=user_id,
            expense_category_id=category.id,
            business_unit_id=material.business_unit_id,
            source_type=KG_SOURCE_TYPE,
            source_id=charge.id,
            tariff_id=tariff.id,
            warehouse_id=billing_wh,
        )
        mm_inc = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_income",
            amount=amount,
            account_id=None,
            date=charge.date,
            description=desc,
            user_id=user_id,
            business_unit_id=material.business_unit_id,
            source_type=KG_SOURCE_TYPE,
            source_id=charge.id,
            tariff_id=tariff.id,
            warehouse_id=charge.warehouse_id,
        )
        mm_exp.transfer_pair_id = mm_inc.id
        mm_inc.transfer_pair_id = mm_exp.id
        charge.maquila_amount = amount

    # ================================================================== #
    # Validaciones                                                        #
    # ================================================================== #
    @staticmethod
    def _generate_charge_number(db: Session, organization_id: UUID) -> int:
        """Siguiente `charge_number` de la org (lock estable + MAX+1 en el helper
        unico, #106)."""
        return next_number(db, organization_id, "crucible_number")

    def _validate_warehouse(self, db: Session, warehouse_id: UUID, organization_id: UUID) -> Warehouse:
        wh = db.get(Warehouse, warehouse_id)
        if not wh or wh.organization_id != organization_id:
            raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if not wh.is_active:
            raise _err(f"La bodega '{wh.name}' no esta activa")
        return wh

    def _validate_plant(self, db: Session, organization_id: UUID, warehouse: Warehouse) -> None:
        """Calco de D8 de #100: el crisol vive en planta (`willard_sede_drosses`).
        Sin el setting no valida (compat)."""
        plant_id = get_org_setting(db, organization_id, "willard_sede_drosses")
        if not plant_id:
            return
        if str(warehouse.id) != str(plant_id):
            plant = db.get(Warehouse, UUID(str(plant_id)))
            raise _err(
                f"Los documentos de crisol se registran en la planta"
                f"{f' ({plant.name})' if plant else ''}, no en '{warehouse.name}'."
            )

    def _validate_material(self, db: Session, material_id: UUID, organization_id: UUID) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise _err("Material no encontrado", status.HTTP_404_NOT_FOUND)
        if not material.is_active:
            raise _err(f"El material '{material.code}' no esta activo")
        return material

    def _require_crudo(self, db: Session, material: Material, organization_id: UUID) -> None:
        """Al crisol solo entra plomo CRUDO (spec §4.1: "el crisol solo recibe
        plomo crudo del horno"). La clasificacion sale de `lead_product` y de
        NADA MAS (#103 D1): sin fila de perfil = 'none' = bloqueado."""
        profile = db.execute(
            select(MaterialKgProfile).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id == material.id,
            )
        ).scalar_one_or_none()
        lead = profile.lead_product if profile is not None else "none"
        label = f"'{material.code} {material.name}'"
        if lead == "puro":
            raise _err(
                f"{label} ya es plomo PURO: al crisol entra plomo crudo, y el puro "
                "sale de el por una venta.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if lead != "crudo":
            raise _err(
                f"{label} no esta marcado como plomo crudo. Al crisol solo entra "
                "crudo; marquelo en Config -> Materiales (kg) si corresponde.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    @staticmethod
    def _validate_not_future(value: datetime) -> None:
        if value.date() > business_today_noon().date():
            raise _err("La fecha no puede ser futura")

    @staticmethod
    def _intersede_account(db: Session, organization_id: UUID) -> KgLedgerAccount:
        account = db.execute(
            select(KgLedgerAccount).where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.account_type == "intersede",
                KgLedgerAccount.warehouse_id.is_(None),
                KgLedgerAccount.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if account is None:
            raise _err(
                "No hay cuenta en kg activa de tipo 'intersede'. Creela en Plomo (kg) "
                "antes de mover plomo entre el horno y el crisol."
            )
        return account


crucible_charge_service = CrucibleChargeService()
