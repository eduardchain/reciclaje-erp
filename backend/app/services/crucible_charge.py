"""
Documentos de crisol (#107 D2/D3, corregidos en #109) — el 4º "ítem" que Hugo
pidió en Salidas de Plomo (28-ago :377: "te faltaría hacer un ítem ahí que sería
salida a crisoles").

Dos documentos sobre la cuenta intersede (la deuda de planta con Circunvalar es
UNA, con dos etapas — Johana: "intersede = horno grande + crisol"):

    charge        traslado a crisoles   horno −kg / crisol +kg       sin pesos
                                        inventario: crudo −kg / puro +kg (1:1)
    dross_return  retorno de dross      crisol −kg DROSS / horno +kg PLOMO
                                        par de maquila sobre los kg de PLOMO
                                        inventario: puro −kg dross / crudo +kg plomo

🔴 #109 SUPERSEDE dos cosas de #107, las dos por respuesta del cliente:

1. El retorno de dross YA NO es neto cero. Se digitan kg de DROSS; el plomo es
   el 70 % (formula `drosses_to_lead` del material). Hugo 16-sep: "los 20 kg es
   dross... tiene un plomo a devolver, que serian 14... el valor de la maquila
   seria sobre 14, no sobre 20". Y Johana el 18-sep, con sus palabras: el
   crisol baja 20 (L433), el horno "no subiría 20, sino 14" (L451) y "la deuda
   total cambiaría en 6 kilos" (L517). Que eso sea INTENCIONAL (la fraccion que
   no es plomo deja de deberse) es lectura NUESTRA de sus numeros, no frase de
   ella. `intersede == horno + crisol` sigue siendo por
   construccion (SUM GROUP BY stage); lo que dejo de valer es "neto cero", que
   hoy solo cumple `charge`.
2. Los documentos SI mueven inventario (Johana 18-sep, cita COMPUESTA de dos
   turnos suyos: L555 "En el crisol no hay ninguna transformación," + L579
   "salen 200 de crudo, ingresan 200 de puro"): no hay un SEGUNDO paso para el
   usuario. Por dentro es una transformacion `proportional_weight` de un destino
   creada por ESTE servicio (`from_crucible=True, commit=False`) y enlazada por
   `transformation_id`: el motor ya resuelve MCH, pool negativo (#65), anulacion
   por remocion ponderada (#66), as-of (#61) y avisos de stock (#17/#76). Un
   escritor nuevo de inventario valorizado es exactamente donde nacieron #64–#66.

Escalas (F1 de QA): `inventory_movements.quantity` guarda TRES decimales y el
libro kg, la transformacion y el stock del material cuatro. Este servicio
FABRICA cuartos decimales al multiplicar (33,333 x 0,70 = 23,3331), asi que
todo se cuantiza a `CRUCIBLE_Q` ANTES de calcular nada — si no, el stock del
material y la suma de sus movimientos dejan de coincidir sin aviso (#95 (e)).

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
from app.models.material_transformation import (
    MaterialTransformation,
    MaterialTransformationLine,
)
from app.models.material_kg_profile import MaterialKgProfile
from app.models.money_movement import MoneyMovement
from app.models.plant_process import CrucibleCharge
from app.models.service_tariff import ServiceTariff
from app.models.warehouse import Warehouse
from app.schemas.crucible_charge import CrucibleChargeCreate
from app.schemas.material_transformation import (
    MaterialTransformationCreate,
    TransformationLineCreate,
)
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
# F1 — la escala del inventario (`inventory_movements.quantity` Numeric(10,3)).
CRUCIBLE_Q = Decimal("0.001")
DROSS_FORMULA_TYPE = "drosses_to_lead"


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
        self._validate_not_future(data.date)
        account = self._intersede_account(db, organization_id)

        # F1: UNA escala, antes de cualquier calculo. `gt=0` del schema valida
        # ANTES de cuantizar: 0,0004 pasaria y aqui quedaria en 0.
        quantity_kg = data.quantity_kg.quantize(CRUCIBLE_Q)
        if quantity_kg <= 0:
            raise _err(
                "La cantidad minima de un documento de crisol es 0,001 kg.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        formula_snapshot: Optional[dict] = None
        if data.event_type == "charge":
            self._require_crudo(db, material, organization_id)
            lead_kg = quantity_kg
            source_material = material
            dest_material = self._resolve_lead_material(
                db, organization_id, "puro", data.puro_material_id
            )
        else:
            self._require_crucible_dross(db, material, organization_id)
            lead_kg, formula_snapshot = self._dross_lead_kg(
                db, material, quantity_kg, organization_id
            )
            source_material = self._resolve_lead_material(
                db, organization_id, "puro", data.puro_material_id
            )
            dest_material = self._resolve_lead_material(
                db, organization_id, "crudo", data.crudo_material_id
            )

        warnings: list[str] = []
        down, up = STAGE_FLOW[data.event_type]
        balances = kg_ledger_service.intersede_stage_balances(db, organization_id)
        # La etapa que BAJA lo hace por los kg fisicos (20 de dross salen del crisol).
        after = balances[down] - quantity_kg
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

        # Declaracion anticipada de locks (#106 D4). El orden natural de este
        # metodo YA es ascendente — documento (14) -> par (30) -> transformacion
        # (41) — asi que la declaracion es DEFENSIVA, no load-bearing (O1 de QA):
        # se deja porque es barata y fija el orden si alguien reordena el cuerpo.
        if data.event_type == "dross_return":
            lock_sequences(
                db, organization_id,
                "crucible_number", "movement_number", "transformation_number",
            )
        else:
            lock_sequences(db, organization_id, "crucible_number", "transformation_number")
        charge = CrucibleCharge(
            organization_id=organization_id,
            charge_number=self._generate_charge_number(db, organization_id),
            event_type=data.event_type,
            date=data.date,
            quantity_kg=quantity_kg,
            lead_kg=lead_kg,
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
            + self._qty_text(material, quantity_kg, lead_kg, data.event_type)
        )
        for stage, delta in ((down, -quantity_kg), (up, lead_kg)):
            add_kg_movement(
                db,
                organization_id=organization_id,
                account=account,
                delta_kg=delta,
                transaction_date=data.date,
                description=desc,
                source_type=KG_SOURCE_TYPE,
                source_id=charge.id,
                stage=stage,
                # El snapshot viaja en el movimiento que SUBE: es el que lleva
                # los kg derivados de la formula.
                conversion_formula_snapshot=formula_snapshot if delta > 0 else None,
                created_by=user_id,
            )
        if data.event_type == "dross_return":
            self._emit_dross_pair(db, charge, material, organization_id, user_id, warnings)

        self._move_inventory(
            db, charge, source_material, dest_material, organization_id, user_id, warnings
        )

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
    ) -> tuple[CrucibleCharge, list[str]]:
        """Reversa por `(source_type, source_id)`, patron de la Salida: los dos
        movimientos kg, el par de maquila si hubo, y la transformacion que movio
        el inventario (#109). No valida (#99): un documento viejo tiene que poder
        anularse aunque hoy no pasara el guard, y uno previo al ciclo
        (`transformation_id` NULL) anula como antes.

        Devuelve warnings: `material_transformation.annul` nunca bloquea (#66)
        pero tampoco avisa, asi que el aviso de "ese plomo ya salio" se calcula
        AQUI, antes de anular (respuesta 1 (iii) de QA)."""
        charge = self._get_or_404(db, charge_id, organization_id)
        if charge.status == "annulled":
            raise _err("El documento de crisol ya esta anulado.")
        warnings: list[str] = []
        if charge.transformation_id is not None:
            from app.services.material_transformation import material_transformation

            transformation = db.execute(
                select(MaterialTransformation)
                .options(joinedload(MaterialTransformation.lines))
                .where(MaterialTransformation.id == charge.transformation_id)
            ).unique().scalar_one()
            if transformation.status == "confirmed":
                for line in transformation.lines:
                    dest = db.get(Material, line.destination_material_id)
                    left = dest.current_stock_liquidated - line.quantity
                    if left < 0:
                        warnings.append(
                            f"'{dest.code} {dest.name}' queda en {float(left):g} kg tras la "
                            f"anulacion: parte del plomo que entro con {charge.label} ya salio."
                        )
                material_transformation.annul(
                    db,
                    transformation.id,
                    f"Anulacion de documento de crisol — {charge.label}: {reason}",
                    organization_id,
                    user_id=user_id,
                    commit=False,
                    from_module=True,
                )
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
        return charge, warnings

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
            .options(
                joinedload(CrucibleCharge.material),
                joinedload(CrucibleCharge.warehouse),
                joinedload(CrucibleCharge.transformation).joinedload(MaterialTransformation.source_material),
                joinedload(CrucibleCharge.transformation)
                .joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_material),
            )
            .where(*filters)
            .order_by(CrucibleCharge.date.desc(), CrucibleCharge.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).unique().scalars().all()
        return rows, total

    def _get_or_404(self, db: Session, charge_id: UUID, organization_id: UUID) -> CrucibleCharge:
        charge = db.execute(
            select(CrucibleCharge)
            .options(
                joinedload(CrucibleCharge.material),
                joinedload(CrucibleCharge.warehouse),
                joinedload(CrucibleCharge.transformation).joinedload(MaterialTransformation.source_material),
                joinedload(CrucibleCharge.transformation)
                .joinedload(MaterialTransformation.lines)
                .joinedload(MaterialTransformationLine.destination_material),
            )
            .where(
                CrucibleCharge.id == charge_id,
                CrucibleCharge.organization_id == organization_id,
            )
        ).unique().scalar_one_or_none()
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
        # #109: la maquila del reproceso va sobre el PLOMO, no sobre el dross
        # (Hugo 16-sep: "el valor de la maquila seria sobre 14, no sobre 20").
        amount = (charge.lead_kg * tariff.unit_price_cop).quantize(Decimal("0.01"))
        if amount <= 0:
            return
        from app.services.money_movement import money_movement
        from app.services.transfer import TransferService

        category = TransferService()._get_or_create_maquila_category(db, organization_id)
        desc = (
            f"Maquila reproceso dross — {charge.label} — "
            + self._qty_text(material, charge.quantity_kg, charge.lead_kg, "dross_return")
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

    def _move_inventory(
        self,
        db: Session,
        charge: CrucibleCharge,
        source_material: Material,
        dest_material: Material,
        organization_id: UUID,
        user_id: Optional[UUID],
        warnings: list[str],
    ) -> None:
        """#109 D4 — el inventario lo mueve el motor de transformaciones:

            charge        crudo −q  ->  puro  +q          merma 0
            dross_return  puro  −q  ->  crudo +lead_kg    merma q − lead_kg

        `proportional_weight` con UN destino = el destino entra al costo del
        origen (value_difference 0; la merma se valora al avg del origen y cae
        en la linea de transformaciones del P&L, org-level). Conservacion de
        valor estricta: entrar al avg propio del destino inventaria una
        diferencia contable que nadie produjo."""
        from app.services.material_transformation import material_transformation

        transformation, t_warnings = material_transformation.create(
            db,
            MaterialTransformationCreate(
                source_material_id=source_material.id,
                source_warehouse_id=charge.warehouse_id,
                source_quantity=charge.quantity_kg,
                waste_quantity=charge.quantity_kg - charge.lead_kg,
                cost_distribution="proportional_weight",
                lines=[
                    TransformationLineCreate(
                        destination_material_id=dest_material.id,
                        destination_warehouse_id=charge.warehouse_id,
                        quantity=charge.lead_kg,
                    )
                ],
                date=charge.date,
                reason=f"{EVENT_LABELS[charge.event_type]} — {charge.label}",
            ),
            organization_id,
            user_id=user_id,
            commit=False,
            from_crucible=True,
        )
        charge.transformation_id = transformation.id
        warnings.extend(t_warnings)

    @staticmethod
    def _qty_text(material: Material, quantity_kg: Decimal, lead_kg: Decimal, event_type: str) -> str:
        """Un retorno son kg de DROSS que llevan kg de plomo; rotularlos "kg
        plomo" seria el formateador que miente (#97)."""
        if event_type == "dross_return":
            return (
                f"{material.code} x {float(quantity_kg):g} kg dross "
                f"→ {float(lead_kg):g} kg plomo"
            )
        return f"{material.code} x {float(quantity_kg):g} kg plomo"

    def _dross_lead_kg(
        self, db: Session, material: Material, quantity_kg: Decimal, organization_id: UUID
    ) -> tuple[Decimal, dict]:
        """kg de plomo de un retorno = kg de dross x `lead_percentage` de la
        formula `drosses_to_lead` VIGENTE del material.

        🔴 NO se reusa `_compute_lead_kg` de Salidas (F2 de QA): su rama sin
        formula es 1:1, correcta ALLA porque el clasificador es `lead_product`.
        Heredar el 1:1 seria el defecto de #103 por la otra puerta. Sin formula:
        422 que nombra el material.

        ⚠️ La formula CALCULA, no clasifica (C2 de QA): que material puede
        volver como dross lo decide `_require_crucible_dross`, que corre antes."""
        from app.services.material_conversion_formula import material_conversion_formula

        current = material_conversion_formula.get_current(
            db, organization_id, material_id=material.id
        )
        formula = next((f for f in current if f.formula_type == DROSS_FORMULA_TYPE), None)
        if formula is None:
            raise _err(
                f"'{material.code} {material.name}' no tiene formula de conversion a plomo "
                "(dross → plomo). Creela en Config → Materiales (kg): de ahi sale el "
                "porcentaje de plomo que vuelve al horno.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        factor = Decimal(str((formula.parameters or {})["lead_percentage"]))
        lead_kg = (quantity_kg * factor).quantize(CRUCIBLE_Q)
        if lead_kg <= 0 or lead_kg > quantity_kg:
            raise _err(
                f"Con {float(quantity_kg):g} kg de dross al {float(factor * 100):g} % salen "
                f"{float(lead_kg):g} kg de plomo: la cantidad no es valida para un retorno.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return lead_kg, {
            "formula_id": str(formula.id),
            "formula_type": formula.formula_type,
            "parameters": formula.parameters,
        }

    @staticmethod
    def _resolve_lead_material(
        db: Session, organization_id: UUID, lead: str, explicit_id: Optional[UUID]
    ) -> Material:
        """El material que entra o sale del inventario lo decide `lead_product`
        (#103), no un nombre: el unico activo marcado. Cero -> 422 que dice donde
        marcarlo; mas de uno -> hay que decir cual (`puro_material_id` /
        `crudo_material_id` en el payload)."""
        candidates = db.execute(
            select(Material)
            .join(MaterialKgProfile, MaterialKgProfile.material_id == Material.id)
            .where(
                Material.organization_id == organization_id,
                Material.is_active.is_(True),
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.lead_product == lead,
            )
            .order_by(Material.code)
        ).scalars().all()
        if explicit_id is not None:
            chosen = next((m for m in candidates if m.id == explicit_id), None)
            if chosen is None:
                raise _err(
                    f"El material indicado no esta marcado como plomo {lead}.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return chosen
        if not candidates:
            raise _err(
                f"Ningun material activo esta marcado como plomo {lead}: el documento "
                "no sabria que mover en el inventario. Marquelo en Config → Materiales (kg).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        if len(candidates) > 1:
            codes = ", ".join(m.code for m in candidates)
            raise _err(
                f"Hay mas de un material marcado como plomo {lead} ({codes}). "
                f"Indique cual con '{lead}_material_id'.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return candidates[0]

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

    def _require_crucible_dross(
        self, db: Session, material: Material, organization_id: UUID
    ) -> None:
        """Un retorno de dross solo acepta el dross que SALE del crisol: un
        material SIN mundo Willard (C2 de QA, #109).

        Por que hace falta: la v1.1 del plan decia "la formula es el
        clasificador" y los datos reales lo desmintieron — en SAC 16 materiales
        tienen formula `drosses_to_lead` y 15 son lo que MANDA Willard (guarru,
        cenizas, scrap). Es #103 D1 literal: ni la formula ni la categoria
        clasifican. Sin este guard, por API un retorno con GUARRU (41 %) bajaba
        el crisol 20, subia el horno 8,2 y movia puro/crudo, sin error.

        MISMO predicado que el selector de la pantalla
        (`CrucibleChargeCreatePage`): sin fila de perfil = 'none' = pasa."""
        profile = db.execute(
            select(MaterialKgProfile).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id == material.id,
            )
        ).scalar_one_or_none()
        world = profile.willard_world if profile is not None else "none"
        if world != "none":
            raise _err(
                f"'{material.code} {material.name}' es un material que envia Willard "
                f"(mundo {world}): su formula convierte lo que LLEGA de Willard, no el "
                "dross que sale del crisol. El retorno de dross es para el dross del "
                "crisol (un material sin mundo Willard en Config → Materiales (kg)).",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

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
