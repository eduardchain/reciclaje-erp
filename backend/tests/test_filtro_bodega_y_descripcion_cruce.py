"""
Filtro por bodega en Compras/Ventas + descripcion por lado en el cruce entre
terceros (pedido de Gustavo, Costa, 2026-10-21).

Plan: docs/planes/plan-filtro-bodega-y-descripcion-cruce.md v1.2. Los T# y P#
de los docstrings son los de la grilla de §7, commiteada ANTES de plantar.

Los asserts de compras van sobre `total`, `active_total` y `total_amount_sum`
contra valores calculados A MANO, nunca sobre `len(items)`: la Query legacy con
joinedload de coleccion unifica entidades, asi que un join a lineas puede dejar
la lista visible bien mientras los conteos salen inflados (C1 de QA).
"""
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models import Material, Warehouse
from tests.conftest import create_third_party_with_category

DATE = "2026-03-20T12:00:00Z"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _warehouse(db, org_id, name):
    wh = Warehouse(id=uuid4(), name=name, organization_id=org_id, is_active=True)
    db.add(wh)
    db.flush()
    return wh


def _material(db, org_id, code):
    mat = Material(
        id=uuid4(), code=code, name=f"Material {code}", default_unit="kg",
        current_stock=Decimal("0"), current_average_cost=Decimal("0"),
        organization_id=org_id, is_active=True,
    )
    db.add(mat)
    db.flush()
    return mat


@pytest.fixture
def escenario(db_session, test_organization):
    """Dos bodegas, tres materiales, dos proveedores y un cliente."""
    org = test_organization.id
    data = {
        "A": _warehouse(db_session, org, "San Alberto"),
        "B": _warehouse(db_session, org, "Bodega Principal"),
        "m1": _material(db_session, org, "COB-1"),
        "m2": _material(db_session, org, "COB-2"),
        "m3": _material(db_session, org, "COB-3"),
        "s1": create_third_party_with_category(db_session, org, "Chatarreria Uno", "material_supplier"),
        "s2": create_third_party_with_category(db_session, org, "Recicladora Dos", "material_supplier"),
        "cust": create_third_party_with_category(db_session, org, "Fundicion Cliente", "customer"),
    }
    db_session.commit()
    return data


def _line(mat, qty, price, wh=None):
    line = {"material_id": str(mat.id), "quantity": qty, "unit_price": price}
    if wh is not None:
        line["warehouse_id"] = str(wh.id)
    return line


