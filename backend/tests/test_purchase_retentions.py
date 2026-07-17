"""
Tests Retenciones D9 (SAC E2, plan-sac-e2-kgledger-inbound.md §8).

Cubre: bloques compensatorios (proveedor neto, entidad sistema, pasivo
conservado), entidades idempotentes con matching sin acentos (H4), categoria
liability de sistema (Balance + pago), pago inmediato NETO + regresion del
camino bruto, cancel con reverted_at, paridad statement vs saldo vivo
(clase #55), flag gating y validaciones.
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models.purchase_retention import PurchaseRetention
from app.models.third_party import ThirdParty
from tests.integration_helpers import create_warehouse, create_account
from tests.conftest import create_third_party_with_category

PURCHASES_URL = "/api/v1/purchases"
STATEMENT_URL = "/api/v1/money-movements/third-party"
TP_URL = "/api/v1/third-parties"
BS_URL = "/api/v1/reports/balance-sheet"


def _biz_date() -> str:
    """Fecha de negocio pasada (tz-robusta): el validador de liquidacion de
    compras usa date.today() LOCAL, mientras el test corre en UTC — en la
    ventana 00-05 UTC 'hoy UTC' es futuro respecto a 'hoy local'. Una fecha
    pasada evita el boundary en cualquier zona horaria."""
    return (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Bodega Ret")
    db_session.commit()
    return wh


@pytest.fixture
def supplier(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Chatarra", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def material(db_session, test_organization):
    from tests.integration_helpers import create_material, create_material_category
    cat = create_material_category(db_session, test_organization.id, "Cat Ret")
    mat = create_material(db_session, test_organization.id, "RET-MAT", "Material Ret", cat.id)
    db_session.commit()
    return mat


@pytest.fixture
def account(db_session, test_organization):
    acc = create_account(db_session, test_organization.id, "Caja Ret", balance=10_000_000)
    db_session.commit()
    return acc


def _create_purchase(client, headers, supplier, material, warehouse, qty=100, price=10_000):
    resp = client.post(
        PURCHASES_URL,
        headers=headers,
        json={
            "supplier_id": str(supplier.id),
            "date": _biz_date(),
            "lines": [{
                "material_id": str(material.id),
                "warehouse_id": str(warehouse.id),
                "quantity": qty,
                "unit_price": price,
            }],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _liquidate(client, headers, purchase_id, retentions=None, **extra):
    body = {"liquidation_date": _biz_date(), **extra}
    if retentions is not None:
        body["retentions"] = retentions
    return client.patch(f"{PURCHASES_URL}/{purchase_id}/liquidate", headers=headers, json=body)


def _system_entities(db, org_id):
    return db.execute(
        select(ThirdParty).where(
            ThirdParty.organization_id == org_id,
            ThirdParty.is_system_entity == True,  # noqa: E712
            ThirdParty.name.like("[Retenciones]%"),
        )
    ).scalars().all()


class TestRetentionLiquidation:
    def test_happy_compensating_blocks(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)  # $1.000.000
        resp = _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "25000", "rate": "2.5"},
            {"retention_type": "ica", "municipality": "Barranquilla", "amount": "10000"},
        ])
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["retentions"]) == 2

        # Proveedor acreditado NETO: −(1.000.000 − 35.000)
        db_session.expire_all()
        db_session.refresh(supplier)
        assert supplier.current_balance == Decimal("-965000.00")

        # Entidades sistema con saldo negativo (les debemos) y categoria liability
        entities = _system_entities(db_session, test_organization.id)
        by_name = {e.name: e for e in entities}
        assert by_name["[Retenciones] ReteFuente"].current_balance == Decimal("-25000.00")
        assert by_name["[Retenciones] ICA Barranquilla"].current_balance == Decimal("-10000.00")
        for e in entities:
            behaviors = {
                a.category.behavior_type for a in e.category_assignments
            }
            assert "liability" in behaviors

        # Pasivo total conservado: proveedor + entidades == −total
        total_liability = supplier.current_balance + sum(e.current_balance for e in entities)
        assert total_liability == Decimal("-1000000.00")

    def test_flag_off_422(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        test_organization.settings = {}
        db_session.commit()
        resp = _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "1000"},
        ])
        assert resp.status_code == 422
        assert "no habilitado" in resp.json()["detail"]

    def test_no_retentions_path_untouched(
        self, client, org_headers, db_session, supplier, material, warehouse,
        test_organization,
    ):
        """Regresion: sin retenciones el camino es el actual (bruto)."""
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        resp = _liquidate(client, org_headers, p["id"])
        assert resp.status_code == 200
        db_session.refresh(supplier)
        assert supplier.current_balance == Decimal("-1000000.00")
        assert _system_entities(db_session, test_organization.id) == []

    def test_sum_exceeds_total_422(
        self, client, org_headers, supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        resp = _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "1000000"},
        ])
        assert resp.status_code == 422
        assert "menor al" in resp.json()["detail"]

    def test_ica_municipality_validation(
        self, client, org_headers, supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        # ICA sin municipio -> 422 (schema)
        resp = _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "ica", "amount": "1000"},
        ])
        assert resp.status_code == 422
        # ReteFuente CON municipio -> 422 (schema)
        resp = _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "municipality": "Bogota", "amount": "1000"},
        ])
        assert resp.status_code == 422

    def test_ica_accent_case_insensitive_h4(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        """H4 QA: 'Bogotá' y 'bogota' resuelven a la MISMA entidad; se
        persiste el display bonito de la primera vez."""
        p1 = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p1["id"], retentions=[
            {"retention_type": "ica", "municipality": "Bogotá", "amount": "5000"},
        ])
        p2 = _create_purchase(client, org_headers, supplier, material, warehouse)
        resp = _liquidate(client, org_headers, p2["id"], retentions=[
            {"retention_type": "ica", "municipality": "bogota", "amount": "3000"},
        ])
        assert resp.status_code == 200, resp.text

        entities = [
            e for e in _system_entities(db_session, test_organization.id)
            if "ICA" in e.name
        ]
        assert len(entities) == 1
        assert entities[0].name == "[Retenciones] ICA Bogotá"
        assert entities[0].current_balance == Decimal("-8000.00")

    def test_entity_reuse_idempotent(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        for _ in range(2):
            p = _create_purchase(client, org_headers, supplier, material, warehouse)
            resp = _liquidate(client, org_headers, p["id"], retentions=[
                {"retention_type": "reteiva", "amount": "2000"},
            ])
            assert resp.status_code == 200
        entities = [
            e for e in _system_entities(db_session, test_organization.id)
            if "ReteIVA" in e.name
        ]
        assert len(entities) == 1
        assert entities[0].current_balance == Decimal("-4000.00")


class TestRetentionImmediatePayment:
    def test_pays_net(
        self, client, org_headers, db_session, supplier, material, warehouse, account,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        resp = _liquidate(
            client, org_headers, p["id"],
            retentions=[{"retention_type": "retefuente", "amount": "35000"}],
            immediate_payment=True,
            payment_account_id=str(account.id),
        )
        assert resp.status_code == 200, resp.text
        db_session.expire_all()
        db_session.refresh(account)
        db_session.refresh(supplier)
        # Pago NETO: 1.000.000 − 35.000 = 965.000
        assert account.current_balance == Decimal("9035000.00")
        assert supplier.current_balance == Decimal("0.00")

    def test_gross_regression_without_retentions(
        self, client, org_headers, db_session, supplier, material, warehouse, account,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        resp = _liquidate(
            client, org_headers, p["id"],
            immediate_payment=True,
            payment_account_id=str(account.id),
        )
        assert resp.status_code == 200
        db_session.refresh(account)
        assert account.current_balance == Decimal("9000000.00")


class TestRetentionCancel:
    def test_cancel_reverts_blocks(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "25000"},
        ])
        resp = client.patch(f"{PURCHASES_URL}/{p['id']}/cancel", headers=org_headers)
        assert resp.status_code == 200, resp.text

        db_session.expire_all()
        db_session.refresh(supplier)
        assert supplier.current_balance == Decimal("0.00")
        entity = _system_entities(db_session, test_organization.id)[0]
        assert entity.current_balance == Decimal("0.00")
        ret = db_session.execute(
            select(PurchaseRetention).where(PurchaseRetention.purchase_id == p["id"])
        ).scalar_one()
        assert ret.reverted_at is not None


class TestRetentionStatementParity:
    def _final_balance(self, client, headers, tp_id):
        resp = client.get(
            f"{STATEMENT_URL}/{tp_id}",
            headers=headers,
            params={"date_from": "2020-01-01", "limit": 500},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        items = data["items"]
        return (items[-1]["balance_after"] if items else 0.0), data["current_balance"], items

    def test_supplier_statement_matches_live(
        self, client, org_headers, supplier, material, warehouse,
    ):
        """Clase #55: saldo corrido del statement == saldo vivo, con el evento
        sintetico +retencion compensando el −total del evento compra."""
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "25000"},
        ])
        final, live, items = self._final_balance(client, org_headers, supplier.id)
        assert live == pytest.approx(-975000.0)  # −(1.000.000 − 25.000)
        assert final == pytest.approx(live)
        assert any("Retencion ReteFuente" in (i.get("description") or "") for i in items)

    def test_entity_statement_matches_live(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "ica", "municipality": "Monteria", "amount": "12000"},
        ])
        entity = _system_entities(db_session, test_organization.id)[0]
        final, live, items = self._final_balance(client, org_headers, entity.id)
        assert live == pytest.approx(-12000.0)
        assert final == pytest.approx(live)
        assert any("ICA Monteria" in (i.get("description") or "") for i in items)

    def test_statement_after_cancel_returns_to_zero(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "reteiva", "amount": "9000"},
        ])
        client.patch(f"{PURCHASES_URL}/{p['id']}/cancel", headers=org_headers)

        final, live, _ = self._final_balance(client, org_headers, supplier.id)
        assert live == pytest.approx(0.0)
        assert final == pytest.approx(0.0)
        entity = _system_entities(db_session, test_organization.id)[0]
        final_e, live_e, _ = self._final_balance(client, org_headers, entity.id)
        assert live_e == pytest.approx(0.0)
        assert final_e == pytest.approx(0.0)


class TestRetentionBalanceAndPayment:
    def test_entity_in_balance_sheet_liability(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        bs_before = client.get(BS_URL, headers=org_headers).json()
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "40000"},
        ])
        bs_after = client.get(BS_URL, headers=org_headers).json()
        delta = bs_after["liabilities"]["liability_debt"] - bs_before["liabilities"]["liability_debt"]
        assert delta == pytest.approx(40000.0)

    def test_liabilities_selector_include_system(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse,
    ):
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "reteiva", "amount": "5000"},
        ])
        names = [
            i["name"] for i in client.get(
                f"{TP_URL}/liabilities", headers=org_headers
            ).json()["items"]
        ]
        assert "[Retenciones] ReteIVA" not in names
        names = [
            i["name"] for i in client.get(
                f"{TP_URL}/liabilities", headers=org_headers,
                params={"include_system": True},
            ).json()["items"]
        ]
        assert "[Retenciones] ReteIVA" in names

    def test_pay_retention_entity_via_payment_to_supplier(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse, account,
    ):
        """El pago mensual de la retencion es un payment_to_supplier normal
        (la categoria liability lo habilita, #33)."""
        p = _create_purchase(client, org_headers, supplier, material, warehouse)
        _liquidate(client, org_headers, p["id"], retentions=[
            {"retention_type": "retefuente", "amount": "30000"},
        ])
        entity = _system_entities(db_session, test_organization.id)[0]
        resp = client.post(
            "/api/v1/money-movements/supplier-payment",
            headers=org_headers,
            json={
                "supplier_id": str(entity.id),
                "amount": 30000,
                "account_id": str(account.id),
                "date": _biz_date(),
                "description": "Pago retenciones mes",
            },
        )
        assert resp.status_code in (200, 201), resp.text
        db_session.expire_all()
        entity = db_session.get(ThirdParty, entity.id)
        assert entity.current_balance == Decimal("0.00")
