"""
Tests InboundOrder (SAC E2 + recepcion simplificada, plan-sac-recepcion-y-materiales.md).

Cubre: tipo willard (identidad D2 — incluido el guardian sobre pool negativo,
MCH=HOY H1a, kg por linea D5, ruteo cuenta por willard_world del material D1,
mundos mixtos en una orden), derivacion a compras (composabilidad D7, guard D7b,
warehouse header D11), anulacion D8 (remocion ponderada, reversal backdateado,
8a fuente P&L, as-of H2), edicion D18, centro Willard D12, flag gating y RBAC.
Sin subtipo escurrido/pinza (CC-001: son materiales distintos con su factor).
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerMovement
from app.models.material import Material
from app.models.material_cost_history import MaterialCostHistory
from tests.integration_helpers import create_material, create_material_category, create_warehouse
from tests.conftest import create_third_party_with_category
from app.utils.dates import business_today

INBOUND_URL = "/api/v1/inbound-orders"
KG_URL = "/api/v1/kg-ledger"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
PROFILES_URL = "/api/v1/material-kg-profiles"
ADJ_URL = "/api/v1/inventory/adjustments"
PNL_URL = "/api/v1/reports/profit-and-loss"
BS_URL = "/api/v1/reports/balance-sheet"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_kg_ledger_flag(db_session, test_organization, test_organization2):
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Planta CV")
    db_session.commit()
    return wh


@pytest.fixture
def willard_tp(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A.", "material_supplier"
    )
    db_session.commit()
    return tp


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _post_formula(client, headers, material_id, ftype, params):
    body = {"material_id": str(material_id), "formula_type": ftype, "parameters": params}
    resp = client.post(FORMULAS_URL, headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_profile(client, headers, material_id, *, compra_regular=False, willard_world="none"):
    """Clasificacion Willard del material (CC-005): rutea la cuenta kg por linea."""
    resp = client.put(
        f"{PROFILES_URL}/{material_id}",
        headers=headers,
        json={"compra_regular": compra_regular, "willard_world": willard_world},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _seed_avg(client, headers, material_id, warehouse_id, qty, unit_cost):
    """Fija stock y costo promedio via ajuste increase (pool 0 -> avg = cost)."""
    resp = client.post(
        f"{ADJ_URL}/increase",
        headers=headers,
        json={
            "material_id": str(material_id),
            "warehouse_id": str(warehouse_id),
            "quantity": qty,
            "unit_cost": unit_cost,
            "date": business_today().isoformat(),
            "reason": "Seed test",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _decrease(client, headers, material_id, warehouse_id, qty):
    resp = client.post(
        f"{ADJ_URL}/decrease",
        headers=headers,
        json={
            "material_id": str(material_id),
            "warehouse_id": str(warehouse_id),
            "quantity": qty,
            "date": business_today().isoformat(),
            "reason": "Merma test",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def mat_bat(db_session, test_organization, client, org_headers):
    """Bateria (unidad), formula battery_to_lead 2.5, mundo postconsumo."""
    mat = _mat(db_session, test_organization.id, "BAT-GEN", unit="unidad")
    _post_formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


@pytest.fixture
def mat_dross(db_session, test_organization, client, org_headers):
    """Jamiche (kg), formula drosses 0.53, mundo drosses."""
    mat = _mat(db_session, test_organization.id, "JAMICHE", unit="kg")
    _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.53})
    _set_profile(client, org_headers, mat.id, willard_world="drosses")
    return mat


@pytest.fixture
def mat_regular(db_session, test_organization, client, org_headers):
    """Material de compra regular (world=none, compra_regular=True) — los paths
    tipo purchase lo usan desde Ciclo B (B3: mat_dross es Willard-puro y ya no
    entra por compra)."""
    mat = _mat(db_session, test_organization.id, "CHATARRA-REG", unit="kg")
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
    return mat


@pytest.fixture
def kg_bat_account(client, org_headers, warehouse, willard_tp):
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "WILLARD-BAT-CV",
            "display_name": "Willard Baterias CV",
            "account_type": "willard_baterias",
            "warehouse_id": str(warehouse.id),
            "third_party_id": str(willard_tp.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def kg_dross_account(client, org_headers, willard_tp):
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "WILLARD-DROSS",
            "display_name": "Willard Drosses",
            "account_type": "willard_drosses",
            "third_party_id": str(willard_tp.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _inbound(client, headers, *, inbound_type, warehouse_id, third_party_id, lines,
             date_str=None, center=None, **extra):
    body = {
        "inbound_type": inbound_type,
        "warehouse_id": str(warehouse_id),
        "third_party_id": str(third_party_id),
        "date": date_str or business_today().isoformat(),
        "lines": lines,
        **extra,
    }
    if center is not None:
        body["willard_distribution_center"] = center
    return client.post(INBOUND_URL, headers=headers, json=body)


def _kg_movs(db, order_id, status=None):
    q = select(KgLedgerMovement).where(KgLedgerMovement.source_id == order_id)
    if status:
        q = q.where(KgLedgerMovement.status == status)
    return db.execute(q).scalars().all()


def _confirm(client, headers, order_id):
    """B.2: draft -> confirmed — los efectos willard nacen aca (re-semantizacion
    mecanica del 1-paso previo, patron #73/#76)."""
    resp = client.post(f"{INBOUND_URL}/{order_id}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Tipos Willard — create (D2/D4/D5/D6)
# ---------------------------------------------------------------------------

class TestWillardCreate:
    def test_postconsumo_happy_identity(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        db_session.refresh(mat_bat)
        avg_before = mat_bat.current_average_cost
        liq_before = mat_bat.current_stock_liquidated

        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        # B.2: la captura queda Registrada (draft) — los efectos nacen al confirmar
        assert body["status"] == "draft"
        assert body["order_number"] == 1
        body = _confirm(client, org_headers, body["id"])
        assert body["status"] == "confirmed"

        # D2: identidad — avg intacto, stock liquidated sube
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_average_cost == avg_before
        assert mat.current_stock_liquidated == liq_before + 10

        # Snapshot D8 en la linea
        assert Decimal(body["lines"][0]["unit_cost"]) == Decimal("50.00")

        # D5/D6: kg = 10 x 2.5 = 25 al account de la sede
        assert Decimal(body["lines"][0]["kg_lead"]) == Decimal("25")
        assert Decimal(body["total_kg_lead"]) == Decimal("25")
        movs = _kg_movs(db_session, body["id"], "confirmed")
        assert len(movs) == 1
        assert movs[0].account_id.hex == kg_bat_account["id"].replace("-", "")
        assert movs[0].source_type == "postconsumo_receipt"
        assert movs[0].conversion_formula_snapshot["parameters"] == {"kg_lead_per_unit": 2.5}
        # F1 gate: el snapshot ya NO lleva willard_account_subtype (el :307 era un
        # AttributeError post-drop que ni build ni tsc atrapan)
        assert "willard_account_subtype" not in movs[0].conversion_formula_snapshot
        assert movs[0].inventory_movement_id is not None

        # H1a: MCH HOY con prev == new (identidad)
        mch = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_type == "inbound_receipt",
                MaterialCostHistory.source_id == body["id"],
            )
        ).scalar_one()
        assert mch.transaction_date == business_today()
        assert mch.previous_cost == mch.new_cost == avg_before

        # Saldo de la cuenta kg refleja la deuda
        accounts = client.get(f"{KG_URL}/accounts", headers=org_headers).json()
        acc = next(a for a in accounts if a["id"] == kg_bat_account["id"])
        assert Decimal(acc["current_balance_kg"]) == Decimal("25")

    def test_identity_on_negative_pool_guardian(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_dross, kg_dross_account,
    ):
        """Test guardian D2: inbound sobre pool NEGATIVO -> adjustment 0, avg
        intacto (fija la identidad contra 'fixes' futuros)."""
        _seed_avg(client, org_headers, mat_dross.id, warehouse.id, 10, 100)
        _decrease(client, org_headers, mat_dross.id, warehouse.id, 30)  # liq -20
        db_session.expire_all()
        mat = db_session.get(Material, mat_dross.id)
        assert mat.current_stock_liquidated == -20
        avg_before = mat.current_average_cost

        pnl_before = client.get(
            PNL_URL, headers=org_headers,
            params={"date_from": "2020-01-01", "date_to": "2030-01-01"},
        ).json()

        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "5"}],
        )
        assert resp.status_code == 201, resp.text
        _confirm(client, org_headers, resp.json()["id"])

        db_session.expire_all()
        mat = db_session.get(Material, mat_dross.id)
        assert mat.current_average_cost == avg_before  # identidad, sin reset
        assert mat.current_stock_liquidated == -15

        pnl_after = client.get(
            PNL_URL, headers=org_headers,
            params={"date_from": "2020-01-01", "date_to": "2030-01-01"},
        ).json()
        assert pnl_after["oversell_cost_adjustment"] == pnl_before["oversell_cost_adjustment"]

    def test_drosses_kg_by_percentage(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_dross, kg_dross_account,
    ):
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "1000"}],
        )
        assert resp.status_code == 201, resp.text
        body = _confirm(client, org_headers, resp.json()["id"])
        # 1000 kg x 0.53 = 530 kg plomo — cuenta org-wide
        assert Decimal(body["total_kg_lead"]) == Decimal("530")
        movs = _kg_movs(db_session, body["id"], "confirmed")
        assert movs[0].source_type == "drosses_receipt"

    def test_mixed_worlds_rejected_homogeneity(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, mat_dross, kg_bat_account, kg_dross_account,
    ):
        """Ciclo B (B2, Q-10): una recepcion Willard es de UN solo mundo —
        camion mixto = dos recepciones. Re-semantiza el viejo
        test_mixed_worlds_route_per_line (D1 sigue vigente como MECANISMO de
        ruteo por linea; lo que cambio es que una orden no mezcla mundos)."""
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[
                {"material_id": str(mat_bat.id), "quantity": "10"},
                {"material_id": str(mat_dross.id), "quantity": "100"},
            ],
        )
        assert resp.status_code == 422, resp.text
        assert "dos recepciones" in resp.json()["detail"]

    def test_material_without_willard_profile_422(
        self, client, org_headers, db_session, test_organization,
        warehouse, willard_tp, kg_dross_account,
    ):
        """Un material sin clasificacion Willard (o world=none) no puede recibirse
        en una orden Willard — se recibe como Compra regular."""
        mat = _mat(db_session, test_organization.id, "COMPRA-ONLY", unit="kg")
        _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.5})
        _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="none")
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat.id), "quantity": "100"}],
        )
        assert resp.status_code == 422
        assert "mundo Willard" in resp.json()["detail"]

    def test_no_formula_422(
        self, client, org_headers, db_session, test_organization,
        warehouse, willard_tp, kg_bat_account,
    ):
        """Material clasificado Willard pero sin factor vigente -> 422."""
        mat = _mat(db_session, test_organization.id, "BAT-SIN-F", unit="unidad")
        _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat.id), "quantity": "3"}],
        )
        assert resp.status_code == 422
        assert "formula" in resp.json()["detail"]

    def test_no_kg_account_422(
        self, client, org_headers, warehouse, willard_tp, mat_bat,
    ):
        # Sin fixture kg_bat_account
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        )
        assert resp.status_code == 422
        assert "cuenta kg" in resp.json()["detail"]

    def test_collapsed_types_rejected_422(self, client, org_headers, warehouse, willard_tp, mat_bat):
        """CC-004: los tipos viejos (reventa/ruta/postconsumo_baterias/drosses)
        ya no son validos — el schema solo acepta purchase | willard."""
        for dead_type in ("reventa", "ruta", "postconsumo_baterias", "drosses"):
            resp = _inbound(
                client, org_headers,
                inbound_type=dead_type,
                warehouse_id=warehouse.id,
                third_party_id=willard_tp.id,
                lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
            )
            assert resp.status_code == 422, f"{dead_type}: {resp.text}"

    def test_future_date_422(self, client, org_headers, warehouse, willard_tp, mat_bat):
        future = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            date_str=future,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        )
        assert resp.status_code == 422

    def test_willard_center_validation(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account,
    ):
        # Invalido -> 422 con lista de validos
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            center="cartagena",
            lines=[{"material_id": str(mat_bat.id), "quantity": "1"}],
        )
        assert resp.status_code == 422
        assert "no configurado" in resp.json()["detail"]
        # Valido (default D12) -> 201
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            center="monteria",
            lines=[{"material_id": str(mat_bat.id), "quantity": "1"}],
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["willard_distribution_center"] == "monteria"


