"""
Tests SAC #93 — Entrada sin proveedor: reparto al liquidar y descuadre
(plan-sac-entrada-sin-proveedor.md v1.4, GO).

Cobertura de los criterios de aceptacion §7 (los backend-testables):
- Captura y revision: 1, 2, 3, 5 (+ guards de captura).
- Reparto y descuadre: 6-15.
- Invariantes: 16 (estrella), 17, 18, 21 (+ 20/33 sobre el annul W-1).
- Reversas: 22-26, 34, 35.
- Atomicidad: 27.
- No-regresion: 28, 29 (30 lo cubren las suites existentes; 31 es el golden).
- Estabilidad temporal D21: 32.
- D11: comision UNA por entrada; D12: remision/factura separadas.

El criterio 19 (una sola vez en la bandeja) usa 13 proveedores — el numero
del Excel real de Johana (entrada 15.422).
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.core.security import get_password_hash  # noqa: F401  (usado en fixtures)
from app.models.inbound_order import InboundLineAllocation, InboundOrderPurchase
from app.models.inventory_adjustment import InventoryAdjustment
from app.models.material import Material
from app.models.material_cost_history import MaterialCostHistory
from app.models.money_movement import MoneyMovement
from app.models.user import OrganizationMember
from app.models.purchase import Purchase
from app.models.role import Role
from app.models.third_party import ThirdParty
from app.models.user import User
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

INBOUND_URL = "/api/v1/inbound-orders"
PURCHASES_URL = "/api/v1/purchases"
ADJUSTMENTS_URL = "/api/v1/inventory/adjustments"
PROFILES_URL = "/api/v1/material-kg-profiles"
REPORTS_URL = "/api/v1/reports"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar 93")
    db_session.commit()
    return w


def _supplier(db, org_id, name):
    tp = create_third_party_with_category(db, org_id, name, "material_supplier")
    db.commit()
    return tp


@pytest.fixture
def sup1(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor Uno 93")


@pytest.fixture
def sup2(db_session, test_organization):
    return _supplier(db_session, test_organization.id, "Proveedor Dos 93")


@pytest.fixture
def collector(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Green Loop 93", "service_provider"
    )
    db_session.commit()
    return tp


def _mat(db, org_id, code, unit="kg"):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _set_profile(client, headers, material_id, *, compra_regular=True, willard_world="none"):
    resp = client.put(
        f"{PROFILES_URL}/{material_id}",
        headers=headers,
        json={"compra_regular": compra_regular, "willard_world": willard_world},
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture
def mat_moto(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "MOTO-93", unit="kg")
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def mat_balancin(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BALANCIN-93", unit="unidad")
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def mat_grupo4(db_session, test_organization, client, org_headers):
    """Material de truncamiento — reportado por proveedores, no pesado."""
    mat = _mat(db_session, test_organization.id, "GRUPO4-93", unit="unidad")
    _set_profile(client, org_headers, mat.id)
    return mat


@pytest.fixture
def revisor_headers(client, db_session, test_organization):
    """Usuario con rol custom que SI tiene purchases.review (D10 positivo —
    el admin bypassa y no prueba nada)."""
    from app.models.permission import Permission
    from app.models.role import RolePermission
    from app.core.security import create_access_token

    user = User(
        email="revisor-93@example.com",
        hashed_password=get_password_hash("pass1234"),
        full_name="Revisor 93",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    role = Role(
        organization_id=test_organization.id,
        name="revisor_inventario_test",
        display_name="Revisor Test",
        is_system_role=False,
    )
    db_session.add(role)
    db_session.flush()
    perm_codes = ["purchases.view", "purchases.review"]
    perms = db_session.execute(
        select(Permission).where(Permission.code.in_(perm_codes))
    ).scalars().all()
    assert len(perms) == len(perm_codes), "catalogo sin purchases.review"
    for p in perms:
        db_session.add(RolePermission(role_id=role.id, permission_id=p.id))
    db_session.add(OrganizationMember(
        user_id=user.id, organization_id=test_organization.id, role_id=role.id,
    ))
    db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(test_organization.id),
    }


def _past(days=2):
    # 🔴 Reloj de NEGOCIO, no UTC (#91/#92). `now(utc) - 1 dia` NO es "ayer"
    # entre las 19:00 y las 24:00 hora Colombia: es HOY, porque en esa franja la
    # fecha UTC ya avanzo. Con eso, `_past(1)` caia sobre el mismo dia en que el
    # servicio fecha la liquidacion y el corte "de ayer" si cambiaba.
    return (business_today() - timedelta(days=days)).isoformat()


def _capture(client, headers, wh, lines, expect=201, **extra):
    resp = client.post(
        INBOUND_URL, headers=headers,
        json={
            "inbound_type": "purchase",
            "warehouse_id": str(wh.id),
            "date": _past(),
            "lines": lines,
            **extra,
        },
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _line(mat, qty, price=None, weight="100"):
    """Q-13: toda linea llega pesada — el peso es opcional al capturar pero
    obligatorio al REVISAR. `weight=None` captura sin peso a proposito."""
    body = {"material_id": str(mat.id), "quantity": str(qty)}
    if price is not None:
        body["unit_price"] = str(price)
    if weight is not None:
        body["scale_weight_kg"] = str(weight)
    return body


def _review(client, headers, order_id, expect=200):
    resp = client.post(f"{INBOUND_URL}/{order_id}/review", headers=headers)
    assert resp.status_code == expect, resp.text
    return resp.json()


def _alloc(tp, qty, price=None, invoice=None, total=None, per_kg=None):
    """Q-15 + modo por kg: EXACTAMENTE uno de los tres precios."""
    body = {"third_party_id": str(tp.id), "quantity": str(qty)}
    if price is not None:
        body["unit_price"] = str(price)
    if total is not None:
        body["total_price"] = str(total)
    if per_kg is not None:
        body["price_per_kg"] = str(per_kg)
    if invoice:
        body["invoice_number"] = invoice
    return body


def _liq_line(mat, allocations, ref_price=None, unallocated=False):
    body = {"material_id": str(mat.id), "allocations": allocations}
    if ref_price is not None:
        body["reference_unit_price"] = str(ref_price)
    if unallocated:
        body["unallocated_intentional"] = True
    return body


def _liquidate(client, headers, order_id, lines, expect=200, **extra):
    resp = client.post(
        f"{INBOUND_URL}/{order_id}/liquidate", headers=headers,
        json={"lines": lines, **extra},
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _captured_reviewed(client, headers, wh, lines, **extra):
    body = _capture(client, headers, wh, lines, **extra)
    _review(client, headers, body["id"])
    return body


def _order_purchases(db, order_id):
    db.expire_all()
    return db.execute(
        select(Purchase)
        .join(InboundOrderPurchase, InboundOrderPurchase.purchase_id == Purchase.id)
        .where(InboundOrderPurchase.inbound_order_id == UUID(str(order_id)))
        .order_by(Purchase.purchase_number)
    ).scalars().all()


def _order_adjustments(db, order_id):
    db.expire_all()
    return db.execute(
        select(InventoryAdjustment).where(
            InventoryAdjustment.inbound_order_id == UUID(str(order_id))
        )
    ).scalars().all()


def _entrada_accruals(db, order_id):
    db.expire_all()
    return db.execute(
        select(MoneyMovement).where(
            MoneyMovement.source_type == "collector_commission",
            MoneyMovement.source_id == UUID(str(order_id)),
        )
    ).scalars().all()


def _fresh(db, obj):
    db.expire_all()
    return db.get(type(obj), obj.id)


# ---------------------------------------------------------------------------
# Captura y revision (criterios 1, 2, 3, 5)
# ---------------------------------------------------------------------------

class TestCaptura:
    def test_capture_without_supplier_zero_effects(
        self, client, org_headers, db_session, wh, mat_moto
    ):
        """Criterio 1: entrada tipo compra sin proveedor — cero efectos."""
        stock0 = mat_moto.current_stock
        avg0 = mat_moto.current_average_cost

        body = _capture(
            client, org_headers, wh, [_line(mat_moto, "1018")],
            remission_number="REM-15422",
        )
        assert body["third_party_id"] is None
        assert body["status"] == "draft"
        assert body["display_status"] == "registered"
        assert body["remission_number"] == "REM-15422"
        assert body["purchases"] == []

        m = _fresh(db_session, mat_moto)
        assert m.current_stock == stock0
        assert m.current_stock_transit == 0
        assert m.current_average_cost == avg0
        assert _order_purchases(db_session, body["id"]) == []

    def test_capture_with_supplier_rejected(
        self, client, org_headers, wh, mat_moto, sup1
    ):
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "purchase",
                "warehouse_id": str(wh.id),
                "third_party_id": str(sup1.id),
                "date": _past(),
                "lines": [_line(mat_moto, "10")],
            },
        )
        assert resp.status_code == 422
        assert "reparto" in resp.json()["detail"]

    def test_capture_duplicate_material_rejected(
        self, client, org_headers, wh, mat_moto
    ):
        """Criterio 5: dos lineas con el mismo material -> rechazado (D3)."""
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "purchase",
                "warehouse_id": str(wh.id),
                "date": _past(),
                "lines": [_line(mat_moto, "10"), _line(mat_moto, "5")],
            },
        )
        assert resp.status_code == 422
        assert "una fila por material" in resp.json()["detail"]

    def test_capture_invoice_rejected_use_remission(
        self, client, org_headers, wh, mat_moto
    ):
        """D12: la factura llega con la liquidacion, por proveedor."""
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "purchase",
                "warehouse_id": str(wh.id),
                "date": _past(),
                "invoice_number": "FAC-1",
                "lines": [_line(mat_moto, "10")],
            },
        )
        assert resp.status_code == 422
        assert "liquidar" in resp.json()["detail"]

    def test_capture_qty_zero_rejected(self, client, org_headers, wh, mat_moto):
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "purchase",
                "warehouse_id": str(wh.id),
                "date": _past(),
                "lines": [_line(mat_moto, "0")],
            },
        )
        assert resp.status_code == 422


class TestRevision:
    def test_liquidate_draft_guides_to_review(
        self, client, org_headers, wh, mat_moto, sup1
    ):
        """Criterio 2: registrada -> liquidar da error que guia a revisar."""
        body = _capture(client, org_headers, wh, [_line(mat_moto, "10")])
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [_liq_line(mat_moto, [_alloc(sup1, "10", "900")])]},
        )
        assert resp.status_code == 400
        assert "revis" in resp.json()["detail"].lower()

    def test_review_permission_denied_and_granted(
        self, client, org_headers, revisor_headers, org_headers2,
        db_session, test_organization2, wh, mat_moto,
    ):
        """Criterio 3: sin purchases.review -> 403; con el permiso -> revisada."""
        body = _capture(client, org_headers, wh, [_line(mat_moto, "10")])

        # viewer de org2 en SU org no aplica (otra org); el 403 del permiso se
        # prueba en la MISMA org con un usuario sin purchases.review: el propio
        # viewer de org2 no es miembro de org1 -> tomamos el camino directo:
        # el revisor SIN admin puede; un viewer de la misma org no. Org2 como
        # no-miembro daria 403 de membership, no de permiso — por eso el rol
        # custom es la prueba positiva y el negativo usa un rol viewer real.
        reviewed = _review(client, revisor_headers, body["id"])
        assert reviewed["status"] == "reviewed"
        assert reviewed["display_status"] == "reviewed"
        assert reviewed["reviewed_by_name"] == "Revisor 93"
        assert reviewed["reviewed_at"] is not None

    def test_review_denied_for_viewer_same_org(
        self, client, db_session, test_organization, wh, mat_moto, org_headers
    ):
        """El negativo del criterio 3: viewer (sistema) NO tiene purchases.review."""
        from app.core.security import create_access_token
        user = User(
            email="viewer-93@example.com",
            hashed_password=get_password_hash("pass1234"),
            full_name="Viewer 93",
            is_active=True,
        )
        db_session.add(user)
        db_session.flush()
        viewer_role = db_session.execute(
            select(Role).where(
                Role.organization_id == test_organization.id,
                Role.name == "viewer",
            )
        ).scalar_one()
        db_session.add(OrganizationMember(
            user_id=user.id, organization_id=test_organization.id,
            role_id=viewer_role.id,
        ))
        db_session.commit()
        token = create_access_token(data={"sub": str(user.id)})
        viewer_headers = {
            "Authorization": f"Bearer {token}",
            "X-Organization-ID": str(test_organization.id),
        }
        body = _capture(client, org_headers, wh, [_line(mat_moto, "10")])
        resp = client.post(f"{INBOUND_URL}/{body['id']}/review", headers=viewer_headers)
        assert resp.status_code == 403

    def test_review_willard_rejected(
        self, client, org_headers, db_session, test_organization, wh, sup1
    ):
        # willard exige tercero — basta el guard sin armar todo el mundo kg
        resp = client.post(
            INBOUND_URL, headers=org_headers,
            json={
                "inbound_type": "willard",
                "warehouse_id": str(wh.id),
                "date": _past(),
                "lines": [{"material_id": str(sup1.id), "quantity": "1"}],
            },
        )
        # sin third_party_id el 422 llega antes de tocar materiales
        assert resp.status_code == 422
        assert "titular" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Reparto y descuadre (criterios 6-15)
# ---------------------------------------------------------------------------

class TestLiquidacion:
    def test_thirteen_suppliers_thirteen_purchases_consecutive(
        self, client, org_headers, db_session, test_organization, wh, mat_moto, mat_balancin
    ):
        """Criterios 6 y 19: 13 proveedores -> 13 compras liquidadas con
        consecutivos seguidos; la entrada aparece UNA vez en la bandeja."""
        sups = [
            _supplier(db_session, test_organization.id, f"Recuperador {i:02d}")
            for i in range(13)
        ]
        body = _captured_reviewed(
            client, org_headers, wh,
            [_line(mat_moto, "1018"), _line(mat_balancin, "69")],
        )
        # 8 proveedores sobre MOTO (como el Excel), 5 sobre BALANCIN
        moto_allocs = [_alloc(s, "127.25", "900") for s in sups[:8]]  # 8x127.25=1018
        bal_allocs = [_alloc(s, "13.8", "4418") for s in sups[8:]]    # 5x13.8=69
        result = _liquidate(
            client, org_headers, body["id"],
            [
                _liq_line(mat_moto, moto_allocs),
                _liq_line(mat_balancin, bal_allocs),
            ],
        )
        assert result["status"] == "liquidated"
        assert result["display_status"] == "liquidated"

        purchases = _order_purchases(db_session, body["id"])
        assert len(purchases) == 13
        assert all(p.status == "liquidated" for p in purchases)
        numbers = [p.purchase_number for p in purchases]
        assert numbers == list(range(numbers[0], numbers[0] + 13)), \
            "consecutivos seguidos (Excel: 16166..16178)"
        # D21: liquidated_at = HOY, date = fecha de la Entrada
        for p in purchases:
            assert p.liquidated_at.date() == business_today()
            assert p.date.date() != business_today()

        # Criterio 19: UNA sola fila en la bandeja
        listing = client.get(
            INBOUND_URL, headers=org_headers, params={"limit": 100}
        ).json()
        matching = [i for i in listing["items"] if i["id"] == body["id"]]
        assert len(matching) == 1
        assert len(matching[0]["purchases"]) == 13

        # Criterio 18: stock == repartido + descuadre(0) == pesado
        m = _fresh(db_session, mat_moto)
        assert m.current_stock_liquidated == Decimal("1018")

    def test_sobrante_increase_at_reference_price(
        self, client, org_headers, db_session, wh, mat_balancin, sup1
    ):
        """Criterio 7: 69 pesadas, 67 reportadas -> increase de 2 a $4.418."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, "69")])
        result = _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "67", "4418")], ref_price="4418")],
        )
        adjs = _order_adjustments(db_session, body["id"])
        assert len(adjs) == 1
        adj = adjs[0]
        assert adj.adjustment_type == "increase"
        assert adj.quantity == Decimal("2")
        assert adj.unit_cost == Decimal("4418")
        assert adj.total_value == Decimal("2") * Decimal("4418")
        assert adj.status == "confirmed"
        # D21: fechado el dia de la liquidacion (hoy), no el de la captura
        assert adj.date.date() == business_today()

        m = _fresh(db_session, mat_balancin)
        assert m.current_stock_liquidated == Decimal("69")
        # linea en la respuesta con descuadre visible
        line = result["lines"][0]
        assert Decimal(str(line["discrepancy"])) == Decimal("2")
        assert Decimal(str(line["allocated_quantity"])) == Decimal("67")

    def test_faltante_decrease_at_reference_price_clean_branch(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Criterios 8 y 16 (aritmetica del plan, caso MOTO real): el faltante
        sale del pool a $100 y el avg queda EXACTO al de una compra limpia de
        1.018 — la perdida es qty x precio de referencia."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "1018")])
        # los proveedores reportan 1.022,7 contra 1.018 de bascula
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(
                mat_moto,
                [_alloc(sup1, "1000", "100"), _alloc(sup2, "22.7", "80")],
                ref_price="100",
            )],
        )
        adjs = _order_adjustments(db_session, body["id"])
        assert len(adjs) == 1
        adj = adjs[0]
        assert adj.adjustment_type == "decrease"
        assert adj.quantity == Decimal("-4.7")
        assert adj.unit_cost == Decimal("100")  # referencia, NO el promedio
        assert adj.total_value == Decimal("4.7") * Decimal("100")
        assert adj.cost_adjustment == 0  # rama limpia

        # criterio 18: stock final == pesado
        m = _fresh(db_session, mat_moto)
        assert m.current_stock_liquidated == Decimal("1018")

        # criterio 21: avg == MCH del descuadre (created_at empata dentro de
        # la transaccion — filtramos por tipo, no por orden)
        disc_mch = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.material_id == mat_moto.id,
                MaterialCostHistory.source_type == "inbound_discrepancy",
            )
        ).scalars().one()
        assert disc_mch.new_cost == m.current_average_cost
        mch_day = getattr(disc_mch.transaction_date, "date", lambda: disc_mch.transaction_date)()
        assert mch_day == business_today()  # D21

    def test_no_discrepancy_no_adjustment(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Criterio 9: descuadre cero -> ningun ajuste creado."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "900")])],
        )
        assert _order_adjustments(db_session, body["id"]) == []

    def test_line_without_allocation_named_error_and_intentional(
        self, client, org_headers, db_session, wh, mat_moto, mat_balancin, sup1
    ):
        """Criterio 11: linea sin asignaciones -> error que la NOMBRA; con
        unallocated_intentional -> pasa y entra como ganancia."""
        body = _captured_reviewed(
            client, org_headers, wh,
            [_line(mat_moto, "100"), _line(mat_balancin, "69")],
        )
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [
                _liq_line(mat_moto, [_alloc(sup1, "100", "900")]),
                _liq_line(mat_balancin, []),  # sin asignaciones, sin intencion
            ]},
        )
        assert resp.status_code == 422
        assert "BALANCIN-93" in resp.json()["detail"]
        assert _order_purchases(db_session, body["id"]) == []  # nada grabado

        # con intencion explicita: 69 x $4.418 entran como ganancia
        _liquidate(
            client, org_headers, body["id"],
            [
                _liq_line(mat_moto, [_alloc(sup1, "100", "900")]),
                _liq_line(mat_balancin, [], ref_price="4418", unallocated=True),
            ],
        )
        adjs = _order_adjustments(db_session, body["id"])
        assert len(adjs) == 1
        assert adjs[0].adjustment_type == "increase"
        assert adjs[0].total_value == Decimal("69") * Decimal("4418")

    def test_adjust_weighed_then_liquidate_clean(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Criterio 12 (respuesta 4): ajustar la cantidad pesada y liquidar
        -> descuadre cero, sin ajuste."""
        body = _capture(client, org_headers, wh, [_line(mat_moto, "1018")])
        # correccion de bascula ANTES de liquidar
        resp = client.patch(
            f"{INBOUND_URL}/{body['id']}", headers=org_headers,
            json={"lines": [_line(mat_moto, "1022.7")]},
        )
        assert resp.status_code == 200, resp.text
        _review(client, org_headers, body["id"])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "1022.7", "100")])],
        )
        assert _order_adjustments(db_session, body["id"]) == []
        m = _fresh(db_session, mat_moto)
        assert m.current_stock_liquidated == Decimal("1022.7")

    def test_price_exception_per_supplier(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Criterio 13: la excepcion lleva SU precio; el descuadre el de
        referencia."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(
                mat_moto,
                [_alloc(sup1, "60", "900"), _alloc(sup2, "30", "850")],  # excepcion
                ref_price="900",
            )],
        )
        purchases = {p.supplier_id: p for p in _order_purchases(db_session, body["id"])}
        assert purchases[sup1.id].total_amount == Decimal("60") * Decimal("900")
        assert purchases[sup2.id].total_amount == Decimal("30") * Decimal("850")
        adj = _order_adjustments(db_session, body["id"])[0]
        assert adj.unit_cost == Decimal("900")  # referencia, no la excepcion
        assert adj.quantity == Decimal("10")

    def test_truncation_material_not_in_entrada(
        self, client, org_headers, db_session, wh, mat_balancin, mat_grupo4, sup1
    ):
        """Criterio 14: material repartido que la bascula no vio -> linea con
        cantidad 0 y faltante completo a precio de referencia (D16)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, "69")])
        result = _liquidate(
            client, org_headers, body["id"],
            [
                # lo pesado como BALANCIN en parte era GRUPO4: sobran 2
                _liq_line(mat_balancin, [_alloc(sup1, "67", "4418")], ref_price="4418"),
                _liq_line(mat_grupo4, [_alloc(sup1, "2", "2200")], ref_price="2200"),
            ],
        )
        lines = {l["material_code"]: l for l in result["lines"]}
        assert Decimal(str(lines["GRUPO4-93"]["quantity"])) == 0
        assert Decimal(str(lines["GRUPO4-93"]["discrepancy"])) == Decimal("-2")

        adjs = {a.material_id: a for a in _order_adjustments(db_session, body["id"])}
        # BALANCIN: +2 a 4418 (ganancia) | GRUPO4: -2 a 2200 (perdida)
        assert adjs[mat_balancin.id].adjustment_type == "increase"
        assert adjs[mat_balancin.id].total_value == Decimal("2") * Decimal("4418")
        assert adjs[mat_grupo4.id].adjustment_type == "decrease"
        assert adjs[mat_grupo4.id].total_value == Decimal("2") * Decimal("2200")
        # D5: NO se netean — $4.436 de diferencia real quedan en resultados
        # (2x4418 ganancia - 2x2200 perdida)

    def test_missing_line_rejected(
        self, client, org_headers, db_session, wh, mat_moto, mat_balancin, sup1
    ):
        """Completitud D14: toda linea de la entrada debe venir en el reparto."""
        body = _captured_reviewed(
            client, org_headers, wh,
            [_line(mat_moto, "100"), _line(mat_balancin, "69")],
        )
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [_liq_line(mat_moto, [_alloc(sup1, "100", "900")])]},
        )
        assert resp.status_code == 422
        assert "BALANCIN-93" in resp.json()["detail"]

    def test_discrepancy_without_reference_price_fails_before_writes(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Criterio 15: descuadre != 0 sin precio de referencia -> error ANTES
        de empezar (cero compras grabadas)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [_liq_line(mat_moto, [_alloc(sup1, "95", "900")])]},
        )
        assert resp.status_code == 422
        assert "referencia" in resp.json()["detail"]
        assert _order_purchases(db_session, body["id"]) == []
        assert client.get(
            f"{INBOUND_URL}/{body['id']}", headers=org_headers
        ).json()["status"] == "reviewed"

    def test_tolerance_warnings_never_block(
        self, client, org_headers, db_session, test_organization, wh, mat_moto, sup1
    ):
        """Criterio 10: dentro de tolerancia aviso, fuera resaltado — jamas
        bloqueo por monto."""
        test_organization.settings = {
            "kg_ledger_enabled": True,
            "inbound_discrepancy_tolerance_pct": 0.05,
        }
        db_session.commit()
        # 2% de descuadre: dentro
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        r1 = _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "98", "900")], ref_price="900")],
        )
        w1 = [w for w in r1["warnings"] if "Descuadre" in w]
        assert len(w1) == 1 and "dentro de" in w1[0]

        # 40% de descuadre: fuera — pero LIQUIDA igual
        body2 = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        r2 = _liquidate(
            client, org_headers, body2["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "60", "900")], ref_price="900")],
        )
        w2 = [w for w in r2["warnings"] if "Descuadre" in w]
        assert len(w2) == 1 and "FUERA de" in w2[0]
        assert r2["status"] == "liquidated"


# ---------------------------------------------------------------------------
# Invariantes (criterios 16, 17)
# ---------------------------------------------------------------------------

class TestInvariantes:
    def test_star_avg_identical_1_vs_13_suppliers(
        self, client, org_headers, db_session, test_organization, wh
    ):
        """🔴 Criterio 16 (estrella): el avg es IDENTICO liquidando con 1
        proveedor o con 13, con y sin descuadre, con stock final positivo."""
        mat_a = _mat(db_session, test_organization.id, "STAR-A", unit="kg")
        _set_profile(client, org_headers, mat_a.id)
        mat_b = _mat(db_session, test_organization.id, "STAR-B", unit="kg")
        _set_profile(client, org_headers, mat_b.id)
        sups = [
            _supplier(db_session, test_organization.id, f"Star Sup {i}")
            for i in range(13)
        ]

        # mat_a: UN proveedor, 1.018 @ 900, sobrante 2 @ 900
        body_a = _captured_reviewed(client, org_headers, wh, [_line(mat_a, "1020")])
        _liquidate(
            client, org_headers, body_a["id"],
            [_liq_line(mat_a, [_alloc(sups[0], "1018", "900")], ref_price="900")],
        )
        # mat_b: TRECE proveedores, mismas cantidades totales y mismo precio.
        # Cantidades a 1 decimal: InventoryMovement es Numeric(10,3) preexistente
        # y un 4o decimal metería ruido de escala ajeno a #93.
        body_b = _captured_reviewed(client, org_headers, wh, [_line(mat_b, "1020")])
        allocs = [_alloc(s, "78.3", "900") for s in sups[:12]]  # 12 x 78.3 = 939.6
        rest = Decimal("1018") - Decimal("78.3") * 12           # 78.4
        allocs.append(_alloc(sups[12], str(rest), "900"))
        _liquidate(
            client, org_headers, body_b["id"],
            [_liq_line(mat_b, allocs, ref_price="900")],
        )

        a = _fresh(db_session, mat_a)
        b = _fresh(db_session, mat_b)
        assert a.current_stock_liquidated == b.current_stock_liquidated == Decimal("1020")
        assert a.current_average_cost == b.current_average_cost
        assert a.current_average_cost == Decimal("900")

    def test_hueco_degrades_to_current_behavior(
        self, client, org_headers, db_session, test_organization, wh, sup1
    ):
        """Criterio 17: faltante con pool en hueco -> P&L neto == -q*A (la
        degradacion de D7): perdida q*p en adjustment_net compensada por
        q*(p-A) en cost_adjustment."""
        mat = _mat(db_session, test_organization.id, "HUECO-93", unit="kg")
        _set_profile(client, org_headers, mat.id)
        # pool en hueco: avg $50, stock -30 (oversell previo simulado)
        mat.current_average_cost = Decimal("50")
        mat.current_stock_liquidated = Decimal("-30")
        mat.current_stock = Decimal("-30")
        db_session.commit()

        body = _captured_reviewed(client, org_headers, wh, [_line(mat, "10")])
        # reparto 25 con 10 pesados -> faltante de 15; el pool tras las compras
        # queda -30+25=-5 (hueco) -> rama de degradacion
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat, [_alloc(sup1, "25", "100")], ref_price="100")],
        )
        adj = _order_adjustments(db_session, body["id"])[0]
        q, p, a_cost = Decimal("15"), Decimal("100"), Decimal("50")
        # P&L neto del descuadre: -total_value + cost_adjustment == -q*A
        assert -adj.total_value + adj.cost_adjustment == -q * a_cost
        assert adj.cost_adjustment == q * (p - a_cost)


