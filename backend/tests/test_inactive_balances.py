"""
Tests del Panel de Dinero Inactivo (R1).

Plan: docs/planes/plan-panel-dinero-inactivo.md

Regla central: lista saldos del LADO ACTIVO (terceros que nos deben) sin
movimiento >= min_days. El reloj se reinicia con cualquier evento VIVO que
mueva el saldo (D1); las canceladas/anuladas NO cuentan. Terceros sin eventos
cuentan desde created_at (fallback D6). Umbral configurable por query param.

Watch-points de QA cubiertos:
- El agregado filtra confirmed/liquidated SOLO (test_cancellation_does_not_reset_clock).
- DP alimenta AMBOS roles del group-by (test_double_entry_feeds_both_roles).
- Timezone Bogota sin off-by-one (todos los asserts de days_inactive).
- organization_id en cada rama (test_other_org_not_leaked).
"""
import itertools
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import update

from app.models.money_movement import MoneyMovement
from app.models.third_party import ThirdParty
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    create_material_category,
    create_material,
    create_warehouse,
    create_account,
    api_create_adjustment,
    api_create_sale,
    api_create_double_entry,
    api_cancel_sale,
)

URL = "/api/v1/reports/inactive-balances"
BOGOTA = timezone(timedelta(hours=-5))
_num = itertools.count(70000)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today():
    return datetime.now(BOGOTA).date()


def _ago(n: int) -> str:
    return (_today() - timedelta(days=n)).isoformat()


def _mm(db, org_id, tp_id, days_ago, *, mtype="payment_to_supplier",
        amount=100000, status="confirmed"):
    """Crea un MoneyMovement directo con date = mediodia UTC de hace `days_ago` dias.

    Solo controla el reloj de ultima actividad; NO toca current_balance del tercero
    (ese se setea aparte al crear el tercero) — permite fijar saldo y antiguedad
    de forma independiente y determinista.
    """
    d = _today() - timedelta(days=days_ago)
    dt = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
    mm = MoneyMovement(
        organization_id=org_id, movement_type=mtype, amount=Decimal(str(amount)),
        description="Actividad test", date=dt, status=status,
        movement_number=next(_num), third_party_id=tp_id,
    )
    db.add(mm)
    db.commit()  # el endpoint corre en otra sesion (override_get_db) → necesita commit
    return mm


def _tp(db, org_id, name, behavior, balance, *, created_days_ago=None, system=False):
    """Crea un tercero del lado activo con balance y opcionalmente created_at controlado."""
    tp = create_third_party_with_category(
        db, org_id, name, behavior,
        current_balance=Decimal(str(balance)), initial_balance=Decimal(str(balance)),
        is_system_entity=system,
    )
    if created_days_ago is not None:
        d = _today() - timedelta(days=created_days_ago)
        dt = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
        db.execute(update(ThirdParty).where(ThirdParty.id == tp.id).values(created_at=dt))
    db.commit()  # visibilidad para la sesion del endpoint
    return tp