def _purchase(client, headers, supplier, lines, header_wh=None):
    payload = {"supplier_id": str(supplier.id), "date": DATE, "lines": lines, "auto_liquidate": False}
    if header_wh is not None:
        payload["warehouse_id"] = str(header_wh.id)
    resp = client.post("/api/v1/purchases", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def compras(client, org_headers, escenario):
    """Fixture de compras de §7 (C1/C2/G1). Totales a mano:

    - tres_a: 3 lineas en A (forma Costa, cabecera NULL)   = 10*100 + 20*100 + 30*100 = 6000
    - mixta: 1 linea en A + 1 en B                          = 10*200 + 5*200          = 3000
    - sac: cabecera A (forma SAC, fuerza las lineas)        = 7*100                    =  700
    - cancelada: 1 linea en A, despues cancelada            = 1*500                    =  500
    - solo_b: 1 linea en B (G1)                             = 4*250                    = 1000
    - dp: pasa mano, lineas sin bodega                      = 10*100 (compra)          = 1000
    """
    e = escenario
    h = org_headers
    out = {
        "tres_a": _purchase(client, h, e["s1"], [
            _line(e["m1"], 10, 100, e["A"]), _line(e["m2"], 20, 100, e["A"]), _line(e["m3"], 30, 100, e["A"]),
        ]),
        "mixta": _purchase(client, h, e["s2"], [_line(e["m1"], 10, 200, e["A"]), _line(e["m2"], 5, 200, e["B"])]),
        "sac": _purchase(client, h, e["s2"], [_line(e["m1"], 7, 100)], header_wh=e["A"]),
        "cancelada": _purchase(client, h, e["s2"], [_line(e["m3"], 1, 500, e["A"])]),
        "solo_b": _purchase(client, h, e["s1"], [_line(e["m2"], 4, 250, e["B"])]),
    }
    resp = client.patch(f"/api/v1/purchases/{out['cancelada']['id']}/cancel", headers=h)
    assert resp.status_code == 200, resp.text

    dp = client.post("/api/v1/double-entries", json={
        "lines": [{"material_id": str(e["m1"].id), "quantity": 10, "purchase_unit_price": 100, "sale_unit_price": 120}],
        "supplier_id": str(e["s2"].id), "customer_id": str(e["cust"].id),
        "date": "2026-03-20", "commissions": [],
    }, headers=h)
    assert dp.status_code == 201, dp.text
    out["dp"] = dp.json()
    return out


def _list(client, headers, **params):
    resp = client.get("/api/v1/purchases", params={"limit": 100, **params}, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _numbers(data):
    return {p["purchase_number"] for p in data["items"]}


# ---------------------------------------------------------------------------
# Pedido 1 — filtro por bodega en compras
# ---------------------------------------------------------------------------

class TestFiltroBodegaCompras:

    def test_t1_filtra_por_lineas_de_cada_bodega(self, client, org_headers, escenario, compras):
        """T1. Con A: las compras con linea en A, en sus DOS formas (Costa con
        cabecera NULL y SAC con cabecera puesta), la de 3 lineas UNA vez y la de
        solo-B ausente (G1). Con B: la de solo-B y la mixta. Conteos a mano.

        Cae con P1 (join: la de 3 lineas infla los conteos), P8 (filtrar por la
        cabecera: las de forma Costa desaparecen), P10 (EXISTS sin correlacion:
        aparecen todas) y P11 (IS NOT NULL: la de solo-B aparece con A).
        """
        c = compras
        con_a = _list(client, org_headers, warehouse_id=str(escenario["A"].id))
        assert _numbers(con_a) == {
            c["tres_a"]["purchase_number"], c["mixta"]["purchase_number"],
            c["sac"]["purchase_number"], c["cancelada"]["purchase_number"],
        }
        assert con_a["total"] == 4
        assert con_a["active_total"] == 3
        assert con_a["total_amount_sum"] == 6000 + 3000 + 700

        con_b = _list(client, org_headers, warehouse_id=str(escenario["B"].id))
        assert _numbers(con_b) == {c["mixta"]["purchase_number"], c["solo_b"]["purchase_number"]}
        assert con_b["total"] == 2
        assert con_b["active_total"] == 2
        assert con_b["total_amount_sum"] == 3000 + 1000

    def test_t2_filtro_y_busqueda_juntos(self, client, org_headers, escenario, compras):
        """T2. Filtro A + search por el nombre de un proveedor. El search ya hace
        join al proveedor: con un join a lineas encima, la de 3 lineas saldria
        3 veces en los conteos (P1)."""
        data = _list(client, org_headers, warehouse_id=str(escenario["A"].id), search="Chatarreria Uno")
        assert _numbers(data) == {compras["tres_a"]["purchase_number"]}
        assert data["total"] == 1
        assert data["active_total"] == 1
        assert data["total_amount_sum"] == 6000

    def test_t3_pasa_mano_no_aparece_con_filtro(self, client, org_headers, escenario, compras):
        """T3. La compra de pasa mano no tiene bodega: aparece sin filtro y no
        con ninguna bodega. Cae con P2 (OR cabecera IS NULL) y P10."""
        sin_filtro = _list(client, org_headers)
        dp_items = [p for p in sin_filtro["items"] if p.get("double_entry_id")]
        assert len(dp_items) == 1, "la compra de pasa mano debe existir sin filtro"
        dp_number = dp_items[0]["purchase_number"]
        for wh in ("A", "B"):
            data = _list(client, org_headers, warehouse_id=str(escenario[wh].id))
            assert dp_number not in _numbers(data), f"pasa mano aparecio filtrando por {wh}"

    def test_t4_sin_parametro_igual_que_antes(self, client, org_headers, compras):
        """T4. Sin warehouse_id: las 6 compras (5 + la de pasa mano), 5 activas
        y el total a mano. Cae con P3 (aplicar el filtro siempre: con None
        queda `warehouse_id IS NULL` y solo sale la de pasa mano)."""
        data = _list(client, org_headers)
        assert data["total"] == 6
        assert data["active_total"] == 5
        assert data["total_amount_sum"] == 6000 + 3000 + 700 + 1000 + 1000

    def test_t5_bodega_de_otra_organizacion(self, client, org_headers, db_session, test_organization2, compras):
        """T5. Una bodega de OTRA org no devuelve nada. Es control salvo bajo
        P11 (IS NOT NULL), que ignora cual bodega se pidio y devuelve todas las
        compras propias con bodega."""
        ajena = _warehouse(db_session, test_organization2.id, "Bodega Ajena")
        db_session.commit()
        data = _list(client, org_headers, warehouse_id=str(ajena.id))
        assert data["total"] == 0
        assert data["active_total"] == 0
        assert data["total_amount_sum"] == 0


# ---------------------------------------------------------------------------
# Pedido 1 — filtro por bodega en ventas (el backend ya existia; faltaba test)
# ---------------------------------------------------------------------------

class TestFiltroBodegaVentas:

    def test_t6_ventas_por_bodega(self, client, org_headers, escenario, compras):
        """T6. Solo las ventas de esa bodega; la venta de pasa mano (sin bodega)
        no aparece con filtro. Cae con P4 (el endpoint ignora el parametro)."""
        e = escenario
        numeros = {}
        for wh in ("A", "B"):
            resp = client.post("/api/v1/sales", json={
                "customer_id": str(e["cust"].id), "warehouse_id": str(e[wh].id), "date": DATE,
                "lines": [{"material_id": str(e["m1"].id), "quantity": 2, "unit_price": 300}],
                "commissions": [], "auto_liquidate": False,
            }, headers=org_headers)
            assert resp.status_code == 201, resp.text
            numeros[wh] = resp.json()["sale_number"]

        for wh in ("A", "B"):
            resp = client.get("/api/v1/sales", params={"warehouse_id": str(e[wh].id), "limit": 100}, headers=org_headers)
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert {s["sale_number"] for s in data["items"]} == {numeros[wh]}
            assert data["total"] == 1
            assert data["total_amount_sum"] == 600

        # Sin filtro: las 2 ventas de bodega + la de pasa mano.
        resp = client.get("/api/v1/sales", params={"limit": 100}, headers=org_headers)
        assert resp.json()["total"] == 3


# ---------------------------------------------------------------------------
# Pedido 2 — descripcion por lado en el cruce entre terceros
# ---------------------------------------------------------------------------

def _cruce(client, headers, origen, destino, **extra):
    payload = {
        "source_third_party_id": str(origen.id),
        "destination_third_party_id": str(destino.id),
        "amount": 50000,
        "date": DATE,
        "description": "Consignacion bancaria",
        **extra,
    }
    return client.post("/api/v1/money-movements/tp-transfer", json=payload, headers=headers)


def _descripciones_del_statement(client, headers, tercero):
    # `date_from` EXPLICITO: sin el, el estado de cuenta muestra los ultimos 90
    # dias y DATE (marzo) queda afuera — la lista sale vacia, y los asserts de
    # "no se creo nada" (T9, T10) pasarian en verde sin medir nada.
    resp = client.get(
        f"/api/v1/money-movements/third-party/{tercero.id}",
        params={"date_from": "2026-01-01"}, headers=headers,
    )
    assert resp.status_code == 200, resp.text
    return [
        (i["event_type"], i["description"], i["status"])
        for i in resp.json()["items"]
        if i["event_type"] in ("tp_transfer_out", "tp_transfer_in")
    ]


class TestDescripcionPorLadoDelCruce:

    def test_t7_cada_pierna_con_su_descripcion(self, client, org_headers, escenario):
        """T7. Cada pierna guarda la suya, y el estado de cuenta de CADA tercero,
        leido por HTTP, muestra la suya. Cae con P5 (description en las dos)."""
        e = escenario
        resp = _cruce(client, org_headers, e["cust"], e["s1"], destination_description="Dinero para impuesto X")
        assert resp.status_code == 201, resp.text
        out = resp.json()
        assert out["description"] == "Consignacion bancaria"

        par = client.get(f"/api/v1/money-movements/{out['transfer_pair_id']}", headers=org_headers)
        assert par.status_code == 200
        assert par.json()["movement_type"] == "tp_transfer_in"
        assert par.json()["description"] == "Dinero para impuesto X"

        assert _descripciones_del_statement(client, org_headers, e["cust"]) == [
            ("tp_transfer_out", "Consignacion bancaria", "confirmed"),
        ]
        assert _descripciones_del_statement(client, org_headers, e["s1"]) == [
            ("tp_transfer_in", "Dinero para impuesto X", "confirmed"),
        ]

    def test_t8_sin_descripcion_destino_las_dos_iguales(self, client, org_headers, escenario):
        """T8. No-regresion: sin destination_description, el destino lleva la
        del origen, como siempre. Cae con P6 (destino en NULL)."""
        e = escenario
        resp = _cruce(client, org_headers, e["cust"], e["s1"])
        assert resp.status_code == 201, resp.text
        par = client.get(f"/api/v1/money-movements/{resp.json()['transfer_pair_id']}", headers=org_headers)
        assert par.json()["description"] == "Consignacion bancaria"
        assert _descripciones_del_statement(client, org_headers, e["s1"]) == [
            ("tp_transfer_in", "Consignacion bancaria", "confirmed"),
        ]

    @pytest.mark.parametrize("valor", ["", "x" * 501])
    def test_t9_validacion_descripcion_destino(self, client, org_headers, escenario, valor):
        """T9. Vacia o de 501 caracteres → 422, y no se crea nada. Cae con P7."""
        e = escenario
        resp = _cruce(client, org_headers, e["cust"], e["s1"], destination_description=valor)
        assert resp.status_code == 422, resp.text
        assert _descripciones_del_statement(client, org_headers, e["s1"]) == []
        # Control positivo: la misma lectura SI ve un cruce valido. Sin esto, el
        # `== []` de arriba no distingue "no se creo" de "la consulta no mira".
        assert _cruce(client, org_headers, e["cust"], e["s1"]).status_code == 201
        assert len(_descripciones_del_statement(client, org_headers, e["s1"])) == 1

    def test_t10_clave_desconocida_es_422(self, client, org_headers, escenario):
        """T10 (C4). Una clave mal escrita era descartada en silencio y el
        destino recibia la descripcion del origen — identico a que funcione.
        Con extra=forbid es 422. Cae con P9."""
        e = escenario
        resp = _cruce(client, org_headers, e["cust"], e["s1"], destination_descripton="Dinero para impuesto X")
        assert resp.status_code == 422, resp.text
        assert _descripciones_del_statement(client, org_headers, e["s1"]) == []
        assert _cruce(client, org_headers, e["cust"], e["s1"]).status_code == 201
        assert len(_descripciones_del_statement(client, org_headers, e["s1"])) == 1

    def test_t11_anular_conserva_cada_descripcion(self, client, org_headers, escenario):
        """T11 (control). Anular el cruce anula las dos piernas y cada una
        conserva su descripcion."""
        e = escenario
        resp = _cruce(client, org_headers, e["cust"], e["s1"], destination_description="Dinero para impuesto X")
        assert resp.status_code == 201, resp.text
        anul = client.post(f"/api/v1/money-movements/{resp.json()['id']}/annul", json={"reason": "Error"}, headers=org_headers)
        assert anul.status_code == 200, anul.text
        assert _descripciones_del_statement(client, org_headers, e["cust"]) == [
            ("tp_transfer_out", "Consignacion bancaria", "annulled"),
        ]
        assert _descripciones_del_statement(client, org_headers, e["s1"]) == [
            ("tp_transfer_in", "Dinero para impuesto X", "annulled"),
        ]