# ---------------------------------------------------------------------------
# Reversas (criterios 20, 22-26, 33, 34, 35)
# ---------------------------------------------------------------------------

class TestReversas:
    def _liquidated_entrada(self, client, org_headers, db_session, wh, mat, sups,
                            collector=None):
        body = _captured_reviewed(client, org_headers, wh, [_line(mat, "100")])
        extra = {}
        if collector is not None:
            extra["collector_commission"] = {
                "third_party_id": str(collector.id), "amount": "1400",
            }
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(
                mat,
                [_alloc(sups[0], "60", "900"), _alloc(sups[1], "35", "900")],
                ref_price="900",
            )],
            **extra,
        )
        return body

    def test_unliquidate_full_roundtrip(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2, collector
    ):
        """Criterio 22: unliquidate revierte N compras + ajuste + comision,
        vuelve a revisada, CONSERVA el reparto, sin quemar consecutivos y sin
        canceladas en los estados de cuenta."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2], collector
        )
        purchases_before = _order_purchases(db_session, body["id"])
        numbers_before = sorted(p.purchase_number for p in purchases_before)
        max_number = db_session.execute(
            select(Purchase.purchase_number).order_by(Purchase.purchase_number.desc())
        ).scalars().first()

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers
        )
        assert resp.status_code == 200, resp.text
        result = resp.json()
        assert result["status"] == "reviewed"
        # reparto CONSERVADO
        assert len(result["lines"][0]["allocations"]) == 2

        db_session.expire_all()
        purchases_after = _order_purchases(db_session, body["id"])
        assert sorted(p.purchase_number for p in purchases_after) == numbers_before
        assert all(p.status == "registered" for p in purchases_after)
        assert all(p.liquidated_at is None for p in purchases_after)
        # sin consecutivos nuevos, sin canceladas
        new_max = db_session.execute(
            select(Purchase.purchase_number).order_by(Purchase.purchase_number.desc())
        ).scalars().first()
        assert new_max == max_number
        assert all(p.status != "cancelled" for p in purchases_after)

        # saldos de proveedor de vuelta a 0
        for sup in (sup1, sup2):
            assert _fresh(db_session, sup).current_balance == 0
        # ajuste de descuadre anulado (round-trip: stock vuelve a lo repartido
        # + descuadre revertido == transit ahora)
        adjs = _order_adjustments(db_session, body["id"])
        assert all(a.status == "annulled" for a in adjs)
        # comision anulada y saldo del recolector restaurado
        accruals = _entrada_accruals(db_session, body["id"])
        assert len(accruals) == 1 and accruals[0].status == "annulled"
        assert _fresh(db_session, collector).current_balance == 0
        # el material quedo INTEGRO en transito (registradas)
        m = _fresh(db_session, mat_moto)
        assert m.current_stock_transit == Decimal("95")
        assert m.current_stock_liquidated == Decimal("0")

        # re-liquidar funciona (reusa las mismas compras — cero consecutivos)
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(
                mat_moto,
                [_alloc(sup1, "60", "900"), _alloc(sup2, "35", "900")],
                ref_price="900",
            )],
        )
        db_session.expire_all()
        final = _order_purchases(db_session, body["id"])
        assert sorted(p.purchase_number for p in final) == numbers_before
        assert all(p.status == "liquidated" for p in final)

    def test_unliquidate_after_sale_warns_never_blocks(
        self, client, org_headers, db_session, test_organization, wh, mat_moto,
        sup1, sup2,
    ):
        """Criterio 23: con el material ya vendido, unliquidate AVISA (#76) —
        si bloqueara vuelve el deadlock del Ciclo C con 13 compras adentro."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2]
        )
        customer = create_third_party_with_category(
            db_session, test_organization.id, "Cliente 93", "customer"
        )
        db_session.commit()
        resp = client.post(
            "/api/v1/sales/", headers=org_headers,
            json={
                "customer_id": str(customer.id),
                "date": business_today().isoformat(),
                "warehouse_id": str(wh.id),
                "lines": [{
                    "material_id": str(mat_moto.id),
                    "warehouse_id": str(wh.id),
                    "quantity": "98", "unit_price": "1200",
                }],
            },
        )
        assert resp.status_code == 201, resp.text
        # Modelo L (#64): solo la venta LIQUIDADA extrae del pool liquidado —
        # sin liquidar, el bucket no queda negativo y no habria aviso
        sale_id = resp.json()["id"]
        resp = client.patch(
            f"/api/v1/sales/{sale_id}/liquidate", headers=org_headers, json={}
        )
        assert resp.status_code == 200, resp.text

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers
        )
        assert resp.status_code == 200, resp.text
        warnings = resp.json()["warnings"]
        assert any("negativo" in w for w in warnings)

    def test_cancel_individual_purchase_400(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Criterio 24: cancelar una compra derivada por separado -> 400 que
        guia a la Entrada."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2]
        )
        p = _order_purchases(db_session, body["id"])[0]
        resp = client.patch(
            f"{PURCHASES_URL}/{p.id}/cancel", headers=org_headers
        )
        assert resp.status_code == 400
        assert "Entrada" in resp.json()["detail"]

    def test_annul_liquidated_delegates_to_unliquidate(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2, collector
    ):
        """Criterio 25: anular una entrada LIQUIDADA (imposible pre-#93) —
        delega en unliquidate y cancela."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2], collector
        )
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/annul", headers=org_headers,
            json={"reason": "camion equivocado"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "annulled"

        db_session.expire_all()
        purchases = _order_purchases(db_session, body["id"])
        assert all(p.status == "cancelled" for p in purchases)
        adjs = _order_adjustments(db_session, body["id"])
        assert all(a.status == "annulled" for a in adjs)
        m = _fresh(db_session, mat_moto)
        assert m.current_stock == 0
        assert m.current_stock_transit == 0
        assert m.current_stock_liquidated == 0
        for tp in (sup1, sup2, collector):
            assert _fresh(db_session, tp).current_balance == 0

    def test_annul_discrepancy_adjustment_from_inventory_422(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Criterio 26 (D17): anular el ajuste de descuadre desde Ajustes ->
        422 que guia a la Entrada. El mensaje nombra el NUMERO de la entrada y
        usa el MISMO verbo del boton (pruebas de usuario: "anule la
        liquidacion" mandaba a buscar un boton inexistente)."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2]
        )
        adj = _order_adjustments(db_session, body["id"])[0]
        resp = client.post(
            f"{ADJUSTMENTS_URL}/{adj.id}/annul", headers=org_headers,
            json={"reason": "no deberia poder"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert f"Entrada #{body['order_number']}" in detail
        assert "Revertir Liquidación" in detail

    def test_annul_transfer_merma_from_adjustments_422(
        self, client, org_headers, db_session, test_organization, wh, mat_moto
    ):
        """Criterio 35 (A3): la merma de un traslado tampoco se anula desde
        Ajustes — mismo guard, FK hermana."""
        from app.services.inventory_adjustment import inventory_adjustment
        from app.schemas.inventory_adjustment import IncreaseCreate, DecreaseCreate
        from app.models.transfer import Transfer

        # seed minimo: un decrease hijo de traslado (FK directa — el guard lee
        # la FK, no el flujo completo de E3.1)
        mat_moto.current_stock_liquidated = Decimal("50")
        mat_moto.current_stock = Decimal("50")
        db_session.commit()
        adj, _ = inventory_adjustment.decrease(
            db_session,
            DecreaseCreate(
                material_id=mat_moto.id, warehouse_id=wh.id,
                date=business_today().isoformat(),
                quantity=Decimal("5"), reason="merma traslado test",
            ),
            test_organization.id, commit=True,
        )
        transfer = Transfer(
            organization_id=test_organization.id,
            transfer_number=999,
            from_warehouse_id=wh.id, to_warehouse_id=wh.id,
            transit_warehouse_id=wh.id,
            dispatch_date=datetime.now(timezone.utc),
            status="received",
        )
        db_session.add(transfer)
        db_session.flush()
        adj.transfer_id = transfer.id
        db_session.commit()

        resp = client.post(
            f"{ADJUSTMENTS_URL}/{adj.id}/annul", headers=org_headers,
            json={"reason": "no deberia poder"},
        )
        assert resp.status_code == 422
        assert "traslado" in resp.json()["detail"].lower()

    def test_decrease_override_annul_roundtrip_exact(
        self, db_session, test_organization, client, org_headers, wh
    ):
        """🔴 Criterio 20 (el bug del fix 4 de D7, W-1): anular un decrease con
        precio explicito en rama de hueco -> round-trip EXACTO al pool
        original (el codigo viejo inventaba valor: $1.000 -> $3.700)."""
        from app.services.inventory_adjustment import inventory_adjustment
        from app.schemas.inventory_adjustment import DecreaseCreate

        mat = _mat(db_session, test_organization.id, "W1-93", unit="kg")
        mat.current_average_cost = Decimal("100")
        mat.current_stock_liquidated = Decimal("10")   # pool $1.000
        mat.current_stock = Decimal("10")
        db_session.commit()

        adj, _ = inventory_adjustment.decrease(
            db_session,
            DecreaseCreate(
                material_id=mat.id, warehouse_id=wh.id,
                date=business_today().isoformat(),
                quantity=Decimal("30"), reason="descuadre hueco",
            ),
            test_organization.id, commit=True,
            unit_cost_override=Decimal("100"),
        )
        db_session.expire_all()
        adj = db_session.get(InventoryAdjustment, adj.id)

        inventory_adjustment.annul(
            db_session, adj.id, "reversa", test_organization.id,
            commit=True, from_module=True,
        )
        m = db_session.get(Material, mat.id)
        assert m.current_stock_liquidated == Decimal("10")
        assert m.current_average_cost == Decimal("100")
        # pool EXACTO $1.000 — no $3.700
        assert m.current_stock_liquidated * m.current_average_cost == Decimal("1000")

    def test_annul_preexisting_decrease_unchanged(
        self, db_session, test_organization, client, org_headers, wh
    ):
        """Criterio 33: el fix del annul es no-op por algebra para los
        decreases de hoy (cost_adjustment=0) — round-trip al avg persistido."""
        from app.services.inventory_adjustment import inventory_adjustment
        from app.schemas.inventory_adjustment import DecreaseCreate

        mat = _mat(db_session, test_organization.id, "C33-93", unit="kg")
        mat.current_average_cost = Decimal("80")
        mat.current_stock_liquidated = Decimal("100")
        mat.current_stock = Decimal("100")
        db_session.commit()

        adj, _ = inventory_adjustment.decrease(
            db_session,
            DecreaseCreate(
                material_id=mat.id, warehouse_id=wh.id,
                date=business_today().isoformat(),
                quantity=Decimal("40"), reason="merma normal",
            ),
            test_organization.id, commit=True,
        )
        db_session.expire_all()
        assert db_session.get(InventoryAdjustment, adj.id).cost_adjustment == 0

        inventory_adjustment.annul(
            db_session, adj.id, "reversa", test_organization.id, commit=True,
        )
        m = db_session.get(Material, mat.id)
        assert m.current_stock_liquidated == Decimal("100")
        assert m.current_average_cost == Decimal("80")

    def test_unliquidate_mch_purchase_unliquidation_and_original_stays(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Criterio 34 (D20a/D20b): la reversa escribe purchase_unliquidation
        y el purchase_liquidation original PERMANECE."""
        body = self._liquidated_entrada(
            client, org_headers, db_session, wh, mat_moto, [sup1, sup2]
        )
        client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)

        db_session.expire_all()
        mch = db_session.execute(
            select(MaterialCostHistory)
            .where(MaterialCostHistory.material_id == mat_moto.id)
            .order_by(MaterialCostHistory.created_at)
        ).scalars().all()
        types = [m.source_type for m in mch]
        assert "purchase_liquidation" in types  # el original permanece (D20b)
        assert "purchase_unliquidation" in types
        # la reversa es posterior al original
        assert types.index("purchase_unliquidation") > types.index("purchase_liquidation")


