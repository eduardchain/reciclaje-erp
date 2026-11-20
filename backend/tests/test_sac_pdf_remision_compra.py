"""
Tests SAC — la remision de la Entrada llega en la respuesta de la compra
(pedido de Johana 2026-11-19; plan-sac-entrada-editar-sede.md §7).

El PDF de una compra de SAC se titula «Entrada #<remision>». El PDF se arma en
el navegador con lo que devuelve GET /purchases (listado) y GET
/purchases/{id} (detalle) — los dos llamadores de exportPurchasePDF — asi que
la remision tiene que llegar en LAS DOS respuestas.
"""
import pytest

from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)
from app.utils.dates import business_today

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
PROFILES_URL = "/api/v1/material-kg-profiles"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar PDF")
    db_session.commit()
    return w


@pytest.fixture
def sup(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor PDF", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def mat(db_session, test_organization, client, org_headers):
    cat = create_material_category(db_session, test_organization.id, "Cat PDF")
    m = create_material(db_session, test_organization.id, "SCR-PDF", "Scrap PDF", cat.id)
    m.default_unit = "kg"
    db_session.commit()
    resp = client.put(
        f"{PROFILES_URL}/{m.id}", headers=org_headers,
        json={"compra_regular": True, "willard_world": "none", "lead_product": "none"},
    )
    assert resp.status_code == 200, resp.text
    return m


def _entrada_liquidada(client, headers, wh, mat, sup, remision):
    body = {
        "inbound_type": "purchase", "warehouse_id": str(wh.id),
        "date": business_today().isoformat(),
        "lines": [{"material_id": str(mat.id), "quantity": "100", "scale_weight_kg": "100"}],
    }
    if remision is not None:
        body["remission_number"] = remision
    resp = client.post(INBOUND_URL, headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    oid = resp.json()["id"]
    assert client.post(f"{INBOUND_URL}/{oid}/review", headers=headers).status_code == 200
    resp = client.post(
        f"{INBOUND_URL}/{oid}/liquidate", headers=headers,
        json={"lines": [{
            "material_id": str(mat.id),
            "allocations": [{"third_party_id": str(sup.id), "quantity": "100",
                             "unit_price": "900"}],
        }]},
    )
    assert resp.status_code == 200, resp.text
    compras = resp.json()["purchases"]
    assert len(compras) == 1
    return compras[0]["purchase_id"]


def _detalle_y_listado(client, headers, purchase_id):
    det = client.get(f"{PURCHASES_URL}/{purchase_id}", headers=headers)
    assert det.status_code == 200, det.text
    lst = client.get(PURCHASES_URL, headers=headers, params={"limit": 100})
    assert lst.status_code == 200, lst.text
    fila = [p for p in lst.json()["items"] if p["id"] == purchase_id]
    assert len(fila) == 1
    return det.json(), fila[0]


class TestRemisionEnLaCompra:

    def test_con_remision_llega_en_detalle_y_listado(
        self, client, org_headers, wh, mat, sup,
    ):
        pid = _entrada_liquidada(client, org_headers, wh, mat, sup, "16254")
        det, fila = _detalle_y_listado(client, org_headers, pid)
        assert det["inbound_order_id"] is not None
        assert det["inbound_remission_number"] == "16254"
        assert fila["inbound_remission_number"] == "16254"

    def test_sin_remision_llega_null(self, client, org_headers, wh, mat, sup):
        """La Entrada existe pero sin remision: el PDF dira «Entrada (sin
        remision)», asi que lo que importa es que la Entrada SI llegue."""
        pid = _entrada_liquidada(client, org_headers, wh, mat, sup, None)
        det, fila = _detalle_y_listado(client, org_headers, pid)
        assert det["inbound_order_id"] is not None
        assert det["inbound_remission_number"] is None
        assert fila["inbound_remission_number"] is None

    def test_compra_directa_sin_entrada_llega_null(
        self, client, org_headers, wh, mat, sup,
    ):
        """Compra que no nacio de una Entrada (el caso de toda org sin SAC):
        la clave esta y vale null, y el PDF sigue diciendo «Compra #N»."""
        resp = client.post(
            PURCHASES_URL, headers=org_headers,
            json={
                "supplier_id": str(sup.id), "date": business_today().isoformat(),
                "lines": [{"material_id": str(mat.id), "warehouse_id": str(wh.id),
                           "quantity": "10", "unit_price": "900"}],
            },
        )
        assert resp.status_code == 201, resp.text
        det, fila = _detalle_y_listado(client, org_headers, resp.json()["id"])
        assert det["inbound_order_id"] is None
        assert "inbound_remission_number" in det and det["inbound_remission_number"] is None
        assert "inbound_remission_number" in fila and fila["inbound_remission_number"] is None