# ---------------------------------------------------------------------------
# Derivacion a compras (D7/D7b/D11)
# ---------------------------------------------------------------------------

class TestPurchaseDerivation:
    def _create_purchase_order(self, client, org_headers, warehouse, willard_tp, material,
                               inbound_type="purchase", unit_price="1200", date_str=None):
        return _inbound(
            client, org_headers,
            inbound_type=inbound_type,
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            date_str=date_str,
            lines=[{
                "material_id": str(material.id),
                "quantity": "500",
                "unit_price": unit_price,
            }],
        )

    def test_purchase_type_derives_registered(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular,
    ):
        resp = self._create_purchase_order(client, org_headers, warehouse, willard_tp, mat_regular)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["purchase_id"] is not None
        assert body["purchase_status"] == "registered"
        assert body["total_kg_lead"] is None  # no toca cuentas kg (D7)
        assert _kg_movs(db_session, body["id"]) == []

        # Derivada con header D11 y stock en transito
        purchase = client.get(
            f"/api/v1/purchases/{body['purchase_id']}", headers=org_headers
        ).json()
        assert purchase["status"] == "registered"
        assert purchase["lines"][0]["warehouse_id"] == str(warehouse.id)
        # Ciclo B (B1): la derivada expone su origen
        assert purchase["inbound_order_id"] == body["id"]
        assert purchase["inbound_order_number"] == body["order_number"]
        db_session.expire_all()
        mat = db_session.get(Material, mat_regular.id)
        assert mat.current_stock_transit == 500

    def test_direct_cancel_of_derived_400(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        body = self._create_purchase_order(
            client, org_headers, warehouse, willard_tp, mat_regular
        ).json()
        resp = client.patch(
            f"/api/v1/purchases/{body['purchase_id']}/cancel", headers=org_headers
        )
        assert resp.status_code == 400
        assert f"orden de recepción #{body['order_number']}" in resp.json()["detail"]

    def test_annul_order_cancels_registered_purchase(
        self, client, org_headers, db_session, warehouse, willard_tp, mat_regular,
    ):
        body = self._create_purchase_order(
            client, org_headers, warehouse, willard_tp, mat_regular
        ).json()
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul",
            headers=org_headers,
            json={"reason": "Captura erronea"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "annulled"
        purchase = client.get(
            f"/api/v1/purchases/{body['purchase_id']}", headers=org_headers
        ).json()
        assert purchase["status"] == "cancelled"
        db_session.expire_all()
        mat = db_session.get(Material, mat_regular.id)
        assert mat.current_stock_transit == 0

    def test_annul_order_with_liquidated_purchase_400(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        # Fecha pasada para no chocar con el boundary UTC vs local de la
        # validacion de liquidacion de compras (date.today() local) — la orden
        # y la liquidacion comparten fecha en cualquier zona horaria.
        past = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        body = self._create_purchase_order(
            client, org_headers, warehouse, willard_tp, mat_regular, date_str=past
        ).json()
        liq = client.patch(
            f"/api/v1/purchases/{body['purchase_id']}/liquidate",
            headers=org_headers,
            json={"liquidation_date": past},
        )
        assert liq.status_code == 200, liq.text
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul",
            headers=org_headers,
            json={"reason": "x"},
        )
        assert resp.status_code == 400
        assert "Cancele primero la compra" in resp.json()["detail"]

    def test_edit_derived_purchase_allowed(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        """D7b: el edit de la derivada se permite (flujo Erwin §7.2)."""
        body = self._create_purchase_order(
            client, org_headers, warehouse, willard_tp, mat_regular
        ).json()
        resp = client.patch(
            f"/api/v1/purchases/{body['purchase_id']}",
            headers=org_headers,
            json={
                "lines": [{
                    "material_id": str(mat_regular.id),
                    "warehouse_id": str(warehouse.id),
                    "quantity": 450,
                    "unit_price": 1300,
                }]
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["lines"][0]["quantity"] == 450

    def test_supplier_behavior_enforced(
        self, client, org_headers, db_session, test_organization, warehouse, mat_regular,
    ):
        generic_tp = create_third_party_with_category(
            db_session, test_organization.id, "Generico X", "generic"
        )
        db_session.commit()
        resp = _inbound(
            client, org_headers,
            inbound_type="purchase",
            warehouse_id=warehouse.id,
            third_party_id=generic_tp.id,
            lines=[{"material_id": str(mat_regular.id), "quantity": "10"}],
        )
        assert resp.status_code == 400
        assert "proveedor de material" in resp.json()["detail"]

    def test_purchase_header_warehouse_forces_lines_direct_api(
        self, client, org_headers, db_session, test_organization,
        warehouse, willard_tp, mat_regular,
    ):
        """D11 directo en /purchases: header fuerza lineas aunque difieran."""
        other_wh = create_warehouse(db_session, test_organization.id, "Bodega Otra")
        db_session.commit()
        resp = client.post(
            "/api/v1/purchases",
            headers=org_headers,
            json={
                "supplier_id": str(willard_tp.id),
                "date": business_today().isoformat(),
                "warehouse_id": str(warehouse.id),
                "lines": [{
                    "material_id": str(mat_regular.id),
                    "warehouse_id": str(other_wh.id),  # difiere -> forzada
                    "quantity": 100,
                    "unit_price": 900,
                }],
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["lines"][0]["warehouse_id"] == str(warehouse.id)

        # Y el full edit valida contra el header (422 si difiere)
        pid = resp.json()["id"]
        resp = client.patch(
            f"/api/v1/purchases/{pid}",
            headers=org_headers,
            json={
                "lines": [{
                    "material_id": str(mat_regular.id),
                    "warehouse_id": str(other_wh.id),
                    "quantity": 100,
                    "unit_price": 900,
                }]
            },
        )
        assert resp.status_code == 422
        assert "bodega de cabecera" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Anulacion Willard (D8)
# ---------------------------------------------------------------------------

class TestWillardAnnul:
    def test_annul_round_trip(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        order_date = (datetime.now(timezone.utc) - timedelta(days=5)).date()
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            date_str=order_date.isoformat(),
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        ).json()
        _confirm(client, org_headers, body["id"])

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul",
            headers=org_headers,
            json={"reason": "Doble digitacion"},
        )
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["status"] == "annulled"
        assert out["warnings"] == []

        # Stock y avg de vuelta al origen (round-trip identidad)
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_stock_liquidated == 100
        assert mat.current_average_cost == Decimal("50.0000")

        # kg movements anulados -> saldo cuenta 0
        assert all(m.status == "annulled" for m in _kg_movs(db_session, body["id"]))
        accounts = client.get(f"{KG_URL}/accounts", headers=org_headers).json()
        acc = next(a for a in accounts if a["id"] == kg_bat_account["id"])
        assert Decimal(acc["current_balance_kg"]) == 0

        # Reversal backdateado a order.date (doctrina #41: la orden anulada
        # desaparece de TODOS los cortes) y MCH annulment HOY
        reversal = db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == body["id"],
                InventoryMovement.movement_type == "inbound_reversal",
            )
        ).scalar_one()
        assert reversal.date.date() == order_date  # NO hoy — backdateado
        mch = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_type == "inbound_annulment",
                MaterialCostHistory.source_id == body["id"],
            )
        ).scalar_one()
        assert mch.transaction_date == business_today()

        # Identidad limpia -> sin diferencia de remocion
        detail = client.get(f"{INBOUND_URL}/{body['id']}", headers=org_headers).json()
        assert detail["status"] == "annulled"

    def test_annul_with_value_extraction_conserves_via_pnl(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_dross, kg_dross_account,
    ):
        """Conservacion D8: si el avg cambio entre entrada y anulacion, la
        diferencia de remocion cae a annul_cost_adjustment y entra a la linea
        P&L de reversiones (fechada annulled_at)."""
        _seed_avg(client, org_headers, mat_dross.id, warehouse.id, 10, 100)
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_dross.id), "quantity": "50"}],
        ).json()
        _confirm(client, org_headers, body["id"])  # entra 50 @ 100 (identidad) -> pool 60 @ 100

        _decrease(client, org_headers, mat_dross.id, warehouse.id, 55)  # pool 5 @ 100
        _seed_avg(client, org_headers, mat_dross.id, warehouse.id, 45, 20)  # pool 50 @ 28

        pnl_before = client.get(
            PNL_URL, headers=org_headers,
            params={"date_from": "2020-01-01", "date_to": "2030-01-01"},
        ).json()

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul",
            headers=org_headers,
            json={"reason": "Reversa con extraccion"},
        )
        assert resp.status_code == 200, resp.text

        # remove_from_pool(50, 28, 50, 100): valor insuficiente ->
        # avg queda, adj = 50 x (100 - 28) = 3600
        from app.models.inbound_order import InboundOrder
        order = db_session.get(InboundOrder, body["id"])
        db_session.refresh(order)
        assert order.annul_cost_adjustment == Decimal("3600.00")

        pnl_after = client.get(
            PNL_URL, headers=org_headers,
            params={"date_from": "2020-01-01", "date_to": "2030-01-01"},
        ).json()
        delta = pnl_after["oversell_cost_adjustment"] - pnl_before["oversell_cost_adjustment"]
        assert delta == pytest.approx(3600.0, abs=0.01)

    def test_annul_already_annulled_422(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "1"}],
        ).json()
        client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers, json={"reason": "a"}
        )
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers, json={"reason": "b"}
        )
        assert resp.status_code == 400

    def test_annulled_inbound_invisible_in_historic_cut(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """Extension H2: la orden anulada desaparece del corte as-of (reversal
        backdateado neutraliza cantidad + MCH inbound_receipt excluido)."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        today = business_today().isoformat()

        bs_seed = client.get(
            BS_URL, headers=org_headers, params={"as_of_date": today}
        ).json()
        inv_seed = bs_seed["assets"]["inventory"]

        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        ).json()
        _confirm(client, org_headers, body["id"])
        bs_with = client.get(
            BS_URL, headers=org_headers, params={"as_of_date": today}
        ).json()
        assert bs_with["assets"]["inventory"] == pytest.approx(inv_seed + 500.0, abs=0.01)

        client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers, json={"reason": "x"}
        )
        bs_after = client.get(
            BS_URL, headers=org_headers, params={"as_of_date": today}
        ).json()
        assert bs_after["assets"]["inventory"] == pytest.approx(inv_seed, abs=0.01)


# ---------------------------------------------------------------------------
# Edicion (D18)
# ---------------------------------------------------------------------------

class TestEditD18:
    def test_edit_willard_lines_reapply(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        ).json()
        _confirm(client, org_headers, body["id"])

        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={"lines": [{"material_id": str(mat_bat.id), "quantity": "7"}]},
        )
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["status"] == "confirmed"
        assert Decimal(out["lines"][0]["quantity"]) == Decimal("7")
        assert Decimal(out["total_kg_lead"]) == Decimal("17.5")  # 7 x 2.5

        # Stock refleja SOLO las lineas nuevas (revert-and-reapply)
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_stock_liquidated == 107
        assert mat.current_average_cost == Decimal("50.0000")

        # kg viejos anulados, uno nuevo confirmado
        movs = _kg_movs(db_session, body["id"])
        confirmed = [m for m in movs if m.status == "confirmed"]
        annulled = [m for m in movs if m.status == "annulled"]
        assert len(confirmed) == 1 and len(annulled) == 1
        assert confirmed[0].delta_kg == Decimal("17.5")

    def test_edit_header_only_no_reapply(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        ).json()
        _confirm(client, org_headers, body["id"])
        mov_ids_before = {m.id for m in _kg_movs(db_session, body["id"], "confirmed")}

        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={"willard_distribution_center": "baq"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["willard_distribution_center"] == "baq"
        db_session.expire_all()
        mov_ids_after = {m.id for m in _kg_movs(db_session, body["id"], "confirmed")}
        assert mov_ids_before == mov_ids_after  # sin re-apply

    def test_edit_date_moves_kg_events(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "10"}],
        ).json()
        _confirm(client, org_headers, body["id"])
        new_date = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}", headers=org_headers, json={"date": new_date}
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        confirmed = _kg_movs(db_session, body["id"], "confirmed")
        assert len(confirmed) == 1
        assert confirmed[0].transaction_date.date().isoformat() == new_date

    def test_edit_purchase_type_lines_422(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="purchase",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_regular.id), "quantity": "100", "unit_price": "900"}],
        ).json()
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={"lines": [{"material_id": str(mat_regular.id), "quantity": "90"}]},
        )
        assert resp.status_code == 422
        assert "compra derivada" in resp.json()["detail"]
        # Cabecera sin efectos SI se permite (goes_directly_to_jm ya no existe
        # — B4 Ciclo B; driver_id es el campo de cabecera editable)
        drv = client.post(
            "/api/v1/drivers", headers=org_headers, json={"name": "Pedro Conductor"}
        ).json()
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={"driver_id": drv["id"]},
        )
        assert resp.status_code == 200

    def test_edit_annulled_404(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_bat.id), "quantity": "1"}],
        ).json()
        client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers, json={"reason": "a"}
        )
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={"willard_distribution_center": "baq"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# B.2 — Willard a 2 pasos: capturar (draft) -> confirmar (efectos)
# ---------------------------------------------------------------------------

class TestWillardTwoStep:
    def _capture(self, client, org_headers, warehouse, willard_tp, material,
                 qty="10", date_str=None):
        resp = _inbound(
            client, org_headers,
            inbound_type="willard",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            date_str=date_str,
            lines=[{"material_id": str(material.id), "quantity": qty}],
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    def test_capture_draft_zero_effects(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """B.2: la captura es SOLO documento — cero inventario, cero kg, cero MCH."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        db_session.refresh(mat_bat)
        avg_before = mat_bat.current_average_cost
        liq_before = mat_bat.current_stock_liquidated

        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        assert body["status"] == "draft"
        # Documento visible, efectos ausentes
        assert body["lines"][0]["unit_cost"] is None  # snapshot D8 nace al confirmar
        assert body["lines"][0]["kg_lead"] is None
        assert body["total_kg_lead"] is None

        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_average_cost == avg_before
        assert mat.current_stock_liquidated == liq_before
        assert _kg_movs(db_session, body["id"]) == []
        movs = db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == body["id"]
            )
        ).scalars().all()
        assert movs == []
        mch = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_id == body["id"]
            )
        ).scalars().all()
        assert mch == []

    def test_confirm_effects_identical_to_one_step(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """W1: el confirm produce EXACTAMENTE los efectos del 1-paso previo —
        identidad D2, snapshot D8, kg D5, MCH HOY (H1a) e InventoryMovement en
        la fecha de la ORDEN (D4) aunque la confirmacion sea dias despues
        (simulado con orden backdateada)."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        db_session.refresh(mat_bat)
        avg_before = mat_bat.current_average_cost
        order_date = (datetime.now(timezone.utc) - timedelta(days=4)).date()

        body = self._capture(
            client, org_headers, warehouse, willard_tp, mat_bat,
            date_str=order_date.isoformat(),
        )
        body = _confirm(client, org_headers, body["id"])
        assert body["status"] == "confirmed"

        # Identidad D2 + snapshot D8 + kg D5 (mismos asserts del happy 1-paso)
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_average_cost == avg_before
        assert mat.current_stock_liquidated == 110
        assert Decimal(body["lines"][0]["unit_cost"]) == Decimal("50.00")
        assert Decimal(body["total_kg_lead"]) == Decimal("25")

        # D4: la CANTIDAD vive en la fecha de negocio (orden), no en la del confirm
        mov = db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == body["id"],
                InventoryMovement.movement_type == "inbound_receipt",
            )
        ).scalar_one()
        assert mov.date.date() == order_date
        kg = _kg_movs(db_session, body["id"], "confirmed")
        assert len(kg) == 1
        assert kg[0].transaction_date.date() == order_date

        # H1a: MCH fechado HOY (dia de la confirmacion — checkpoint al escribir)
        mch = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_type == "inbound_receipt",
                MaterialCostHistory.source_id == body["id"],
            )
        ).scalar_one()
        assert mch.transaction_date == business_today()
        assert mch.previous_cost == mch.new_cost == avg_before

    def test_confirm_twice_400(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account,
    ):
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        _confirm(client, org_headers, body["id"])
        resp = client.post(f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers)
        assert resp.status_code == 400
        assert "ya esta confirmada" in resp.json()["detail"]

    def test_confirm_purchase_type_400(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        body = _inbound(
            client, org_headers,
            inbound_type="purchase",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_regular.id), "quantity": "100",
                    "unit_price": "900"}],
        ).json()
        resp = client.post(f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers)
        assert resp.status_code == 400
        assert "compra derivada" in resp.json()["detail"]

    def test_confirm_annulled_400(
        self, client, org_headers, warehouse, willard_tp, mat_bat, kg_bat_account,
    ):
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "capturada por error"},
        )
        resp = client.post(f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers)
        assert resp.status_code == 400
        assert "anulada" in resp.json()["detail"]

    def test_confirm_rbac_no_liquidate_403(
        self, client, org_headers, org_headers2, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """Viewer tiene purchases.view pero NO purchases.liquidate — el split
        David captura / Johana confirma vive en ese permiso."""
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        resp = client.post(f"{INBOUND_URL}/{body['id']}/confirm", headers=org_headers2)
        assert resp.status_code == 403

    def test_draft_edit_simple_then_confirm(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """Editar un draft es reemplazo simple (cero reversa, cero MCH); el
        confirm posterior refleja las lineas NUEVAS."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        new_date = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}",
            headers=org_headers,
            json={
                "lines": [{"material_id": str(mat_bat.id), "quantity": "7"}],
                "date": new_date,
            },
        )
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["status"] == "draft"
        assert Decimal(out["lines"][0]["quantity"]) == Decimal("7")
        # Sin efectos ni rastro de reversa
        assert _kg_movs(db_session, body["id"]) == []
        assert db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_id == body["id"]
            )
        ).scalars().all() == []

        confirmed = _confirm(client, org_headers, body["id"])
        assert Decimal(confirmed["total_kg_lead"]) == Decimal("17.5")  # 7 x 2.5
        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_stock_liquidated == 107
        kg = _kg_movs(db_session, body["id"], "confirmed")
        assert len(kg) == 1 and kg[0].transaction_date.date().isoformat() == new_date

    def test_draft_annul_no_reversal(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """Anular un draft es solo status + auditoria — no movio nada, no
        reversa nada (ni inbound_reversal ni MCH ni adjustment)."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "camion devuelto"},
        )
        assert resp.status_code == 200, resp.text
        out = resp.json()
        assert out["status"] == "annulled"
        assert out["annulled_reason"] == "camion devuelto"

        db_session.expire_all()
        mat = db_session.get(Material, mat_bat.id)
        assert mat.current_stock_liquidated == 100  # intacto
        assert db_session.execute(
            select(InventoryMovement).where(
                InventoryMovement.reference_id == body["id"]
            )
        ).scalars().all() == []
        assert db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.source_id == body["id"]
            )
        ).scalars().all() == []
        from app.models.inbound_order import InboundOrder
        order = db_session.get(InboundOrder, body["id"])
        assert order.annul_cost_adjustment == 0

    def test_formula_changed_between_capture_and_confirm(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """#35 append-only: si la formula cambio entre captura y confirmacion,
        el confirm aplica la VIGENTE al confirmar (el estimado de captura era
        preview)."""
        body = self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        # Nueva version de la formula: 2.5 -> 3.0 kg/unidad
        _post_formula(
            client, org_headers, mat_bat.id, "battery_to_lead",
            {"kg_lead_per_unit": 3.0},
        )
        confirmed = _confirm(client, org_headers, body["id"])
        assert Decimal(confirmed["total_kg_lead"]) == Decimal("30")  # 10 x 3.0
        kg = _kg_movs(db_session, body["id"], "confirmed")
        assert kg[0].conversion_formula_snapshot["parameters"] == {"kg_lead_per_unit": 3.0}

    def test_purchase_type_still_confirmed_on_create(
        self, client, org_headers, warehouse, willard_tp, mat_regular,
    ):
        """El tipo compra queda intacto: nace confirmed y su 2-pasos vive en la
        Purchase derivada (registered -> liquidar en Compras)."""
        body = _inbound(
            client, org_headers,
            inbound_type="purchase",
            warehouse_id=warehouse.id,
            third_party_id=willard_tp.id,
            lines=[{"material_id": str(mat_regular.id), "quantity": "100",
                    "unit_price": "900"}],
        ).json()
        assert body["status"] == "confirmed"
        assert body["purchase_status"] == "registered"

    def test_draft_invisible_in_kg_and_balance(
        self, client, org_headers, db_session, warehouse, willard_tp,
        mat_bat, kg_bat_account,
    ):
        """Un draft no toca ni el saldo kg ni el balance — solo existe como
        documento en la bandeja."""
        _seed_avg(client, org_headers, mat_bat.id, warehouse.id, 100, 50)
        today = business_today().isoformat()
        bs_before = client.get(
            BS_URL, headers=org_headers, params={"as_of_date": today}
        ).json()
        self._capture(client, org_headers, warehouse, willard_tp, mat_bat)
        bs_after = client.get(
            BS_URL, headers=org_headers, params={"as_of_date": today}
        ).json()
        assert bs_after["assets"]["inventory"] == bs_before["assets"]["inventory"]
        accounts = client.get(f"{KG_URL}/accounts", headers=org_headers).json()
        acc = next(a for a in accounts if a["id"] == kg_bat_account["id"])
        assert Decimal(acc["current_balance_kg"]) == 0


# ---------------------------------------------------------------------------
# Flag gating + RBAC
# ---------------------------------------------------------------------------

class TestGatingAndRbac:
    def test_flag_off_403(self, client, org_headers, db_session, test_organization):
        test_organization.settings = {}
        db_session.commit()
        resp = client.get(INBOUND_URL, headers=org_headers)
        assert resp.status_code == 403
        assert "habilitado" in resp.json()["detail"]

    def test_viewer_can_view_not_create(self, client, org_headers2, warehouse):
        """D13: reusa purchases.* — viewer tiene view pero no create."""
        resp = client.get(INBOUND_URL, headers=org_headers2)
        assert resp.status_code == 200
        resp = client.post(
            INBOUND_URL,
            headers=org_headers2,
            json={
                "inbound_type": "purchase",
                "warehouse_id": str(warehouse.id),
                "third_party_id": str(warehouse.id),
                "date": business_today().isoformat(),
                "lines": [{"material_id": str(warehouse.id), "quantity": "1"}],
            },
        )
        assert resp.status_code == 403