# ---------------------------------------------------------------------------
# Atomicidad (criterio 27) y comision D11
# ---------------------------------------------------------------------------

class TestAtomicidadYComision:
    def test_late_failure_leaves_nothing(
        self, client, org_headers, db_session, test_organization, wh, mat_moto,
        sup1, sup2,
    ):
        """🔴 Criterio 27: una falla DESPUES de liquidar las N compras (la
        comision con un tercero invalido) -> NINGUNA queda grabada; la entrada
        sigue revisada."""
        not_provider = create_third_party_with_category(
            db_session, test_organization.id, "No Es Proveedor Serv", "customer"
        )
        db_session.commit()
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={
                "lines": [_liq_line(
                    mat_moto,
                    [_alloc(sup1, "60", "900"), _alloc(sup2, "40", "900")],
                )],
                "collector_commission": {
                    "third_party_id": str(not_provider.id), "amount": "1000",
                },
            },
        )
        assert resp.status_code == 422

        db_session.expire_all()
        assert _order_purchases(db_session, body["id"]) == []
        assert _fresh(db_session, sup1).current_balance == 0
        m = _fresh(db_session, mat_moto)
        assert m.current_stock == 0
        assert client.get(
            f"{INBOUND_URL}/{body['id']}", headers=org_headers
        ).json()["status"] == "reviewed"

    def test_collector_commission_once_per_entrada(
        self, client, org_headers, db_session, wh, mat_moto, mat_balancin,
        sup1, sup2, collector,
    ):
        """D11: UNA comision por entrada (no una por compra), source_id = la
        entrada, purchase_id NULL, fechada HOY (D21)."""
        body = _captured_reviewed(
            client, org_headers, wh,
            [_line(mat_moto, "100"), _line(mat_balancin, "10")],
        )
        _liquidate(
            client, org_headers, body["id"],
            [
                _liq_line(mat_moto, [_alloc(sup1, "100", "900")]),
                _liq_line(mat_balancin, [_alloc(sup2, "10", "4418")]),
            ],
            collector_commission={
                "third_party_id": str(collector.id),
                # base pesada: 100 kg + 10 unidades x 14 = 240 kg x $100
                "amount": "24000",
            },
        )
        accruals = _entrada_accruals(db_session, body["id"])
        assert len(accruals) == 1
        acc = accruals[0]
        assert acc.movement_type == "expense_accrual"
        assert acc.amount == Decimal("24000")
        assert acc.purchase_id is None
        assert acc.status == "confirmed"
        assert acc.date.date() == business_today()  # D21
        assert _fresh(db_session, collector).current_balance == Decimal("-24000")


