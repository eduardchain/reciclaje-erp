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

Plata (Hugo 00:29/00:31): sobre TODA entrega se factura maquila + flete a
Willard y nace la CxC. De la maquila, una porcion se le abona a planta — no es
plata que se mueva de cuenta, es como se reparte el ingreso entre sedes, y por
eso viaja en el par `internal_maquila_*` de #84.
"""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.models.inventory_adjustment import InventoryAdjustment
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.money_movement import MoneyMovement
from app.models.sale import Sale
from app.models.service_tariff import ServiceTariff
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.models.willard_delivery import WillardDelivery, WillardDeliveryLine
from app.schemas.inventory_adjustment import DecreaseCreate
from app.schemas.sale import SaleCreate, SaleLineCreate
from app.schemas.willard_delivery import (
    WillardDeliveryCreate,
    WillardDeliveryLiquidate,
    WillardDeliveryUpdate,
)
from app.utils.dates import business_today_noon
from app.utils.org_settings import get_org_setting

logger = logging.getLogger(__name__)

KG_SOURCE_TYPE = "willard_delivery"
MAQUILA_TARIFF_CODE = "maquila_willard"
FREIGHT_TARIFF_CODE = "flete_willard_planta_planta"
PLANT_CREDIT_TARIFF_CODE = "abono_planta_por_kg"

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
    """Salidas de plomo a Willard — 3 pasos: registrar, revisar, liquidar."""

    # ================================================================== #
    # Escritura                                                           #
    # ================================================================== #

    def create(
        self,
        db: Session,
        data: WillardDeliveryCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> WillardDelivery:
        warehouse = self._validate_warehouse(db, data.warehouse_id, organization_id)
        self._validate_plant_origin(db, organization_id, warehouse)
        self._validate_third_party(db, data.third_party_id, organization_id)
        self._validate_not_future(data.date)

        delivery = WillardDelivery(
            organization_id=organization_id,
            delivery_number=self._next_number(db, organization_id),
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
        return delivery

    def update(
        self,
        db: Session,
        delivery_id: UUID,
        data: WillardDeliveryUpdate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> WillardDelivery:
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

        for key, value in fields.items():
            setattr(delivery, key, value)

        if lines is not None:
            # D17 de #95: editar las LINEAS devuelve la salida a `draft` — la
            # revision certifica pesos y cantidades, o sea lineas. La cabecera no.
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
        return delivery

    def review(
        self,
        db: Session,
        delivery_id: UUID,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> WillardDelivery:
        """Certifica los pesos. Sin peso no se puede revisar (#95 Q-13)."""
        delivery = self._get_or_404(db, delivery_id, organization_id)
        if delivery.status != "draft":
            raise _err(
                f"Solo se puede revisar una salida registrada "
                f"(esta es {self._status_label(delivery.status)})."
            )

        self._require_scale_weights(db, delivery)

        delivery.status = "reviewed"
        delivery.reviewed_by = user_id
        delivery.reviewed_at = datetime.now(tz=None).astimezone()
        db.commit()
        db.refresh(delivery)
        return delivery

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
        if delivery.status != "reviewed":
            raise _err(
                "Solo se puede liquidar una salida revisada "
                f"(esta es {self._status_label(delivery.status)})."
            )
        if not delivery.lines:
            raise _err("La salida no tiene lineas.")

        # Fail-fast ANTES de cualquier efecto: sin esto el 422 sale desde adentro
        # de la venta derivada ("El tercero no es cliente"), que es cierto pero no
        # dice donde arreglarlo. Willard es proveedor Y cliente: entrega baterias
        # y compra plomo.
        if delivery.delivery_type == "venta":
            self._require_customer(db, delivery)

        warnings: list[str] = []
        liq_dt = business_today_noon()

        # 1. kg de plomo por linea, desde la formula VIGENTE (snapshot al liquidar)
        total_kg = self._compute_lead_kg(db, delivery, organization_id, warnings)

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
        self._discharge_kg(db, delivery, total_kg, organization_id, user_id, liq_dt)

        # 4. Facturacion a Willard + reparto entre sedes.
        #    D4d: si falta una tarifa esto avisa, pero los kg de arriba YA se
        #    descargaron. Un efecto fisico no queda colgado de un dato de
        #    configuracion.
        self._bill_and_split(
            db, delivery, total_kg, organization_id, user_id, liq_dt, warnings
        )

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
    ) -> Decimal:
        from app.services.material_conversion_formula import material_conversion_formula

        formulas = {
            f.material_id: f
            for f in material_conversion_formula.get_current(db, organization_id)
        }
        total = Decimal("0")
        for line in delivery.lines:
            material = db.get(Material, line.material_id)
            formula = formulas.get(line.material_id)
            if formula is None:
                # Sin formula el material YA es plomo: la cantidad es el kg.
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
        if total <= 0:
            raise _err("La salida no equivale a ningun kg de plomo.")
        return total

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
                notes=f"Salida a Willard #{delivery.delivery_number}",
                lines=sale_lines,
            ),
            organization_id,
            user_id=user_id,
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
                    reason=f"{label} Willard — Salida #{delivery.delivery_number}",
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
        organization_id: UUID,
        user_id: Optional[UUID],
        liq_dt: datetime,
    ) -> None:
        """Los kg bajan en NEGATIVO. Los dos contadores del abono de bateria
        bajan la MISMA cantidad: es un pago que salda dos deudas encadenadas."""
        for account_type in DISCHARGE_MAP[delivery.delivery_type]:
            account = self._resolve_kg_account(db, organization_id, account_type)
            db.add(
                KgLedgerMovement(
                    organization_id=organization_id,
                    account_id=account.id,
                    delta_kg=-total_kg,
                    transaction_date=liq_dt,
                    description=(
                        f"Salida a Willard #{delivery.delivery_number} — "
                        f"{self._type_label(delivery.delivery_type)}"
                    ),
                    source_type=KG_SOURCE_TYPE,
                    source_id=delivery.id,
                    created_by=user_id,
                    status="confirmed",
                )
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
                    f"{concept} Salida a Willard #{delivery.delivery_number} — "
                    f"{float(total_kg):g} kg plomo"
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

        # (b) Reparto entre sedes — sin el setting no hay a quien abonarle.
        if billing_wh is None or plant_credit <= 0:
            delivery.plant_credit_amount = Decimal("0")
            return
        self._emit_split_pair(
            db, delivery, plant_credit, credit_tariff, billing_wh,
            organization_id, user_id, liq_dt,
        )
        delivery.plant_credit_amount = plant_credit

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
        La porcion de la maquila que Circunvalar le abona a planta. Cuenta y
        tercero NULL: no es plata que se mueva, es como se reparte el ingreso
        entre sedes (#84).

        D11 — este par NO se gatea con `internal_maquila_enabled`. Ese flag
        gobierna el cobro del TRASLADO, que segun Hugo (24-ago) cobra en el
        momento equivocado: la maquila se gana cuando el plomo vuelve a Willard.
        SAC lo apaga, y si compartieramos el gate apagarlo mataria tambien este
        reparto — el modo de falla de #94/#99 donde "el guard funciona" y "lo
        apague para todos" se ven identicos.
        """
        from app.services.money_movement import money_movement
        from app.services.transfer import TransferService

        category = TransferService()._get_or_create_maquila_category(
            db, organization_id
        )
        desc = (
            f"Abono a planta — Salida a Willard #{delivery.delivery_number}"
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
                f"Anulacion de Salida a Willard #{delivery.delivery_number}",
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
                f"Anulacion de Salida a Willard #{delivery.delivery_number}"
            )

        delivery.maquila_amount = Decimal("0")
        delivery.freight_amount = Decimal("0")
        delivery.plant_credit_amount = Decimal("0")

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
                "Sin peso de báscula no se puede revisar. Falta el peso de: "
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
        from app.services.third_party import third_party as tp_service

        tp = db.get(ThirdParty, delivery.third_party_id)
        if tp is not None and tp_service.has_behavior_type(db, tp.id, ["customer"]):
            return
        raise _err(
            f"'{tp.name if tp else 'El tercero'}' no está marcado como cliente, "
            "así que no se le puede facturar la venta. Agréguele la categoría de "
            "cliente en Terceros y vuelva a liquidar."
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

    def _next_number(self, db: Session, organization_id: UUID) -> int:
        lock_id = hash(str(organization_id)) % (2**63)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        current = db.execute(
            select(func.max(WillardDelivery.delivery_number)).where(
                WillardDelivery.organization_id == organization_id
            )
        ).scalar_one_or_none()
        return (current or 0) + 1

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
