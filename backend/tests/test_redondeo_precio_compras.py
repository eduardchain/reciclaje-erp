"""
El valor total digitado llega exacto a la compra (plan-redondeo-precio-compras.md v1.1).

Johana digito $3.138.450 para 1.503 unidades y la compra nacio en
$3.138.444,36: el unitario se derivaba como total/cantidad con 2 decimales y el
error de ese redondeo se multiplicaba por la cantidad. Con el unitario a 8
decimales (`purchase_lines.unit_price`, `inventory_movements.unit_cost` e
`inbound_line_allocations.unit_price`, migracion `b4c6d8e0f2a5`) el error queda
bajo medio centavo para cualquier cantidad que admite la linea.

Cobertura (§5 del plan): T1–T8. Lo que cada uno tumba bajo un defecto plantado
esta en la matriz del §6.

Notas de lectura:
- Las cifras de negocio se leen por HTTP donde el usuario las ve (T1): un
  assert sobre el ORM en la misma sesion lee el valor EN MEMORIA, antes del
  redondeo de la columna, y no distingue 2 de 8 decimales (C3 de QA).
- En una Entrada la diferencia de la reversa no va a
  `purchases.cancellation_cost_adjustment` sino a
  `inbound_orders.annul_cost_adjustment` (el caller la acumula ahi, #93 D20).
"""
from decimal import Decimal

import pytest

from app.models.inbound_order import InboundOrder
from app.models.material import Material
from app.models.purchase import Purchase
from app.utils.dates import business_today_noon
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)
from tests.test_sac_entrada_sin_proveedor import (
    INBOUND_URL,
    PURCHASES_URL,
    _alloc,
    _captured_reviewed,
    _line,
    _liq_line,
    _liquidate,
    _order_adjustments,
    _order_purchases,
    _set_profile,
)

CENT = Decimal("0.01")
# Error por unidad que deja un unitario a 8 decimales: medio de 1e-8 por
# redondeo, mas la escala del promedio (15,4) que redondea a 0,00005.
AVG_STEP = Decimal("0.00005")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sac(db_session, test_organization):
    """Flag de SAC: solo los tests de Entrada lo piden. T5 y T7 corren SIN el
    flag, como Costa."""
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Bodega Redondeo")
    db_session.commit()
    return w


def _tp(db, org_id, name, behavior="material_supplier"):
    tp = create_third_party_with_category(db, org_id, name, behavior)
    db.commit()
    return tp


@pytest.fixture
def sup1(db_session, test_organization):
    return _tp(db_session, test_organization.id, "Proveedor Redondeo Uno")


@pytest.fixture
def sup2(db_session, test_organization):
    return _tp(db_session, test_organization.id, "Proveedor Redondeo Dos")


@pytest.fixture
def comisionista(db_session, test_organization):
    return _tp(db_session, test_organization.id, "Comisionista Redondeo", "service_provider")


def _mat(db, org_id, code, unit):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