# ---------------------------------------------------------------------------
# No-regresion (criterios 28, 29) y estabilidad temporal (criterio 32)
# ---------------------------------------------------------------------------

class TestNoRegresion:
    def test_org_without_flag_sees_purchases_unchanged(
        self, client, org_headers, db_session, test_organization, wh, sup1, mat_moto
    ):
        """Criterio 28: sin flag, el listado de compras es campo por campo
        identico — la puente esta vacia y el lookup no agrega nada."""
        test_organization.settings = {}
        db_session.commit()
        resp = client.post(
            f"{PURCHASES_URL}/", headers=org_headers,
            json={
                "supplier_id": str(sup1.id),
                "date": _past(),
                "lines": [{
                    "material_id": str(mat_moto.id),
                    "warehouse_id": str(wh.id),
                    "quantity": "10", "unit_price": "900",
                }],
            },
        )
        assert resp.status_code == 201, resp.text
        listing = client.get(f"{PURCHASES_URL}/", headers=org_headers).json()
        item = next(i for i in listing["items"] if i["id"] == resp.json()["id"])
        assert item["inbound_order_id"] is None
        assert item["inbound_order_number"] is None

    def test_decrease_without_override_byte_identical(
        self, client, org_headers, db_session, test_organization, wh
    ):
        """Criterio 29: decrease sin override — sin MCH, avg intacto,
        cost_adjustment 0 (endpoint, el mismo camino de las 7 orgs)."""
        mat = _mat(db_session, test_organization.id, "C29-93", unit="kg")
        mat.current_average_cost = Decimal("75")
        mat.current_stock_liquidated = Decimal("100")
        mat.current_stock = Decimal("100")
        db_session.commit()
        mch_before = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.material_id == mat.id
            )
        ).scalars().all()

        resp = client.post(
            f"{ADJUSTMENTS_URL}/decrease", headers=org_headers,
            json={
                "material_id": str(mat.id), "warehouse_id": str(wh.id),
                "date": business_today().isoformat(),
                "quantity": "20", "reason": "merma normal",
            },
        )
        assert resp.status_code == 201, resp.text

        db_session.expire_all()
        m = db_session.get(Material, mat.id)
        assert m.current_average_cost == Decimal("75")
        mch_after = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.material_id == mat.id
            )
        ).scalars().all()
        assert len(mch_after) == len(mch_before)  # cero MCH nuevos
        adj = db_session.execute(
            select(InventoryAdjustment).where(
                InventoryAdjustment.material_id == mat.id
            )
        ).scalars().first()
        assert adj.cost_adjustment == 0
        assert adj.unit_cost == Decimal("75")  # el promedio, como siempre

    def test_liquidation_does_not_change_past_cuts(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """🔴 Criterio 32 (D21): liquidar una entrada capturada dias atras NO
        cambia ningun corte anterior al dia de la liquidacion."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])

        capture_date = _past(2)
        yesterday = _past(1)

        def snapshot(as_of):
            r = client.get(
                f"{REPORTS_URL}/balance-sheet", headers=org_headers,
                params={"as_of_date": as_of},
            )
            assert r.status_code == 200, r.text
            return r.json()

        before_capture = snapshot(capture_date)
        before_yesterday = snapshot(yesterday)

        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "98", "900")], ref_price="900")],
        )

        assert snapshot(capture_date) == before_capture
        assert snapshot(yesterday) == before_yesterday


# ---------------------------------------------------------------------------
# Busqueda y filtros 1:N (R2)
# ---------------------------------------------------------------------------

class TestBusqueda:
    def test_search_by_alloc_supplier_invoice_and_remission(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        body = _capture(
            client, org_headers, wh, [_line(mat_moto, "100")],
            remission_number="REM-777",
        )
        _review(client, org_headers, body["id"])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(
                mat_moto,
                [
                    _alloc(sup1, "60", "900", invoice="FAC-UNO-1"),
                    _alloc(sup2, "40", "900"),
                ],
            )],
        )

        def search(q):
            r = client.get(INBOUND_URL, headers=org_headers, params={"search": q})
            return [i["id"] for i in r.json()["items"]]

        assert body["id"] in search("REM-777")
        assert body["id"] in search("Proveedor Uno")
        assert body["id"] in search("FAC-UNO")
        # y sigue apareciendo UNA sola vez
        assert search("Proveedor Uno").count(body["id"]) == 1

    def test_filter_by_third_party_matches_allocations(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "900")])],
        )
        r = client.get(
            INBOUND_URL, headers=org_headers,
            params={"third_party_id": str(sup1.id)},
        )
        assert body["id"] in [i["id"] for i in r.json()["items"]]
        r2 = client.get(
            INBOUND_URL, headers=org_headers,
            params={"third_party_id": str(sup2.id)},
        )
        assert body["id"] not in [i["id"] for i in r2.json()["items"]]

    def test_display_status_filter_reviewed(
        self, client, org_headers, wh, mat_moto
    ):
        body = _capture(client, org_headers, wh, [_line(mat_moto, "10")])
        _review(client, org_headers, body["id"])
        r = client.get(
            INBOUND_URL, headers=org_headers,
            params={"display_status": "reviewed"},
        )
        assert body["id"] in [i["id"] for i in r.json()["items"]]
        r2 = client.get(
            INBOUND_URL, headers=org_headers,
            params={"display_status": "registered"},
        )
        assert body["id"] not in [i["id"] for i in r2.json()["items"]]


# ---------------------------------------------------------------------------
# Addendum retenciones (hallazgo QA 2026-08-06)
# ---------------------------------------------------------------------------

class TestRetencionesEntrada:
    """Sin esto, #93 dejaba el bloque de retenciones de #79 INALCANZABLE en
    SAC (regresion, no gap: canal unico #80 + liquidacion atomica D14 = nadie
    vuelve a pasar por PurchaseLiquidatePage). Daniel: "si les descuenta, pero
    no a todas, es opcional" -> bloques OPCIONALES por proveedor, pass-through
    a purchase.liquidate() (#79 heredado: neto, entidad sistema, tope, H4)."""

    @staticmethod
    def _entity(db, name):
        db.expire_all()
        return db.execute(
            select(ThirdParty).where(ThirdParty.name == name)
        ).scalar_one_or_none()

    def test_optional_per_supplier_net_credit(
        self, client, org_headers, db_session, wh, sup1, sup2, mat_moto
    ):
        """Retencion en UNO de dos proveedores: ese queda acreditado NETO, el
        otro completo — y la entidad [Retenciones] conserva el pasivo al peso."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "1000")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "600", "1000"), _alloc(sup2, "400", "1000")])],
            supplier_retentions=[{
                "third_party_id": str(sup1.id),
                "retentions": [
                    {"retention_type": "retefuente", "rate": "2.5",
                     "base": "600000", "amount": "15000"},
                ],
            }],
        )
        db_session.expire_all()
        s1 = db_session.get(ThirdParty, sup1.id)
        s2 = db_session.get(ThirdParty, sup2.id)
        assert s1.current_balance == Decimal("-585000")  # 600.000 - 15.000: NETO
        assert s2.current_balance == Decimal("-400000")  # sin retencion: completo
        entity = self._entity(db_session, "[Retenciones] ReteFuente")
        assert entity is not None
        assert entity.current_balance == Decimal("-15000")

        # La fila vive en la compra del proveedor correcto
        by_sup = {p.supplier_id: p for p in _order_purchases(db_session, body["id"])}
        assert [r.amount for r in by_sup[sup1.id].retentions] == [Decimal("15000")]
        assert list(by_sup[sup2.id].retentions or []) == []

        # El summary del detalle expone el total vivo (display del neto)
        detail = client.get(f"{INBOUND_URL}/{body['id']}", headers=org_headers).json()
        by_tp = {p["supplier_id"]: p for p in detail["purchases"]}
        assert by_tp[str(sup1.id)]["retentions_total"] == 15000.0
        assert by_tp[str(sup2.id)]["retentions_total"] is None

    def test_block_for_supplier_not_in_reparto_422_named(
        self, client, org_headers, db_session, wh, sup1, sup2, mat_moto
    ):
        """Fail-fast del plan D14: el bloque nombra al proveedor intruso y
        NADA persiste (la validacion corre antes de escribir)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=[{
                "third_party_id": str(sup2.id),
                "retentions": [{"retention_type": "reteiva", "amount": "100"}],
            }],
            expect=422,
        )
        assert "no esta en el reparto" in resp["detail"]
        assert sup2.name in resp["detail"]
        assert _order_purchases(db_session, body["id"]) == []

    def test_duplicate_supplier_blocks_422(
        self, client, org_headers, db_session, wh, sup1, mat_moto
    ):
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=[
                {"third_party_id": str(sup1.id),
                 "retentions": [{"retention_type": "retefuente", "amount": "100"}]},
                {"third_party_id": str(sup1.id),
                 "retentions": [{"retention_type": "reteiva", "amount": "200"}]},
            ],
            expect=422,
        )
        assert "consolide" in resp["detail"].lower()
        assert _order_purchases(db_session, body["id"]) == []

    def test_total_over_purchase_total_rolls_back_everything(
        self, client, org_headers, db_session, wh, sup1, mat_moto
    ):
        """El tope Σret < total vive en _apply_retentions (#79) y dispara
        TARDE — con las compras ya escritas en la transaccion. D14 lo cubre:
        rollback total, nada persiste (criterio 27 extendido al addendum)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],  # total 100.000
            supplier_retentions=[{
                "third_party_id": str(sup1.id),
                "retentions": [{"retention_type": "retefuente", "amount": "100000"}],
            }],
            expect=422,
        )
        assert "menor al total" in resp["detail"]
        db_session.expire_all()
        assert _order_purchases(db_session, body["id"]) == []
        assert db_session.get(ThirdParty, sup1.id).current_balance == 0
        # Ni la entidad sistema nace (el tope se valida antes del get-or-create)
        assert self._entity(db_session, "[Retenciones] ReteFuente") is None

    def test_unliquidate_roundtrip_and_reliquidate(
        self, client, org_headers, db_session, wh, sup1, mat_moto
    ):
        """Round-trip completo: liquidar con retencion (ICA por municipio H4)
        -> unliquidate (el helper D20 revierte proveedor Y entidad, reverted_at
        como auditoria) -> re-liquidar con la retencion de nuevo -> neto otra
        vez, en la MISMA compra (re-sync por firma)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        ret = [{
            "third_party_id": str(sup1.id),
            "retentions": [{"retention_type": "ica", "municipality": "Barranquilla",
                            "amount": "700"}],
        }]
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=ret,
        )
        db_session.expire_all()
        p0 = _order_purchases(db_session, body["id"])[0]
        number = p0.purchase_number
        assert db_session.get(ThirdParty, sup1.id).current_balance == Decimal("-99300")
        ica = self._entity(db_session, "[Retenciones] ICA Barranquilla")
        assert ica.current_balance == Decimal("-700")

        resp = client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        assert db_session.get(ThirdParty, sup1.id).current_balance == 0
        assert self._entity(db_session, "[Retenciones] ICA Barranquilla").current_balance == 0
        p0 = db_session.get(Purchase, p0.id)
        assert all(r.reverted_at is not None for r in p0.retentions)

        # Re-liquidar: reparto conservado, el payload vuelve completo (la UI
        # re-manda las retenciones — nada se re-aplica en silencio)
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=ret,
        )
        db_session.expire_all()
        purchases = _order_purchases(db_session, body["id"])
        assert [p.purchase_number for p in purchases] == [number]
        assert db_session.get(ThirdParty, sup1.id).current_balance == Decimal("-99300")
        assert self._entity(db_session, "[Retenciones] ICA Barranquilla").current_balance == Decimal("-700")
        live = [r for r in purchases[0].retentions if r.reverted_at is None]
        assert len(live) == 1 and live[0].amount == Decimal("700")

    def test_statement_parity_after_reliquidation(
        self, client, org_headers, db_session, wh, sup1, mat_moto
    ):
        """Fix QA del addendum: tras des-liquidar y re-liquidar, la compra
        queda con DOS filas de retencion (vieja revertida + nueva viva). El
        statement debe seguir a la FILA (reverted_at), no al status de la
        compra: UNA retencion confirmada + la vieja como par que neta a cero
        (evento cancelled + reversa annulled, ninguno mueve saldo) — sin esto
        el estado de cuenta mostraba $1.400 donde el saldo tiene $700, en
        ambos lados (#55/#61)."""
        def statement(tp_id):
            resp = client.get(
                f"/api/v1/money-movements/third-party/{tp_id}",
                headers=org_headers,
                params={"date_from": "2020-01-01", "limit": 500},
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            items = data["items"]
            return (items[-1]["balance_after"] if items else 0.0), data["current_balance"], items

        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        ret = [{
            "third_party_id": str(sup1.id),
            "retentions": [{"retention_type": "ica", "municipality": "Barranquilla",
                            "amount": "700"}],
        }]
        liq_lines = [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])]
        _liquidate(client, org_headers, body["id"], liq_lines, supplier_retentions=ret)
        assert client.post(
            f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers
        ).status_code == 200
        _liquidate(client, org_headers, body["id"], liq_lines, supplier_retentions=ret)

        db_session.expire_all()
        entity = db_session.execute(
            select(ThirdParty).where(ThirdParty.name == "[Retenciones] ICA Barranquilla")
        ).scalar_one()

        for tp_id, expected in ((sup1.id, -99300.0), (entity.id, -700.0)):
            final, live, items = statement(tp_id)
            assert live == pytest.approx(expected)
            assert final == pytest.approx(expected), (
                "el saldo corrido del statement debe cerrar en el saldo vivo"
            )
            ret_events = [i for i in items if i.get("event_type") == "purchase_retention"]
            assert len([i for i in ret_events if i["status"] == "confirmed"]) == 1, (
                "solo la fila VIVA se muestra confirmada — la fantasma era el bug"
            )
            assert len([i for i in ret_events if i["status"] == "cancelled"]) == 1
            reversals = [
                i for i in items
                if i.get("event_type") == "purchase_retention_cancellation"
            ]
            assert len(reversals) == 1
            assert "des-liquidacion" in reversals[0]["description"]


