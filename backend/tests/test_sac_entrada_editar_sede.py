"""
Tests SAC — editar la sede de una Entrada registrada o revisada
(plan-sac-entrada-editar-sede.md v1.1, GO de QA con C1–C4).

Pedido de Johana (2026-11-19): se equivoco de sede en algunas Entradas y no
podia corregirla. Decisiones de Daniel:
- D1: una desliquidada (revisada con compras vivas) -> 422, anular y recrear.
- D2: cambiar la sede de una revisada NO la devuelve a registrada.
"""
import pytest
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.models.inbound_order import InboundOrderPurchase
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.inventory_movement import InventoryMovement
from app.models.money_movement import MoneyMovement
from app.models.purchase import Purchase
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)
from tests.reparto_slots import con_slots

INBOUND_URL = "/api/v1/inbound-orders"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"

MSG_ESTADO = "la sede ya no se puede cambiar"
MSG_COMPRAS = "ya tuvo compras"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


def _wh(db, org_id, name):
    w = create_warehouse(db, org_id, name)
    db.commit()
    return w


@pytest.fixture
def wh_vieja(db_session, test_organization):
    return _wh(db_session, test_organization.id, "Sede Equivocada")


@pytest.fixture
def wh_nueva(db_session, test_organization):
    return _wh(db_session, test_organization.id, "Sede Correcta")


@pytest.fixture
def sup(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Sede", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def collector(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Recolector Sede", "service_provider"
    )
    db_session.commit()
    return tp


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _profile(client, headers, material_id, *, compra_regular, willard_world):
    resp = client.put(
        f"{PROFILES_URL}/{material_id}", headers=headers,
        json={"compra_regular": compra_regular, "willard_world": willard_world,
              "lead_product": "none"},
    )
    assert resp.status_code == 200, resp.text


def _formula(client, headers, material_id, ftype, params):
    resp = client.post(
        FORMULAS_URL, headers=headers,
        json={"material_id": str(material_id), "formula_type": ftype, "parameters": params},
    )
    assert resp.status_code == 201, resp.text


@pytest.fixture
def mat_compra(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "CHATARRA-SEDE")
    _profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def mat_dross(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "DROSS-SEDE")
    _formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.5})
    _profile(client, org_headers, mat.id, compra_regular=False, willard_world="drosses")
    return mat