def _call(client, headers, min_days=10, min_amount=0):
    resp = client.get(f"{URL}?min_days={min_days}&min_amount={min_amount}", headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


def _find(data, tp_id):
    for item in data["items"]:
        if item["third_party_id"] == str(tp_id):
            return item
    return None


@pytest.fixture
def setup(db_session, test_organization, client, org_headers):
    """Material con stock + bodega + cuenta, para las operaciones reales."""
    org_id = test_organization.id
    cat = create_material_category(db_session, org_id, "InactCat")
    mat = create_material(db_session, org_id, "INA-1", "Chatarra", cat.id)
    wh = create_warehouse(db_session, org_id, "Bodega Inact")
    acc = create_account(db_session, org_id, "Caja Inact", balance=50_000_000)
    db_session.commit()  # el API (sesion nueva) necesita ver los maestros
    api_create_adjustment(
        client, org_headers, adjustment_type="increase",
        material_id=mat.id, warehouse_id=wh.id, quantity=100000, unit_cost=1000,
    )
    return {"org_id": org_id, "mat": mat, "wh": wh, "acc": acc}


# ---------------------------------------------------------------------------
# Caso feliz + umbral
# ---------------------------------------------------------------------------

class TestInactiveBasics:

    def test_supplier_advance_appears(self, client, org_headers, db_session, test_organization):
        """Anticipo a proveedor inactivo 15 dias, umbral 10 → aparece con days=15."""
        tp = _tp(db_session, test_organization.id, "Prov Anticipo", "material_supplier", 3_000_000)
        _mm(db_session, test_organization.id, tp.id, 15)
        data = _call(client, org_headers, min_days=10)
        item = _find(data, tp.id)
        assert item is not None
        assert item["days_inactive"] == 15
        assert item["amount_inactive"] == 3_000_000
        assert item["third_party_type"] == "material_supplier"
        assert item["has_movements"] is True

    def test_customer_receivable_appears(self, client, org_headers, db_session, test_organization):
        """CxC de cliente inactiva → aparece del lado activo."""
        tp = _tp(db_session, test_organization.id, "Cliente CxC", "customer", 5_000_000)
        _mm(db_session, test_organization.id, tp.id, 30, mtype="collection_from_client")
        item = _find(_call(client, org_headers), tp.id)
        assert item is not None and item["days_inactive"] == 30
        assert item["third_party_type"] == "customer"

    def test_below_threshold_excluded(self, client, org_headers, db_session, test_organization):
        """Mismo tercero de 15 dias, umbral 20 → no aparece."""
        tp = _tp(db_session, test_organization.id, "Prov Reciente", "material_supplier", 3_000_000)
        _mm(db_session, test_organization.id, tp.id, 15)
        assert _find(_call(client, org_headers, min_days=20), tp.id) is None

    def test_min_amount_filter(self, client, org_headers, db_session, test_organization):
        """Saldo de $500 con min_amount=1000 → excluido."""
        tp = _tp(db_session, test_organization.id, "Prov Chico", "material_supplier", 500)
        _mm(db_session, test_organization.id, tp.id, 40)
        assert _find(_call(client, org_headers, min_amount=1000), tp.id) is None
        # sin filtro de monto sí aparece
        assert _find(_call(client, org_headers, min_amount=0), tp.id) is not None

    def test_min_days_zero_returns_active_side(self, client, org_headers, db_session, test_organization):
        """min_days=0 → todos los del lado activo con balance != 0 (aun de hoy)."""
        tp = _tp(db_session, test_organization.id, "Prov Hoy", "material_supplier", 2_000_000)
        _mm(db_session, test_organization.id, tp.id, 0)
        item = _find(_call(client, org_headers, min_days=0), tp.id)
        assert item is not None and item["days_inactive"] == 0

    def test_ordered_oldest_first(self, client, org_headers, db_session, test_organization):
        """La lista viene ordenada por dias inactivos DESC (mas viejo arriba)."""
        a = _tp(db_session, test_organization.id, "Prov A", "material_supplier", 1_000_000)
        b = _tp(db_session, test_organization.id, "Prov B", "material_supplier", 1_000_000)
        _mm(db_session, test_organization.id, a.id, 12)
        _mm(db_session, test_organization.id, b.id, 55)
        items = _call(client, org_headers)["items"]
        days = [i["days_inactive"] for i in items]
        assert days == sorted(days, reverse=True)
        assert items[0]["third_party_id"] == str(b.id)  # 55 dias arriba


# ---------------------------------------------------------------------------
# Clasificacion — solo lado activo
# ---------------------------------------------------------------------------

class TestClassification:

    def test_liability_side_excluded(self, client, org_headers, db_session, test_organization):
        """Tercero al que le DEBEMOS (saldo pasivo) inactivo → NO aparece."""
        tp = _tp(db_session, test_organization.id, "Le Debemos", "material_supplier", -4_000_000)
        _mm(db_session, test_organization.id, tp.id, 60)
        assert _find(_call(client, org_headers), tp.id) is None

    def test_prepaid_expense_excluded(self, client, org_headers, db_session, test_organization):
        """Entidad de sistema (prepago) con balance > 0 → NO aparece (no perseguible)."""
        tp = _tp(db_session, test_organization.id, "[Prepago] Arriendo", "service_provider",
                 6_000_000, system=True)
        _mm(db_session, test_organization.id, tp.id, 45)
        assert _find(_call(client, org_headers), tp.id) is None

    def test_provision_funds_included_abs(self, client, org_headers, db_session, test_organization):
        """Provision con balance < 0 (fondos apartados) → aparece con amount = abs()."""
        tp = _tp(db_session, test_organization.id, "Proyecto Congelado", "provision", -8_000_000)
        _mm(db_session, test_organization.id, tp.id, 22, mtype="provision_deposit")
        item = _find(_call(client, org_headers), tp.id)
        assert item is not None
        assert item["amount_inactive"] == 8_000_000  # abs
        assert item["third_party_type"] == "provision"

    def test_zero_balance_excluded(self, client, org_headers, db_session, test_organization):
        """Balance 0 → no aparece."""
        tp = _tp(db_session, test_organization.id, "Saldado", "material_supplier", 0)
        _mm(db_session, test_organization.id, tp.id, 30)
        assert _find(_call(client, org_headers, min_days=0), tp.id) is None


# ---------------------------------------------------------------------------
# Fuentes de ultima actividad (D1)
# ---------------------------------------------------------------------------

class TestActivitySources:

    def test_last_activity_from_liquidated_sale(self, client, org_headers, db_session, setup):
        """La ultima actividad de un cliente viene de una venta liquidada (rama ventas)."""
        cust = _tp(db_session, setup["org_id"], "Cliente Venta", "customer", 0)
        sale = api_create_sale(
            client, org_headers, customer_id=cust.id, warehouse_id=setup["wh"].id,
            lines=[{"material_id": setup["mat"].id, "quantity": 100, "unit_price": 5000}],
            date=_ago(20),
        )
        resp = client.patch(f"/api/v1/sales/{sale['id']}/liquidate",
                            json={"liquidation_date": _ago(20)}, headers=org_headers)
        assert resp.status_code == 200, resp.json()
        item = _find(_call(client, org_headers), cust.id)
        assert item is not None
        assert item["days_inactive"] == 20
        assert item["has_movements"] is True
        assert item["last_activity_date"][:10] == _ago(20)

    def test_money_movement_resets_clock(self, client, org_headers, db_session, test_organization):
        """Un movimiento reciente (hace 5d) manda sobre uno viejo (hace 50d)."""
        tp = _tp(db_session, test_organization.id, "Prov Dos Mov", "material_supplier", 2_000_000)
        _mm(db_session, test_organization.id, tp.id, 50)
        _mm(db_session, test_organization.id, tp.id, 5)
        # con umbral 10, el reloj esta en 5d (mas reciente) → NO aparece
        assert _find(_call(client, org_headers, min_days=10), tp.id) is None

    def test_cancellation_does_not_reset_clock(self, client, org_headers, db_session, setup):
        """Venta viva vieja + venta cancelada reciente → el reloj mide desde la VIVA (D1)."""
        cust = _tp(db_session, setup["org_id"], "Cliente Cancel", "customer", 0)
        # venta viva hace 40 dias
        s1 = api_create_sale(
            client, org_headers, customer_id=cust.id, warehouse_id=setup["wh"].id,
            lines=[{"material_id": setup["mat"].id, "quantity": 100, "unit_price": 5000}],
            date=_ago(40),
        )
        client.patch(f"/api/v1/sales/{s1['id']}/liquidate",
                     json={"liquidation_date": _ago(40)}, headers=org_headers)
        # segunda venta, liquidada hace 2 dias, luego CANCELADA
        s2 = api_create_sale(
            client, org_headers, customer_id=cust.id, warehouse_id=setup["wh"].id,
            lines=[{"material_id": setup["mat"].id, "quantity": 50, "unit_price": 5000}],
            date=_ago(2),
        )
        client.patch(f"/api/v1/sales/{s2['id']}/liquidate",
                     json={"liquidation_date": _ago(2)}, headers=org_headers)
        api_cancel_sale(client, org_headers, s2["id"])
        item = _find(_call(client, org_headers), cust.id)
        assert item is not None
        # el reloj NO se resetea a 2d por la cancelacion — sigue en 40d (la venta viva)
        assert item["days_inactive"] == 40

    def test_double_entry_feeds_both_roles(self, client, org_headers, db_session, setup):
        """DP alimenta AMBOS roles del group-by (watch-point #2 de QA).

        El proveedor del DP trae un anticipo previo LEJANO (hace 100d). Si la rama
        6a (supplier) del agregado no existiera, su ultima actividad seria 100d;
        con ella, es la del DP (25d). El cliente del DP (rama 6b) aparece a 25d.
        """
        org_id = setup["org_id"]
        supp = _tp(db_session, org_id, "Prov DP", "material_supplier", 0)
        cust = _tp(db_session, org_id, "Cliente DP", "customer", 0)
        # anticipo previo lejano al proveedor (lo deja con saldo a favor + actividad de 100d)
        _mm(db_session, org_id, supp.id, 100, mtype="advance_payment", amount=20_000_000)
        db_session.execute(
            update(ThirdParty).where(ThirdParty.id == supp.id).values(current_balance=Decimal("20000000"))
        )
        db_session.commit()
        de = api_create_double_entry(
            client, org_headers, supplier_id=supp.id, customer_id=cust.id,
            lines=[{"material_id": setup["mat"].id, "quantity": 100,
                    "purchase_unit_price": 3000, "sale_unit_price": 5000}],
            date=_ago(25),
        )
        client.patch(f"/api/v1/double-entries/{de['id']}/liquidate",
                     json={"liquidation_date": _ago(25)}, headers=org_headers)
        data = _call(client, org_headers, min_days=10)
        # cliente del DP (rama 6b): nos debe → aparece a 25d
        ci = _find(data, cust.id)
        assert ci is not None and ci["days_inactive"] == 25
        # proveedor del DP (rama 6a): el DP (25d) mando sobre el anticipo (100d)
        si = _find(data, supp.id)
        assert si is not None, "el proveedor deberia seguir con saldo a favor y aparecer"
        assert si["days_inactive"] == 25, "la rama 6a (supplier) del DP debe alimentar el reloj"
        # sin duplicados: cada tercero una sola vez
        ids = [i["third_party_id"] for i in data["items"]]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Edge + fallback D6
# ---------------------------------------------------------------------------

class TestEdge:

    def test_no_movements_falls_back_to_created_at(self, client, org_headers, db_session, test_organization):
        """Tercero con initial_balance y CERO eventos → dias desde created_at (D6)."""
        tp = _tp(db_session, test_organization.id, "Migrado Sin Mov", "material_supplier",
                 14_000_000, created_days_ago=70)
        item = _find(_call(client, org_headers), tp.id)
        assert item is not None
        assert item["has_movements"] is False
        assert item["last_activity_date"] is None
        assert item["days_inactive"] == 70

    def test_totals_and_count(self, client, org_headers, db_session, test_organization):
        """total_inactive_balance e item_count reflejan lo listado."""
        a = _tp(db_session, test_organization.id, "T A", "material_supplier", 1_000_000)
        b = _tp(db_session, test_organization.id, "T B", "customer", 2_500_000)
        _mm(db_session, test_organization.id, a.id, 30)
        _mm(db_session, test_organization.id, b.id, 20, mtype="collection_from_client")
        data = _call(client, org_headers)
        assert data["item_count"] >= 2
        listed = sum(i["amount_inactive"] for i in data["items"])
        assert abs(data["total_inactive_balance"] - listed) < 0.01


# ---------------------------------------------------------------------------
# Multi-tenancy + RBAC
# ---------------------------------------------------------------------------

class TestTenancyAndRBAC:

    def test_other_org_not_leaked(self, client, org_headers, org_headers2, db_session,
                                  test_organization, test_organization2):
        """Un tercero inactivo de otra org NO aparece (organization_id en cada rama)."""
        other = _tp(db_session, test_organization2.id, "Prov Otra Org", "material_supplier", 9_000_000)
        _mm(db_session, test_organization2.id, other.id, 50)
        # consultado desde la org 1 no debe verse
        assert _find(_call(client, org_headers), other.id) is None
        # desde la org 2 sí
        assert _find(_call(client, org_headers2), other.id) is not None

    def test_requires_permission(self, client, db_session, test_organization):
        """Sin reports.view / reports.view_balance → 403; con permiso → 200."""
        from app.core.security import create_access_token
        from app.models.role import Role
        from app.models.user import User, OrganizationMember

        def _user_with_role(role_name, email):
            u = User(email=email, hashed_password="x", full_name=email, is_active=True)
            db_session.add(u)
            db_session.flush()
            role = db_session.query(Role).filter(
                Role.organization_id == test_organization.id,
                Role.name == role_name, Role.is_system_role == True,
            ).first()
            assert role is not None, f"Rol {role_name} no encontrado"
            db_session.add(OrganizationMember(
                user_id=u.id, organization_id=test_organization.id, role_id=role.id,
            ))
            db_session.commit()  # el endpoint valida el token en otra sesion
            return u

        def _hdr(user):
            token = create_access_token(data={"sub": str(user.id)})
            return {"Authorization": f"Bearer {token}",
                    "X-Organization-ID": str(test_organization.id)}

        # bascula: no ve reportes → 403
        denied = client.get(URL, headers=_hdr(_user_with_role("bascula", "basc-inact@test.com")))
        assert denied.status_code == 403, denied.json()
        # viewer: acceso de lectura a reportes → 200
        allowed = client.get(URL, headers=_hdr(_user_with_role("viewer", "view-inact@test.com")))
        assert allowed.status_code == 200, allowed.json()