class TestTarifaKgPerUnit:
    """D11: la equivalencia kg/unidad viaja CON la tarifa (se versionan
    juntas, append-only #35) y solo existe en comision_green_loop."""

    TARIFFS_URL = "/api/v1/service-tariffs"

    def test_green_loop_accepts_and_versions(self, client, org_headers):
        r1 = client.post(self.TARIFFS_URL, headers=org_headers, json={
            "tariff_code": "comision_green_loop", "unit_price_cop": "100",
            "unit": "per_kg_material", "kg_per_unit": "14",
        })
        assert r1.status_code == 201, r1.text
        assert float(r1.json()["kg_per_unit"]) == 14

        # Version nueva con otra equivalencia -> la vigente cambia, la vieja queda
        r2 = client.post(self.TARIFFS_URL, headers=org_headers, json={
            "tariff_code": "comision_green_loop", "unit_price_cop": "100",
            "unit": "per_kg_material", "kg_per_unit": "12",
        })
        assert r2.status_code == 201, r2.text
        current = client.get(f"{self.TARIFFS_URL}/current", headers=org_headers).json()
        vigente = next(
            t for t in current["items"] if t["tariff_code"] == "comision_green_loop"
        )
        assert float(vigente["kg_per_unit"]) == 12

    def test_other_code_rejected(self, client, org_headers):
        resp = client.post(self.TARIFFS_URL, headers=org_headers, json={
            "tariff_code": "maquila_willard", "unit_price_cop": "50",
            "unit": "per_kg_lead", "kg_per_unit": "14",
        })
        assert resp.status_code == 422, resp.text
        assert "comision_green_loop" in resp.json()["detail"]