@pytest.fixture
def mat_bat(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BAT-SEDE", unit="unidad")
    _formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
    _profile(client, org_headers, mat.id, compra_regular=False, willard_world="postconsumo")
    return mat


def _kg_account(client, headers, code, account_type, titular, warehouse=None):
    body = {
        "code": code, "display_name": code, "account_type": account_type,
        "third_party_id": str(titular.id),
    }
    if warehouse is not None:
        body["warehouse_id"] = str(warehouse.id)
    resp = client.post(f"{KG_URL}/accounts", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _today():
    return business_today().isoformat()


def _capture_compra(client, headers, wh, mat, qty="100"):
    resp = client.post(
        INBOUND_URL, headers=headers,
        json={
            "inbound_type": "purchase", "warehouse_id": str(wh.id), "date": _today(),
            "lines": [{"material_id": str(mat.id), "quantity": qty,
                       "scale_weight_kg": qty}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _capture_willard(client, headers, wh, titular, mat, qty="10"):
    resp = client.post(
        INBOUND_URL, headers=headers,
        json={
            "inbound_type": "willard", "warehouse_id": str(wh.id), "date": _today(),
            "third_party_id": str(titular.id),
            "lines": [{"material_id": str(mat.id), "quantity": qty,
                       "scale_weight_kg": "100"}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _review(client, headers, order_id):
    resp = client.post(f"{INBOUND_URL}/{order_id}/review", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _liquidate(client, headers, order_id, mat, sup, qty="100", **extra):
    resp = client.post(
        f"{INBOUND_URL}/{order_id}/liquidate", headers=headers,
        json=con_slots({"lines": [{
            "material_id": str(mat.id),
            "allocations": [{"third_party_id": str(sup.id), "quantity": qty,
                             "unit_price": "900"}],
            "reference_unit_price": "900",
        }], **extra}),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _patch(client, headers, order_id, body):
    return client.patch(f"{INBOUND_URL}/{order_id}", headers=headers, json=body)


def _sede(client, headers, order_id):
    resp = client.get(f"{INBOUND_URL}/{order_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["warehouse_id"]


def _stock(db, mat, wh):
    db.expire_all()
    return db.execute(
        select(func.coalesce(func.sum(InventoryMovement.quantity), 0)).where(
            InventoryMovement.material_id == mat.id,
            InventoryMovement.warehouse_id == wh.id,
        )
    ).scalar_one()


# ---------------------------------------------------------------------------
# Tipo compra
# ---------------------------------------------------------------------------

class TestEntradaCompra:

    def test_t1_cambiar_y_liquidar_todo_nace_en_la_sede_nueva(
        self, client, org_headers, db_session, wh_vieja, wh_nueva, mat_compra,
        sup, collector,
    ):
        """T1 (C1) — los tres consumidores de la sede al liquidar: compras
        (cabecera y lineas), ajuste de descuadre y comision del recolector, y
        el stock por bodega medido desde los movimientos."""
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra, "100")
        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(wh_nueva.id)})
        assert resp.status_code == 200, resp.text
        assert _sede(client, org_headers, body["id"]) == str(wh_nueva.id)

        _review(client, org_headers, body["id"])
        # 95 repartidos de 100 pesados -> descuadre de 5 (increase)
        _liquidate(
            client, org_headers, body["id"], mat_compra, sup, qty="95",
            collector_commission={"third_party_id": str(collector.id), "amount": "1000"},
        )

        db_session.expire_all()
        compras = db_session.execute(
            select(Purchase)
            .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
            .where(InboundOrderPurchase.inbound_order_id == UUID(body["id"]))
        ).scalars().all()
        assert len(compras) == 1
        assert compras[0].warehouse_id == wh_nueva.id
        assert [line.warehouse_id for line in compras[0].lines] == [wh_nueva.id]

        ajustes = db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.inbound_order_id == UUID(body["id"])
            )
        ).scalars().all()
        assert len(ajustes) == 1, "el escenario necesita descuadre para medir"
        assert ajustes[0].warehouse_id == wh_nueva.id

        comision = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.source_type == "collector_commission",
                MoneyMovement.source_id == UUID(body["id"]),
            )
        ).scalars().all()
        assert len(comision) == 1, "el escenario necesita comision para medir"
        assert comision[0].warehouse_id == wh_nueva.id

        assert _stock(db_session, mat_compra, wh_nueva) == Decimal("100")
        assert _stock(db_session, mat_compra, wh_vieja) == 0

    def test_t2_revisada_sigue_revisada(
        self, client, org_headers, wh_vieja, wh_nueva, mat_compra,
    ):
        """T2 (D2) — la sede es cabecera: no decertifica."""
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        _review(client, org_headers, body["id"])
        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(wh_nueva.id)})
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["status"] == "reviewed"
        assert out["warehouse_id"] == str(wh_nueva.id)

    def test_t3_liquidada_no_se_cambia(
        self, client, org_headers, wh_vieja, wh_nueva, mat_compra, sup,
    ):
        """T3 (C2) — el TEXTO del guard de estado, no el de D1, que tambien
        rechazaria (la liquidada tiene compras vivas)."""
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        _review(client, org_headers, body["id"])
        _liquidate(client, org_headers, body["id"], mat_compra, sup)
        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(wh_nueva.id)})
        assert resp.status_code == 422, resp.text
        assert MSG_ESTADO in resp.json()["detail"]
        assert "liquidada" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(wh_vieja.id)

    def test_t4_desliquidada_no_se_cambia(
        self, client, org_headers, db_session, wh_vieja, wh_nueva, mat_compra, sup,
    ):
        """T4 (D1) — revisada con compras vivas: 422 que nombra la compra."""
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        _review(client, org_headers, body["id"])
        _liquidate(client, org_headers, body["id"], mat_compra, sup)
        resp = client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "reviewed"

        db_session.expire_all()
        numero = db_session.execute(
            select(Purchase.purchase_number)
            .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
            .where(InboundOrderPurchase.inbound_order_id == UUID(body["id"]))
        ).scalar_one()

        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(wh_nueva.id)})
        assert resp.status_code == 422, resp.text
        assert MSG_COMPRAS in resp.json()["detail"]
        assert f"#{numero}" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(wh_vieja.id)

    @pytest.mark.parametrize("caso", ["no_receptora", "inactiva", "otra_org"])
    def test_t5_bodega_invalida(
        self, client, org_headers, db_session, test_organization, test_organization2,
        wh_vieja, mat_compra, caso,
    ):
        """T5 — el mismo validador de create: receptora, activa, de la org."""
        if caso == "otra_org":
            destino = _wh(db_session, test_organization2.id, "Bodega Ajena")
            esperado = 404
        else:
            destino = _wh(db_session, test_organization.id, f"Bodega {caso}")
            if caso == "no_receptora":
                destino.is_receiving = False
                esperado = 422
            else:
                destino.is_active = False
                esperado = 400
            db_session.commit()
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(destino.id)})
        assert resp.status_code == esperado, resp.text
        assert _sede(client, org_headers, body["id"]) == str(wh_vieja.id)

    def test_t6_sede_nula(self, client, org_headers, wh_vieja, mat_compra):
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        resp = _patch(client, org_headers, body["id"], {"warehouse_id": None})
        assert resp.status_code == 422, resp.text
        assert "obligatoria" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(wh_vieja.id)

    def test_t9_misma_sede_en_una_liquidada_es_no_op(
        self, client, org_headers, wh_vieja, mat_compra, sup,
    ):
        """T9 (C3) — sobre un estado donde un CAMBIO se rechazaria: reenviar
        la misma sede no rompe la edicion de la nota."""
        body = _capture_compra(client, org_headers, wh_vieja, mat_compra)
        _review(client, org_headers, body["id"])
        _liquidate(client, org_headers, body["id"], mat_compra, sup)
        resp = _patch(
            client, org_headers, body["id"],
            {"notes": "nota tras liquidar", "warehouse_id": str(wh_vieja.id)},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["notes"] == "nota tras liquidar"
        assert resp.json()["warehouse_id"] == str(wh_vieja.id)


# ---------------------------------------------------------------------------
# Willard
# ---------------------------------------------------------------------------

class TestEntradaWillard:

    def test_t7_drosses_solo_en_planta(
        self, client, org_headers, db_session, test_organization, sup, mat_dross,
    ):
        """T7 — se revalida la captura con la sede nueva."""
        planta = _wh(db_session, test_organization.id, "Juan Mina Sede")
        otra = _wh(db_session, test_organization.id, "Circunvalar Sede")
        test_organization.settings = {
            "kg_ledger_enabled": True, "willard_sede_drosses": str(planta.id),
        }
        db_session.commit()
        _kg_account(client, org_headers, "W-DROSS-SEDE", "willard_drosses", sup)
        body = _capture_willard(client, org_headers, planta, sup, mat_dross, "100")

        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(otra.id)})
        assert resp.status_code == 422, resp.text
        assert "Juan Mina Sede" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(planta.id)

    def test_t7c_lineas_y_sede_en_el_mismo_patch_validan_contra_la_nueva(
        self, client, org_headers, db_session, test_organization, sup, mat_dross,
    ):
        """T7c (O3 de QA) — con `lines` en el payload, el bloque de lineas es
        el que valida, y tiene que hacerlo contra la sede NUEVA: el cambio de
        sede corre antes que ese bloque."""
        planta = _wh(db_session, test_organization.id, "Juan Mina Lineas")
        otra = _wh(db_session, test_organization.id, "Circunvalar Lineas")
        test_organization.settings = {
            "kg_ledger_enabled": True, "willard_sede_drosses": str(planta.id),
        }
        db_session.commit()
        _kg_account(client, org_headers, "W-DROSS-LIN", "willard_drosses", sup)
        body = _capture_willard(client, org_headers, planta, sup, mat_dross, "100")

        resp = _patch(client, org_headers, body["id"], {
            "warehouse_id": str(otra.id),
            "lines": [{"material_id": str(mat_dross.id), "quantity": "120",
                       "scale_weight_kg": "120"}],
        })
        assert resp.status_code == 422, resp.text
        assert "Juan Mina Lineas" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(planta.id)

    def test_t7b_postconsumo_necesita_cuenta_de_baterias(
        self, client, org_headers, db_session, test_organization, sup, mat_bat,
    ):
        """T7b — sin cuenta en el destino: 422. Control positivo: hacia otra
        sede con cuenta del mismo titular, 200."""
        cv = _wh(db_session, test_organization.id, "CV Bat")
        sin_cuenta = _wh(db_session, test_organization.id, "Sin Cuenta")
        con_cuenta = _wh(db_session, test_organization.id, "Con Cuenta")
        _kg_account(client, org_headers, "W-BAT-CV-S", "willard_baterias", sup, cv)
        _kg_account(client, org_headers, "W-BAT-CC-S", "willard_baterias", sup, con_cuenta)
        body = _capture_willard(client, org_headers, cv, sup, mat_bat)

        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(sin_cuenta.id)})
        assert resp.status_code == 422, resp.text
        # O2 de QA: el 422 viene del revalidador, no de otro guard
        assert "No existe cuenta kg activa" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(cv.id)

        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(con_cuenta.id)})
        assert resp.status_code == 200, resp.text
        assert _sede(client, org_headers, body["id"]) == str(con_cuenta.id)

    def test_t8_confirmada_no_se_cambia(
        self, client, org_headers, db_session, test_organization, sup, mat_bat,
    ):
        """T8 (C2) — destino donde la revalidacion PASARIA (cuenta del mismo
        titular): el 422 tiene que venir del guard de estado."""
        cv = _wh(db_session, test_organization.id, "CV Conf")
        con_cuenta = _wh(db_session, test_organization.id, "Con Cuenta Conf")
        _kg_account(client, org_headers, "W-BAT-CV-C", "willard_baterias", sup, cv)
        _kg_account(client, org_headers, "W-BAT-CC-C", "willard_baterias", sup, con_cuenta)
        body = _capture_willard(client, org_headers, cv, sup, mat_bat)
        _review(client, org_headers, body["id"])
        resp = client.post(f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers)
        assert resp.status_code == 200, resp.text

        resp = _patch(client, org_headers, body["id"], {"warehouse_id": str(con_cuenta.id)})
        assert resp.status_code == 422, resp.text
        assert MSG_ESTADO in resp.json()["detail"]
        assert "confirmada" in resp.json()["detail"]
        assert _sede(client, org_headers, body["id"]) == str(cv.id)
