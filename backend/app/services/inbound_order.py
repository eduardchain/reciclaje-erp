"""
Servicio InboundOrder — Entradas (SAC E2 §4.2, rediseño #93 entrada-sin-proveedor).

Tipos Willard (D13 — intactos): el material entra al inventario al costo
promedio VIGENTE (identidad D2) + un KgLedgerMovement por linea (D5) con la
formula vigente. MCH con transaction_date = HOY (H1a). Proveedor = titular de
la cuenta kg. Flujo: draft (captura) -> confirmed.

Tipos purchase (#93): la captura registra SOLO el hecho fisico — sin proveedor
(D1), sin efectos de inventario ni financieros (D9). Flujo:
    draft (registrada) -> reviewed (revisada, permiso purchases.review D10)
        -> liquidated | annulled
La LIQUIDACION es atomica (D14): el reparto asigna cada linea a N proveedores
-> N compras nacen y se liquidan en UNA transaccion (commit unico), el
descuadre pesado-repartido se ajusta al precio de referencia (D5-D7, SIEMPRE
despues de las N compras — requisito de orden del pool), y la comision del
recolector se causa UNA vez por entrada sobre lo pesado (D11). Todo el evento
lleva EL MISMO dia de negocio: el de la liquidacion (D21 — las compras nacen
con date = fecha de la Entrada pero TODO efecto aterriza en business_today).

Reversa (D20): unliquidate revierte las N compras (helper compartido de
purchase.py), anula ajustes de descuadre y comision, y vuelve a 'revisada'
CONSERVANDO el reparto — sin quemar consecutivos. El annul de una liquidada
delega en unliquidate y despues cancela (D14 fix 3).
"""
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import String as SAString, and_, cast, func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.inbound_order import (
    InboundLineAllocation,
    InboundOrder,
    InboundOrderLine,
    InboundOrderPurchase,
)
from app.utils.dates import business_today, business_today_noon
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_conversion_formula import MaterialConversionFormula
from app.models.material_kg_profile import MaterialKgProfile
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.purchase import Purchase
from app.models.fleet import Driver, Vehicle
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.schemas.inbound_order import (
    PURCHASE_INBOUND_TYPES,
    WILLARD_INBOUND_TYPES,
    InboundLiquidateRequest,
    InboundOrderCreate,
    InboundOrderUpdate,
)
from app.schemas.inventory_adjustment import DecreaseCreate, IncreaseCreate
from app.schemas.purchase import PurchaseCreate, PurchaseFullUpdate, PurchaseLineCreate
from app.services.inventory_costing import incorporate_into_pool, remove_from_pool
from app.services.material_cost_history import material_cost_history_service
from app.utils.org_settings import get_org_setting

# D1/CC-004: el ruteo de la cuenta kg es POR LINEA segun willard_world del
# material (no por un tipo de encabezado). El inbound_type solo distingue
# willard (efectos propios) de purchase (deriva compra).
KG_SOURCE_BY_WORLD = {
    "postconsumo": "postconsumo_receipt",
    "drosses": "drosses_receipt",
}

WORLD_LABELS = {
    "postconsumo": "Postconsumo baterias",
    "drosses": "Drosses",
}


def _err(detail: str, code: int = status.HTTP_422_UNPROCESSABLE_ENTITY):
    return HTTPException(status_code=code, detail=detail)