class TestSuperficieDetalle:
    """Pruebas de usuario (Daniel, 2026-08-11): lo que la Entrada YA hacia bien
    era invisible. Dos superficies nuevas de SOLO LECTURA en el GET de detalle
    — el descuadre que se mando a resultados y las retenciones aplicadas — y
    ninguna toca el camino de escritura."""

    @staticmethod
    def _detail(client, headers, order_id):
        resp = client.get(f"{INBOUND_URL}/{order_id}", headers=headers)
        assert resp.status_code == 200, resp.text
        return resp.json()

    def test_discrepancy_adjustments_signed_in_detail(
        self, client, org_headers, db_session, wh, mat_balancin, mat_grupo4, sup1
    ):
        """El detalle expone los ajustes de descuadre con el signo del NEGOCIO
        (+ ganancia, - perdida), no el |valor| de la tabla: sin esto el usuario
        tenia que ir a Reportes a saber si la entrada gano o perdio."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, "69")])
        _liquidate(
            client, org_headers, body["id"],
            [
                _liq_line(mat_balancin, [_alloc(sup1, "67", "4418")], ref_price="4418"),
                _liq_line(mat_grupo4, [_alloc(sup1, "2", "2200")], ref_price="2200"),
            ],
        )
        detail = self._detail(client, org_headers, body["id"])
        adjs = {a["material_code"]: a for a in detail["discrepancy_adjustments"]}
        assert len(adjs) == 2

        gain = adjs["BALANCIN-93"]
        assert gain["adjustment_type"] == "increase"
        assert Decimal(str(gain["total_value"])) == Decimal("8836")  # +2 x 4418
        assert Decimal(str(gain["quantity"])) == Decimal("2")  # siempre positiva
        assert gain["material_unit"] == "unidad"
        assert gain["status"] == "confirmed"
        assert gain["adjustment_number"] is not None

        loss = adjs["GRUPO4-93"]
        assert loss["adjustment_type"] == "decrease"
        assert Decimal(str(loss["total_value"])) == Decimal("-4400")  # -2 x 2200
        assert Decimal(str(loss["quantity"])) == Decimal("2")

        # D5: no se netean — el neto que pinta la UI sale de la suma con signo
        assert sum(Decimal(str(a["total_value"])) for a in adjs.values()) == Decimal("4436")

    def test_discrepancy_adjustments_absent_in_list(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """Detail-only por costo: el listado pagina y una query por fila seria
        N+1. La UI del listado no los usa."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "90", "1000")], ref_price="1000")],
        )
        assert self._detail(client, org_headers, body["id"])["discrepancy_adjustments"]

        listed = client.get(INBOUND_URL, headers=org_headers).json()["items"]
        row = next(o for o in listed if o["id"] == body["id"])
        assert row["discrepancy_adjustments"] == []

    def test_discrepancy_adjustments_annulled_after_unliquidate(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Tras des-liquidar el ajuste sigue listado pero como `annulled` — la
        UI filtra por status, asi que la tarjeta desaparece sin que el backend
        tenga que borrar el rastro (append-only)."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "90", "1000")], ref_price="1000")],
        )
        resp = client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        assert resp.status_code == 200, resp.text

        adjs = self._detail(client, org_headers, body["id"])["discrepancy_adjustments"]
        assert len(adjs) == 1 and adjs[0]["status"] == "annulled"

    def test_retentions_exposed_live_and_after_unliquidate(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """La precarga al re-liquidar necesita VER las retenciones: vivas
        mientras la compra lo esta, y el ULTIMO lote revertido tras des-liquidar
        (si no, re-liquidar obligaba a re-teclearlas de memoria). El total en
        cambio cuenta solo las vivas — es el saldo real del proveedor."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        ret = [{
            "third_party_id": str(sup1.id),
            "retentions": [{"retention_type": "ica", "municipality": "Barranquilla",
                            "rate": "0.7", "base": "100000", "amount": "700"}],
        }]
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=ret,
        )
        summary = self._detail(client, org_headers, body["id"])["purchases"][0]
        assert Decimal(str(summary["retentions_total"])) == Decimal("700")
        assert len(summary["retentions"]) == 1
        row = summary["retentions"][0]
        assert row["retention_type"] == "ica"
        assert row["municipality"] == "Barranquilla"
        assert Decimal(str(row["rate"])) == Decimal("0.7")  # audita el precalculo
        assert Decimal(str(row["amount"])) == Decimal("700")

        client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        summary = self._detail(client, org_headers, body["id"])["purchases"][0]
        assert not summary["retentions_total"]  # nada vivo -> nada acreditado
        assert len(summary["retentions"]) == 1  # el lote revertido, para precargar

    def test_retention_preload_shows_only_last_batch(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Tras re-liquidar hay DOS filas en BD (la revertida + la viva). La
        precarga debe ver UNA — la viva — o la UI duplicaria la retencion, que
        es exactamente el bug que QA encontro en el estado de cuenta."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        ret = [{
            "third_party_id": str(sup1.id),
            "retentions": [{"retention_type": "retefuente", "amount": "700"}],
        }]
        args = (client, org_headers, body["id"],
                [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])])
        _liquidate(*args, supplier_retentions=ret)
        client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        _liquidate(*args, supplier_retentions=[{
            "third_party_id": str(sup1.id),
            "retentions": [{"retention_type": "retefuente", "amount": "900"}],
        }])

        db_session.expire_all()
        purchase = _order_purchases(db_session, body["id"])[0]
        assert len(purchase.retentions) == 2  # el rastro completo sigue en BD

        summary = self._detail(client, org_headers, body["id"])["purchases"][0]
        assert len(summary["retentions"]) == 1
        assert Decimal(str(summary["retentions"][0]["amount"])) == Decimal("900")
        assert Decimal(str(summary["retentions_total"])) == Decimal("900")


class TestPagoContadoYWillard:
    """Pruebas de usuario (Daniel, 2026-08-11): dos huecos de la MISMA familia
    que las retenciones — el canal unico (#80) dejo campos de
    PurchaseLiquidateRequest sin superficie en SAC — mas la exclusion del
    tercero Willard, que vivia en la captura y no viajo a la liquidacion."""

    KG_URL = "/api/v1/kg-ledger"

    @pytest.fixture
    def account(self, db_session, test_organization):
        from app.models.money_account import MoneyAccount
        acc = MoneyAccount(
            name="Caja Principal", account_type="cash",
            current_balance=Decimal("1000000"),
            organization_id=test_organization.id, is_active=True,
        )
        db_session.add(acc)
        db_session.commit()
        db_session.refresh(acc)
        return acc

    # ---------------- Willard excluido del reparto ----------------

    def test_kg_account_holder_rejected_as_supplier(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """#80: "lo Willard nunca es compra" (Q-04). El titular de una cuenta
        kg no puede ser proveedor del reparto — 422 con su nombre, y NADA
        persiste (D14). El MATERIAL si puede venir por compra si esta marcado
        compra_regular: lo exclusivo por canal es el TERCERO."""
        resp = client.post(f"{self.KG_URL}/accounts", headers=org_headers, json={
            "code": "W-BAT", "display_name": "Willard Baterias",
            "account_type": "willard_baterias",
            "warehouse_id": str(wh.id), "third_party_id": str(sup1.id),
        })
        assert resp.status_code == 201, resp.text

        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])]},
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json()["detail"]
        assert sup1.name in detail and "recepcion Willard" in detail
        assert _order_purchases(db_session, body["id"]) == []

    def test_non_holder_supplier_unaffected(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2
    ):
        """El guard es POR TERCERO: con una cuenta kg de sup1 viva, sup2
        reparte normal (no es una prohibicion global de material)."""
        client.post(f"{self.KG_URL}/accounts", headers=org_headers, json={
            "code": "W-BAT2", "display_name": "Willard Baterias 2",
            "account_type": "willard_baterias",
            "warehouse_id": str(wh.id), "third_party_id": str(sup1.id),
        })
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup2, "100", "1000")])],
        )
        assert len(_order_purchases(db_session, body["id"])) == 1

    # ---------------- Pago de contado por proveedor ----------------

    def test_payment_only_for_marked_supplier(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2, account
    ):
        """Opcional y POR PROVEEDOR (analogo a retenciones): a sup1 se le paga
        de contado, a sup2 se le queda debiendo. La caja baja solo lo de sup1."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "1000")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "600", "1000"), _alloc(sup2, "400", "1000")])],
            supplier_payments=[{
                "third_party_id": str(sup1.id), "account_id": str(account.id),
            }],
        )
        db_session.expire_all()
        assert db_session.get(ThirdParty, sup1.id).current_balance == 0  # pagado
        assert db_session.get(ThirdParty, sup2.id).current_balance == Decimal("-400000")
        from app.models.money_account import MoneyAccount
        assert db_session.get(MoneyAccount, account.id).current_balance == Decimal("400000")

        movs = db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.movement_type == "payment_to_supplier",
                MoneyMovement.status == "confirmed",
            )
        ).scalars().all()
        assert len(movs) == 1 and movs[0].amount == Decimal("600000")

    def test_payment_pays_net_of_retentions(
        self, client, org_headers, db_session, wh, mat_moto, sup1, account
    ):
        """El monto NO viaja en el payload: purchase.liquidate paga el NETO
        (#75). Con retencion de $15.000 sobre $100.000, sale $85.000 de caja y
        el proveedor queda en cero — no puede desalinearse del saldo."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
            supplier_retentions=[{
                "third_party_id": str(sup1.id),
                "retentions": [{"retention_type": "retefuente", "amount": "15000"}],
            }],
            supplier_payments=[{
                "third_party_id": str(sup1.id), "account_id": str(account.id),
            }],
        )
        db_session.expire_all()
        from app.models.money_account import MoneyAccount
        assert db_session.get(MoneyAccount, account.id).current_balance == Decimal("915000")
        assert db_session.get(ThirdParty, sup1.id).current_balance == 0

    def test_double_payment_blocked_on_reliquidation(
        self, client, org_headers, db_session, wh, mat_moto, sup1, account
    ):
        """🔴 El candado que abre esta feature: des-liquidar NO anula el pago
        (queda como anticipo, #16/#63), asi que re-liquidar marcando contado
        otra vez pagaria DOS veces. 422 con el monto vivo, y rollback total."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        pay = [{"third_party_id": str(sup1.id), "account_id": str(account.id)}]
        args = (client, org_headers, body["id"],
                [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])])
        _liquidate(*args, supplier_payments=pay)
        client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)

        resp = client.post(
            f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
            json={"lines": [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
                  "supplier_payments": pay},
        )
        assert resp.status_code == 422, resp.text
        assert "ya tiene un pago vivo" in resp.json()["detail"]

        # Rollback total: la entrada sigue revisada, sin compras liquidadas
        db_session.expire_all()
        assert client.get(
            f"{INBOUND_URL}/{body['id']}", headers=org_headers
        ).json()["display_status"] == "reviewed"

        # Sin pago SI puede re-liquidar (el anticipo se cruza con la deuda)
        _liquidate(*args)
        db_session.expire_all()
        assert db_session.get(ThirdParty, sup1.id).current_balance == 0

    def test_payment_validations(
        self, client, org_headers, db_session, wh, mat_moto, sup1, sup2, account
    ):
        """Proveedor fuera del reparto, bloque duplicado y cuenta inexistente."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        line = [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])]

        def liq(payments):
            return client.post(
                f"{INBOUND_URL}/{body['id']}/liquidate", headers=org_headers,
                json={"lines": line, "supplier_payments": payments},
            )

        r = liq([{"third_party_id": str(sup2.id), "account_id": str(account.id)}])
        assert r.status_code == 422 and "no esta en el reparto" in r.json()["detail"]

        r = liq([
            {"third_party_id": str(sup1.id), "account_id": str(account.id)},
            {"third_party_id": str(sup1.id), "account_id": str(account.id)},
        ])
        assert r.status_code == 422 and "dos veces" in r.json()["detail"]

        from uuid import uuid4
        r = liq([{"third_party_id": str(sup1.id), "account_id": str(uuid4())}])
        assert r.status_code == 404

        assert _order_purchases(db_session, body["id"]) == []  # nada persistio

    def test_no_payments_byte_identical(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """Data-gate: sin supplier_payments el camino queda igual — proveedor
        acreditado completo y CERO movimientos de dinero."""
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
        )
        db_session.expire_all()
        assert db_session.get(ThirdParty, sup1.id).current_balance == Decimal("-100000")
        assert db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.movement_type == "payment_to_supplier"
            )
        ).scalars().all() == []

    # ---------------- Hora real de la liquidacion ----------------

    def test_liquidated_ts_is_a_real_instant(
        self, client, org_headers, db_session, wh, mat_moto, sup1
    ):
        """La hora del clic vive en inbound_orders.liquidated_ts (tabla
        exclusiva SAC). NO se confunde con liquidated_at, que es fecha de
        NEGOCIO a mediodia UTC (#42/#87) y es por donde cortan los reportes."""
        from datetime import datetime, timezone
        body = _captured_reviewed(client, org_headers, wh, [_line(mat_moto, "100")])
        before = datetime.now(timezone.utc)
        _liquidate(
            client, org_headers, body["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", "1000")])],
        )
        detail = client.get(f"{INBOUND_URL}/{body['id']}", headers=org_headers).json()
        ts = datetime.fromisoformat(detail["liquidated_ts"])
        assert before <= ts <= datetime.now(timezone.utc)
        # la fecha de negocio sigue a mediodia — son campos distintos
        assert datetime.fromisoformat(detail["liquidated_at"]).hour == 12

        client.post(f"{INBOUND_URL}/{body['id']}/unliquidate", headers=org_headers)
        cleared = client.get(f"{INBOUND_URL}/{body['id']}", headers=org_headers).json()
        assert cleared["liquidated_ts"] is None  # se re-estampa al re-liquidar


