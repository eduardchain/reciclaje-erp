"""
T12 de plan-sac-retefuente-porcentajes: el servidor topa la tasa en 100.

`PurchaseRetentionCreate.rate` y `DocumentTaxCreate.rate` eran libres (`gt=0`).
La columna es `Numeric(7,4)`: desde 1000 desbordaba y el servidor daba 500 por
`DataError` (medido por QA 1, `qa-1-rate-sin-tope/medicion.log`). Con `le=100`
un valor fuera de rango da 422 y no se escribe nada.

Un validador, todos los puntos de entrada (#103 D3): los cinco caminos que
llegan a esos dos schemas, salidos del grep por SIMBOLO en `app/`
(`barrido_t12.log`):

| #  | Camino                                   | Schema                   |
|----|------------------------------------------|--------------------------|
| B1 | liquidar compra directa, `retentions`    | PurchaseRetentionCreate  |
| B2 | liquidar Entrada, `supplier_retentions`  | PurchaseRetentionCreate  |
| B3 | liquidar Entrada, `purchase_taxes`       | DocumentTaxCreate        |
| B4 | liquidar venta, `taxes`                  | DocumentTaxCreate        |
| B5 | liquidar Salida de Plomo, `taxes`        | DocumentTaxCreate        |

Cada camino con 1000 / 100.01 (422) y 100 (200, el borde legitimo). En cada
422 se afirma que NO quedo nada escrito: el documento sigue en su estado, y
no hay compras, retenciones, impuestos ni cambio de saldo.
"""
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models.document_tax import DocumentTax
from app.models.inbound_order import InboundOrder, InboundOrderPurchase
from app.models.purchase import Purchase
from app.models.purchase_retention import PurchaseRetention
from app.models.sale import Sale
from app.models.third_party import ThirdParty
from app.models.willard_delivery import WillardDelivery
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.reparto_slots import con_slots
from tests.test_sac_entrada_sin_proveedor import (
    INBOUND_URL, _alloc, _captured_reviewed, _line, _liq_line, _set_profile,
)
from tests.test_sac_impuestos_ventas import SALE_DATE, SEED_DATE, WILLARD_URL, _sale

PURCHASES_URL = "/api/v1/purchases"

CASOS = [
    pytest.param("1000", 422, id="1000-desborda"),
    pytest.param("100.01", 422, id="100.01-fuera"),
    pytest.param("100", 200, id="100-borde"),
]


@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    """La bandera SAC (los cinco caminos la exigen para mandar impuestos).
    `flags_willard` la reescribe con la planta, despues de esta."""
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


# Fixtures propias (patron de test_redondeo_precio_compras): importar fixtures
# de otro modulo de tests las redefine ante ruff (F811).

ADJUST_URL = "/api/v1/inventory/adjustments"


def _stock(client, headers, mat, wh, qty):
    r = client.post(f"{ADJUST_URL}/increase", headers=headers, json={
        "material_id": str(mat.id), "warehouse_id": str(wh.id), "quantity": qty,
        "unit_cost": "2000", "date": SEED_DATE, "reason": "Seed",
    })
    assert r.status_code == 201, r.text


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar T12")
    db_session.commit()
    return w