@pytest.fixture
def bat(db_session, test_organization, client, org_headers, sac):
    """Material por UNIDAD, como las baterias de la Entrada de Johana."""
    mat = _mat(db_session, test_organization.id, "BAT-RED", "unidad")
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def chatarra(db_session, test_organization, client, org_headers, sac):
    mat = _mat(db_session, test_organization.id, "CHAT-RED", "kg")
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def mat_costa(db_session, test_organization):
    """Material de una org SIN el flag (compra directa estilo Costa)."""
    return _mat(db_session, test_organization.id, "COSTA-RED", "kg")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _purchase_http(client, headers, purchase_id):
    r = client.get(f"{PURCHASES_URL}/{purchase_id}", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _balance_http(client, headers, tp_id):
    r = client.get(f"/api/v1/third-parties/{tp_id}", headers=headers)
    assert r.status_code == 200, r.text
    return Decimal(str(r.json()["current_balance"]))


def _statement_http(client, headers, tp_id):
    r = client.get(
        f"/api/v1/money-movements/third-party/{tp_id}", headers=headers,
        params={"date_from": "2020-01-01", "limit": 500},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _d(x) -> Decimal:
    return Decimal(str(x))


def _pool(mat: Material) -> Decimal:
    return mat.current_average_cost * mat.current_stock_liquidated


def _fresh(db, model, id_):
    db.expire_all()
    return db.get(model, id_)


def _entrada_por_total(client, headers, wh, mat, qty, total, sup):
    order = _captured_reviewed(client, headers, wh, [_line(mat, qty, weight=qty)])
    _liquidate(client, headers, order["id"],
               [_liq_line(mat, [_alloc(sup, qty, total=total)])])
    return order


def _direct_purchase(client, headers, sup, mat, wh, qty, price, commissions=None,
                     auto_liquidate=True):
    body = {
        "supplier_id": str(sup.id),
        "date": business_today_noon().isoformat(),
        "lines": [{
            "material_id": str(mat.id), "quantity": str(qty),
            "unit_price": str(price), "warehouse_id": str(wh.id),
        }],
        "auto_liquidate": auto_liquidate,
    }
    if commissions:
        body["commissions"] = commissions
    r = client.post(PURCHASES_URL, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# T1, T2 — el total digitado es el total de la compra
# ---------------------------------------------------------------------------

class TestTotalExacto:

    def test_t1_caso_de_johana(self, client, org_headers, db_session, wh, bat, sup1):
        """$3.138.450 para 1.503 unidades (la Entrada real del 19-nov).

        Con 2 decimales el unitario era 2.088,12 y la compra nacia en
        $3.138.444,36. El assert clave es el unitario PERSISTIDO leido por HTTP:
        es el unico que tumba P3 (la columna de la linea de vuelta en 2)."""
        order = _entrada_por_total(client, org_headers, wh, bat, "1503", "3138450", sup1)
        (purchase,) = _order_purchases(db_session, order["id"])

        p = _purchase_http(client, org_headers, purchase.id)
        (line,) = p["lines"]
        assert _d(line["unit_price"]) == Decimal("2088.1237525")
        assert _d(line["total_price"]) == Decimal("3138450")
        assert _d(p["total_amount"]) == Decimal("3138450")

        # El proveedor queda con exactamente lo digitado, en saldo y en el
        # estado de cuenta (#55: corrido == vivo).
        assert _balance_http(client, org_headers, sup1.id) == Decimal("-3138450")
        st = _statement_http(client, org_headers, sup1.id)
        montos = [_d(i["amount"]) for i in st["items"] if i.get("amount") is not None]
        assert Decimal("3138450") in montos, montos
        assert _d(st["items"][-1]["balance_after"]) == Decimal("-3138450")

    def test_t2_cantidad_grande_en_kg(self, client, org_headers, db_session, wh, chatarra, sup1):
        """45.660 kg por $987.654.321: con 2 decimales el error podia llegar a
        45.660 x $0,005 = $228,30. Con 8 queda bajo el centavo."""
        order = _entrada_por_total(client, org_headers, wh, chatarra, "45660",
                                   "987654321", sup1)
        (purchase,) = _order_purchases(db_session, order["id"])
        p = _purchase_http(client, org_headers, purchase.id)
        assert _d(p["total_amount"]) == Decimal("987654321")
        assert _d(p["lines"][0]["total_price"]) == Decimal("987654321")
        assert _balance_http(client, org_headers, sup1.id) == Decimal("-987654321")


# ---------------------------------------------------------------------------
# T3, T4 — la reversa y la re-liquidacion
# ---------------------------------------------------------------------------

class TestReversa:

    def _unliquidate(self, client, headers, order_id):
        r = client.post(f"{INBOUND_URL}/{order_id}/unliquidate", headers=headers)
        assert r.status_code == 200, r.text

    def test_t3a_con_stock_previo(self, client, org_headers, db_session, wh, bat, sup1, sup2):
        """Rama 1 de remove_from_pool: queda stock, el residuo se esconde en el
        promedio (15,4). Cota: (2 x stock_previo + cantidad) x $0,00005."""
        _direct_purchase(client, org_headers, sup2, bat, wh, "200", "1999.99")
        m0 = _fresh(db_session, Material, bat.id)
        pool0, stock0 = _pool(m0), m0.current_stock_liquidated
        bal0 = _balance_http(client, org_headers, sup1.id)

        order = _entrada_por_total(client, org_headers, wh, bat, "1503", "3138450", sup1)
        self._unliquidate(client, org_headers, order["id"])

        assert _balance_http(client, org_headers, sup1.id) == bal0
        m1 = _fresh(db_session, Material, bat.id)
        assert m1.current_stock_liquidated == stock0
        cota = (2 * stock0 + Decimal("1503")) * AVG_STEP
        assert abs(_pool(m1) - pool0) <= cota, (_pool(m1), pool0, cota)

    def test_t3b_con_pool_vacio(self, client, org_headers, db_session, wh, bat, sup1):
        """Ramas 2/3: la diferencia va al P&L. Cota: cantidad x $0,00005 + $0,005.

        NO discrimina base contra nuevo (con la base tambien da $0,00, porque
        linea y movimiento estan en la misma escala). Lo que discrimina es P2."""
        order = _entrada_por_total(client, org_headers, wh, bat, "1503", "3138450", sup1)
        self._unliquidate(client, org_headers, order["id"])

        assert _balance_http(client, org_headers, sup1.id) == 0
        o = _fresh(db_session, InboundOrder, order["id"])
        cota = Decimal("1503") * AVG_STEP + Decimal("0.005")
        assert abs(o.annul_cost_adjustment) <= cota, o.annul_cost_adjustment
        m = _fresh(db_session, Material, bat.id)
        assert m.current_stock_liquidated == 0

    def test_t4_reliquidar_sin_cambios(self, client, org_headers, db_session, wh, bat, sup1):
        """La firma de re-liquidacion (#93) compara unitarios a PRICE_Q: el
        mismo reparto reusa la misma compra, y el total sigue exacto."""
        order = _entrada_por_total(client, org_headers, wh, bat, "1503", "3138450", sup1)
        (antes,) = _order_purchases(db_session, order["id"])
        numero = antes.purchase_number
        self._unliquidate(client, org_headers, order["id"])
        _liquidate(client, org_headers, order["id"],
                   [_liq_line(bat, [_alloc(sup1, "1503", total="3138450")])])

        (despues,) = _order_purchases(db_session, order["id"])
        assert despues.purchase_number == numero
        assert despues.id == antes.id
        p = _purchase_http(client, org_headers, despues.id)
        assert _d(p["total_amount"]) == Decimal("3138450")
        assert _balance_http(client, org_headers, sup1.id) == Decimal("-3138450")


# ---------------------------------------------------------------------------
# T5, T7 — compra directa (sin flag, estilo Costa)
# ---------------------------------------------------------------------------

class TestCompraDirecta:

    def test_t5_unitario_de_dos_decimales_no_cambia(
        self, client, org_headers, db_session, wh, mat_costa, sup1,
    ):
        """No-regresion: un unitario de centavos da el mismo total de siempre."""
        body = _direct_purchase(client, org_headers, sup1, mat_costa, wh, "1250.5", "843.27")
        assert _d(body["total_amount"]) == (Decimal("1250.5") * Decimal("843.27")).quantize(CENT)
        p = _purchase_http(client, org_headers, body["id"])
        assert _d(p["lines"][0]["unit_price"]) == Decimal("843.27")
        assert _balance_http(client, org_headers, sup1.id) == -Decimal("1054509.14")
        m = _fresh(db_session, Material, mat_costa.id)
        assert m.current_average_cost == Decimal("843.27")

    def test_t7_comision_que_no_cae_en_centavos(
        self, client, org_headers, db_session, wh, mat_costa, sup1, comisionista,
    ):
        """#30: la comision se prorratea al costo — $1.000 entre 7 kg suman
        142,857142857... por kg. El pool recibe el valor sin redondear y la
        reversa saca el costo leido del InventoryMovement (#66 H1): con el
        movimiento en 2 decimales la diferencia ($0,02) caia al P&L. Con 8,
        bajo la cota."""
        body = _direct_purchase(
            client, org_headers, sup1, mat_costa, wh, "7", "1000",
            commissions=[{
                "third_party_id": str(comisionista.id), "concept": "Comision",
                "commission_type": "fixed", "commission_value": "1000",
            }],
        )
        r = client.patch(f"{PURCHASES_URL}/{body['id']}/cancel", headers=org_headers)
        assert r.status_code == 200, r.text

        p = _fresh(db_session, Purchase, body["id"])
        cota = Decimal("7") * AVG_STEP + Decimal("0.005")
        assert abs(p.cancellation_cost_adjustment) <= cota, p.cancellation_cost_adjustment
        assert _balance_http(client, org_headers, sup1.id) == 0
        assert _balance_http(client, org_headers, comisionista.id) == 0


# ---------------------------------------------------------------------------
# T6, T8 — modo por kg y reparto entre dos proveedores
# ---------------------------------------------------------------------------

class TestModosDeReparto:

    def test_t6_por_kg_que_no_divide(self, client, org_headers, db_session, wh, bat, sup1):
        """#101: el total es peso x precio por kg, a centavos — el mismo numero
        que pinta la pantalla. 7,333 kg x $1.000,5 = $7.336,6665 → $7.336,67.
        Con el unitario a 2 decimales (2.445,56) la compra nacia en $7.336,68."""
        order = _captured_reviewed(client, org_headers, wh, [_line(bat, "3", weight="7.333")])
        _liquidate(client, org_headers, order["id"],
                   [_liq_line(bat, [_alloc(sup1, "3", per_kg="1000.5")])])
        (purchase,) = _order_purchases(db_session, order["id"])
        p = _purchase_http(client, org_headers, purchase.id)
        esperado = (Decimal("7.333") * Decimal("1000.5")).quantize(CENT)
        assert esperado == Decimal("7336.67")
        assert _d(p["total_amount"]) == esperado
        assert _balance_http(client, org_headers, sup1.id) == -esperado

    def test_t8_dos_proveedores_por_total(
        self, client, org_headers, db_session, wh, bat, sup1, sup2,
    ):
        """Cada compra exacta, y el descuadre (pesado − repartido) no se mueve:
        1.600 pesadas, 1.503 repartidas → 97 al precio de referencia."""
        order = _captured_reviewed(client, org_headers, wh, [_line(bat, "1600", weight="1600")])
        _liquidate(client, org_headers, order["id"], [_liq_line(
            bat,
            [_alloc(sup1, "700", total="1462345"), _alloc(sup2, "803", total="1676105")],
            ref_price="2000",
        )])
        by_tp = {p.supplier_id: p for p in _order_purchases(db_session, order["id"])}
        assert _d(_purchase_http(client, org_headers, by_tp[sup1.id].id)["total_amount"]) == Decimal("1462345")
        assert _d(_purchase_http(client, org_headers, by_tp[sup2.id].id)["total_amount"]) == Decimal("1676105")
        assert _balance_http(client, org_headers, sup1.id) == Decimal("-1462345")
        assert _balance_http(client, org_headers, sup2.id) == Decimal("-1676105")

        (adj,) = _order_adjustments(db_session, order["id"])
        assert adj.quantity == Decimal("97")
        assert adj.unit_cost == Decimal("2000")


# ---------------------------------------------------------------------------
# T9 — C1 de QA: el precio de referencia se valora a centavos en el servidor
# ---------------------------------------------------------------------------

class TestReferenciaACentavos:

    def test_t9_ref_de_ocho_decimales_por_el_api(
        self, client, org_headers, db_session, wh, bat, sup1,
    ):
        """La pantalla autollenaba la referencia con el unitario derivado, que
        ahora tiene 8 decimales. La columna es Numeric(15,2), pero el valor en
        memoria valoraba el descuadre sin redondear (ajuste a 4 decimales, aviso
        con 7). El ref llega por el API, con el payload directo: lo que se prueba
        es la defensa del servidor, que cubre a cualquier cliente."""
        order = _captured_reviewed(client, org_headers, wh, [_line(bat, "100", weight="100")])
        body = _liquidate(client, org_headers, order["id"], [_liq_line(
            bat, [_alloc(sup1, "60", "900")], ref_price="2088.1237525",
        )])

        (adj,) = _order_adjustments(db_session, order["id"])
        assert adj.quantity == Decimal("40")
        assert adj.unit_cost == Decimal("2088.12")

        r = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers)
        assert r.status_code == 200, r.text
        (line,) = r.json()["lines"]
        assert _d(line["reference_unit_price"]) == Decimal("2088.12")

        avisos = [w for w in body.get("warnings", []) if "valorado a" in w]
        assert avisos, body.get("warnings")
        assert all("2088.12" in w and "2088.1237" not in w for w in avisos), avisos

    def test_t10_ref_que_redondea_a_cero_rechaza_sin_escribir(
        self, client, org_headers, db_session, wh, bat, sup1,
    ):
        """C2 de QA: $0,001 pasa el gt=0 del schema y queda en $0,00 al
        redondear a la columna. La guarda responde 422 nombrando el material,
        ANTES de escribir nada (criterio 15 de #93: fallar antes, no a mitad)."""
        order = _captured_reviewed(client, org_headers, wh, [_line(bat, "100", weight="100")])
        resp = _liquidate(client, org_headers, order["id"], [_liq_line(
            bat, [_alloc(sup1, "60", "900")], ref_price="0.001",
        )], expect=422)
        assert "BAT-RED" in resp["detail"]
        assert "precio de referencia" in resp["detail"]

        r = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "reviewed"
        assert _order_purchases(db_session, order["id"]) == []
        assert _order_adjustments(db_session, order["id"]) == []
        assert _balance_http(client, org_headers, sup1.id) == 0