# ---------------------------------------------------------------------------
# Ciclo Entradas (reunion 12-ago + respuestas telefonicas 13-ago)
# Q-13 peso obligatorio al revisar · D17 des-certificacion al editar lineas
# ---------------------------------------------------------------------------

class TestPesoObligatorioAlRevisar:
    """Q-13: opcional al CAPTURAR (el pesador es el eslabon apurado),
    obligatorio al REVISAR (el revisor es justo quien certifica lo pesado)."""

    def test_capturar_sin_peso_se_permite(self, client, org_headers, wh, mat_balancin):
        order = _capture(client, org_headers, wh, [_line(mat_balancin, 10, weight=None)])
        assert order["lines"][0]["scale_weight_kg"] is None

    def test_revisar_sin_peso_rechaza_y_nombra_el_material(
        self, client, org_headers, wh, mat_balancin,
    ):
        """El error nombra el material — el revisor tiene que saber cual
        devolver a bascula, no que 'falta un peso'."""
        order = _capture(client, org_headers, wh, [_line(mat_balancin, 10, weight=None)])
        resp = client.post(f"{INBOUND_URL}/{order['id']}/review", headers=org_headers)
        assert resp.status_code == 400, resp.text
        assert "BALANCIN-93" in resp.json()["detail"]
        # La revision fallida no deja rastro: sigue Registrada y sin certificar
        got = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers).json()
        assert got["status"] == "draft"
        assert got["reviewed_at"] is None

    def test_revisar_con_peso_pasa_y_lo_conserva(
        self, client, org_headers, wh, mat_balancin,
    ):
        order = _capture(client, org_headers, wh, [_line(mat_balancin, 10, weight="55.5")])
        body = _review(client, org_headers, order["id"])
        assert body["status"] == "reviewed"
        assert Decimal(body["lines"][0]["scale_weight_kg"]) == Decimal("55.5")

    def test_material_en_kg_autocompleta_el_peso(
        self, client, org_headers, wh, mat_moto, db_session,
    ):
        """D2: si el material YA se mide en kg, el peso ES la cantidad — pedir
        los dos seria friccion pura. Se PERSISTE, no se deriva al vuelo: el
        informe de peso promedio lee la columna."""
        order = _capture(client, org_headers, wh, [_line(mat_moto, "40", weight=None)])
        body = _review(client, org_headers, order["id"])
        assert body["status"] == "reviewed"
        assert Decimal(body["lines"][0]["scale_weight_kg"]) == Decimal("40")

    def test_mezcla_kg_y_unidad_solo_reclama_la_de_unidad(
        self, client, org_headers, wh, mat_moto, mat_balancin,
    ):
        order = _capture(
            client, org_headers, wh,
            [_line(mat_moto, "40", weight=None), _line(mat_balancin, 10, weight=None)],
        )
        resp = client.post(f"{INBOUND_URL}/{order['id']}/review", headers=org_headers)
        assert resp.status_code == 400, resp.text
        detail = resp.json()["detail"]
        assert "BALANCIN-93" in detail and "MOTO-93" not in detail

    def test_entrada_vieja_sin_peso_se_edita_y_se_revisa(
        self, client, org_headers, wh, mat_balancin,
    ):
        """Camino de salida para lo capturado antes de Q-13: editar y revisar.
        Sin esto, toda entrada vieja quedaria irrevisable."""
        order = _capture(client, org_headers, wh, [_line(mat_balancin, 10, weight=None)])
        _review(client, org_headers, order["id"], expect=400)
        resp = client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            json={"lines": [_line(mat_balancin, 10, weight="88")]},
        )
        assert resp.status_code == 200, resp.text
        body = _review(client, org_headers, order["id"])
        assert body["status"] == "reviewed"


class TestD17Descertificacion:
    """D17: el revisor certifica pesos y cantidades, que son LINEAS. Cambiarlas
    exige revisar de nuevo; la cabecera no toca lo certificado."""

    def test_editar_lineas_devuelve_a_registrada(
        self, client, org_headers, wh, mat_balancin,
    ):
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10)])
        got = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers).json()
        assert got["status"] == "reviewed"
        resp = client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            json={"lines": [_line(mat_balancin, 12)]},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "draft"
        assert body["reviewed_at"] is None
        assert any("Registrada" in w for w in body["warnings"])

    def test_editar_cabecera_no_descertifica(
        self, client, org_headers, wh, mat_balancin,
    ):
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10)])
        resp = client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            # La factura NO sirve de ejemplo de cabecera en tipo compra: vive
            # en el reparto por proveedor (#93 D12) y el PATCH la rechaza
            json={"notes": "llego con lluvia", "remission_number": "R-99"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "reviewed"
        assert body["reviewed_at"] is not None
        assert body["warnings"] == []

    def test_descertificada_no_se_liquida_hasta_revisar_de_nuevo(
        self, client, org_headers, wh, mat_balancin, sup1,
    ):
        """El punto de D17: sin esto se podia certificar y despues cambiar
        justo lo certificado, y liquidar igual."""
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10)])
        client.patch(
            f"{INBOUND_URL}/{order['id']}", headers=org_headers,
            json={"lines": [_line(mat_balancin, 12)]},
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 12, 500)])],
            expect=400,
        )
        _review(client, org_headers, order["id"])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 12, 500)])],
        )


class TestLiquidarPorValorTotal:
    """Q-15: Johana digita el VALOR TOTAL de la asignacion; el unitario es una
    formula, total / cantidad. El peso NO participa del calculo."""

    def test_total_deriva_el_unitario(
        self, client, org_headers, db_session, wh, mat_balancin, sup1,
    ):
        """El caso canonico del centavo: $200.000 entre 3 unidades dan
        $66.666,67 y el total vuelve como $200.000,01. Se acepta (D8) — hacerlo
        exacto obligaria a tocar purchase_lines, tabla compartida, por 1 centavo.
        Lo que NO se acepta es que sea una sorpresa: la pantalla muestra el
        total resultante antes de guardar."""
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 3)])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 3, total="200000")])],
        )
        allocs = db_session.execute(
            select(InboundLineAllocation).join(
                InboundLineAllocation.line
            ).where(InboundLineAllocation.third_party_id == sup1.id)
        ).scalars().all()
        assert len(allocs) == 1
        assert allocs[0].unit_price == Decimal("66666.67")
        assert allocs[0].total_price == Decimal("200000.00")  # el MODO persiste

        purchases = _order_purchases(db_session, order["id"])
        assert len(purchases) == 1
        assert purchases[0].total_amount == Decimal("200000.01")

    def test_mezcla_unitario_y_total_en_la_misma_entrada(
        self, client, org_headers, db_session, wh, mat_balancin, mat_moto, sup1, sup2,
    ):
        order = _captured_reviewed(
            client, org_headers, wh,
            [_line(mat_balancin, 10), _line(mat_moto, 20)],
        )
        _liquidate(
            client, org_headers, order["id"],
            [
                _liq_line(mat_balancin, [_alloc(sup1, 10, 500)]),
                _liq_line(mat_moto, [_alloc(sup2, 20, total="3000")]),
            ],
        )
        by_tp = {
            p.supplier_id: p for p in _order_purchases(db_session, order["id"])
        }
        assert by_tp[sup1.id].total_amount == Decimal("5000.00")
        assert by_tp[sup2.id].total_amount == Decimal("3000.00")  # 150 x 20

    def test_ni_precio_ni_total_rechaza(
        self, client, org_headers, wh, mat_balancin, sup1,
    ):
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10)])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 10)])],
            expect=422,
        )

    def test_precio_y_total_juntos_rechaza(
        self, client, org_headers, wh, mat_balancin, sup1,
    ):
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10)])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 10, 500, total="5000")])],
            expect=422,
        )

    def test_total_demasiado_bajo_avisa_claro(
        self, client, org_headers, wh, mat_balancin, sup1,
    ):
        """Sin este guard el unitario quedaria en $0 y reventaria mas abajo,
        en purchase.liquidate, con un error que no explica nada."""
        resp = _liquidate(
            client, org_headers,
            _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 10000)])["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 10000, total="0.01")])],
            expect=422,  # idioma del modulo: la Entrada responde 422 (#80)
        )
        assert "precio unitario queda en $0" in resp["detail"]

    def test_round_trip_conserva_el_modo_y_no_recrea_compras(
        self, client, org_headers, db_session, wh, mat_balancin, sup1,
    ):
        """D20 promete que el reparto sobrevive desliquidar/re-liquidar. El
        MODO es parte del reparto: si el total no se persistiera, al re-abrir
        Johana veria un unitario derivado en vez de lo que ella escribio.
        Y la firma cuantizada tiene que ver el MISMO numero, o cada
        re-liquidacion recrearia las compras."""
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 3)])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 3, total="200000")])],
        )
        before = [p.purchase_number for p in _order_purchases(db_session, order["id"])]

        client.post(f"{INBOUND_URL}/{order['id']}/unliquidate", headers=org_headers)
        detail = client.get(f"{INBOUND_URL}/{order['id']}", headers=org_headers).json()
        alloc = detail["lines"][0]["allocations"][0]
        assert Decimal(alloc["total_price"]) == Decimal("200000.00")

        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, 3, total="200000")])],
        )
        db_session.expire_all()
        after = [p.purchase_number for p in _order_purchases(db_session, order["id"])]
        assert after == before  # mismas compras, no nacieron nuevas

    def test_cuantizacion_cierra_la_identidad_al_gramo(
        self, client, org_headers, db_session, wh, mat_balancin, sup1, sup2,
    ):
        """Defecto pre-existente que el total hace mas probable: la asignacion
        guardaba 4 decimales y al inventario entra la de la compra, con 3 —
        la identidad 'pesado = repartido + descuadre' se rompia hasta 0,0005 kg
        por asignacion SIN NINGUN AVISO."""
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 100)])
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(
                mat_balancin,
                [_alloc(sup1, "33.3333", 500), _alloc(sup2, "66.6666", 500)],
                ref_price=500,
            )],
        )
        allocs = db_session.execute(
            select(InboundLineAllocation)
        ).scalars().all()
        # Persistido a la escala REAL (3 decimales), no a la de la columna
        assert {a.quantity for a in allocs} == {Decimal("33.333"), Decimal("66.667")}

        repartido = sum(a.quantity for a in allocs)
        adjustments = _order_adjustments(db_session, order["id"])
        descuadre = sum(
            (a.quantity if a.adjustment_type == "increase" else -a.quantity)
            for a in adjustments
        )
        # pesado == repartido + descuadre, exacto
        assert repartido - descuadre == Decimal("100.000")

    def test_cantidad_que_desaparece_al_cuantizar_explica(
        self, client, org_headers, wh, mat_balancin, sup1,
    ):
        """El schema exige cantidad > 0, pero valida ANTES de cuantizar: 0,0004
        pasa el Field y queda en 0,000. Antes de la guarda, la derivacion del
        unitario dividia por cero y devolvia un 500 sin explicacion."""
        order = _captured_reviewed(client, org_headers, wh, [_line(mat_balancin, 100)])
        r = client.post(
            f"/api/v1/inbound-orders/{order['id']}/liquidate",
            headers=org_headers,
            json={"lines": [_liq_line(
                mat_balancin, [_alloc(sup1, "0.0004", total="50000")], ref_price=500,
            )]},
        )
        assert r.status_code == 422, r.text
        assert "demasiado pequena" in r.json()["detail"]
        assert mat_balancin.code in r.json()["detail"]


