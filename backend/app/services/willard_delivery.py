"""
Servicio de Salidas de plomo a Willard (W1).

Espejo de la Entrada (#93): el documento fisico gobierna, la cara financiera se
deriva. Tres tipos, y lo que cada uno mueve sale de UN hecho — hay dos deudas en
plomo con Willard y son de duenos distintos (reunion 24-ago, Hugo 00:37):

    venta           intersede--            planta le paga a Circunvalar con plomo
    abono_bateria   willard_baterias-- e intersede-- (MISMO kg)
    abono_material  willard_drosses--

El abono de bateria baja dos contadores por la misma cantidad porque es UN pago
que salda dos deudas encadenadas (planta -> Circunvalar -> Willard). El de
material no toca `intersede` porque los drosses llegan derecho a planta y
Circunvalar nunca estuvo en esa cadena.

Plata: sobre TODA entrega se factura maquila + flete a Willard y nace la CxC.
El reparto entre sedes (`internal_maquila_*` de #84) es OTRA cosa y NO va en
toda entrega — ver `_emit_split_pair`. CC-009 (demo 28-ago + Johana 3-sep):
la maquila interna se causa AL TRASLADAR, una sola vez, asi que repetirla en
la entrega la cobraria dos veces.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.utils.advisory_locks import lock_sequences, next_number, sequence_lock_key
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_kg_profile import MaterialKgProfile
from app.models.money_movement import MoneyMovement
from app.models.sale import Sale
from app.models.service_tariff import ServiceTariff
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.models.willard_delivery import (
    WillardDelivery,
    WillardDeliveryLine,
    series_of,
)
from app.schemas.inventory_adjustment import DecreaseCreate
from app.schemas.sale import SaleCreate, SaleLineCreate
from app.schemas.willard_delivery import (
    WillardDeliveryCreate,
    WillardDeliveryLiquidate,
    WillardDeliveryUpdate,
)
from app.utils.dates import business_today_noon
from app.utils.org_settings import get_org_setting
from app.services.kg_ledger import (
    INTERSEDE_STAGES,
    STAGE_LABELS,
    add_kg_movement,
    kg_ledger_service,
)

logger = logging.getLogger(__name__)

KG_SOURCE_TYPE = "willard_delivery"
MAQUILA_TARIFF_CODE = "maquila_willard"
FREIGHT_TARIFF_CODE = "flete_willard_planta_planta"
PLANT_CREDIT_TARIFF_CODE = "abono_planta_por_kg"
# #107 D4: diferencial de refinacion, causado al VENDER plomo puro (Hugo 28-ago)
CRUCIBLE_TARIFF_CODE = "maquila_crisol"
CRUCIBLE_CATEGORY_NAME = "Crisol Refinación"

# Que cuentas kg descarga cada tipo. `intersede` es el contador interno (lo que
# planta le debe a Circunvalar); los otros dos son las deudas con Willard.
DISCHARGE_MAP: dict[str, tuple[str, ...]] = {
    "venta": ("intersede",),
    "abono_bateria": ("willard_baterias", "intersede"),
    "abono_material": ("willard_drosses",),
}


def _err(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


class WillardDeliveryService:
    """Salidas de Plomo desde planta — 2 pasos: registrar, liquidar."""

    # ================================================================== #
    # Escritura                                                           #
    # ================================================================== #

    def create(
        self,
        db: Session,
        data: WillardDeliveryCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[WillardDelivery, list[str]]:
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        self._validate_plant_origin(db, organization_id, warehouse)
        self._validate_third_party(db, data.third_party_id, organization_id)
        self._validate_willard_holder(
            db, data.third_party_id, data.delivery_type, organization_id
        )
        # Venta: el tercero tiene que ser CLIENTE ya al capturar. El check vivia
        # solo en liquidate, o sea que una venta a un proveedor se aceptaba y
        # reventaba dias despues (#103 D3). Daniel lo vio en pantalla: el
        # selector ofrecia a todos. No hace falta en update: tipo y tercero son
        # solo-lectura al editar (schema extra=forbid, #103 D9). El check de
        # liquidate se queda para el unico camino que le queda: que al tercero
        # le quiten la categoria de cliente DESPUES de capturar.
        if data.delivery_type == "venta":
            self._require_customer_id(db, data.third_party_id)
        self._validate_not_future(data.date)
        warnings = self._validate_lead_products(
            db,
            [ln.material_id for ln in data.lines],
            data.delivery_type,
            organization_id,
        )

        series = series_of(data.delivery_type)
        delivery = WillardDelivery(
            organization_id=organization_id,
            delivery_number=self._next_number(db, organization_id, series),
            series=series,
            delivery_type=data.delivery_type,
            warehouse_id=data.warehouse_id,
            third_party_id=data.third_party_id,
            date=data.date,
            driver_id=data.driver_id,
            vehicle_id=data.vehicle_id,
            invoice_number=data.invoice_number,
            remission_number=data.remission_number,
            notes=data.notes,
            status="draft",
            created_by=user_id,
        )
        db.add(delivery)
        db.flush()

        self._replace_lines(db, delivery, data.lines, organization_id)
        db.commit()
        db.refresh(delivery)
        return delivery, warnings

    def update(
        self,
        db: Session,
        delivery_id: UUID,
        data: WillardDeliveryUpdate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[WillardDelivery, list[str]]:
        delivery = self._get_or_404(db, delivery_id, organization_id)
        if delivery.status in ("liquidated", "annulled"):
            raise _err(
                f"No se puede editar una salida {self._status_label(delivery.status)}."
            )

        fields = data.model_dump(exclude_unset=True)
        lines = fields.pop("lines", None)

        if "warehouse_id" in fields and fields["warehouse_id"]:
            wh = self._validate_warehouse(db, fields["warehouse_id"], organization_id)
            self._validate_plant_origin(db, organization_id, wh)
        if "date" in fields and fields["date"]:
            self._validate_not_future(fields["date"])

        new_type = fields.get("delivery_type") or delivery.delivery_type
        if fields.get("third_party_id"):
            self._validate_third_party(db, fields["third_party_id"], organization_id)
            self._validate_willard_holder(
                db, fields["third_party_id"], new_type, organization_id
            )

        # ANTES de mutar nada. Si las lineas cambian se validan las nuevas; si no,
        # se revalidan las vigentes, porque cambiar el TIPO tambien puede volver
        # invalido lo que ya estaba (una salida de puro que pasa a ser un abono).
        warnings = self._validate_lead_products(
            db,
            (
                [ln["material_id"] for ln in lines]
                if lines is not None
                else [ln.material_id for ln in delivery.lines]
            ),
            new_type,
            organization_id,
        )

        for key, value in fields.items():
            setattr(delivery, key, value)

        if lines is not None:
            # Editar las LINEAS devuelve la salida a `draft`. Venia de D17 (#95):
            # la revision certificaba lineas. Sin paso de revision (Hugo, 28-ago)
            # solo tiene efecto sobre las filas `reviewed` que quedaron de la
            # version anterior; una registrada ya esta en `draft`.
            from app.schemas.willard_delivery import WillardDeliveryLineCreate

            self._replace_lines(
                db,
                delivery,
                [WillardDeliveryLineCreate(**ln) for ln in lines],
                organization_id,
            )
            if delivery.status == "reviewed":
                delivery.status = "draft"
                delivery.reviewed_by = None
                delivery.reviewed_at = None

        db.commit()
        db.refresh(delivery)
        return delivery, warnings

    def liquidate(
        self,
        db: Session,
        delivery_id: UUID,
        data: WillardDeliveryLiquidate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[WillardDelivery, list[str]]:
        """
        Aplica TODOS los efectos, en una sola transaccion (D14 de #93).

        Un solo reloj para el evento entero (D21 de #93): `business_today_noon()`
        fecha la venta derivada, los ajustes, los kg y los movimientos de dinero.
        """
        delivery = self._get_or_404(db, delivery_id, organization_id)
        # Hugo, demo 28-ago: en salidas no hay revisor — "esto funciona muy
        # diferente porque inmediatamente queda la deuda: registrado y liquidar".
        # `reviewed` se sigue aceptando por las filas que quedaron de la version
        # anterior; ninguna nueva puede llegar a ese estado.
        if delivery.status not in ("draft", "reviewed"):
            raise _err(
                "Solo se puede liquidar una salida registrada "
                f"(esta es {self._status_label(delivery.status)})."
            )
        if not delivery.lines:
            raise _err("La salida no tiene lineas.")
        # El peso de bascula se certificaba al revisar (#95 Q-13). Al desaparecer
        # ese paso, la liquidacion es la unica puerta antes de que se muevan kg y
        # pesos — la certificacion se mueve aqui, no se pierde.
        self._require_scale_weights(db, delivery)

        # Fail-fast ANTES de cualquier efecto: sin esto el 422 sale desde adentro
        # de la venta derivada ("El tercero no es cliente"), que es cierto pero no
        # dice donde arreglarlo. Willard es proveedor Y cliente: entrega baterias
        # y compra plomo.
        if delivery.delivery_type == "venta":
            self._require_customer(db, delivery)

        warnings: list[str] = self._validate_lead_products(
            db,
            [ln.material_id for ln in delivery.lines],
            delivery.delivery_type,
            organization_id,
        )
        liq_dt = business_today_noon()

        # Declaracion anticipada de locks (plan advisory-locks D4): la venta
        # numera una Sale (y sus movimientos al liquidar); el abono numera el
        # ajuste de descarga (D12) y DESPUES la factura y el par — orden inverso
        # al canonico. Se toman aqui en orden canonico para los tres tipos.
        lock_sequences(
            db, organization_id, "sale_number", "movement_number", "adjustment_number"
        )

        # 1. kg de plomo por linea, desde la formula VIGENTE (snapshot al liquidar)
        total_kg, kg_by_stage = self._compute_lead_kg(
            db, delivery, organization_id, warnings
        )

        # 2. Salida fisica del inventario
        if delivery.delivery_type == "venta":
            self._create_derived_sale(
                db, delivery, data, organization_id, user_id, liq_dt, warnings
            )
        else:
            self._discharge_inventory_as_adjustment(
                db, delivery, organization_id, user_id, liq_dt, warnings
            )

        # 3. Descarga de las cuentas en kg
        self._discharge_kg(
            db, delivery, total_kg, kg_by_stage, organization_id, user_id, liq_dt, warnings
        )

        # 4. Facturacion a Willard + reparto entre sedes.
        #    D4d: si falta una tarifa esto avisa, pero los kg de arriba YA se
        #    descargaron. Un efecto fisico no queda colgado de un dato de
        #    configuracion.
        self._bill_and_split(
            db, delivery, total_kg, organization_id, user_id, liq_dt, warnings
        )
        # 4b. Diferencial del crisol (#107 D4): solo venta, solo kg de PURO.
        self._emit_crucible_differential(
            db,
            delivery,
            kg_by_stage.get("crisol", Decimal("0")),
            organization_id,
            user_id,
            liq_dt,
            warnings,
        )
        # Q-30 (#107 D5): la sede que factura se estampa al liquidar (snapshot
        # del setting); el P&L por sede le atribuye la venta derivada.
        delivery.billing_warehouse_id = self._billing_warehouse_id(db, organization_id)
        delivery.status = "liquidated"
        delivery.liquidated_by = user_id
        delivery.liquidated_at = liq_dt
        delivery.liquidated_ts = datetime.now(tz=None).astimezone()

        db.commit()
        db.refresh(delivery)
        return delivery, warnings

    def annul(
        self,
        db: Session,
        delivery_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> WillardDelivery:
        """Reversa completa: venta/ajustes, kg, factura y par."""
        delivery = self._get_or_404(db, delivery_id, organization_id)
        if delivery.status == "annulled":
            raise _err("La salida ya esta anulada.")

        if delivery.status == "liquidated":
            self._reverse_liquidation(db, delivery, organization_id, user_id)

        delivery.status = "annulled"
        delivery.annulled_reason = reason
        delivery.annulled_at = datetime.now(tz=None).astimezone()
        delivery.annulled_by = user_id
        db.commit()
        db.refresh(delivery)
        return delivery

    # ================================================================== #
    # Efectos                                                             #
    # ================================================================== #

    def _compute_lead_kg(
        self,
        db: Session,
        delivery: WillardDelivery,
        organization_id: UUID,
        warnings: list[str],
    ) -> tuple[Decimal, dict[str, Decimal]]:
        """kg de plomo por linea y, ademas, por ETAPA de intersede (#107 D4):
        crudo -> horno, puro -> crisol. El perfil ya lo valido
        `_validate_lead_products`; aqui solo se lee."""
        from app.services.material_conversion_formula import material_conversion_formula

        formulas = {
            f.material_id: f
            for f in material_conversion_formula.get_current(db, organization_id)
        }
        leads = self._lead_products(
            db, [ln.material_id for ln in delivery.lines], organization_id
        )
        by_stage: dict[str, Decimal] = {s: Decimal("0") for s in INTERSEDE_STAGES}
        total = Decimal("0")
        for line in delivery.lines:
            material = db.get(Material, line.material_id)
            formula = formulas.get(line.material_id)
            if formula is None:
                # Sin formula la conversion es 1:1: la cantidad YA esta en kg de
                # plomo. Esto CALCULA, no clasifica — que el material sea plomo
                # entregable lo decide `lead_product` en `_validate_lead_products`,
                # que ya corrio. Usar esta ausencia como clasificador es el defecto
                # que ese guard cierra: el aluminio y el plastico tampoco tienen
                # formula, y saldaban la deuda 1:1.
                kg = line.quantity
                line.conversion_formula_snapshot = None
            else:
                kg = self._kg_from_formula(formula, line.quantity)
                line.conversion_formula_snapshot = {
                    "formula_id": str(formula.id),
                    "formula_type": formula.formula_type,
                    "parameters": formula.parameters,
                }
            line.kg_lead_equivalent = kg
            line.unit = material.default_unit if material else None
            total += kg
            by_stage[self._stage_of(leads.get(line.material_id))] += kg
        if total <= 0:
            raise _err("La salida no equivale a ningun kg de plomo.")
        return total, by_stage

    @staticmethod
    def _kg_from_formula(formula, qty: Decimal) -> Decimal:
        params = formula.parameters or {}
        if formula.formula_type == "battery_to_lead":
            factor = Decimal(str(params["kg_lead_per_unit"]))
        elif formula.formula_type == "drosses_to_lead":
            factor = Decimal(str(params["lead_percentage"]))
        else:
            raise _err(
                f"Tipo de formula '{formula.formula_type}' no soportado en salidas"
            )
        return (qty * factor).quantize(Decimal("0.0001"))

    def _create_derived_sale(
        self,
        db: Session,
        delivery: WillardDelivery,
        data: WillardDeliveryLiquidate,
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
        warnings: list[str],
    ) -> None:
        """D2: solo el tipo `venta` deriva una Sale (patron #93 Entrada->Purchase)."""
        from app.services.sale import crud_sale as sale_service

        prices = {p.line_id: p for p in data.line_prices}
        missing = [ln.id for ln in delivery.lines if ln.id not in prices]
        if missing:
            raise _err(
                "Faltan precios: una venta necesita el precio de todas sus lineas."
            )

        sale_lines = []
        for line in delivery.lines:
            p = prices[line.id]
            if p.unit_price is not None:
                unit_price = p.unit_price
                line.unit_price = unit_price
                line.total_price = None
            else:
                # #95 D8: se digita el VALOR TOTAL y el unitario es formula. Se
                # persiste el total para que sobreviva a un des-liquidar.
                unit_price = (p.total_price / line.quantity).quantize(Decimal("0.01"))
                line.unit_price = unit_price
                line.total_price = p.total_price
            sale_lines.append(
                SaleLineCreate(
                    material_id=line.material_id,
                    quantity=line.quantity,
                    unit_price=unit_price,
                )
            )

        sale = sale_service.create(
            db,
            SaleCreate(
                customer_id=data.customer_id or delivery.third_party_id,
                warehouse_id=delivery.warehouse_id,
                date=liq_dt,
                invoice_number=delivery.invoice_number,
                notes=f"Salida de Plomo — {delivery.label}",
                lines=sale_lines,
            ),
            organization_id,
            user_id=user_id,
            # La venta derivada es la UNICA venta legitima de plomo entregable:
            # sin esto, el guard de Ventas la rechazaria a ella tambien.
            from_willard_delivery=True,
        )
        warnings.extend(getattr(sale, "_warnings", []) or [])

        sale = sale_service.liquidate(
            db, sale.id, organization_id, user_id=user_id, liquidation_date=liq_dt
        )
        sale.willard_delivery_id = delivery.id
        delivery.sale_id = sale.id
        for line in delivery.lines:
            sl = next(
                (s for s in sale.lines if s.material_id == line.material_id), None
            )
            if sl is not None:
                line.unit_cost = sl.unit_cost

    def _discharge_inventory_as_adjustment(
        self,
        db: Session,
        delivery: WillardDelivery,
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
        warnings: list[str],
    ) -> None:
        """
        Los abonos no son ventas: no hay ingreso por el plomo. Pero el inventario
        que sale SI esta valorizado, y ese costo tiene que llegar al P&L — si no,
        el activo baja sin que nada lo compense y el resultado del mes miente.

        El `decrease` es el vehiculo: entra a `adjustment_net` del P&L, conserva
        valor por construccion (#66) y ya esta probado. Es el mismo camino que
        #84 uso para la merma de traslados.
        """
        from app.services.inventory_adjustment import inventory_adjustment

        label = (
            "Abono a batería" if delivery.delivery_type == "abono_bateria"
            else "Abono a material"
        )
        for line in delivery.lines:
            adj, adj_warnings = inventory_adjustment.decrease(
                db,
                DecreaseCreate(
                    material_id=line.material_id,
                    warehouse_id=delivery.warehouse_id,
                    quantity=line.quantity,
                    date=liq_dt,
                    reason=f"{label} Willard — Salida de Plomo — {delivery.label}",
                ),
                organization_id,
                user_id=user_id,
                commit=False,
            )
            adj.willard_delivery_id = delivery.id
            line.unit_cost = adj.unit_cost
            warnings.extend(adj_warnings)

    def _discharge_kg(
        self,
        db: Session,
        delivery: WillardDelivery,
        total_kg: Decimal,
        kg_by_stage: dict[str, Decimal],
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
        warnings: list[str],
    ) -> None:
        """Los kg bajan en NEGATIVO. Los dos contadores del abono de bateria
        bajan la MISMA cantidad: es un pago que salda dos deudas encadenadas.

        #107 D4: la cuenta intersede se descarga POR ETAPA segun el plomo de
        cada linea (crudo -> horno, puro -> crisol); las cuentas Willard bajan
        el total sin etapa. Una etapa que quede en negativo AVISA, no bloquea
        (#17/#76): lo tipico es haber vendido puro sin registrar el traslado a
        crisoles, y el aviso dice donde registrarlo.
        """
        desc = (
            f"Salida de Plomo — {delivery.label} — "
            f"{self._type_label(delivery.delivery_type)}"
        )
        for account_type in DISCHARGE_MAP[delivery.delivery_type]:
            account = self._resolve_kg_account(db, organization_id, account_type)
            if account_type != "intersede":
                add_kg_movement(
                    db,
                    organization_id=organization_id,
                    account=account,
                    delta_kg=-total_kg,
                    transaction_date=liq_dt,
                    description=desc,
                    source_type=KG_SOURCE_TYPE,
                    source_id=delivery.id,
                    created_by=user_id,
                )
                continue
            balances = kg_ledger_service.intersede_stage_balances(db, organization_id)
            for stage in INTERSEDE_STAGES:
                kg = kg_by_stage.get(stage, Decimal("0"))
                if kg <= 0:
                    continue
                after = balances[stage] - kg
                if after < 0 and stage == "crisol":
                    # Solo la etapa crisol avisa (D4): vender puro sin haber
                    # registrado el traslado a crisoles es un olvido de
                    # captura con remedio. El horno en negativo NO avisa
                    # aqui: es el mismo "planta entrega lo que Circunvalar
                    # aun no le mando" de antes de este ciclo, y una venta
                    # con todo configurado sigue siendo una salida perfecta
                    # (test_la_venta_no_pide_anular_una_salida_perfecta).
                    warnings.append(
                        f"La etapa {STAGE_LABELS[stage]} de intersede queda en "
                        f"{float(after):g} kg tras esta salida. Registre el "
                        "Traslado a crisoles (Salidas de Plomo → Crisol)."
                    )
                add_kg_movement(
                    db,
                    organization_id=organization_id,
                    account=account,
                    delta_kg=-kg,
                    transaction_date=liq_dt,
                    description=desc,
                    source_type=KG_SOURCE_TYPE,
                    source_id=delivery.id,
                    stage=stage,
                    created_by=user_id,
                )

    def _bill_and_split(
        self,
        db: Session,
        delivery: WillardDelivery,
        total_kg: Decimal,
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
        warnings: list[str],
    ) -> None:
        from app.services.money_movement import money_movement

        # CC-009: en una VENTA, Willard paga el precio del plomo y nada mas
        # (Hugo 4-sep: "de venta normal, solamente el precio de venta. La
        # maquila solamente aplica para el plomo a devolucion... y el flete
        # afecta solamente cuando facturamos maquila. En venta no").
        # El corte va ARRIBA DE TODO a proposito: mas abajo hay un warning de
        # tarifa faltante que le pediria al usuario anular una salida que esta
        # perfecta (familia de #100 D10, el mensaje que mandaba al modulo
        # equivocado). Nada de lo que sigue tiene efectos: son lecturas puras.
        if delivery.delivery_type == "venta":
            delivery.maquila_amount = Decimal("0")
            delivery.freight_amount = Decimal("0")
            delivery.plant_credit_amount = Decimal("0")
            return

        billing_wh = self._billing_warehouse_id(db, organization_id)
        willard = db.get(ThirdParty, delivery.third_party_id)

        def _amount(code: str) -> tuple[Optional[ServiceTariff], Decimal]:
            tariff = self._current_tariff(db, organization_id, code)
            if tariff is None:
                return None, Decimal("0")
            return tariff, (total_kg * tariff.unit_price_cop).quantize(Decimal("0.01"))

        maquila_tariff, maquila = _amount(MAQUILA_TARIFF_CODE)
        freight_tariff, freight = _amount(FREIGHT_TARIFF_CODE)
        credit_tariff, plant_credit = _amount(PLANT_CREDIT_TARIFF_CODE)

        for tariff, code in (
            (maquila_tariff, MAQUILA_TARIFF_CODE),
            (freight_tariff, FREIGHT_TARIFF_CODE),
        ):
            if tariff is None:
                warnings.append(
                    f"Sin tarifa vigente '{code}': no se facturo esa parte. "
                    "Configurela en Config → Tarifas y anule/rehaga la salida."
                )

        # (a) Factura a Willard — CxC. NO entra al flujo de caja: es causado.
        #     Solo llega aca un abono: la venta ya corto arriba.
        for concept, amount, tariff in (
            ("Maquila", maquila, maquila_tariff),
            ("Flete", freight, freight_tariff),
        ):
            if amount <= 0:
                continue
            money_movement._create_movement(
                db=db,
                organization_id=organization_id,
                movement_type="service_income_accrual",
                amount=amount,
                account_id=None,
                date=liq_dt,
                description=(
                    f"{concept} Salida de Plomo — {delivery.label} "
                    f"({float(total_kg):g} kg plomo)"
                ),
                third_party_id=delivery.third_party_id,
                user_id=user_id,
                source_type=KG_SOURCE_TYPE,
                source_id=delivery.id,
                tariff_id=tariff.id if tariff else None,
                warehouse_id=billing_wh,
            )
            if willard:
                willard.current_balance += amount

        delivery.maquila_amount = maquila
        delivery.freight_amount = freight

        # (b) Reparto entre sedes — SOLO en el abono en materiales (CC-009).
        #     En venta y abono de baterias ese material paso por Circunvalar,
        #     asi que la maquila interna ya se causo al trasladar.
        if (
            delivery.delivery_type != "abono_material"
            or billing_wh is None
            or plant_credit <= 0
        ):
            delivery.plant_credit_amount = Decimal("0")
            return

        # Q-27 volvio al abono una TAJADA de la maquila ("de los $2.097, $1.500
        # van a planta"), asi que existe un invariante nuevo: el abono no puede
        # superar lo facturado. En el codigo son dos tarifas sin relacion, y si
        # divergen en Config la sede que factura queda en perdida en silencio
        # — la forma exacta del defecto de #100 D13, por la otra puerta.
        # Avisa, no bloquea (#17/#76): mientras Q-29 este abierta nadie puede
        # afirmar que deban ser iguales, solo que esta no puede ser mayor.
        if plant_credit > maquila:
            # `_fmt_money` y no un f-string: `f"${x:,.0f}"` imprime $75,000 —
            # separador ingles. En formato colombiano eso se lee 75 pesos con
            # decimales. Es "el formateador que miente" (#102) y lo atrapo el
            # test al exigir el NUMERO, no solo que el aviso existiera.
            from app.services.obligation_interest import _fmt_money

            warnings.append(
                f"El abono a planta ({_fmt_money(plant_credit)}) supera la "
                f"maquila facturada a Willard ({_fmt_money(maquila)}): la sede "
                "que factura queda en perdida en esta salida. Revise "
                "'abono_planta_por_kg' y 'maquila_willard' en Config → Tarifas."
            )
        self._emit_split_pair(
            db, delivery, plant_credit, credit_tariff, billing_wh,
            organization_id, user_id, liq_dt,
        )
        delivery.plant_credit_amount = plant_credit

    def _emit_crucible_differential(
        self,
        db: Session,
        delivery: WillardDelivery,
        kg_puro: Decimal,
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
        warnings: list[str],
    ) -> None:
        """
        #107 D4 — el diferencial del crisol ($300/kg, `maquila_crisol`) se causa
        al VENDER plomo puro (Hugo 28-ago :425 "cuando resta ese plomo puro, le
        abonas un diferencial a la maquila de planta que es de 300"), de planta
        a Circunvalar: `internal_maquila_income` (sede de la salida) /
        `internal_maquila_expense` (sede que factura), categoria sistema
        "Crisol Refinacion" (spec §5). Sin tarifa o sin sede de facturacion los
        kg ya salieron y se avisa (D4d de #100).

        ⚠️ F4a de QA — en este modulo conviven DOS regimenes de gate y NO se
        unifican: el par de `abono_material` (`_emit_split_pair`, reparto del
        ingreso de Willard) es por TIPO e IGNORA `internal_maquila_enabled`;
        este par y el del retorno de dross (crucible_charge) son por FLAG.
        Contraste a tres bandas en los tests: T5b + T7b (flag OFF, sin par) +
        test_par_emite_en_abono_material (flag OFF, par emitido).
        """
        delivery.crucible_amount = Decimal("0")
        if delivery.delivery_type != "venta" or kg_puro <= 0:
            return
        if not get_org_setting(db, organization_id, "internal_maquila_enabled"):
            return
        billing_wh = self._billing_warehouse_id(db, organization_id)
        if billing_wh is None:
            warnings.append(
                "Sin sede de facturacion configurada: el plomo puro salio sin "
                "causar el diferencial del crisol. Definala en la configuracion "
                "de la organizacion."
            )
            return
        tariff = self._current_tariff(db, organization_id, CRUCIBLE_TARIFF_CODE)
        if tariff is None:
            warnings.append(
                f"Sin tarifa vigente '{CRUCIBLE_TARIFF_CODE}': el plomo puro salio "
                "sin causar el diferencial del crisol. Configurela en Config → Tarifas."
            )
            return
        amount = (kg_puro * tariff.unit_price_cop).quantize(Decimal("0.01"))
        if amount <= 0:
            return
        from app.services.money_movement import money_movement
        from app.services.transfer import TransferService

        category = TransferService()._get_or_create_maquila_category(
            db,
            organization_id,
            name=CRUCIBLE_CATEGORY_NAME,
            description="Diferencial de refinacion en crisol al vender plomo puro (SAC, #107)",
        )
        desc = (
            f"Diferencial crisol — Salida de Plomo — {delivery.label} "
            f"({float(kg_puro):g} kg puro)"
        )
        mm_exp = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_expense",
            amount=amount,
            account_id=None,
            date=liq_dt,
            description=desc,
            user_id=user_id,
            expense_category_id=category.id,
            source_type=KG_SOURCE_TYPE,
            source_id=delivery.id,
            tariff_id=tariff.id,
            warehouse_id=billing_wh,
        )
        mm_inc = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_income",
            amount=amount,
            account_id=None,
            date=liq_dt,
            description=desc,
            user_id=user_id,
            source_type=KG_SOURCE_TYPE,
            source_id=delivery.id,
            tariff_id=tariff.id,
            warehouse_id=delivery.warehouse_id,
        )
        mm_exp.transfer_pair_id = mm_inc.id
        mm_inc.transfer_pair_id = mm_exp.id
        delivery.crucible_amount = amount

    def _emit_split_pair(
        self,
        db: Session,
        delivery: WillardDelivery,
        amount: Decimal,
        tariff: Optional[ServiceTariff],
        billing_wh: UUID,
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
    ) -> None:
        """
        La porcion que Circunvalar le abona a planta, SOLO en el abono en
        materiales. Cuenta y tercero NULL: no es plata que se mueva, es como
        se reparte el ingreso entre sedes (#84).

        🔴 CC-009 (2026-09-03) SUPERSEDE a D11. D11 decia que este par se emite
        en TODA entrega y que por eso no comparte gate con
        `internal_maquila_enabled`. La demo del 28-ago lo desmintio: en venta y
        en abono de baterias el material paso por Circunvalar, asi que la
        maquila interna YA se causo al trasladar (Hugo: "no se le afecta maquila
        porque ya yo la maquila la tengo causada"). Repetirla aqui la cobraria
        dos veces. Los drosses son la excepcion porque llegan derecho a planta
        y nunca hubo traslado.

        El gate por TIPO se conserva separado del flag a proposito: son dos
        preguntas distintas (que tipo de salida reparte / si el traslado cobra),
        y compartirlo reproduciria el modo de falla de #94/#99.

        Q-27 CERRADA (Hugo, 4-sep): esta rama existe y el numero es $1.500/kg
        — "cuando facturamos, si le cobramos la maquila a Willard se le factura
        y se le abona una parte a planta y la otra le queda a la Circunvalar".
        No contradice a Johana (3-sep): ella dice que Circunvalar no le debe una
        MAQUILA a planta, y es cierto — no hubo traslado; esto es repartir el
        ingreso de Willard, que es otra cosa.

        ⚠️ Abierto, y a proposito: `abono_planta_por_kg` vale hoy lo mismo que
        `maquila_intersede_cv_jm` ($1.500) y son DOS filas. Nadie ha dicho que
        sean el mismo numero — es una coincidencia sin verificar, la tercera de
        este ciclo con ese valor. Si Hugo confirma que se mueven juntas, se
        unifican; mientras tanto, quien edite una en Config debe mirar la otra.
        """
        from app.services.money_movement import money_movement
        from app.services.transfer import TransferService

        category = TransferService()._get_or_create_maquila_category(
            db, organization_id
        )
        desc = (
            f"Abono a planta — Salida de Plomo — {delivery.label}"
        )
        mm_exp = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_expense",
            amount=amount,
            account_id=None,
            date=liq_dt,
            description=desc,
            user_id=user_id,
            expense_category_id=category.id,
            source_type=KG_SOURCE_TYPE,
            source_id=delivery.id,
            tariff_id=tariff.id if tariff else None,
            warehouse_id=billing_wh,
        )
        mm_inc = money_movement._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="internal_maquila_income",
            amount=amount,
            account_id=None,
            date=liq_dt,
            description=desc,
            user_id=user_id,
            source_type=KG_SOURCE_TYPE,
            source_id=delivery.id,
            tariff_id=tariff.id if tariff else None,
            warehouse_id=delivery.warehouse_id,
        )
        mm_exp.transfer_pair_id = mm_inc.id
        mm_inc.transfer_pair_id = mm_exp.id

    def _reverse_liquidation(
        self,
        db: Session,
        delivery: WillardDelivery,
        organization_id: UUID,
        user_id: Optional[UUID],
    ) -> None:
        from app.services.inventory_adjustment import inventory_adjustment
        from app.services.sale import crud_sale as sale_service

        # 1. Venta derivada
        if delivery.sale_id:
            sale = db.get(Sale, delivery.sale_id)
            if sale is not None and sale.status != "cancelled":
                sale_service.cancel(db, sale.id, organization_id, user_id=user_id)

        # 2. Ajustes hijos
        adjustments = db.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.willard_delivery_id == delivery.id,
                InventoryAdjustment.status == "confirmed",
            )
        ).scalars().all()
        for adj in adjustments:
            inventory_adjustment.annul(
                db,
                adj.id,
                f"Anulacion de Salida de Plomo — {delivery.label}",
                organization_id,
                user_id=user_id,
                commit=False,
                from_module=True,
            )

        # 3. kg — se anulan, no se borran (el libro es append-only)
        kg_movements = db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.source_type == KG_SOURCE_TYPE,
                KgLedgerMovement.source_id == delivery.id,
                KgLedgerMovement.status == "confirmed",
            )
        ).scalars().all()
        for mv in kg_movements:
            mv.status = "annulled"

        # 4. Factura y par. NO se pasa por money_movement.annul(): su guard
        #    422-earia estos mismos movimientos (mismo deadlock que resolvio #84).
        movements = db.execute(
            select(MoneyMovement).where(
                MoneyMovement.source_type == KG_SOURCE_TYPE,
                MoneyMovement.source_id == delivery.id,
                MoneyMovement.status == "confirmed",
            )
        ).scalars().all()
        now = datetime.now(tz=None).astimezone()
        for mv in movements:
            if mv.movement_type == "service_income_accrual" and mv.third_party_id:
                tp = db.get(ThirdParty, mv.third_party_id)
                if tp:
                    tp.current_balance -= mv.amount
            mv.status = "annulled"
            mv.annulled_at = now
            mv.annulled_by = user_id
            mv.annulled_reason = (
                f"Anulacion de Salida de Plomo — {delivery.label}"
            )

        delivery.maquila_amount = Decimal("0")
        delivery.freight_amount = Decimal("0")
        delivery.plant_credit_amount = Decimal("0")
        delivery.crucible_amount = Decimal("0")
        delivery.billing_warehouse_id = None

    # ================================================================== #
    # Validaciones y helpers                                              #
    # ================================================================== #

    def _replace_lines(
        self,
        db: Session,
        delivery: WillardDelivery,
        lines,
        organization_id: UUID,
    ) -> None:
        for old in list(delivery.lines):
            db.delete(old)
        db.flush()
        seen: set[UUID] = set()
        for item in lines:
            if item.material_id in seen:
                raise _err("Un material no puede repetirse en la misma salida.")
            seen.add(item.material_id)
            material = self._validate_material(db, item.material_id, organization_id)
            db.add(
                WillardDeliveryLine(
                    organization_id=organization_id,
                    willard_delivery_id=delivery.id,
                    material_id=item.material_id,
                    quantity=item.quantity,
                    unit=material.default_unit,
                    scale_weight_kg=self._auto_weight(material, item),
                )
            )
        db.flush()

    @staticmethod
    def _auto_weight(material: Material, item) -> Optional[Decimal]:
        """D2 de #95: si el material YA se mide en kg, el peso ES la cantidad —
        y se autocompleta en el SERVIDOR, no solo en la pantalla."""
        if item.scale_weight_kg is not None:
            return item.scale_weight_kg
        if (material.default_unit or "kg").lower() == "kg":
            return item.quantity
        return None

    def _require_scale_weights(self, db: Session, delivery: WillardDelivery) -> None:
        faltantes = []
        for line in delivery.lines:
            if line.scale_weight_kg is None or line.scale_weight_kg <= 0:
                material = db.get(Material, line.material_id)
                faltantes.append(material.code if material else str(line.material_id))
        if faltantes:
            raise _err(
                "Sin peso de báscula no se puede liquidar. Falta el peso de: "
                + ", ".join(faltantes)
            )

    def _validate_warehouse(
        self, db: Session, warehouse_id: UUID, organization_id: UUID
    ) -> Warehouse:
        from app.services.transfer import validate_not_transit_warehouse

        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.organization_id != organization_id:
            raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if not warehouse.is_active:
            raise _err("La bodega no esta activa")
        validate_not_transit_warehouse(db, organization_id, warehouse)
        return warehouse

    def _validate_plant_origin(
        self, db: Session, organization_id: UUID, warehouse: Warehouse
    ) -> None:
        """
        D8 — el plomo sale de planta. Hugo, 00:27: *"drosses nunca sale de
        Circunvalar, siempre sale de Juan Mina"*, y 00:38 *"cuando yo despacho
        el plomo de la planta"*.

        Se lleva a guard porque salir de otra sede daria numeros equivocados en
        SILENCIO: descargaria la deuda sin que el material haya estado en planta.
        Sin el setting configurado no valida (compat).
        """
        plant_id = get_org_setting(db, organization_id, "willard_sede_drosses")
        if not plant_id:
            return
        if str(warehouse.id) != str(plant_id):
            plant = db.get(Warehouse, UUID(str(plant_id)))
            raise _err(
                f"El plomo a Willard sale de la planta"
                f"{f' ({plant.name})' if plant else ''}, no de '{warehouse.name}'. "
                "Trasladelo primero y despache desde alli."
            )

    def _require_customer(self, db: Session, delivery: WillardDelivery) -> None:
        self._require_customer_id(db, delivery.third_party_id)

    def _require_customer_id(self, db: Session, third_party_id: UUID) -> None:
        from app.services.third_party import third_party as tp_service

        tp = db.get(ThirdParty, third_party_id)
        # QA F4 (#104): un cliente puede DESACTIVARSE entre la captura y la
        # liquidacion (se permite con saldo 0); sin este check el 400 salia desde
        # adentro de la venta derivada, sin decir donde arreglarlo.
        if tp is not None and not tp.is_active:
            raise _err(
                f"'{tp.name}' está inactivo, así que no se le puede facturar una "
                "venta. Reactívelo en Terceros y vuelva a intentarlo."
            )
        if tp is not None and tp_service.has_behavior_type(db, tp.id, ["customer"]):
            return
        # El mismo texto sirve al capturar y al liquidar: dice DONDE arreglarlo
        # y no presume en que paso estamos ("vuelva a liquidar" mentia al capturar).
        raise _err(
            f"'{tp.name if tp else 'El tercero'}' no está marcado como cliente, "
            "así que no se le puede facturar una venta. Agréguele la categoría de "
            "cliente en Terceros y vuelva a intentarlo."
        )

    def _lead_products(
        self, db: Session, material_ids: list[UUID], organization_id: UUID
    ) -> dict[UUID, str]:
        """`lead_product` por material (#103 D1). Sin fila de perfil no hay
        entrada en el dict: el consumidor lee 'none' (fail-closed)."""
        if not material_ids:
            return {}
        rows = db.execute(
            select(MaterialKgProfile.material_id, MaterialKgProfile.lead_product).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(material_ids),
            )
        ).all()
        return {r[0]: (r[1] or "none") for r in rows}

    @staticmethod
    def _stage_of(lead: Optional[str]) -> str:
        """Etapa de intersede que descarga cada plomo (#107 D4): puro -> crisol,
        crudo -> horno. 'none' no llega aqui: el validador lo rechazo antes."""
        return "crisol" if lead == "puro" else "horno"

    def _validate_lead_products(
        self,
        db: Session,
        material_ids: list[UUID],
        delivery_type: str,
        organization_id: UUID,
    ) -> list[str]:
        """
        Solo el plomo entregable sale hacia Willard.

        UN validador para los TRES puntos de entrada (`create`, `update`,
        `liquidate`), calco de `_validate_willard_capture` (#81). Eran cuatro
        hasta que `review` desaparecio (Hugo, demo 28-ago). Si viviera solo en la
        liquidacion, el material equivocado se aceptaria en el patio y el error
        saldria dias despues, con el camion ido.

        `annul` queda fuera A PROPOSITO (#99): anular no valida — una salida vieja
        tiene que poder anularse aunque su material hoy no pasara el guard.

        ⚠️ La clasificacion sale de `lead_product` y de NADA MAS. NO reutilizar
        "sin formula" (el aluminio y el plastico tampoco tienen) ni la categoria
        (la categoria "Plomo" de SAC contiene cajas plasticas): ese atajo ES el
        defecto que este guard cierra.
        """
        if not material_ids:
            return []

        leads = self._lead_products(db, material_ids, organization_id)
        warnings: list[str] = []
        for material_id in material_ids:
            # Sin fila de perfil = sin marcar = bloqueado (fail-closed): el modo
            # de falla correcto es no dejar pasar, con un mensaje que dice donde
            # marcarlo, en vez de seguir calculando mal en silencio.
            lead = leads.get(material_id, "none")
            material = db.get(Material, material_id)
            label = (
                f"'{material.code} {material.name}'" if material else "El material"
            )
            if lead == "none":
                raise _err(
                    f"{label} no esta marcado como plomo entregable a Willard. "
                    "Solo el plomo crudo o puro salda la deuda. Marquelo en "
                    "Config -> Materiales (kg) si corresponde."
                )
            if lead == "puro" and delivery_type in ("abono_bateria", "abono_material"):
                # Avisa, no bloquea: entregar puro NO fabrica un servicio (la
                # fundicion ocurrio, la maquila facturada es trabajo real); lo
                # raro es regalar el margen de refinacion. Hugo describe el puro
                # como lo que se vende, no como algo prohibido en un abono.
                warnings.append(
                    f"Esta abonando con PLOMO PURO ({label}). El puro normalmente "
                    "se vende; el abono se hace con crudo."
                )
        return warnings

    def _validate_willard_holder(
        self,
        db: Session,
        third_party_id: UUID,
        delivery_type: str,
        organization_id: UUID,
    ) -> None:
        """
        En un ABONO el tercero tiene que ser el titular de la cuenta kg que se
        descarga. Las cuentas se resuelven por `account_type`, NO por el tercero
        del documento: sin esto una salida contra otro tercero descarga la deuda
        de Willard y le factura la maquila y el flete a ese otro.

        La VENTA queda fuera y no es un olvido: descarga `intersede`, que por
        CHECK no puede tener titular, y ya tiene su propia regla
        (`_require_customer`) — venderle plomo a otro cliente es legitimo.

        Si la cuenta todavia no existe NO se bloquea la captura: sin cuenta la
        salida no se puede liquidar, o sea que no hay efecto financiero que
        proteger, y reclamar la configuracion faltante es tarea de la liquidacion.
        """
        if delivery_type not in ("abono_bateria", "abono_material"):
            return
        account_type = next(
            (a for a in DISCHARGE_MAP[delivery_type] if a.startswith("willard_")),
            None,
        )
        if account_type is None:
            return
        try:
            account = self._resolve_kg_account(db, organization_id, account_type)
        except HTTPException:
            return
        if account.third_party_id is None or str(account.third_party_id) == str(
            third_party_id
        ):
            return
        holder = db.get(ThirdParty, account.third_party_id)
        raise _err(
            "El abono salda la deuda en kg de "
            f"{holder.name if holder else 'el titular de la cuenta'}, "
            "asi que la salida tiene que ir a ese mismo tercero.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    def _validate_third_party(
        self, db: Session, third_party_id: UUID, organization_id: UUID
    ) -> ThirdParty:
        tp = db.get(ThirdParty, third_party_id)
        if not tp or tp.organization_id != organization_id:
            raise _err("Tercero no encontrado", status.HTTP_404_NOT_FOUND)
        if not tp.is_active:
            raise _err("El tercero no esta activo")
        return tp

    def _validate_material(
        self, db: Session, material_id: UUID, organization_id: UUID
    ) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise _err("Material no encontrado", status.HTTP_404_NOT_FOUND)
        if not material.is_active:
            raise _err(f"El material '{material.code}' no esta activo")
        return material

    @staticmethod
    def _validate_not_future(value: datetime) -> None:
        if value.date() > business_today_noon().date():
            raise _err("La fecha no puede ser futura")

    def _resolve_kg_account(
        self, db: Session, organization_id: UUID, account_type: str
    ) -> KgLedgerAccount:
        """
        `intersede` y `willard_drosses` son org-wide. `willard_baterias` vive por
        sede, y la que se descarga es la de la sede que FACTURA: la deuda de
        postconsumo es de Circunvalar porque las baterias entran por alli
        (Hugo 00:37), aunque el plomo salga de planta.
        """
        filters = [
            KgLedgerAccount.organization_id == organization_id,
            KgLedgerAccount.account_type == account_type,
            KgLedgerAccount.is_active.is_(True),
        ]
        if account_type == "willard_baterias":
            billing_wh = self._billing_warehouse_id(db, organization_id)
            if billing_wh is None:
                raise _err(
                    "No esta configurada la sede que factura a Willard. "
                    "Definala en la configuracion de la organizacion."
                )
            filters.append(KgLedgerAccount.warehouse_id == billing_wh)
        else:
            filters.append(KgLedgerAccount.warehouse_id.is_(None))

        account = db.execute(select(KgLedgerAccount).where(*filters)).scalar_one_or_none()
        if account is None:
            raise _err(
                f"No hay cuenta en kg activa de tipo '{account_type}'. "
                "Creela en Plomo (kg) antes de despachar."
            )
        return account

    @staticmethod
    def _billing_warehouse_id(db: Session, organization_id: UUID) -> Optional[UUID]:
        raw = get_org_setting(db, organization_id, "willard_sede_facturacion")
        return UUID(str(raw)) if raw else None

    @staticmethod
    def _current_tariff(
        db: Session, organization_id: UUID, code: str
    ) -> Optional[ServiceTariff]:
        """Vigente = la mas reciente (append-only #35, tiebreaker por id)."""
        return db.execute(
            select(ServiceTariff)
            .where(
                ServiceTariff.organization_id == organization_id,
                ServiceTariff.tariff_code == code,
            )
            .order_by(ServiceTariff.created_at.desc(), ServiceTariff.id.desc())
            .limit(1)
        ).scalar_one_or_none()

    @staticmethod
    def _lock_key(organization_id: UUID, series: str) -> int:
        """Llave ESTABLE del advisory lock (#105 D3, F2 de QA) — hoy delega en el
        helper unico; la cadena (`org:willard_delivery:serie`) es la misma que
        #105 estreno, asi que el test que la compara contra crc32 sigue valiendo.
        """
        return sequence_lock_key(organization_id, "willard_delivery", series)
    def _next_number(self, db: Session, organization_id: UUID, series: str) -> int:
        """Siguiente numero de la SERIE (#105 D2): venta y abono cuentan aparte."""
        return next_number(db, organization_id, "willard_delivery", series)
    def _get_or_404(
        self, db: Session, delivery_id: UUID, organization_id: UUID
    ) -> WillardDelivery:
        delivery = db.execute(
            select(WillardDelivery)
            .where(
                WillardDelivery.id == delivery_id,
                WillardDelivery.organization_id == organization_id,
            )
            .options(selectinload(WillardDelivery.lines))
        ).scalar_one_or_none()
        if delivery is None:
            raise _err("Salida no encontrada", status.HTTP_404_NOT_FOUND)
        return delivery

    @staticmethod
    def _status_label(status_value: str) -> str:
        return {
            "draft": "registrada",
            "reviewed": "revisada",
            "liquidated": "liquidada",
            "annulled": "anulada",
        }.get(status_value, status_value)

    @staticmethod
    def _type_label(delivery_type: str) -> str:
        return {
            "venta": "Venta",
            "abono_bateria": "Abono a batería",
            "abono_material": "Abono a material",
        }.get(delivery_type, delivery_type)


willard_delivery = WillardDeliveryService()