@pytest.fixture
def sup1(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor T12", "material_supplier")
    db_session.commit()
    return tp


@pytest.fixture
def mat_moto(db_session, test_organization, client, org_headers):
    cat = create_material_category(db_session, test_organization.id, "Cat T12")
    mat = create_material(db_session, test_organization.id, "MOTO-T12", "Moto T12", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def customer(db_session, test_organization):
    return create_third_party_with_category(
        db_session, test_organization.id, "Cliente T12", "customer")


@pytest.fixture
def material(db_session, test_organization, client, org_headers, wh):
    cat = create_material_category(db_session, test_organization.id, "Plomo T12")
    mat = create_material(db_session, test_organization.id, "PB-T12", "Plomo T12", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    _stock(client, org_headers, mat, wh, "1000")
    return mat


@pytest.fixture
def planta(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Juan Mina T12")
    db_session.commit()
    return w


@pytest.fixture
def flags_willard(db_session, test_organization, planta):
    """La salida sale de la planta (D8 de W1)."""
    test_organization.settings = {
        "kg_ledger_enabled": True, "willard_sede_drosses": str(planta.id),
    }
    db_session.commit()


@pytest.fixture
def willard_tp(db_session, test_organization):
    return create_third_party_with_category(
        db_session, test_organization.id, "Willard T12", "customer")


@pytest.fixture
def acc_intersede(db_session, test_organization):
    from app.models.kg_ledger import KgLedgerAccount

    db_session.add(KgLedgerAccount(
        organization_id=test_organization.id, code="INTERSEDE",
        display_name="Intersede", account_type="intersede", is_active=True,
    ))
    db_session.commit()


@pytest.fixture
def plomo_crudo(db_session, test_organization, client, org_headers, planta):
    from app.models.material_kg_profile import MaterialKgProfile

    cat = create_material_category(db_session, test_organization.id, "Plomo crudo T12")
    mat = create_material(db_session, test_organization.id, "PB-CRU-T12", "Plomo Crudo T12", cat.id)
    mat.default_unit = "kg"
    db_session.add(MaterialKgProfile(
        organization_id=test_organization.id, material_id=mat.id, lead_product="crudo",
    ))
    db_session.commit()
    _stock(client, org_headers, mat, planta, "1000")
    return mat


def _balance(db, tp_id) -> Decimal:
    db.expire_all()
    return db.get(ThirdParty, tp_id).current_balance


def _count(db, stmt) -> int:
    db.expire_all()
    return db.execute(stmt).scalar_one()


def _rate_en_el_422(resp) -> bool:
    """El 422 tiene que nombrar `rate`, no venir de otra validacion."""
    detail = resp.json().get("detail")
    return isinstance(detail, list) and any("rate" in [str(x) for x in d.get("loc", [])]
                                            for d in detail)


# ------------------------------------------------------------------- B1 ---

class TestB1CompraDirecta:
    @pytest.mark.parametrize("rate,esperado", CASOS)
    def test_retencion(self, client, org_headers, db_session, wh, sup1, mat_moto,
                       rate, esperado):
        r = client.post(PURCHASES_URL, headers=org_headers, json={
            "supplier_id": str(sup1.id),
            "date": f"{SALE_DATE}",
            "lines": [{"material_id": str(mat_moto.id), "warehouse_id": str(wh.id),
                       "quantity": 100, "unit_price": 10_000}],
        })
        assert r.status_code == 201, r.text
        pid = r.json()["id"]
        antes = _balance(db_session, sup1.id)

        resp = client.patch(f"{PURCHASES_URL}/{pid}/liquidate", headers=org_headers, json={
            "liquidation_date": f"{SALE_DATE}T12:00:00",
            "retentions": [{"retention_type": "retefuente", "rate": rate,
                            "base": "1000000", "amount": "25000"}],
        })
        assert resp.status_code == esperado, resp.text
        db_session.expire_all()
        compra = db_session.get(Purchase, UUID(pid))
        rets = _count(db_session, select(func.count()).select_from(PurchaseRetention)
                      .where(PurchaseRetention.purchase_id == UUID(pid)))
        if esperado == 422:
            assert _rate_en_el_422(resp), resp.text
            assert compra.status == "registered"
            assert rets == 0
            assert _balance(db_session, sup1.id) == antes
        else:
            assert compra.status == "liquidated"
            assert rets == 1
            ret = db_session.execute(select(PurchaseRetention).where(
                PurchaseRetention.purchase_id == UUID(pid))).scalar_one()
            assert ret.rate == Decimal("100")


# --------------------------------------------------------------- B2 / B3 ---

def _entrada(client, headers, wh, mat):
    return _captured_reviewed(client, headers, wh, [_line(mat, "100")])


def _efectos_entrada(db, order_id):
    oid = UUID(order_id)
    db.expire_all()
    order = db.get(InboundOrder, oid)
    compras = _count(db, select(func.count()).select_from(InboundOrderPurchase)
                     .where(InboundOrderPurchase.inbound_order_id == oid))
    pids = select(InboundOrderPurchase.purchase_id).where(
        InboundOrderPurchase.inbound_order_id == oid)
    rets = _count(db, select(func.count()).select_from(PurchaseRetention)
                  .where(PurchaseRetention.purchase_id.in_(pids)))
    taxes = _count(db, select(func.count()).select_from(DocumentTax)
                   .where(DocumentTax.purchase_id.in_(pids)))
    return order.status, compras, rets, taxes


class TestB2B3Entrada:
    @pytest.mark.parametrize("rate,esperado", CASOS)
    def test_b2_supplier_retentions(self, client, org_headers, db_session, wh, sup1,
                                    mat_moto, rate, esperado):
        order = _entrada(client, org_headers, wh, mat_moto)
        antes = _balance(db_session, sup1.id)
        body = {
            "lines": [_liq_line(mat_moto, [_alloc(sup1, "100", "900")])],
            "supplier_retentions": [{"third_party_id": str(sup1.id), "retentions": [
                {"retention_type": "retefuente", "rate": rate, "base": "90000",
                 "amount": "100"}]}],
        }
        resp = client.post(f"{INBOUND_URL}/{order['id']}/liquidate", headers=org_headers,
                           json=con_slots(body))
        assert resp.status_code == esperado, resp.text
        status, compras, rets, taxes = _efectos_entrada(db_session, order["id"])
        if esperado == 422:
            assert _rate_en_el_422(resp), resp.text
            assert (status, compras, rets, taxes) == ("reviewed", 0, 0, 0)
            assert _balance(db_session, sup1.id) == antes
        else:
            assert (status, compras, rets) == ("liquidated", 1, 1)

    @pytest.mark.parametrize("rate,esperado", CASOS)
    def test_b3_purchase_taxes(self, client, org_headers, db_session, wh, sup1,
                               mat_moto, rate, esperado):
        order = _entrada(client, org_headers, wh, mat_moto)
        antes = _balance(db_session, sup1.id)
        body = {
            "lines": [_liq_line(mat_moto, [_alloc(sup1, "100", "900")])],
            "purchase_taxes": [{"third_party_id": str(sup1.id), "taxes": [
                {"tax_type": "iva", "rate": rate, "amount": "100"}]}],
        }
        resp = client.post(f"{INBOUND_URL}/{order['id']}/liquidate", headers=org_headers,
                           json=con_slots(body))
        assert resp.status_code == esperado, resp.text
        status, compras, rets, taxes = _efectos_entrada(db_session, order["id"])
        if esperado == 422:
            assert _rate_en_el_422(resp), resp.text
            assert (status, compras, rets, taxes) == ("reviewed", 0, 0, 0)
            assert _balance(db_session, sup1.id) == antes
        else:
            assert (status, compras, taxes) == ("liquidated", 1, 1)


# ------------------------------------------------------------------- B4 ---

class TestB4Venta:
    @pytest.mark.parametrize("rate,esperado", CASOS)
    def test_taxes(self, client, org_headers, db_session, customer, wh,
                   material, rate, esperado):
        sale = _sale(client, org_headers, customer, wh, material, qty="100",
                     price="3000")
        antes = _balance(db_session, customer.id)
        resp = client.patch(f"/api/v1/sales/{sale['id']}/liquidate", headers=org_headers, json={
            "liquidation_date": f"{SALE_DATE}T12:00:00",
            "taxes": [{"tax_type": "iva", "rate": rate, "base_kind": "subtotal",
                       "amount": "100"}],
        })
        assert resp.status_code == esperado, resp.text
        db_session.expire_all()
        venta = db_session.get(Sale, UUID(sale["id"]))
        taxes = _count(db_session, select(func.count()).select_from(DocumentTax)
                       .where(DocumentTax.sale_id == UUID(sale["id"])))
        if esperado == 422:
            assert _rate_en_el_422(resp), resp.text
            assert venta.status == "registered"
            assert taxes == 0
            assert _balance(db_session, customer.id) == antes
        else:
            assert venta.status == "liquidated"
            assert taxes == 1


# ------------------------------------------------------------------- B5 ---

class TestB5SalidaDePlomo:
    @pytest.mark.parametrize("rate,esperado", CASOS)
    def test_taxes(self, client, org_headers, db_session, flags_willard, planta,
                   willard_tp, plomo_crudo, acc_intersede, rate, esperado):
        r = client.post(WILLARD_URL, headers=org_headers, json={
            "delivery_type": "venta",
            "warehouse_id": str(planta.id),
            "third_party_id": str(willard_tp.id),
            "date": f"{SALE_DATE}T12:00:00",
            "remission_number": "REM-T12",
            "lines": [{"material_id": str(plomo_crudo.id), "quantity": "100"}],
        })
        assert r.status_code == 201, r.text
        d = r.json()
        antes = _balance(db_session, willard_tp.id)
        resp = client.post(f"{WILLARD_URL}/{d['id']}/liquidate", headers=org_headers, json={
            "line_prices": [{"line_id": d["lines"][0]["id"], "unit_price": "3000"}],
            "taxes": [{"tax_type": "iva", "rate": rate, "base_kind": "subtotal",
                       "amount": "100"}],
        })
        assert resp.status_code == esperado, resp.text
        db_session.expire_all()
        entrega = db_session.get(WillardDelivery, UUID(d["id"]))
        taxes = _count(db_session, select(func.count()).select_from(DocumentTax)
                       .where(DocumentTax.willard_delivery_id == UUID(d["id"])))
        if esperado == 422:
            assert _rate_en_el_422(resp), resp.text
            assert entrega.status == "draft"
            assert taxes == 0
            assert _balance(db_session, willard_tp.id) == antes
        else:
            assert entrega.status == "liquidated"
            assert taxes == 1