# ------------------------------------------------- modo por kg (Q-15 v2) ---

def _allocs_de(client, headers, order_id, material_id):
    """Las asignaciones persistidas de un material, leidas por la API.

    Se lee por la API y no por el ORM a proposito: la trampa de #95 fue que el
    endpoint arma InboundAllocationResponse campo por campo, asi que la columna
    puede estar bien en la BD y llegar en None a la pantalla.
    """
    r = client.get(f"{INBOUND_URL}/{order_id}", headers=headers)
    assert r.status_code == 200, r.text
    for line in r.json()["lines"]:
        if line["material_id"] == str(material_id):
            return line["allocations"]
    raise AssertionError(f"material {material_id} no esta en la entrada")


class TestPrecioPorKg:
    """Hugo: 'no le va a pagar 100 unidades, le va a pagar por peso'."""

    def test_caso_canonico(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """10 baterias, 100 kg, $1.000/kg -> $10.000 c/u en inventario.

        El ejemplo de Daniel al pie de la letra. El inventario entra por
        UNIDAD y se costea por unidad (Hugo), aunque el pago sea por peso.
        """
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "10", per_kg="1000")])],
        )
        (purchase,) = _order_purchases(db_session, order["id"])
        (line,) = purchase.lines
        assert line.quantity == Decimal("10.000")
        assert line.unit_price == Decimal("10000.00")
        assert line.total_price == Decimal("100000.00")

    def test_asignaciones_independientes(
        self, client, org_headers, db_session, wh, sup1, sup2, mat_balancin
    ):
        """El argumento que decide el denominador (QA).

        El estimador es kg/unidad de la LINEA, asi que el pago de cada
        proveedor depende solo de su propia cantidad. Con la suma de las
        asignaciones como denominador, agregar el segundo proveedor cambiaria
        el pago del primero — que ya tiene su compra y su factura.
        """
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [
                _alloc(sup1, "6", per_kg="1000"),
                _alloc(sup2, "4", per_kg="1000"),
            ])],
        )
        allocs = {a["third_party_name"]: a for a in
                  _allocs_de(client, org_headers, order["id"], mat_balancin.id)}
        # ⚠️ Este test NO discrimina el denominador y hay que saberlo: con el
        # reparto COMPLETO (6+4=10) la suma de asignaciones iguala lo pesado,
        # asi que los dos criterios dan lo mismo — verificado plantando el
        # defecto: este pasa. Los que lo atrapan son `test_reparto_parcial`
        # (60 vs 100) y `test_sobre_reparto...` (120 vs 100). Lo que si clava
        # este son los numeros de negocio del caso normal.
        assert Decimal(allocs[sup1.name]["weight_kg_used"]) == Decimal("60.000")
        assert Decimal(allocs[sup2.name]["weight_kg_used"]) == Decimal("40.000")
        assert Decimal(allocs[sup1.name]["unit_price"]) == Decimal("10000.00")
        assert Decimal(allocs[sup2.name]["unit_price"]) == Decimal("10000.00")

    def test_precios_distintos_por_proveedor(
        self, client, org_headers, db_session, wh, sup1, sup2, mat_balancin
    ):
        """El caso real: cada proveedor paga SU peso a SU precio."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [
                _alloc(sup1, "6", per_kg="1000"),
                _alloc(sup2, "4", per_kg="1500"),
            ])],
        )
        allocs = {a["third_party_name"]: a for a in
                  _allocs_de(client, org_headers, order["id"], mat_balancin.id)}
        # sup1: 60 kg x 1.000 = 60.000 / 6 unidades = 10.000 c/u
        # sup2: 40 kg x 1.500 = 60.000 / 4 unidades = 15.000 c/u
        assert Decimal(allocs[sup1.name]["unit_price"]) == Decimal("10000.00")
        assert Decimal(allocs[sup2.name]["unit_price"]) == Decimal("15000.00")

    def test_reparto_parcial(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """6 de 10: el proveedor paga 60 kg, los otros 40 son del descuadre."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "6", per_kg="1000")],
                       ref_price="10000")],
        )
        (alloc,) = _allocs_de(client, org_headers, order["id"], mat_balancin.id)
        assert Decimal(alloc["weight_kg_used"]) == Decimal("60.000")

    def test_sobre_reparto_conserva_kg_por_unidad(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """12 unidades repartidas sobre 10 pesadas -> 120 kg, NO 100.

        🔴 Es el test que separa el denominador correcto del incorrecto, y
        hay que mirarle el NUMERO: con sum(allocations) daria 100,000 y
        tambien 'pasaria' cualquier assert que solo pida que exista un peso.
        """
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "12", per_kg="1000")],
                       ref_price="10000")],
        )
        (alloc,) = _allocs_de(client, org_headers, order["id"], mat_balancin.id)
        assert Decimal(alloc["weight_kg_used"]) == Decimal("120.000"), (
            "el estimador es kg/unidad de la linea: 12 unidades x 10 kg/u. "
            "Si dice 100 el denominador quedo en sum(allocations)"
        )

    def test_material_en_kg_con_diferencia_de_bascula(
        self, client, org_headers, db_session, wh, sup1, mat_moto
    ):
        """D4: el modo NO es redundante en materiales por kg.

        Se declaran 100 kg y la bascula certifica 98. Por unidad se pagaria
        sobre 100 declarados; por kg sobre 98 pesados, que es lo que Hugo
        pidio. Sin este test alguien 'simplifica' el modo de vuelta a la
        version equivocada del plan (no ofrecerlo en materiales por kg).
        """
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_moto, "100", weight="98")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_moto, [_alloc(sup1, "100", per_kg="1000")])],
        )
        (alloc,) = _allocs_de(client, org_headers, order["id"], mat_moto.id)
        assert Decimal(alloc["weight_kg_used"]) == Decimal("98.000")
        (purchase,) = _order_purchases(db_session, order["id"])
        (line,) = purchase.lines
        # 98 kg x 1.000 = 98.000 sobre 100 unidades declaradas = 980 c/u
        assert line.total_price == Decimal("98000.00")
        assert line.unit_price == Decimal("980.00")

    def test_truncamiento_sin_cantidad_pesada(
        self, client, org_headers, wh, sup1, mat_balancin, mat_grupo4
    ):
        """D4b guard 1 — el del DENOMINADOR: sin unidades no hay kg/unidad."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        r = client.post(
            f"{INBOUND_URL}/{order['id']}/liquidate", headers=org_headers,
            json={"lines": [
                _liq_line(mat_balancin, [_alloc(sup1, "10", per_kg="1000")]),
                _liq_line(mat_grupo4, [_alloc(sup1, "5", per_kg="1000")],
                          ref_price="100"),
            ]},
        )
        assert r.status_code == 422, r.text
        assert "GRUPO4-93" in r.text
        assert "cantidad pesada" in r.text

    def test_linea_sin_peso_de_bascula(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """D4b guard 2 — el del peso.

        Hoy nunca se alcanza por la via normal (el peso es obligatorio al
        revisar), asi que se fuerza el estado: es justamente el punto de D4b —
        que los dos guards existan por separado, porque hoy coinciden SOLO por
        el orden del flujo y no por un invariante.
        """
        from app.models.inbound_order import InboundOrderLine

        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        line = db_session.execute(
            select(InboundOrderLine).where(
                InboundOrderLine.inbound_order_id == UUID(str(order["id"]))
            )
        ).scalars().one()
        line.scale_weight_kg = None
        db_session.commit()

        r = client.post(
            f"{INBOUND_URL}/{order['id']}/liquidate", headers=org_headers,
            json={"lines": [
                _liq_line(mat_balancin, [_alloc(sup1, "10", per_kg="1000")])
            ]},
        )
        assert r.status_code == 422, r.text
        assert "peso de bascula" in r.text

    def test_xor_de_tres(self, client, org_headers, wh, sup1, mat_balancin):
        """Exactamente uno de los tres precios."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        for alloc in (
            _alloc(sup1, "10", price="100", per_kg="1000"),   # dos
            _alloc(sup1, "10", total="1000", per_kg="1000"),  # dos
            _alloc(sup1, "10"),                               # ninguno
        ):
            r = client.post(
                f"{INBOUND_URL}/{order['id']}/liquidate", headers=org_headers,
                json={"lines": [_liq_line(mat_balancin, [alloc])]},
            )
            assert r.status_code == 422, r.text

    def test_trazabilidad_sobrevive_el_round_trip(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """#93 D20: des-liquidar conserva el reparto — CON su modo e insumos.

        Es la razon de fondo para persistir: un modo de captura que no
        sobrevive el round-trip es un reparto que en realidad no se conservo.
        """
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "10", per_kg="1000")])],
        )
        r = client.post(f"{INBOUND_URL}/{order['id']}/unliquidate",
                        headers=org_headers)
        assert r.status_code == 200, r.text

        (alloc,) = _allocs_de(client, org_headers, order["id"], mat_balancin.id)
        assert Decimal(alloc["price_per_kg"]) == Decimal("1000.00")
        assert Decimal(alloc["weight_kg_used"]) == Decimal("100.000")

    def test_reliquidar_igual_no_dispara_revert_and_reapply(
        self, client, org_headers, db_session, wh, sup1, mat_balancin
    ):
        """La propiedad gratis de D1: el modo kg deriva el MISMO unit_price,
        asi que la firma de #93 no cambia y la compra se reusa tal cual."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        lines = [_liq_line(mat_balancin, [_alloc(sup1, "10", per_kg="1000")])]
        _liquidate(client, org_headers, order["id"], lines)
        (antes,) = _order_purchases(db_session, order["id"])
        numero, pid = antes.purchase_number, antes.id

        client.post(f"{INBOUND_URL}/{order['id']}/unliquidate", headers=org_headers)
        _liquidate(client, org_headers, order["id"], lines)

        (despues,) = _order_purchases(db_session, order["id"])
        assert despues.id == pid and despues.purchase_number == numero

    def test_modo_unitario_no_escribe_los_campos_nuevos(
        self, client, org_headers, wh, sup1, mat_balancin
    ):
        """No-regresion: una asignacion que no usa el modo kg queda igual."""
        order = _captured_reviewed(
            client, org_headers, wh, [_line(mat_balancin, "10", weight="100")]
        )
        _liquidate(
            client, org_headers, order["id"],
            [_liq_line(mat_balancin, [_alloc(sup1, "10", price="10000")])],
        )
        (alloc,) = _allocs_de(client, org_headers, order["id"], mat_balancin.id)
        assert alloc["price_per_kg"] is None
        assert alloc["weight_kg_used"] is None