class InboundOrderService:
    # ------------------------------------------------------------------ #
    # Create                                                              #
    # ------------------------------------------------------------------ #
    def create(
        self,
        db: Session,
        obj_in: InboundOrderCreate,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        warehouse = self._validate_warehouse(db, obj_in.warehouse_id, organization_id)
        is_willard = obj_in.inbound_type in WILLARD_INBOUND_TYPES

        # #93 D1: tipo compra se captura SIN proveedor (nadie sabe todavia de
        # quien es el material); willard lo sigue exigiendo (titular cuenta kg)
        if is_willard:
            if obj_in.third_party_id is None:
                raise _err("Una recepcion Willard requiere el tercero titular de la cuenta kg")
            self._validate_third_party(db, obj_in.third_party_id, organization_id)
        elif obj_in.third_party_id is not None:
            raise _err(
                "La Entrada no registra proveedor — el proveedor se asigna al "
                "liquidar, en el reparto (#93)"
            )
        if obj_in.driver_id is not None:
            self._validate_org(db, Driver, obj_in.driver_id, organization_id, "Conductor")
        if obj_in.vehicle_id is not None:
            self._validate_org(db, Vehicle, obj_in.vehicle_id, organization_id, "Vehiculo")

        # Ciclo D: recolector en AMBOS tipos (en willard es informativo — la
        # comision solo nace al liquidar compras regulares, correccion Daniel)
        if obj_in.collector_id is not None:
            self._validate_collector(db, obj_in.collector_id, organization_id)

        # D12: centro de distribucion Willard — pertenencia contra settings
        if obj_in.willard_distribution_center is not None:
            if not is_willard:
                raise _err("willard_distribution_center solo aplica a tipos Willard")
            valid_centers = get_org_setting(
                db, organization_id, "willard_distribution_centers"
            ) or []
            if obj_in.willard_distribution_center not in valid_centers:
                raise _err(
                    f"Centro de distribucion '{obj_in.willard_distribution_center}' no "
                    f"configurado — validos: {', '.join(valid_centers)}"
                )

        # #93 D12: la factura llega con la liquidacion, POR PROVEEDOR — en la
        # captura tipo compra no hay donde colgarla (explicito > silencioso)
        if not is_willard and obj_in.invoice_number is not None:
            raise _err(
                "La factura se registra al liquidar, por proveedor (en el "
                "reparto). En la captura use la remision del camion."
            )

        order = InboundOrder(
            organization_id=organization_id,
            order_number=self._generate_order_number(db, organization_id),
            inbound_type=obj_in.inbound_type,
            warehouse_id=obj_in.warehouse_id,
            third_party_id=obj_in.third_party_id,
            date=obj_in.date,
            driver_id=obj_in.driver_id,
            vehicle_id=obj_in.vehicle_id,
            collector_id=obj_in.collector_id,
            willard_distribution_center=obj_in.willard_distribution_center,
            # goes_directly_to_jm retirado de la superficie (Ciclo B B4, Q-03) —
            # la columna queda inerte con su server_default
            notes=obj_in.notes,
            invoice_number=obj_in.invoice_number if is_willard else None,
            remission_number=obj_in.remission_number,  # D12: remision del camion
            # #93 D4: AMBOS tipos nacen "Registrada" (draft) — cero efectos.
            # Willard: draft -> confirmed (B.2). Compra: draft -> reviewed ->
            # liquidated (el proveedor y los efectos llegan al liquidar, D9/D14)
            status="draft",
            created_by=user_id,
        )
        db.add(order)
        db.flush()

        warnings: list[str] = []
        if is_willard:
            # B.2: capturar != confirmar — el draft valida TODO (fail-fast para
            # David: un draft no puede nacer roto) pero NO mueve nada; los
            # efectos (inventario D2 + kg D5 + MCH H1a) nacen al confirmar
            self._validate_willard_capture(
                db, organization_id, obj_in.warehouse_id,
                obj_in.third_party_id, obj_in.lines,
            )
            self._persist_mirror_lines(db, order, obj_in.lines, organization_id)
        else:
            # #93 D9: CERO efectos — solo el documento fisico. Validaciones
            # fail-fast: material activo, willard-puro no entra por compra (B3),
            # cantidad > 0... salvo que D16 permita 0? No: la cantidad 0 nace
            # SOLO en la liquidacion (truncamiento); una captura con 0 es error.
            seen_materials: set[UUID] = set()
            for l in obj_in.lines:
                material = self._validate_material(db, l.material_id, organization_id)
                if l.quantity <= 0:
                    raise _err(
                        f"La cantidad pesada de {material.code} debe ser mayor a 0 "
                        "(las lineas de truncamiento nacen en la liquidacion)"
                    )
                if l.material_id in seen_materials:
                    raise _err(
                        f"El material {material.code} aparece en mas de una linea — "
                        "una fila por material (D3)"
                    )
                seen_materials.add(l.material_id)
            from app.services.purchase import purchase as purchase_service
            purchase_service._guard_willard_pure_materials(
                db, organization_id, [l.material_id for l in obj_in.lines]
            )
            self._persist_mirror_lines(db, order, obj_in.lines, organization_id)

        db.commit()
        db.refresh(order)
        return order, warnings

    def _persist_mirror_lines(
        self, db: Session, order: InboundOrder, lines_in, organization_id: UUID
    ) -> None:
        """Lineas espejo del documento de captura — SIN unit_cost (el snapshot
        D8 nace al confirmar, cuando _apply_willard_effects las recrea)."""
        for l in lines_in:
            material = db.get(Material, l.material_id)
            db.add(
                InboundOrderLine(
                    organization_id=organization_id,
                    inbound_order_id=order.id,
                    material_id=l.material_id,
                    quantity=l.quantity,
                    unit=material.default_unit or "kg",
                    unit_price=l.unit_price,
                    scale_weight_kg=l.scale_weight_kg,
                    quality_notes=l.quality_notes,
                )
            )

    # ------------------------------------------------------------------ #
    # #93 — Revisar (D10), Liquidar (D14/D21) y Desliquidar (D20)         #
    # ------------------------------------------------------------------ #
    def review(
        self,
        db: Session,
        order_id: UUID,
        organization_id: UUID,
        user_id: UUID,
    ) -> InboundOrder:
        """draft -> reviewed: alguien con purchases.review certifico las
        cantidades pesadas. En tipo compra habilita liquidar (criterio 2/3);
        en Willard habilita confirmar (Q-16 — Hugo pidio que Willard pase por
        los mismos pasos; en la reunion del 12-ago se le habia respondido que
        ya era asi y NO lo era, Willard iba draft -> confirmed directo, #81).

        Es el punto UNICO donde el peso de bascula se vuelve obligatorio
        (Q-13): opcional al capturar para no trabar al pesador, exigido aca
        porque el revisor es justo quien certifica lo pesado."""
        order = self._get_or_404(db, order_id, organization_id)
        if order.status != "draft":
            labels = {"reviewed": "ya esta revisada", "liquidated": "ya esta liquidada",
                      "confirmed": "ya esta confirmada", "annulled": "esta anulada"}
            raise _err(
                f"No se puede revisar: la entrada {labels.get(order.status, order.status)}",
                status.HTTP_400_BAD_REQUEST,
            )
        self._require_scale_weights(db, order)
        order.status = "reviewed"
        order.reviewed_by = user_id
        order.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)
        return order

    def _require_scale_weights(self, db: Session, order: InboundOrder) -> None:
        """Q-13: el peso de bascula es obligatorio AL REVISAR, en ambos tipos.

        D2: si el material YA se mide en kg, el peso ES la cantidad — se
        autocompleta en vez de pedirlo dos veces (exigir ambos seria friccion
        pura). Se persiste, no se deriva al vuelo: el informe de peso promedio
        (la carta con la que Hugo renegocia el 5,2 kg/unidad con Willard) lee
        la columna, no reconstruye."""
        if not order.lines:
            raise _err(
                "La entrada no tiene lineas — no hay nada que revisar",
                status.HTTP_400_BAD_REQUEST,
            )
        materials = {
            m.id: m
            for m in db.execute(
                select(Material).where(
                    Material.id.in_([l.material_id for l in order.lines])
                )
            ).scalars()
        }
        faltantes: list[str] = []
        for line in order.lines:
            if line.scale_weight_kg is not None and line.scale_weight_kg > 0:
                continue
            material = materials.get(line.material_id)
            unit = (material.default_unit or "").strip().lower() if material else ""
            if unit == "kg":
                line.scale_weight_kg = line.quantity
                continue
            faltantes.append(material.code if material else str(line.material_id))
        if faltantes:
            raise _err(
                "Falta el peso de bascula en: " + ", ".join(sorted(faltantes))
                + ". La revision certifica lo pesado — sin el peso no se puede revisar.",
                status.HTTP_400_BAD_REQUEST,
            )

    @staticmethod
    def _decertify_if_reviewed(order: InboundOrder) -> Optional[str]:
        """D17: editar las LINEAS de una entrada revisada la devuelve a
        Registrada. El revisor certifico pesos y cantidades, que son lineas;
        dejarla revisada permitiria certificar y despues cambiar justo lo
        certificado. La CABECERA (factura, nota, vehiculo, fecha) NO
        des-certifica — no toca lo que el revisor miro. La distincion no es
        invento: el set bloqueado de #93 D7b ya trata las lineas como el
        contenido sensible."""
        if order.status != "reviewed":
            return None
        order.status = "draft"
        order.reviewed_by = None
        order.reviewed_at = None
        return (
            "La entrada volvio a Registrada porque cambiaron sus lineas — "
            "hay que revisarla de nuevo"
        )

    # Escala del peso prorrateado: la columna es Numeric(15,3) — gramos, la
    # misma que ALLOC_Q usa para la cantidad. Cuantizar aca y no al persistir
    # es lo que hace que el total calculado y el peso guardado sean coherentes
    # entre si (si se guardara el peso sin cuantizar, el documento diria un
    # numero y la multiplicacion daria otro).
    _WEIGHT_Q = Decimal("0.001")

    @staticmethod
    def _total_desde_kg(db: Session, material_id, alloc, order_line):
        """Modo por kg -> (total_price, peso_prorrateado).

        El estimador es **kg por unidad de la LINEA**, no una proporcion del
        total repartido:

            estimador = linea.scale_weight_kg / linea.quantity
            peso      = estimador x asignacion.quantity
            total     = peso x price_per_kg

        El denominador es `linea.quantity` (lo pesado) y NO la suma de las
        asignaciones, porque eso es lo que hace que **cada asignacion sea
        independiente de las demas**: con la suma, agregar un segundo proveedor
        cambiaria en silencio el pago del primero, que ya tiene su compra y su
        factura. Como efecto derivado, un sobre-reparto (12 unidades repartidas
        sobre 10 pesadas) conserva el peso estimado por unidad -> 120 kg, en vez
        de apretar 12 unidades dentro de los 100 kg pesados, que volveria al
        precio por kg una cosa distinta de lo que dice.
        """
        def _falta(motivo: str):
            material = db.get(Material, material_id)
            code = material.code if material else material_id
            return _err(
                f"No se puede liquidar {code} por precio por kg: {motivo}. "
                f"Use precio unitario o valor total."
            )

        # Los DOS guards, y el del denominador es el honesto: no se pueden
        # estimar kg por unidad sin unidades. Hoy los dos casos coinciden (las
        # lineas de truncamiento #93 D5 nacen con quantity=0 y peso NULL porque
        # se crean DESPUES de la revision, o sea que nunca pasan por
        # _require_scale_weights), pero eso es una propiedad del ORDEN del
        # flujo, no un invariante — y un guard que descansa en el orden se
        # rompe el dia que alguien lo cambia.
        if order_line is None or not order_line.quantity:
            raise _falta("no tiene cantidad pesada (se agrego en la liquidacion)")
        if not order_line.scale_weight_kg:
            raise _falta("no tiene peso de bascula")

        estimador = Decimal(str(order_line.scale_weight_kg)) / Decimal(str(order_line.quantity))
        peso = (estimador * alloc.quantity).quantize(InboundOrderService._WEIGHT_Q)
        if peso <= 0:
            raise _falta("el peso prorrateado queda en 0 al redondear a gramos")
        return (peso * alloc.price_per_kg), peso


    def liquidate(
        self,
        db: Session,
        order_id: UUID,
        payload: InboundLiquidateRequest,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        """Liquidacion ATOMICA de la Entrada (D14): reparto -> N compras
        liquidadas + ajustes de descuadre + comision del recolector, en UNA
        transaccion — falla la compra 7 de 13 => ninguna queda (criterio 27).

        D21 — un solo reloj para todo el evento: liquidated_at de las N
        compras, date de los ajustes, date de la comision y transaction_date
        de todos los MCH llevan business_today(); las compras nacen con
        date = fecha de la Entrada (su unico vinculo con el dia de captura).

        Re-liquidacion (tras unliquidate): sincroniza las compras registradas
        existentes con el reparto nuevo — mismo proveedor con las mismas
        lineas se reusa tal cual; con lineas distintas se edita
        (revert-and-reapply de registrada, #8); proveedor removido se cancela
        (from_inbound); proveedor nuevo se crea. Firma cuantizada a la escala
        de la BD (leccion #89: '100.0000' != '100' sin quantize).
        """
        order = self._get_or_404(db, order_id, organization_id)
        if order.inbound_type in WILLARD_INBOUND_TYPES:
            raise _err(
                "Una recepcion Willard no se liquida — se confirma",
                status.HTTP_400_BAD_REQUEST,
            )
        if order.status == "draft":
            raise _err(
                "La entrada esta registrada — revisela primero (confirmar "
                "cantidades habilita liquidar)",
                status.HTTP_400_BAD_REQUEST,
            )
        if order.status == "liquidated":
            raise _err("La entrada ya esta liquidada", status.HTTP_400_BAD_REQUEST)
        if order.status == "annulled":
            raise _err("La entrada esta anulada", status.HTTP_400_BAD_REQUEST)

        from app.services.inventory_adjustment import inventory_adjustment
        from app.services.purchase import purchase as purchase_service

        QTY_Q = Decimal("0.0001")   # escala Numeric(15,4) de la BD
        PRICE_Q = Decimal("0.01")   # escala Numeric(15,2)
        # Escala REAL del reparto: al inventario entra la cantidad de
        # purchase_lines, que es Numeric(10,3). La asignacion permitia 4
        # decimales, asi que la identidad "pesado = repartido + descuadre" se
        # rompia hasta 0,0005 kg por asignacion SIN NINGUN AVISO. Con pesos en
        # kg (Q-13) dejo de ser hipotetico.
        ALLOC_Q = Decimal("0.001")

        # El mapa se arma aca (y no en la fase de validacion, donde estaba)
        # porque el modo por kg necesita el peso y la cantidad de la linea para
        # prorratear ANTES de que exista un unit_price.
        lines_by_material = {l.material_id: l for l in order.lines}

        # Peso prorrateado de cada asignacion liquidada por kg — se persiste
        # junto al price_per_kg (es un INSUMO del documento, no un cache).
        pesos_prorrateados: dict[tuple, Decimal] = {}

        # ---------- Normalizacion del reparto (ANTES de cualquier calculo) ----
        # Que la cantidad y el precio que se validan, se persisten, se comparan
        # en la firma de re-liquidacion y llegan al inventario sean el MISMO
        # numero. Hacerlo aca y no en cada consumidor es lo que hace la
        # identidad exacta por construccion en vez de por vigilancia.
        for pl in payload.lines:
            for a in pl.allocations:
                a.quantity = a.quantity.quantize(ALLOC_Q)
                # El schema exige > 0, pero eso es ANTES de cuantizar: 0,0004
                # pasa el Field y queda en 0,000. Sin esta guarda la division
                # de abajo revienta con un 500 en vez de explicar.
                if a.quantity <= 0:
                    material = db.get(Material, pl.material_id)
                    code = material.code if material else pl.material_id
                    raise _err(
                        f"La cantidad repartida de {code} es demasiado pequena: "
                        f"queda en 0 al redondear a gramos"
                    )
                if a.price_per_kg is not None:
                    # Modo por kg: se resuelve a total_price y DESEMBOCA en la
                    # rama de abajo — un solo camino hacia unit_price, asi que
                    # la firma de re-liquidacion (#93) ve el mismo numero.
                    #
                    # El peso derivado NO se puede colgar del payload (schema
                    # con extra="forbid"), asi que viaja en un mapa con clave de
                    # negocio: el material aparece una sola vez en el reparto
                    # (D3) y la asignacion es unica por (linea, tercero).
                    total, peso = self._total_desde_kg(
                        db, pl.material_id, a, lines_by_material.get(pl.material_id)
                    )
                    a.total_price = total
                    pesos_prorrateados[(pl.material_id, a.third_party_id)] = peso

                if a.total_price is not None:
                    # Q-15: el unitario es una formula — "costo total dividido
                    # unidades" (Hugo). Se cuantiza a PRICE_Q para que la firma
                    # de #93 vea el mismo numero y no dispare un
                    # revert-and-reapply innecesario en cada re-liquidacion.
                    a.unit_price = (a.total_price / a.quantity).quantize(PRICE_Q)
                    if a.unit_price <= 0:
                        material = db.get(Material, pl.material_id)
                        code = material.code if material else pl.material_id
                        raise _err(
                            f"El valor total de {code} es demasiado bajo para la "
                            f"cantidad repartida: el precio unitario queda en $0"
                        )

        # ---------- Fase de validacion COMPLETA (criterio 15: fallar ANTES ----
        # de escribir nada, no a mitad de las compras) ----------
        payload_materials: set = set()
        new_material_lines: list = []
        plan: list[dict] = []  # [{line(payload), order_line|None, material, disc}]

        for pl in payload.lines:
            if pl.material_id in payload_materials:
                material = db.get(Material, pl.material_id)
                code = material.code if material else pl.material_id
                raise _err(f"El material {code} aparece dos veces en el reparto")
            payload_materials.add(pl.material_id)

            order_line = lines_by_material.get(pl.material_id)
            if order_line is None:
                # D16/criterio 14: material repartido que la bascula no vio —
                # nace una linea con cantidad pesada 0
                material = self._validate_material(db, pl.material_id, organization_id)
                purchase_service._guard_willard_pure_materials(
                    db, organization_id, [pl.material_id]
                )
                if not pl.allocations:
                    raise _err(
                        f"El material {material.code} no esta en la entrada y no "
                        "trae asignaciones — no hay nada que liquidar"
                    )
                new_material_lines.append((pl, material))
                weighed = Decimal("0")
            else:
                material = order_line.material or db.get(Material, pl.material_id)
                weighed = order_line.quantity

            allocated = sum((a.quantity for a in pl.allocations), Decimal("0"))
            disc = (weighed - allocated).quantize(QTY_Q)

            # D8: se bloquea la AUSENCIA de intencion, no el monto
            if not pl.allocations and not pl.unallocated_intentional:
                raise _err(
                    f"La linea de {material.code} no tiene ninguna asignacion — "
                    "reparta la cantidad o marquela explicitamente como sin "
                    "proveedor (unallocated_intentional)"
                )
            # D16: descuadre != 0 exige precio de referencia (> 0), ANTES de
            # empezar — un 422 a mitad dejaria compras ya aplicadas sin D14
            if disc != 0 and pl.reference_unit_price is None:
                raise _err(
                    f"La linea de {material.code} queda con descuadre "
                    f"({disc:+}) y no trae precio de referencia — es "
                    "obligatorio para valorar el descuadre (D6)"
                )
            # Proveedor duplicado en la misma linea (UNIQUE en BD — 422 legible)
            seen_tp: set = set()
            for a in pl.allocations:
                if a.third_party_id in seen_tp:
                    raise _err(
                        f"El mismo proveedor aparece dos veces en la linea de "
                        f"{material.code} — consolide las cantidades"
                    )
                seen_tp.add(a.third_party_id)

            plan.append({
                "payload": pl, "order_line": order_line,
                "material": material, "disc": disc, "weighed": weighed,
            })

        # Completitud (D14 "todo de una"): toda linea de la entrada debe venir
        # en el reparto — una olvidada seria un descuadre del 100% en silencio
        missing = [
            l.material.code if l.material else str(l.material_id)
            for l in order.lines
            if l.material_id not in payload_materials
        ]
        if missing:
            raise _err(
                f"El reparto no incluye lineas de la entrada: {', '.join(sorted(missing))} "
                "— la liquidacion es de una sola vez (todas las lineas)"
            )

        # Validar proveedores (activos, org) — material_supplier lo exige
        # purchase.create; aca el fail-fast con nombre
        supplier_ids = {
            a.third_party_id for item in plan for a in item["payload"].allocations
        }
        for tp_id in supplier_ids:
            self._validate_third_party(db, tp_id, organization_id)

        # El titular de una cuenta kg NO puede ser proveedor del reparto (#80
        # addendum: "lo Willard nunca es compra", Q-04). La exclusion vivia en
        # el selector de la captura; al mudarse el proveedor a la liquidacion
        # (#93) se quedo sin dueño — esta es la defensa, no la cortesia de UI.
        # El MATERIAL si puede venir por compra si esta marcado compra_regular:
        # lo exclusivo por canal es el TERCERO, no la referencia.
        kg_holders = set(db.execute(
            select(KgLedgerAccount.third_party_id).where(
                KgLedgerAccount.organization_id == organization_id,
                KgLedgerAccount.third_party_id.in_(supplier_ids),
                KgLedgerAccount.is_active.is_(True),
            )
        ).scalars().all())
        if kg_holders:
            names = ", ".join(sorted(
                (db.get(ThirdParty, h).name or str(h)) for h in kg_holders
            ))
            raise _err(
                f"{names} es titular de una cuenta kg — su material entra como "
                "recepcion Willard, no como compra. Reparta a otro proveedor."
            )

        # Addendum retenciones (QA #93): bloques OPCIONALES por proveedor —
        # cada bloque debe apuntar a un proveedor DEL reparto (fail-fast con
        # nombre) y sin duplicar proveedor. El tope Σret < total de la compra
        # lo valida _apply_retentions donde siempre vivio (#79) — un 422 tardio
        # es seguro: D14 hace rollback total (criterio 27).
        retentions_by_supplier: dict = {}
        for block in (payload.supplier_retentions or []):
            if block.third_party_id not in supplier_ids:
                tp = db.get(ThirdParty, block.third_party_id)
                name = tp.name if tp else str(block.third_party_id)
                raise _err(
                    f"Retenciones para {name}, que no esta en el reparto — "
                    "las retenciones son por proveedor asignado"
                )
            if block.third_party_id in retentions_by_supplier:
                raise _err(
                    "El mismo proveedor aparece dos veces en "
                    "supplier_retentions — consolide sus retenciones en un bloque"
                )
            retentions_by_supplier[block.third_party_id] = block.retentions

        # Pago de contado por proveedor (pruebas de usuario 2026-08-11) —
        # misma forma que las retenciones: opcional, del reparto, sin duplicar.
        # La cuenta se valida aca para fallar ANTES de escribir; el monto lo
        # pone purchase.liquidate (el NETO), nunca este payload.
        payment_by_supplier: dict = {}
        for pay in (payload.supplier_payments or []):
            if pay.third_party_id not in supplier_ids:
                tp = db.get(ThirdParty, pay.third_party_id)
                name = tp.name if tp else str(pay.third_party_id)
                raise _err(
                    f"Pago de contado para {name}, que no esta en el reparto"
                )
            if pay.third_party_id in payment_by_supplier:
                raise _err(
                    "El mismo proveedor aparece dos veces en supplier_payments"
                )
            account = db.get(MoneyAccount, pay.account_id)
            if not account or account.organization_id != organization_id:
                raise _err("Cuenta de dinero no encontrada", status.HTTP_404_NOT_FOUND)
            if not account.is_active:
                raise _err(f"La cuenta '{account.name}' esta inactiva")
            payment_by_supplier[pay.third_party_id] = pay.account_id

        # ---------- Escritura (una transaccion, commit unico al final) ----------
        warnings: list[str] = []
        liq_dt = business_today_noon()  # D21: el dia del evento, una sola vez

        # 1. Lineas nuevas (truncamiento) + reparto persistido en las lineas
        for pl, material in new_material_lines:
            line = InboundOrderLine(
                organization_id=organization_id,
                inbound_order_id=order.id,
                material_id=pl.material_id,
                quantity=Decimal("0"),
                unit=material.default_unit or "kg",
            )
            db.add(line)
            db.flush()
            order.lines.append(line)
            for item in plan:
                if item["payload"] is pl:
                    item["order_line"] = line

        # Re-liquidacion: borrar reparto anterior (se conserva solo hasta que
        # Johana confirma el nuevo — el payload ES el reparto completo)
        line_ids = [l.id for l in order.lines]
        if line_ids:
            db.query(InboundLineAllocation).filter(
                InboundLineAllocation.inbound_line_id.in_(line_ids)
            ).delete(synchronize_session=False)
            db.flush()

        for item in plan:
            order_line = item["order_line"]
            pl = item["payload"]
            order_line.reference_unit_price = pl.reference_unit_price
            order_line.unallocated_intentional = pl.unallocated_intentional
            for a in pl.allocations:
                db.add(InboundLineAllocation(
                    organization_id=organization_id,
                    inbound_line_id=order_line.id,
                    third_party_id=a.third_party_id,
                    quantity=a.quantity,
                    unit_price=a.unit_price,
                    # Q-15: el MODO es parte del reparto — sin persistirlo, el
                    # round-trip de D20 devolveria el unitario derivado y
                    # Johana veria otra cosa de la que guardo
                    total_price=a.total_price,
                    # Modo por kg: los INSUMOS con los que se calculo. El peso
                    # sale del mapa y no se re-deriva aca, para que lo guardado
                    # sea exactamente lo que se uso.
                    price_per_kg=a.price_per_kg,
                    weight_kg_used=pesos_prorrateados.get(
                        (pl.material_id, a.third_party_id)
                    ),
                    invoice_number=a.invoice_number,
                ))
        db.flush()

        # 2. Agrupar por proveedor -> sincronizar/crear las N compras
        groups: dict = {}
        for item in plan:
            for a in item["payload"].allocations:
                groups.setdefault(a.third_party_id, []).append((item["material"], a))

        existing = self._linked_purchases(db, organization_id, order.id)
        live_by_supplier: dict = {}
        for p in existing:
            if p.status == "registered":
                live_by_supplier[p.supplier_id] = p
            elif p.status == "liquidated":
                # No debe pasar (unliquidate las devolvio a registered) —
                # defensa dura antes que corromper el reparto
                raise _err(
                    f"La compra #{p.purchase_number} sigue liquidada — estado "
                    "inconsistente, desliquide la entrada primero",
                    status.HTTP_409_CONFLICT,
                )

        vehicle_plate = order.vehicle.plate if order.vehicle else None

        def group_signature(allocs):
            return sorted(
                (str(m.id), a.quantity.quantize(QTY_Q), a.unit_price.quantize(PRICE_Q))
                for m, a in allocs
            )

        def purchase_signature(p):
            return sorted(
                (str(l.material_id), l.quantity.quantize(QTY_Q), l.unit_price.quantize(PRICE_Q))
                for l in p.lines
            )

        purchases_to_liquidate: list = []
        for tp_id, allocs in groups.items():
            invoice = next((a.invoice_number for _m, a in allocs if a.invoice_number), None)
            existing_p = live_by_supplier.pop(tp_id, None)
            if existing_p is not None:
                if group_signature(allocs) != purchase_signature(existing_p):
                    upd = PurchaseFullUpdate(
                        invoice_number=invoice,
                        lines=[
                            PurchaseLineCreate(
                                material_id=m.id,
                                warehouse_id=order.warehouse_id,
                                quantity=a.quantity,
                                unit_price=a.unit_price,
                            )
                            for m, a in allocs
                        ],
                    )
                    existing_p, u_warnings = purchase_service.update(
                        db, existing_p.id, upd, organization_id,
                        user_id=user_id, commit=False,
                    )
                    warnings.extend(u_warnings)
                elif invoice is not None:
                    existing_p.invoice_number = invoice
                purchases_to_liquidate.append(existing_p)
            else:
                purchase_in = PurchaseCreate(
                    supplier_id=tp_id,
                    date=order.date,  # D21: nace con la fecha del documento
                    warehouse_id=order.warehouse_id,
                    vehicle_plate=vehicle_plate,
                    invoice_number=invoice,
                    lines=[
                        PurchaseLineCreate(
                            material_id=m.id,
                            warehouse_id=order.warehouse_id,
                            quantity=a.quantity,
                            unit_price=a.unit_price,
                        )
                        for m, a in allocs
                    ],
                )
                new_p, c_warnings = purchase_service.create(
                    db, obj_in=purchase_in, organization_id=organization_id,
                    user_id=user_id, commit=False,
                )
                warnings.extend(c_warnings)
                db.add(InboundOrderPurchase(
                    organization_id=organization_id,
                    inbound_order_id=order.id,
                    purchase_id=new_p.id,
                ))
                purchases_to_liquidate.append(new_p)
        db.flush()

        # Proveedor que salio del reparto en la re-liquidacion: su registrada
        # se cancela (from_inbound — el guard D14 bloquea el cancel directo)
        for leftover in live_by_supplier.values():
            _, x_warnings = purchase_service.cancel(
                db, purchase_id=leftover.id, organization_id=organization_id,
                user_id=user_id, commit=False, from_inbound=True,
            )
            warnings.extend(x_warnings)
            warnings.append(
                f"La compra #{leftover.purchase_number} salio del reparto y se cancelo"
            )

        # 3. Liquidar las N compras (consecutivas, D21: liquidated_at = HOY).
        # Retenciones del proveedor (si las hay) entran por el MISMO camino de
        # #79: proveedor acreditado neto, entidad [Retenciones] X con el pasivo
        for p in purchases_to_liquidate:
            pay_account = payment_by_supplier.get(p.supplier_id)
            # Candado anti doble pago: revertir la liquidacion NO anula el pago
            # enlazado — queda como anticipo (#16/#63, "Liquidacion != Pago"),
            # asi que re-liquidar marcando contado otra vez pagaria dos veces.
            # Un 422 aca es seguro: D14 hace rollback total (criterio 27).
            if pay_account is not None:
                already = purchase_service.get_linked_payment_total(
                    db, p.id, organization_id
                )
                if already and already > 0:
                    supplier = db.get(ThirdParty, p.supplier_id)
                    raise _err(
                        f"La compra de {supplier.name if supplier else 'este proveedor'} "
                        f"ya tiene un pago vivo de ${already:,.0f} (quedo como anticipo "
                        "al revertir). Liquide sin pago de contado, o anule ese "
                        "movimiento en Tesoreria primero."
                    )
            purchase_service.liquidate(
                db, purchase_id=p.id, organization_id=organization_id,
                user_id=user_id, liquidation_date=liq_dt, commit=False,
                retentions_data=retentions_by_supplier.get(p.supplier_id),
                immediate_payment=pay_account is not None,
                payment_account_id=pay_account,
            )

        # 4. Descuadres — SIEMPRE despues de las N compras (requisito de orden
        # D7: el pool ya alimentado decide la rama limpia) + tolerancia D8
        tolerance = Decimal(str(
            get_org_setting(db, organization_id, "inbound_discrepancy_tolerance_pct")
        ))
        for item in plan:
            disc = item["disc"]
            if disc == 0:
                continue  # criterio 9: descuadre cero -> ningun ajuste
            material = item["material"]
            order_line = item["order_line"]
            ref_price = order_line.reference_unit_price
            reason = f"Descuadre de entrada #{order.order_number}"
            if disc > 0:
                adj, a_warnings = inventory_adjustment.increase(
                    db,
                    IncreaseCreate(
                        material_id=material.id,
                        warehouse_id=order.warehouse_id,
                        date=liq_dt,  # D21
                        quantity=disc,
                        unit_cost=ref_price,
                        reason=reason,
                    ),
                    organization_id, user_id=user_id, commit=False,
                )
            else:
                adj, a_warnings = inventory_adjustment.decrease(
                    db,
                    DecreaseCreate(
                        material_id=material.id,
                        warehouse_id=order.warehouse_id,
                        date=liq_dt,  # D21
                        quantity=-disc,
                        reason=reason,
                    ),
                    organization_id, user_id=user_id, commit=False,
                    unit_cost_override=ref_price,  # D6/D7: nunca el promedio
                )
            adj.inbound_order_id = order.id  # D7 marcado (guard D17)
            warnings.extend(a_warnings)

            # D8: dentro de tolerancia aviso, fuera resaltado — nunca bloqueo
            weighed = item["weighed"]
            kind = "sobrante" if disc > 0 else "faltante"
            # `:g` sobre Decimal NO quita los ceros de escala (Numeric(15,4)
            # imprime "10.0000"); normalize() sí, y `:f` evita la notación
            # cientifica que normalize() introduce en enteros grandes
            qty_txt = f"{abs(disc).normalize():f}"
            unit = material.default_unit or "kg"
            if weighed > 0:
                pct = abs(disc) / weighed
                marker = "dentro de" if pct <= tolerance else "FUERA de"
                warnings.append(
                    f"Descuadre en {material.code}: {kind} de {qty_txt} {unit} "
                    f"({pct:.1%}, {marker} tolerancia) valorado a ${ref_price}"
                )
            else:
                warnings.append(
                    f"Descuadre en {material.code}: {kind} de {qty_txt} {unit} "
                    "(material no pesado en la entrada) valorado a "
                    f"${ref_price}"
                )

        # 5. Comision del recolector (D11): UNA por entrada, gasto causado
        if payload.collector_commission is not None:
            self._apply_entrada_collector_commission(
                db, order, payload.collector_commission, organization_id,
                user_id, liq_dt,
            )

        order.status = "liquidated"
        # Hora REAL del clic (auditoria, NO frontera de corte — esa es liq_dt,
        # el dia de negocio). Es un instante puro, por eso now(utc) y no el
        # reloj de negocio (#91: la guarda solo prohibe derivar un DIA de aqui)
        order.liquidated_ts = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)
        return order, warnings

    def unliquidate(
        self,
        db: Session,
        order_id: UUID,
        organization_id: UUID,
        user_id: UUID,
        commit: bool = True,
    ) -> tuple[InboundOrder, list[str]]:
        """D20: revierte las N compras (helper compartido — vuelven a
        'registered' con su transito, sin quemar consecutivos), anula los
        ajustes de descuadre (round-trip exacto W-1) y la comision, y devuelve
        la entrada a 'revisada' CONSERVANDO el reparto. NUNCA bloquea (#76,
        criterio 23)."""
        order = self._get_or_404(db, order_id, organization_id)
        if order.inbound_type in WILLARD_INBOUND_TYPES:
            raise _err(
                "Una recepcion Willard no se desliquida — anulela",
                status.HTTP_400_BAD_REQUEST,
            )
        if order.status != "liquidated":
            raise _err(
                "Solo se desliquida una entrada liquidada",
                status.HTTP_400_BAD_REQUEST,
            )

        warnings = self._revert_entrada_liquidation(db, order, organization_id, user_id)
        order.status = "reviewed"
        order.liquidated_ts = None  # se re-estampa al re-liquidar

        if commit:
            db.commit()
            db.refresh(order)
        else:
            db.flush()
        return order, warnings

    def _revert_entrada_liquidation(
        self, db: Session, order: InboundOrder, organization_id: UUID, user_id: UUID
    ) -> list[str]:
        """Reversa del evento de liquidacion (compartida por unliquidate y por
        el annul de una entrada liquidada — D14 fix 3). Sin commit."""
        from app.services.inventory_adjustment import inventory_adjustment
        from app.services.purchase import purchase as purchase_service

        warnings: list[str] = []

        # 1. Desliquidar las N compras (residual de hueco -> header, precedente
        # micro-gap E2: entra al P&L solo si la orden se anula despues)
        total_residual = Decimal("0")
        for p in self._linked_purchases(db, organization_id, order.id):
            if p.status != "liquidated":
                continue
            _, residual, p_warnings = purchase_service.unliquidate(
                db, purchase_id=p.id, organization_id=organization_id,
                user_id=user_id, commit=False,
            )
            total_residual += residual
            warnings.extend(p_warnings)
        if total_residual != 0:
            order.annul_cost_adjustment += total_residual
            warnings.append(
                f"La reversa dejo una diferencia de costo de ${total_residual} "
                "(pool en hueco) — se reconocera en P&L al anular la entrada"
            )

        # 2. Anular ajustes de descuadre (guard D17 exige from_module)
        adjustments = db.scalars(
            select(InventoryAdjustment).where(
                InventoryAdjustment.organization_id == organization_id,
                InventoryAdjustment.inbound_order_id == order.id,
                InventoryAdjustment.status == "confirmed",
            )
        ).all()
        for adj in adjustments:
            inventory_adjustment.annul(
                db, adj.id,
                f"Reversa liquidacion entrada #{order.order_number}",
                organization_id, user_id=user_id, commit=False, from_module=True,
            )

        # 3. Anular la comision de recolector POR ENTRADA (source_id = orden,
        # purchase_id NULL — las purchase-level legacy ya las anulo el helper
        # de cada compra; filtro confirmed evita doble anulacion)
        accruals = db.scalars(
            select(MoneyMovement).where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_type == "expense_accrual",
                MoneyMovement.source_type == "collector_commission",
                MoneyMovement.source_id == order.id,
                MoneyMovement.status == "confirmed",
            )
        ).all()
        for mov in accruals:
            mov.status = "annulled"
            mov.annulled_at = datetime.now(timezone.utc)
            mov.annulled_by = user_id
            mov.annulled_reason = f"Reversa liquidacion entrada #{order.order_number}"
            if mov.third_party_id:
                collector_tp = db.get(ThirdParty, mov.third_party_id)
                if collector_tp:
                    collector_tp.current_balance += mov.amount

        return warnings

    def _apply_entrada_collector_commission(
        self, db: Session, order: InboundOrder, cc, organization_id: UUID,
        user_id: UUID, liq_dt,
    ) -> None:
        """D11: comision del recolector UNA vez por entrada (no 13 por camion,
        #83 la causaba dentro de purchase.liquidate). Sigue siendo GASTO
        causado (expense_accrual, jamas prorrateo #30). Base = lo PESADO
        (respuesta 16) — el monto lo trae el payload (la UI sugiere tarifa x
        base con la regla de los 14 kg/unidad y el editado es la verdad F1)."""
        from app.services.purchase import purchase as purchase_service
        from app.services.money_movement import money_movement as mm_service
        from app.services.third_party import third_party as tp_service
        from app.models.service_tariff import ServiceTariff

        collector = db.get(ThirdParty, cc.third_party_id)
        if not collector or collector.organization_id != organization_id or not collector.is_active:
            raise _err("Recolector no encontrado", status.HTTP_404_NOT_FOUND)
        if not tp_service.has_behavior_type(db, collector.id, ["service_provider"]):
            raise _err(
                "El recolector debe tener una categoria con comportamiento "
                "'Proveedor de Servicios' (recibe comisiones)"
            )

        category = purchase_service._get_or_create_collector_category(db, organization_id)
        tariff_id = db.execute(
            select(ServiceTariff.id)
            .where(
                ServiceTariff.organization_id == organization_id,
                ServiceTariff.tariff_code == "comision_green_loop",
            )
            .order_by(ServiceTariff.created_at.desc(), ServiceTariff.id.desc())
            .limit(1)
        ).scalar_one_or_none()

        mm_service._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="expense_accrual",
            amount=cc.amount,
            account_id=None,
            date=liq_dt,  # D21: el dia de la liquidacion
            description=f"Comisión recolección Entrada #{order.order_number}",
            user_id=user_id,
            third_party_id=collector.id,
            expense_category_id=category.id,
            source_type="collector_commission",
            source_id=order.id,
            tariff_id=tariff_id,
            warehouse_id=order.warehouse_id,
        )
        collector.current_balance -= cc.amount

    def _linked_purchases(
        self, db: Session, organization_id: UUID, order_id: UUID
    ) -> list:
        """Compras de la entrada via PUENTE, con lineas cargadas. R2: jamas un
        join en el listado — esto es lookup puntual por orden."""
        from app.models.purchase import PurchaseLine
        return list(db.execute(
            select(Purchase)
            .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
            .options(
                joinedload(Purchase.lines).joinedload(PurchaseLine.material),
                joinedload(Purchase.supplier),
            )
            .where(
                InboundOrderPurchase.inbound_order_id == order_id,
                Purchase.organization_id == organization_id,
            )
            .order_by(Purchase.purchase_number)
        ).unique().scalars().all())

    # ------------------------------------------------------------------ #
    # Confirmar recepcion Willard (B.2) — los efectos nacen aca           #
    # ------------------------------------------------------------------ #
    def confirm(
        self,
        db: Session,
        order_id: UUID,
        organization_id: UUID,
        user_id: UUID,
    ) -> InboundOrder:
        """Reviewed -> confirmed: borra las lineas y re-aplica via
        _apply_willard_effects (el MISMO camino de efectos del 1-paso previo:
        inventario a identidad D2 + kg ledger D5 + MCH hoy H1a + snapshot de
        formula/avg AL CONFIRMAR — si la formula cambio desde la captura,
        aplica la vigente, #35).

        Q-16: el paso previo pasa de `draft` a `reviewed` — Willard ahora se
        revisa como la compra. Los efectos son byte a byte los mismos; lo
        unico que cambia es de que estado se sale."""
        order = self._get_or_404(db, order_id, organization_id)
        if order.inbound_type not in WILLARD_INBOUND_TYPES:
            raise _err(
                "Una entrada tipo compra no se confirma — revisela y liquidela "
                "con el reparto de proveedores (#93)",
                status.HTTP_400_BAD_REQUEST,
            )
        if order.status == "annulled":
            raise _err(
                "La recepcion esta anulada", status.HTTP_400_BAD_REQUEST
            )
        if order.status == "confirmed":
            raise _err(
                "La recepcion ya esta confirmada", status.HTTP_400_BAD_REQUEST
            )
        if order.status != "reviewed":
            raise _err(
                "Revise la recepcion antes de confirmarla — el revisor certifica "
                "las cantidades pesadas (Q-16)",
                status.HTTP_400_BAD_REQUEST,
            )

        # Re-validar lo que pudo cambiar entre captura y confirmacion
        self._validate_warehouse(db, order.warehouse_id, organization_id)
        self._validate_third_party(db, order.third_party_id, organization_id)

        # Reconstruir lines_in desde las lineas draft persistidas (patron D18)
        lines_in = [
            SimpleNamespace(
                material_id=l.material_id,
                quantity=l.quantity,
                unit_price=l.unit_price,
                scale_weight_kg=l.scale_weight_kg,
                quality_notes=l.quality_notes,
            )
            for l in order.lines
        ]
        # Borrar las draft — _apply_willard_effects las recrea con unit_cost
        db.query(InboundOrderLine).filter(
            InboundOrderLine.inbound_order_id == order.id
        ).delete(synchronize_session=False)
        db.flush()

        self._apply_willard_effects(db, order, lines_in, organization_id, user_id)
        order.status = "confirmed"
        # La pantalla muestra el MISMO verbo ("Liquidar") en los dos tipos, asi
        # que el instante real del clic tiene que existir en ambos: sin esto la
        # Willard mostraba "Liquidada por Johana · 13/08/2026" sin hora y la
        # compra sí. `liquidated_at` es fecha de negocio y no la lleva (#87).
        order.liquidated_ts = datetime.now(timezone.utc)
        db.commit()
        db.refresh(order)
        return order

    # ------------------------------------------------------------------ #
    # Validacion de captura Willard (B.2) — camino UNICO                  #
    # ------------------------------------------------------------------ #
    def _validate_willard_capture(
        self,
        db: Session,
        organization_id: UUID,
        warehouse_id: UUID,
        third_party_id: UUID,
        lines_in,
    ) -> tuple[dict, dict, dict]:
        """Validaciones Willard — corren al CAPTURAR (fail-fast: un draft no
        puede nacer roto) y al CONFIRMAR (via _apply_willard_effects, que las
        consume — B.2 W2: una sola implementacion, cero divergencia).

        Retorna (worlds, formulas, account_by_world) para que apply no
        re-consulte.
        """
        material_ids = [l.material_id for l in lines_in]
        worlds = self._load_kg_worlds(db, organization_id, material_ids)

        # Ciclo B (B2): homogeneidad de mundo — una recepcion Willard es de UN
        # solo mundo; camion mixto = DOS recepciones (Q-10, decision Daniel).
        real_worlds = {
            w for w in (worlds.get(mid) for mid in material_ids)
            if w and w != "none"
        }
        if len(real_worlds) > 1:
            raise _err(
                "Una recepcion Willard es de un solo mundo (drosses o postconsumo) "
                "— separe el camion en dos recepciones"
            )

        # Ciclo B (B2): drosses van SIEMPRE a la planta (Q-03/Q-05). Solo valida
        # si la org configuro willard_sede_drosses (None = compat, no valida).
        if real_worlds == {"drosses"}:
            jm_id = get_org_setting(db, organization_id, "willard_sede_drosses")
            if jm_id is not None and str(warehouse_id) != str(jm_id):
                jm_wh = db.get(Warehouse, UUID(str(jm_id)))
                jm_name = jm_wh.name if jm_wh else "la bodega configurada"
                raise _err(
                    f"Los drosses se reciben en la planta ({jm_name}) — "
                    "seleccione esa bodega"
                )

        # Cache de cuenta kg por mundo (la sede de baterias es fija: warehouse_id)
        account_by_world: dict[str, KgLedgerAccount] = {}

        # Ciclo B addendum (feedback Daniel): el tercero de una recepcion
        # Willard ES el titular de la cuenta kg (fijo en UI; aca defensa) —
        # la cuenta esta amarrada a su tercero por CHECK del modelo
        if real_worlds:
            world0 = next(iter(real_worlds))
            account0 = self._resolve_kg_account_for_world(
                db, organization_id, world0, warehouse_id
            )
            account_by_world[world0] = account0
            if account0.third_party_id and third_party_id != account0.third_party_id:
                titular = db.get(ThirdParty, account0.third_party_id)
                raise _err(
                    "El tercero de una recepcion Willard es el titular de la "
                    f"cuenta kg ({titular.name if titular else 'configurado en la cuenta'})"
                )

        formulas = self._load_current_formulas(db, organization_id, material_ids)

        # Per-linea: material activo, mundo Willard, formula vigente
        seen_materials: set = set()
        for line_in in lines_in:
            material = self._validate_material(db, line_in.material_id, organization_id)
            # #93: el schema relajo quantity a ge=0 (truncamiento D16, solo
            # tipo compra) — willard sigue exigiendo > 0 (un kg movement de 0
            # violaria el CHECK delta_kg != 0)
            if line_in.quantity <= 0:
                raise _err(f"La cantidad de {material.code} debe ser mayor a 0")
            # #93 D3: una fila por material (UNIQUE en BD — aca el 422 legible)
            if line_in.material_id in seen_materials:
                raise _err(
                    f"El material {material.code} aparece en mas de una linea — "
                    "una fila por material"
                )
            seen_materials.add(line_in.material_id)
            world = worlds.get(line_in.material_id)
            # D1/CC-004: el mundo del material rutea la cuenta kg. Un material
            # sin clasificacion Willard se recibe como Compra regular.
            if world is None or world == "none":
                raise _err(
                    f"El material {material.code} no es de mundo Willard "
                    "(postconsumo/drosses) — clasifiquelo en el maestro de materiales "
                    "o recibalo como Compra regular"
                )
            if world not in account_by_world:
                account_by_world[world] = self._resolve_kg_account_for_world(
                    db, organization_id, world, warehouse_id
                )
            if formulas.get(line_in.material_id) is None:
                raise _err(
                    f"No hay formula de conversion vigente para {material.code} — "
                    "creela primero en el maestro de materiales"
                )

        return worlds, formulas, account_by_world

    # ------------------------------------------------------------------ #
    # Efectos Willard (confirm B.2 + re-apply de edicion D18)             #
    # ------------------------------------------------------------------ #
    def _apply_willard_effects(
        self,
        db: Session,
        order: InboundOrder,
        lines_in,
        organization_id: UUID,
        user_id: UUID,
    ) -> None:
        # B.2 (W2): la validacion es el MISMO camino que la captura — aca se
        # re-valida (formula/cuenta/material pueden cambiar entre captura y
        # confirmacion) y se consumen los datos cargados
        worlds, formulas, account_by_world = self._validate_willard_capture(
            db, organization_id, order.warehouse_id, order.third_party_id, lines_in
        )
        today = business_today()

        for line_in in lines_in:
            material = self._validate_material(db, line_in.material_id, organization_id)
            qty = Decimal(str(line_in.quantity))
            world = worlds[line_in.material_id]
            account = account_by_world[world]
            kg_source = KG_SOURCE_BY_WORLD[world]
            label = WORLD_LABELS[world]
            formula = formulas[line_in.material_id]
            delta_kg = self._compute_kg_lead(formula, qty)

            # D2: entrada a identidad — adjustment 0 y avg intacto por construccion
            old_liq = material.current_stock_liquidated
            avg = material.current_average_cost
            new_avg, _adj = incorporate_into_pool(
                liquidated=old_liq, avg_cost=avg, quantity=qty, unit_cost=avg
            )
            material.current_average_cost = new_avg
            material.current_stock_liquidated = old_liq + qty
            material.current_stock += qty

            line = InboundOrderLine(
                organization_id=organization_id,
                inbound_order_id=order.id,
                material_id=line_in.material_id,
                quantity=qty,
                unit=material.default_unit or "kg",
                unit_price=line_in.unit_price,
                unit_cost=avg.quantize(Decimal("0.01")),  # snapshot D8
                scale_weight_kg=line_in.scale_weight_kg,
                quality_notes=line_in.quality_notes,
            )
            db.add(line)

            movement = InventoryMovement(
                organization_id=organization_id,
                material_id=line_in.material_id,
                warehouse_id=order.warehouse_id,
                movement_type="inbound_receipt",
                quantity=qty,
                unit_cost=avg.quantize(Decimal("0.01")),  # espejo del snapshot D8
                reference_type="inbound",
                reference_id=order.id,
                date=order.date,  # la CANTIDAD si vive en la fecha de negocio (D4)
                notes=f"Recepcion {label} #{order.order_number}",
            )
            db.add(movement)
            db.flush()

            # H1a QA: checkpoint del avg al momento de ESCRIBIR (HOY) — nunca
            # backdatear (re-presentaria cortes historicos, doctrina #61)
            material_cost_history_service.record_cost_change(
                db=db,
                material=material,
                previous_cost=avg,
                previous_stock=old_liq,
                new_cost=new_avg,
                new_stock=material.current_stock_liquidated,
                source_type="inbound_receipt",
                source_id=order.id,
                organization_id=organization_id,
                transaction_date=today,
            )

            # D5: un KgLedgerMovement POR LINEA con snapshot de formula propio
            db.add(
                KgLedgerMovement(
                    organization_id=organization_id,
                    account_id=account.id,
                    delta_kg=delta_kg,
                    transaction_date=order.date,
                    description=(
                        f"Recepcion {label} #{order.order_number} — "
                        f"{material.code} x {qty:g} {material.default_unit or 'kg'}"
                    ),
                    source_type=kg_source,
                    source_id=order.id,
                    inventory_movement_id=movement.id,
                    conversion_formula_snapshot={
                        "formula_id": str(formula.id),
                        "formula_type": formula.formula_type,
                        "parameters": formula.parameters,
                    },
                    created_by=user_id,
                    status="confirmed",
                )
            )

    # ------------------------------------------------------------------ #
    # Reversa Willard (annul + revert de edicion D18)                     #
    # ------------------------------------------------------------------ #
    def _revert_willard_effects(
        self,
        db: Session,
        order: InboundOrder,
        organization_id: UUID,
        user_id: UUID,
        reason: str,
    ) -> tuple[Decimal, list[str]]:
        """Remocion ponderada (#66) al snapshot line.unit_cost + anulacion de
        los kg movements (#48). Retorna (diferencia_total, warnings)."""
        warnings: list[str] = []
        total_adjustment = Decimal("0")
        today = business_today()

        for line in order.lines:
            material = db.get(Material, line.material_id)
            qty = line.quantity
            old_liq = material.current_stock_liquidated
            old_avg = material.current_average_cost

            new_avg, adj = remove_from_pool(
                liquidated=old_liq,
                avg_cost=old_avg,
                quantity=qty,
                unit_cost=line.unit_cost or Decimal("0"),
            )
            material.current_average_cost = new_avg
            material.current_stock_liquidated = old_liq - qty
            material.current_stock -= qty
            total_adjustment += adj

            # MCH SIEMPRE (append-only #66) — HOY (H1a)
            material_cost_history_service.record_cost_change(
                db=db,
                material=material,
                previous_cost=old_avg,
                previous_stock=old_liq,
                new_cost=new_avg,
                new_stock=old_liq - qty,
                source_type="inbound_annulment",
                source_id=order.id,
                organization_id=organization_id,
                transaction_date=today,
            )

            # Reversal backdateado a order.date (doctrina #41: la orden anulada
            # desaparece de TODOS los cortes — receipt y reversal se cancelan)
            db.add(
                InventoryMovement(
                    organization_id=organization_id,
                    material_id=line.material_id,
                    warehouse_id=order.warehouse_id,
                    movement_type="inbound_reversal",
                    quantity=-qty,
                    unit_cost=line.unit_cost or Decimal("0"),
                    reference_type="inbound",
                    reference_id=order.id,
                    date=order.date,
                    notes=f"Reversa recepcion #{order.order_number}: {reason}",
                )
            )

            if material.current_stock_liquidated < 0:
                warnings.append(
                    f"El stock liquidado de {material.code} queda negativo tras la "
                    f"reversa: {float(material.current_stock_liquidated):g} "
                    f"{material.default_unit or 'kg'}"
                )

        # Anular los kg movements de la orden (#48)
        kg_movs = db.execute(
            select(KgLedgerMovement).where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id == order.id,
                KgLedgerMovement.status == "confirmed",
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for mov in kg_movs:
            mov.status = "annulled"
            mov.annulled_reason = reason
            mov.annulled_by = user_id
            mov.annulled_at = now

        return total_adjustment, warnings

    # ------------------------------------------------------------------ #
    # Annul (D8)                                                          #
    # ------------------------------------------------------------------ #
    def annul(
        self,
        db: Session,
        order_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        order = self._get_or_404(db, order_id, organization_id)
        # B.2: draft y confirmed son anulables (draft = solo status, sin reversa)
        if order.status == "annulled":
            raise _err(
                "No se puede anular: la orden ya esta anulada",
                status.HTTP_400_BAD_REQUEST,
            )

        warnings: list[str] = []
        if order.inbound_type in WILLARD_INBOUND_TYPES:
            # B.2: un draft no movio nada — anular es solo status + auditoria
            if order.status == "confirmed":
                total_adj, warnings = self._revert_willard_effects(
                    db, order, organization_id, user_id, reason
                )
                order.annul_cost_adjustment = total_adj
        else:
            # #93 D14 fix 3: anular una entrada LIQUIDADA delega en la reversa
            # del evento (unliquidate de las N + ajustes + comision) y despues
            # cancela las registradas. draft/reviewed: cero efectos que revertir.
            from app.services.purchase import purchase as purchase_service
            if order.status == "liquidated":
                warnings.extend(
                    self._revert_entrada_liquidation(db, order, organization_id, user_id)
                )
            for p in self._linked_purchases(db, organization_id, order.id):
                if p.status == "registered":
                    _, p_warnings = purchase_service.cancel(
                        db,
                        purchase_id=p.id,
                        organization_id=organization_id,
                        user_id=user_id,
                        commit=False,
                        from_inbound=True,
                    )
                    warnings.extend(p_warnings)

        order.status = "annulled"
        order.annulled_reason = reason
        order.annulled_at = datetime.now(timezone.utc)
        order.annulled_by = user_id

        db.commit()
        db.refresh(order)
        return order, warnings

    # ------------------------------------------------------------------ #
    # Update (D18)                                                        #
    # ------------------------------------------------------------------ #
    def update(
        self,
        db: Session,
        order_id: UUID,
        obj_in: InboundOrderUpdate,
        organization_id: UUID,
        user_id: UUID,
    ) -> tuple[InboundOrder, list[str]]:
        order = self._get_or_404(db, order_id, organization_id)
        if order.status == "annulled":
            # D18: anuladas no se editan — como si no existieran para el PATCH
            raise _err("Orden no encontrada", status.HTTP_404_NOT_FOUND)

        is_willard = order.inbound_type in WILLARD_INBOUND_TYPES
        fields_set = obj_in.model_dump(exclude_unset=True)

        if not is_willard:
            # #93: la captura ES la fuente de verdad — lineas y fecha editables
            # mientras no este liquidada (draft/reviewed: cero efectos que
            # revertir, D9; respuesta 4: "ajustar la cantidad pesada y liquidar").
            # Liquidada: solo cabecera cosmetica — el reparto/compras ya
            # existen; para tocar cantidades hay que desliquidar (D20).
            if order.status == "liquidated":
                blocked = {"lines", "date", "willard_distribution_center"}
                offending = blocked & set(fields_set.keys())
                if offending:
                    raise _err(
                        f"La entrada esta liquidada — {', '.join(sorted(offending))} "
                        "exige revertir la liquidacion primero"
                    )
            elif "willard_distribution_center" in fields_set and obj_in.willard_distribution_center is not None:
                raise _err("willard_distribution_center solo aplica a tipos Willard")
        else:
            if obj_in.willard_distribution_center is not None:
                valid_centers = get_org_setting(
                    db, organization_id, "willard_distribution_centers"
                ) or []
                if obj_in.willard_distribution_center not in valid_centers:
                    raise _err(
                        f"Centro de distribucion '{obj_in.willard_distribution_center}' "
                        f"no configurado — validos: {', '.join(valid_centers)}"
                    )

        if obj_in.driver_id is not None:
            self._validate_org(db, Driver, obj_in.driver_id, organization_id, "Conductor")
        if obj_in.vehicle_id is not None:
            self._validate_org(db, Vehicle, obj_in.vehicle_id, organization_id, "Vehiculo")

        # Ciclo D: collector_id editable (incl. None explicito para quitarlo)
        # en ambos tipos. En willard es informativo (sin efectos) — editable
        # siempre. En tipo compra se congela al LIQUIDAR (#93): la comision ya
        # se causo (el MM existe); cambiarlo seria cosmetico/engañoso.
        if "collector_id" in fields_set:
            if not is_willard and order.status == "liquidated":
                raise _err(
                    "La entrada ya esta liquidada — la comision de recoleccion "
                    "ya se definio; el recolector no se puede cambiar"
                )
            if obj_in.collector_id is not None:
                self._validate_collector(db, obj_in.collector_id, organization_id)
            order.collector_id = obj_in.collector_id

        warnings: list[str] = []

        # #93: edicion de lineas/fecha en tipo compra (draft/reviewed) —
        # reemplazo simple del espejo, CERO efectos que revertir (D9). El
        # reparto no existe todavia (o quedo de un unliquidate: al borrar las
        # lineas cae en cascada — Johana re-reparte al liquidar de nuevo).
        if not is_willard and {"lines", "date"} & set(fields_set.keys()):
            if obj_in.date is not None:
                order.date = obj_in.date
            if obj_in.lines is not None:
                from app.services.purchase import purchase as purchase_service
                seen_materials: set = set()
                for l in obj_in.lines:
                    material = self._validate_material(db, l.material_id, organization_id)
                    if l.quantity <= 0:
                        raise _err(
                            f"La cantidad pesada de {material.code} debe ser mayor a 0"
                        )
                    if l.material_id in seen_materials:
                        raise _err(
                            f"El material {material.code} aparece en mas de una "
                            "linea — una fila por material (D3)"
                        )
                    seen_materials.add(l.material_id)
                purchase_service._guard_willard_pure_materials(
                    db, organization_id, [l.material_id for l in obj_in.lines]
                )
                db.query(InboundOrderLine).filter(
                    InboundOrderLine.inbound_order_id == order.id
                ).delete(synchronize_session=False)
                db.flush()
                self._persist_mirror_lines(db, order, obj_in.lines, organization_id)
                decert = self._decertify_if_reviewed(order)  # D17
                if decert:
                    warnings.append(decert)

        # Revert-and-reapply Willard cuando cambian lineas o fecha
        # (la fecha mueve los eventos kg e inventario) — SOLO confirmadas;
        # un draft (B.2) no tiene efectos que revertir
        willard_body_changed = is_willard and bool(
            {"lines", "date"} & set(fields_set.keys())
        )
        needs_reapply = willard_body_changed and order.status == "confirmed"
        if willard_body_changed and not needs_reapply:
            # B.2: edicion simple del draft — validar la captura nueva y
            # reemplazar las lineas espejo, cero movimientos
            if obj_in.date is not None:
                order.date = obj_in.date
            if obj_in.lines is not None:
                self._validate_willard_capture(
                    db, organization_id, order.warehouse_id,
                    order.third_party_id, obj_in.lines,
                )
                db.query(InboundOrderLine).filter(
                    InboundOrderLine.inbound_order_id == order.id
                ).delete(synchronize_session=False)
                db.flush()
                self._persist_mirror_lines(db, order, obj_in.lines, organization_id)
                decert = self._decertify_if_reviewed(order)  # D17
                if decert:
                    warnings.append(decert)
        if needs_reapply:
            old_lines = [
                SimpleNamespace(
                    material_id=l.material_id,
                    quantity=l.quantity,
                    unit_price=l.unit_price,
                    scale_weight_kg=l.scale_weight_kg,
                    quality_notes=l.quality_notes,
                )
                for l in order.lines
            ]
            revert_adj, rev_warnings = self._revert_willard_effects(
                db, order, organization_id, user_id,
                reason=f"Edicion de orden #{order.order_number}",
            )
            warnings.extend(rev_warnings)
            if revert_adj != 0:
                # Micro-gap documentado (informe E2): la diferencia se conserva
                # en el header y entra al P&L solo si la orden se anula despues
                order.annul_cost_adjustment += revert_adj
                warnings.append(
                    f"La edicion dejo una diferencia de costo de ${revert_adj} "
                    "(pool negativo al editar) — se reconocera en P&L al anular la orden"
                )

            # Borrar lineas viejas y re-aplicar (nuevo avg de entrada, HOY)
            db.query(InboundOrderLine).filter(
                InboundOrderLine.inbound_order_id == order.id
            ).delete(synchronize_session=False)
            db.flush()

            if obj_in.date is not None:
                order.date = obj_in.date

            new_lines = obj_in.lines if obj_in.lines is not None else old_lines
            self._apply_willard_effects(db, order, new_lines, organization_id, user_id)

        # Cabecera sin efectos
        # `fields_set` (no `is not None`): distingue ausente de null explicito —
        # antes de este ciclo driver/vehiculo usaban `is not None` y por eso NO
        # se podian QUITAR de una entrada. Alineados al patron de notes.
        if "driver_id" in fields_set:
            order.driver_id = obj_in.driver_id
        if "vehicle_id" in fields_set:
            order.vehicle_id = obj_in.vehicle_id
            # E (#87e, extendido a 1:N en #93): las compras guardan la PLACA
            # (no el FK) y el listado de Compras filtra y muestra por ella.
            # Sin guard de estado: una compra liquidada con la placa
            # equivocada es justo el caso a corregir, cero efecto financiero.
            new_plate = (
                db.get(Vehicle, obj_in.vehicle_id).plate
                if obj_in.vehicle_id is not None
                else None
            )
            for p in self._linked_purchases(db, organization_id, order.id):
                if p.status != "cancelled":
                    p.vehicle_plate = new_plate
        if obj_in.willard_distribution_center is not None:
            order.willard_distribution_center = obj_in.willard_distribution_center
        if "notes" in fields_set:
            # None explicito borra la nota (exclude_unset distingue ausente de null)
            order.notes = obj_in.notes
        if "remission_number" in fields_set:
            # #93 D12: remision del camion — dato de referencia (criterio notes)
            order.remission_number = obj_in.remission_number
        if "invoice_number" in fields_set:
            # Willard: columna propia. Legacy 1:1: la compra derivada. Tipo
            # compra #93: la factura vive POR PROVEEDOR en el reparto → 422.
            if is_willard:
                order.invoice_number = obj_in.invoice_number
            elif order.purchase is not None:
                order.purchase.invoice_number = obj_in.invoice_number
            else:
                raise _err(
                    "La factura vive en el reparto, por proveedor — editela al "
                    "liquidar (o en la compra del proveedor correspondiente)"
                )

        db.commit()
        db.refresh(order)
        return order, warnings

    # ------------------------------------------------------------------ #
    # Lectura                                                             #
    # ------------------------------------------------------------------ #
    def get(self, db: Session, order_id: UUID, organization_id: UUID) -> InboundOrder:
        return self._get_or_404(db, order_id, organization_id)

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        inbound_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        display_status: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = "newest",
        willard_world: Optional[str] = None,
        warehouse_id: Optional[UUID] = None,
        third_party_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[InboundOrder], int]:
        q = select(InboundOrder).where(InboundOrder.organization_id == organization_id)
        if inbound_type:
            q = q.where(InboundOrder.inbound_type == inbound_type)
        if status_filter:
            q = q.where(InboundOrder.status == status_filter)

        # #93 D4: el estado es COLUMNA — el espejo SQL con outerjoin(Purchase)
        # del Ciclo C murio con la derivacion. Mapeo trivial display -> status
        # (paridad con display_status_of por construccion, sin join 1:N).
        if display_status:
            status_map = {
                "registered": ["draft"],
                "reviewed": ["reviewed"],
                "liquidated": ["liquidated", "confirmed"],  # confirmed = willard
                "annulled": ["annulled"],
            }
            q = q.where(
                InboundOrder.status.in_(status_map.get(display_status, [display_status]))
            )

        # Ciclo C (C-2): buscador — #, placa, conductor, tercero, material,
        # factura, remision (#93). 🔴 Trampa 1:N (R2): PROHIBIDO joinear
        # Purchase o allocations aca — una entrada de 13 proveedores saldria
        # 13 veces. Todo lo 1:N va por EXISTS. Y el join a ThirdParty de
        # cabecera pasa a OUTER: la cabecera es nullable desde #93 — un join
        # duro haria DESAPARECER en silencio toda entrada tipo compra.
        if search and search.strip():
            from sqlalchemy.orm import aliased
            like = f"%{search.strip()}%"
            material_match = (
                select(InboundOrderLine.id)
                .join(Material, InboundOrderLine.material_id == Material.id)
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    or_(Material.code.ilike(like), Material.name.ilike(like)),
                )
                .exists()
            )
            # Facturas: via PUENTE (cubre legacy 1:1 backfilleado y las N del
            # reparto — la compra hereda la primera factura del proveedor)
            purchase_invoice_match = (
                select(Purchase.id)
                .join(
                    InboundOrderPurchase,
                    InboundOrderPurchase.purchase_id == Purchase.id,
                )
                .where(
                    InboundOrderPurchase.inbound_order_id == InboundOrder.id,
                    Purchase.invoice_number.ilike(like),
                )
                .exists()
            )
            # Proveedores y facturas del reparto (#93) — alias del ThirdParty
            # de cabecera para no chocar con el outerjoin de afuera
            TPAlloc = aliased(ThirdParty)
            alloc_match = (
                select(InboundLineAllocation.id)
                .join(
                    InboundOrderLine,
                    InboundLineAllocation.inbound_line_id == InboundOrderLine.id,
                )
                .join(TPAlloc, InboundLineAllocation.third_party_id == TPAlloc.id)
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    or_(
                        TPAlloc.name.ilike(like),
                        InboundLineAllocation.invoice_number.ilike(like),
                    ),
                )
                .exists()
            )
            q = (
                q.outerjoin(Driver, InboundOrder.driver_id == Driver.id)
                .outerjoin(Vehicle, InboundOrder.vehicle_id == Vehicle.id)
                .outerjoin(ThirdParty, InboundOrder.third_party_id == ThirdParty.id)
                .where(
                    or_(
                        cast(InboundOrder.order_number, SAString).ilike(like),
                        Vehicle.plate.ilike(like),
                        Driver.name.ilike(like),
                        ThirdParty.name.ilike(like),   # willard (cabecera)
                        material_match,
                        InboundOrder.invoice_number.ilike(like),   # willard
                        InboundOrder.remission_number.ilike(like),  # D12
                        purchase_invoice_match,
                        alloc_match,                    # reparto (#93)
                    )
                )
            )

        # Ciclo C (filtros pruebas Daniel): mundo willard — EXISTS sobre lineas
        # con perfil de ese mundo. Restringido a tipo willard: un material
        # "ambos canales" (Q-04, world+compra_regular) NO debe traer compras.
        if willard_world:
            world_match = (
                select(InboundOrderLine.id)
                .join(
                    MaterialKgProfile,
                    InboundOrderLine.material_id == MaterialKgProfile.material_id,
                )
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    MaterialKgProfile.organization_id == organization_id,
                    MaterialKgProfile.willard_world == willard_world,
                )
                .exists()
            )
            q = q.where(
                InboundOrder.inbound_type.in_(WILLARD_INBOUND_TYPES), world_match
            )
        if warehouse_id:
            q = q.where(InboundOrder.warehouse_id == warehouse_id)
        if third_party_id:
            # #93: el proveedor vive en el reparto (tipo compra) O en la
            # cabecera (willard) — EXISTS, jamas join (R2)
            alloc_tp_match = (
                select(InboundLineAllocation.id)
                .join(
                    InboundOrderLine,
                    InboundLineAllocation.inbound_line_id == InboundOrderLine.id,
                )
                .where(
                    InboundOrderLine.inbound_order_id == InboundOrder.id,
                    InboundLineAllocation.third_party_id == third_party_id,
                )
                .exists()
            )
            q = q.where(
                or_(InboundOrder.third_party_id == third_party_id, alloc_tp_match)
            )
        if date_from:
            q = q.where(InboundOrder.date >= date_from)
        if date_to:
            q = q.where(InboundOrder.date <= date_to)

        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        # Ciclo C (C-3): oldest = FIFO para la bandeja de Johana
        order_clause = (
            InboundOrder.created_at.asc()
            if sort == "oldest"
            else InboundOrder.order_number.desc()
        )
        orders = db.execute(
            q.options(
                joinedload(InboundOrder.lines).joinedload(InboundOrderLine.material),
                joinedload(InboundOrder.lines)
                .joinedload(InboundOrderLine.allocations)
                .joinedload(InboundLineAllocation.third_party),
                joinedload(InboundOrder.warehouse),
                joinedload(InboundOrder.third_party),
                joinedload(InboundOrder.collector),
                joinedload(InboundOrder.driver),
                joinedload(InboundOrder.vehicle),
                joinedload(InboundOrder.purchase),
            )
            .order_by(order_clause)
            .offset(skip)
            .limit(limit)
        ).unique().scalars().all()
        return list(orders), total

    @staticmethod
    def display_status_of(order: InboundOrder) -> str:
        """#93 D4: estado UNICO visible, COLUMNA-driven — el espejo derivado
        de Ciclo C murio (el estado ya no se deriva de las compras). Paridad
        con el status_map de get_multi por construccion."""
        if order.status == "annulled":
            return "annulled"
        if order.status == "draft":
            return "registered"
        if order.status == "reviewed":
            return "reviewed"
        # liquidated (compra) | confirmed (willard) | legacy edge
        return "liquidated"

    def willard_confirm_audit(
        self, db: Session, organization_id: UUID, order_ids: list[UUID]
    ) -> dict[UUID, tuple[UUID, datetime]]:
        """Ciclo C (C-5): quien liquido una willard = created_by del primer
        KgLedgerMovement confirmado (decision de auditoria B.2)."""
        if not order_ids:
            return {}
        rows = db.execute(
            select(
                KgLedgerMovement.source_id,
                KgLedgerMovement.created_by,
                KgLedgerMovement.created_at,
            )
            .where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id.in_(order_ids),
                KgLedgerMovement.status == "confirmed",
            )
            .order_by(KgLedgerMovement.created_at.asc())
        ).all()
        audit: dict[UUID, tuple[UUID, datetime]] = {}
        for source_id, created_by, created_at in rows:
            audit.setdefault(source_id, (created_by, created_at))
        return audit

    def willard_worlds_by_order(
        self, db: Session, organization_id: UUID, orders: list[InboundOrder]
    ) -> dict[UUID, str]:
        """Ciclo C (C-4): mundo de la orden willard (homogeneo por construccion
        B2) — perfil del material de la primera linea. 1 query por pagina."""
        material_ids = {
            line.material_id
            for o in orders
            if o.inbound_type in WILLARD_INBOUND_TYPES
            for line in o.lines
        }
        if not material_ids:
            return {}
        rows = db.execute(
            select(MaterialKgProfile.material_id, MaterialKgProfile.willard_world).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(material_ids),
            )
        ).all()
        world_by_material = {mid: w for mid, w in rows if w and w != "none"}
        result: dict[UUID, str] = {}
        for o in orders:
            if o.inbound_type not in WILLARD_INBOUND_TYPES:
                continue
            for line in o.lines:
                world = world_by_material.get(line.material_id)
                if world:
                    result[o.id] = world
                    break
        return result

    def purchases_by_order(
        self, db: Session, organization_id: UUID, order_ids: list[UUID]
    ) -> dict[UUID, list]:
        """#93: compras por entrada via PUENTE — lookup por pagina (patron #87
        B1, R2: cero joins en el listado, cero N+1). Incluye canceladas (el
        display decide como mostrarlas)."""
        if not order_ids:
            return {}
        rows = db.execute(
            select(InboundOrderPurchase.inbound_order_id, Purchase)
            .join(Purchase, InboundOrderPurchase.purchase_id == Purchase.id)
            # retentions: 1 query extra por PAGINA (selectin), no por fila —
            # alimenta retentions_total del summary (addendum retenciones #93)
            .options(joinedload(Purchase.supplier), selectinload(Purchase.retentions))
            .where(
                InboundOrderPurchase.inbound_order_id.in_(order_ids),
                Purchase.organization_id == organization_id,
            )
            .order_by(Purchase.purchase_number)
        ).unique().all()
        result: dict[UUID, list] = {}
        for oid, p in rows:
            result.setdefault(oid, []).append(p)
        return result

    def discrepancy_adjustments(
        self, db: Session, organization_id: UUID, order_id: UUID
    ) -> list:
        """#93 D7: los ajustes de descuadre de UNA entrada, para el detalle.

        Los ajustes ya se marcan con inbound_order_id al liquidar (guard D17);
        aca solo se leen. `total_value` es |qty| x costo, asi que el signo lo
        pone el tipo: increase = ganancia (+), decrease = perdida (−)."""
        from app.schemas.inbound_order import InboundDiscrepancyAdjustment

        rows = db.execute(
            select(InventoryAdjustment)
            .options(joinedload(InventoryAdjustment.material))
            .where(
                InventoryAdjustment.inbound_order_id == order_id,
                InventoryAdjustment.organization_id == organization_id,
            )
            .order_by(InventoryAdjustment.adjustment_number)
        ).unique().scalars().all()
        out = []
        for a in rows:
            signed = a.total_value if a.adjustment_type == "increase" else -a.total_value
            out.append(InboundDiscrepancyAdjustment(
                adjustment_id=a.id,
                adjustment_number=a.adjustment_number,
                material_id=a.material_id,
                material_code=a.material.code if a.material else None,
                material_unit=(a.material.default_unit or "kg") if a.material else "kg",
                adjustment_type=a.adjustment_type,
                quantity=abs(a.quantity),
                unit_cost=a.unit_cost,
                total_value=signed,
                status=a.status,
            ))
        return out

    def kg_deltas_by_movement(
        self, db: Session, organization_id: UUID, order_ids: list[UUID]
    ) -> dict[UUID, Decimal]:
        """Mapa inventory_movement_id -> delta_kg (confirmed) para enriquecer lineas."""
        if not order_ids:
            return {}
        rows = db.execute(
            select(
                KgLedgerMovement.inventory_movement_id,
                KgLedgerMovement.delta_kg,
            ).where(
                KgLedgerMovement.organization_id == organization_id,
                KgLedgerMovement.source_id.in_(order_ids),
                KgLedgerMovement.status == "confirmed",
                KgLedgerMovement.inventory_movement_id.is_not(None),
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    def receipt_movements(
        self, db: Session, organization_id: UUID, order_id: UUID
    ) -> list[InventoryMovement]:
        """Movimientos inbound_receipt vivos de la orden, en orden de creacion
        (paralelo a lines por construccion — mismo loop)."""
        return list(db.execute(
            select(InventoryMovement).where(
                InventoryMovement.organization_id == organization_id,
                InventoryMovement.reference_type == "inbound",
                InventoryMovement.reference_id == order_id,
                InventoryMovement.movement_type == "inbound_receipt",
            ).order_by(InventoryMovement.created_at)
        ).scalars().all())

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _get_or_404(self, db: Session, order_id: UUID, organization_id: UUID) -> InboundOrder:
        order = db.execute(
            select(InboundOrder)
            .options(
                joinedload(InboundOrder.lines).joinedload(InboundOrderLine.material),
                joinedload(InboundOrder.lines)
                .joinedload(InboundOrderLine.allocations)
                .joinedload(InboundLineAllocation.third_party),
                joinedload(InboundOrder.warehouse),
                joinedload(InboundOrder.third_party),
                joinedload(InboundOrder.collector),
                joinedload(InboundOrder.driver),
                joinedload(InboundOrder.vehicle),
                joinedload(InboundOrder.purchase),
            )
            .where(
                InboundOrder.id == order_id,
                InboundOrder.organization_id == organization_id,
            )
        ).unique().scalar_one_or_none()
        if order is None:
            raise _err("Orden no encontrada", status.HTTP_404_NOT_FOUND)
        return order

    def _resolve_kg_account_for_world(
        self, db: Session, organization_id: UUID, world: str, warehouse_id: UUID
    ) -> KgLedgerAccount:
        """D1: postconsumo -> (willard_baterias, sede); drosses ->
        (willard_drosses, org-wide)."""
        if world == "postconsumo":
            acc_type, wh_filter = "willard_baterias", warehouse_id
        else:  # drosses
            acc_type, wh_filter = "willard_drosses", None
        q = select(KgLedgerAccount).where(
            KgLedgerAccount.organization_id == organization_id,
            KgLedgerAccount.account_type == acc_type,
            KgLedgerAccount.is_active.is_(True),
            KgLedgerAccount.warehouse_id == wh_filter
            if wh_filter is not None
            else KgLedgerAccount.warehouse_id.is_(None),
        )
        account = db.execute(q).scalar_one_or_none()
        if account is None:
            scope = "para esta sede" if wh_filter is not None else "org-wide"
            raise _err(
                f"No existe cuenta kg activa '{acc_type}' {scope} — "
                "cree primero la cuenta kg en Plomo (kg)"
            )
        return account

    def _load_kg_worlds(
        self, db: Session, organization_id: UUID, material_ids: list[UUID]
    ) -> dict:
        """willard_world por material (los materiales sin perfil no aparecen)."""
        if not material_ids:
            return {}
        rows = db.execute(
            select(
                MaterialKgProfile.material_id, MaterialKgProfile.willard_world
            ).where(
                MaterialKgProfile.organization_id == organization_id,
                MaterialKgProfile.material_id.in_(material_ids),
            )
        ).all()
        return {mid: world for mid, world in rows}

    def _load_current_formulas(
        self, db: Session, organization_id: UUID, material_ids: list[UUID]
    ) -> dict:
        """Formulas vigentes por material — DISTINCT ON con tiebreaker id."""
        rows = db.execute(
            select(MaterialConversionFormula)
            .distinct(MaterialConversionFormula.material_id)
            .where(
                MaterialConversionFormula.organization_id == organization_id,
                MaterialConversionFormula.material_id.in_(material_ids),
            )
            .order_by(
                MaterialConversionFormula.material_id,
                MaterialConversionFormula.created_at.desc(),
                MaterialConversionFormula.id.desc(),
            )
        ).scalars().all()
        return {f.material_id: f for f in rows}

    @staticmethod
    def _compute_kg_lead(formula: MaterialConversionFormula, qty: Decimal) -> Decimal:
        """delta_kg = qty x kg_lead_per_unit (baterias) / kg x lead_percentage
        (drosses). Params viven como numeros JSON -> Decimal(str())."""
        params = formula.parameters or {}
        if formula.formula_type == "battery_to_lead":
            factor = Decimal(str(params["kg_lead_per_unit"]))
        elif formula.formula_type == "drosses_to_lead":
            factor = Decimal(str(params["lead_percentage"]))
        else:
            raise _err(
                f"Tipo de formula '{formula.formula_type}' no soportado en recepcion"
            )
        return (qty * factor).quantize(Decimal("0.0001"))

    def _generate_order_number(self, db: Session, organization_id: UUID) -> int:
        # Advisory lock por org (patron _generate_purchase_number)
        lock_id = hash(str(organization_id)) % (2**63)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        max_number = db.execute(
            select(func.max(InboundOrder.order_number)).where(
                InboundOrder.organization_id == organization_id
            )
        ).scalar_one_or_none()
        return (max_number or 0) + 1

    def _validate_material(self, db: Session, material_id: UUID, organization_id: UUID) -> Material:
        material = db.get(Material, material_id)
        if not material or material.organization_id != organization_id:
            raise _err("Material no encontrado", status.HTTP_404_NOT_FOUND)
        if not material.is_active:
            raise _err(
                f"El material '{material.code}' esta inactivo", status.HTTP_400_BAD_REQUEST
            )
        return material

    def _validate_warehouse(self, db: Session, warehouse_id: UUID, organization_id: UUID) -> Warehouse:
        warehouse = db.get(Warehouse, warehouse_id)
        if not warehouse or warehouse.organization_id != organization_id:
            raise _err("Bodega no encontrada", status.HTTP_404_NOT_FOUND)
        if not warehouse.is_active:
            raise _err("La bodega esta inactiva", status.HTTP_400_BAD_REQUEST)
        # Q-12 (feedback Daniel): las bodegas internas (molino/transito) no
        # reciben de terceros — el frontend las filtra; aca defensa
        if not warehouse.is_receiving:
            raise _err(
                f"La bodega '{warehouse.name}' es interna (no recibe material "
                "de terceros) — marquela como receptora en Configuracion si aplica"
            )
        return warehouse

    def _validate_third_party(self, db: Session, tp_id: UUID, organization_id: UUID) -> ThirdParty:
        tp = db.get(ThirdParty, tp_id)
        if not tp or tp.organization_id != organization_id:
            raise _err("Tercero no encontrado", status.HTTP_404_NOT_FOUND)
        if not tp.is_active:
            raise _err(f"El tercero '{tp.name}' esta inactivo", status.HTTP_400_BAD_REQUEST)
        return tp

    def _validate_collector(
        self, db: Session, collector_id: UUID, organization_id: UUID
    ) -> ThirdParty:
        """Ciclo D (correccion Daniel 2026-07-18): el recolector se REGISTRA en
        AMBOS tipos de entrada — Green Loop tambien recolecta willard (Q-02),
        solo que ahi es informativo: la comision existe UNICAMENTE al liquidar
        compras regulares (por construccion — willard no tiene liquidacion de
        compra). Debe ser service_provider (#32 — si cobra comision, su saldo
        clasifica en pasivos)."""
        tp = self._validate_third_party(db, collector_id, organization_id)
        from app.services.third_party import third_party as tp_service
        if not tp_service.has_behavior_type(db, tp.id, ["service_provider"]):
            raise _err(
                "El recolector debe tener una categoria con comportamiento "
                "'Proveedor de Servicios' (recibe comisiones)"
            )
        return tp

    @staticmethod
    def _validate_org(db: Session, model, obj_id: UUID, organization_id: UUID, label: str):
        obj = db.get(model, obj_id)
        if not obj or obj.organization_id != organization_id:
            raise _err(f"{label} no encontrado", status.HTTP_404_NOT_FOUND)
        return obj


inbound_order_service = InboundOrderService()
