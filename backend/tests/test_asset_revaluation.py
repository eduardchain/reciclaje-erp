"""
Tests para Revalorización de Activos Fijos (requerimiento D — plan-revalorizacion-activos.md).

Cubre: 4 happy paths (alza/baja × cuenta/tercero), validaciones, recalculo de cuota
(extensión de vida, última cuota, revivir fully_depreciated), anulación (round-trip,
guard LIFO, bloqueo desde Tesorería, cancel del activo), reportes (H1 golden as-of
sin restatement, H2 as-of == vivo, H2b saldo corrido de statements, H4 cash flow +
dashboard MTD, P&L intocado) y RBAC.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.expense_category import ExpenseCategory
from app.models.money_account import MoneyAccount
from app.models.money_movement import MoneyMovement
from app.models.fixed_asset import FixedAsset, AssetRevaluation
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


BASE_URL = "/api/v1/fixed-assets"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fa_category(db_session: Session, test_organization) -> ExpenseCategory:
    cat = ExpenseCategory(
        name="Depreciación Equipos Reval",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def fa_account(db_session: Session, test_organization) -> MoneyAccount:
    acc = MoneyAccount(
        name="Cuenta Principal Reval",
        account_type="bank",
        current_balance=Decimal("5000000000"),
        # Invariante real: initial + Σmovimientos == current. El as-of (H2)
        # reconstruye desde initial_balance — sin esto el test compararía manzanas
        # con peras por artefacto de fixture.
        initial_balance=Decimal("5000000000"),
        organization_id=test_organization.id,
    )
    db_session.add(acc)
    db_session.commit()
    db_session.refresh(acc)
    return acc


@pytest.fixture
def fa_supplier(db_session: Session, test_organization) -> ThirdParty:
    tp = ThirdParty(
        name="Equipos Reval S.A.",
        organization_id=test_organization.id,
        current_balance=Decimal("0"),
        initial_balance=Decimal("0"),
    )
    db_session.add(tp)
    db_session.flush()
    cat = ThirdPartyCategory(
        name="Proveedores Reval",
        behavior_type="material_supplier",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(tp)
    return tp


@pytest.fixture
def fa_provision(db_session: Session, test_organization) -> ThirdParty:
    """Tercero provision — NO válido como contrapartida de revalorización (#32)."""
    tp = ThirdParty(
        name="Provisión Reval",
        organization_id=test_organization.id,
        current_balance=Decimal("0"),
        initial_balance=Decimal("0"),
    )
    db_session.add(tp)
    db_session.flush()
    cat = ThirdPartyCategory(
        name="Provisiones Reval",
        behavior_type="provision",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=tp.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(tp)
    return tp


def _create_asset(client, org_headers, fa_category, fa_account, **overrides):
    """Activo default: 630M, rate 1% → cuota 6.3M, 100 meses."""
    payload = {
        "name": "Retroexcavadora Reval",
        "asset_code": "RV-001",
        "purchase_date": "2026-01-01",
        "purchase_value": 630000000,
        "salvage_value": 0,
        "depreciation_rate": 1.0,
        "depreciation_start_date": "2026-01-01",
        "expense_category_id": str(fa_category.id),
        "source_account_id": str(fa_account.id),
    }
    payload.update(overrides)
    resp = client.post(BASE_URL + "/", json=payload, headers=org_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _revalue(client, org_headers, asset_id, **overrides):
    payload = {
        "revaluation_type": "increase",
        "amount": 50000000,
        "months_extended": 0,
    }
    payload.update(overrides)
    return client.post(f"{BASE_URL}/{asset_id}/revalue", json=payload, headers=org_headers)


# ---------------------------------------------------------------------------
# Happy paths — 4 patas (alza/baja × cuenta/tercero)
# ---------------------------------------------------------------------------

class TestRevalueHappyPaths:

    def test_increase_with_account(
        self, client: TestClient, org_headers, fa_category, fa_account, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        # Tras la compra: cuenta 5.000M − 630M = 4.370M
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id), reason="Overhaul motor",
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()

        assert data["current_value"] == 680000000
        assert data["purchase_value"] == 630000000  # intacto
        assert data["accumulated_depreciation"] == 0  # intacto
        # remaining = ceil(630M/6.3M) = 100 → cuota nueva 680M/100 = 6.8M
        assert data["monthly_depreciation"] == 6800000
        assert data["revalued_total"] == 50000000
        assert len(data["revaluations"]) == 1
        rev = data["revaluations"][0]
        assert rev["revaluation_type"] == "increase"
        assert rev["value_before"] == 630000000
        assert rev["value_after"] == 680000000
        assert rev["monthly_before"] == 6300000
        assert rev["monthly_after"] == 6800000
        assert rev["is_active"] is True

        db_session.expire_all()
        acc = db_session.get(MoneyAccount, fa_account.id)
        assert acc.current_balance == Decimal("4320000000")  # 4.370M − 50M
        mov = db_session.get(MoneyMovement, UUID(rev["money_movement_id"]))
        assert mov.movement_type == "asset_revaluation_payment"
        assert mov.amount == Decimal("50000000")
        assert mov.status == "confirmed"

    def test_increase_with_third_party(
        self, client: TestClient, org_headers, fa_category, fa_account, fa_supplier, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            third_party_id=str(fa_supplier.id),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["current_value"] == 680000000

        db_session.expire_all()
        tp = db_session.get(ThirdParty, fa_supplier.id)
        assert tp.current_balance == Decimal("-50000000")  # le debemos
        mov = db_session.get(
            MoneyMovement, UUID(data["revaluations"][0]["money_movement_id"])
        )
        assert mov.movement_type == "asset_revaluation_credit"
        assert mov.account_id is None
        # La cuenta NO se toca
        acc = db_session.get(MoneyAccount, fa_account.id)
        assert acc.current_balance == Decimal("4370000000")

    def test_decrease_with_account(
        self, client: TestClient, org_headers, fa_category, fa_account, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=30000000,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["current_value"] == 600000000
        # remaining = 100 → cuota 600M/100 = 6M
        assert data["monthly_depreciation"] == 6000000
        assert data["revalued_total"] == -30000000
        assert data["status"] == "active"

        db_session.expire_all()
        acc = db_session.get(MoneyAccount, fa_account.id)
        assert acc.current_balance == Decimal("4400000000")  # 4.370M + 30M
        mov = db_session.get(
            MoneyMovement, UUID(data["revaluations"][0]["money_movement_id"])
        )
        assert mov.movement_type == "asset_devaluation_collection"

    def test_decrease_with_third_party(
        self, client: TestClient, org_headers, fa_category, fa_account, fa_supplier, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=30000000,
            third_party_id=str(fa_supplier.id),
        )
        assert resp.status_code == 201, resp.text

        db_session.expire_all()
        tp = db_session.get(ThirdParty, fa_supplier.id)
        assert tp.current_balance == Decimal("30000000")  # nos debe
        mov = db_session.get(
            MoneyMovement,
            UUID(resp.json()["revaluations"][0]["money_movement_id"]),
        )
        assert mov.movement_type == "asset_devaluation_receivable"


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------

class TestRevalueValidations:

    def test_amount_zero_rejected(self, client, org_headers, fa_category, fa_account):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=0, source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 422

    def test_xor_counterpart_required(self, client, org_headers, fa_category, fa_account, fa_supplier):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        # Ninguna contrapartida
        resp = _revalue(client, org_headers, asset["id"])
        assert resp.status_code == 422
        # Ambas contrapartidas
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id), third_party_id=str(fa_supplier.id),
        )
        assert resp.status_code == 422

    def test_months_extended_on_decrease_rejected(
        self, client, org_headers, fa_category, fa_account,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=1000000, months_extended=5,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 422

    def test_decrease_below_salvage_rejected(
        self, client, org_headers, fa_category, fa_account,
    ):
        asset = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=100000000, salvage_value=20000000,
        )
        # depreciable = 80M; bajar 90M rompe el piso del residual
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=90000000,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 400
        assert "residual" in resp.json()["detail"]

    def test_disposed_asset_rejected(self, client, org_headers, fa_category, fa_account):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/dispose",
            json={"reason": "Vendida"}, headers=org_headers,
        )
        assert resp.status_code == 200
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 400
        assert "disposed" in resp.json()["detail"]

    def test_provision_third_party_rejected(
        self, client, org_headers, fa_category, fa_account, fa_provision,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            third_party_id=str(fa_provision.id),
        )
        assert resp.status_code == 404

    def test_insufficient_funds_on_increase(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        poor = MoneyAccount(
            name="Cuenta Pobre Reval", account_type="cash",
            current_balance=Decimal("1000"),
            organization_id=test_organization.id,
        )
        db_session.add(poor)
        db_session.commit()
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=50000000, source_account_id=str(poor.id),
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Recalculo de cuota
# ---------------------------------------------------------------------------

class TestRevalueRecalc:

    def test_increase_with_extension_lowers_monthly(
        self, client, org_headers, fa_category, fa_account,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=50000000, months_extended=25,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201
        data = resp.json()
        # remaining 100 + 25 = 125 → 680M/125 = 5.44M
        assert data["monthly_depreciation"] == 5440000
        assert data["useful_life_months"] == 125

    def test_conservation_through_last_installment(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization, test_user,
    ):
        """Round-trip completo: reval + depreciaciones hasta el residual —
        el total depreciado == valor revalorizado (conservación)."""
        from app.services.fixed_asset import fixed_asset as fa_service

        # 12M, rate 50% → cuota 6M, 2 meses restantes
        asset = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=12000000, depreciation_rate=50.0,
        )
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=3000000, source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201
        # remaining = ceil(12M/6M) = 2 → cuota = 15M/2 = 7.5M
        assert resp.json()["monthly_depreciation"] == 7500000

        a1 = fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-05",
        )
        assert a1.current_value == Decimal("7500000")
        a2 = fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-06",
        )
        # Última cuota ajusta exacto al residual
        assert a2.current_value == Decimal("0")
        assert a2.status == "fully_depreciated"
        assert a2.accumulated_depreciation == Decimal("15000000")  # 12M + 3M reval

    def test_revive_fully_depreciated_requires_and_uses_extension(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization, test_user,
    ):
        from app.services.fixed_asset import fixed_asset as fa_service

        asset = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=12000000, depreciation_rate=50.0,
        )
        fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-05",
        )
        a = fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-06",
        )
        assert a.status == "fully_depreciated"

        # Sin extensión → 400 (no hay meses sobre los cuales repartir)
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=5000000, source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 400
        assert "months_extended" in resp.json()["detail"]

        # Con extensión → revive
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=5000000, months_extended=5,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "active"
        assert data["current_value"] == 5000000
        assert data["monthly_depreciation"] == 1000000  # 5M/5

    def test_decrease_to_salvage_marks_fully_depreciated(
        self, client, org_headers, fa_category, fa_account,
    ):
        asset = _create_asset(
            client, org_headers, fa_category, fa_account,
            purchase_value=12000000, depreciation_rate=50.0,
        )
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=12000000,
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["current_value"] == 0
        assert data["status"] == "fully_depreciated"


# ---------------------------------------------------------------------------
# Anulación
# ---------------------------------------------------------------------------

class TestRevaluationAnnul:

    def test_annul_round_trip(
        self, client, org_headers, fa_category, fa_account, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            amount=50000000, months_extended=25,
            source_account_id=str(fa_account.id),
        )
        rev_id = resp.json()["revaluations"][0]["id"]

        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revaluations/{rev_id}/annul",
            json={"reason": "Error de captura"}, headers=org_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Round-trip exacto al estado pre-revalorización
        assert data["current_value"] == 630000000
        assert data["monthly_depreciation"] == 6300000
        assert data["useful_life_months"] == 100
        assert data["status"] == "active"
        assert data["revalued_total"] == 0
        assert data["revaluations"][0]["is_active"] is False

        db_session.expire_all()
        acc = db_session.get(MoneyAccount, fa_account.id)
        assert acc.current_balance == Decimal("4370000000")  # devuelto
        mov = db_session.get(
            MoneyMovement,
            UUID(data["revaluations"][0]["money_movement_id"]),
        )
        assert mov.status == "annulled"

    def test_annul_blocked_by_later_depreciation(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization, test_user,
    ):
        from app.services.fixed_asset import fixed_asset as fa_service

        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id),
        )
        rev_id = resp.json()["revaluations"][0]["id"]
        fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-06",
        )
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revaluations/{rev_id}/annul",
            json={"reason": "Tarde"}, headers=org_headers,
        )
        assert resp.status_code == 400
        assert "posteriores" in resp.json()["detail"]

    def test_annul_lifo_order_enforced(
        self, client, org_headers, fa_category, fa_account,
    ):
        """Con dos revalorizaciones, solo la última es anulable; al anularla,
        la primera pasa a ser anulable."""
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        r1 = _revalue(
            client, org_headers, asset["id"],
            amount=50000000, source_account_id=str(fa_account.id),
        )
        rev1_id = r1.json()["revaluations"][0]["id"]
        r2 = _revalue(
            client, org_headers, asset["id"],
            amount=20000000, source_account_id=str(fa_account.id),
        )
        rev2_id = [
            r["id"] for r in r2.json()["revaluations"] if r["id"] != rev1_id
        ][0]

        # Anular la primera con la segunda viva → 400
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revaluations/{rev1_id}/annul",
            json={"reason": "Fuera de orden"}, headers=org_headers,
        )
        assert resp.status_code == 400

        # Anular la segunda → OK (restaura snapshots de la primera)
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revaluations/{rev2_id}/annul",
            json={"reason": "LIFO"}, headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["current_value"] == 680000000

        # Ahora la primera es anulable → vuelve al origen
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revaluations/{rev1_id}/annul",
            json={"reason": "LIFO 2"}, headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["current_value"] == 630000000

    def test_treasury_annul_blocked(
        self, client, org_headers, fa_category, fa_account,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id),
        )
        mm_id = resp.json()["revaluations"][0]["money_movement_id"]
        resp = client.post(
            f"/api/v1/money-movements/{mm_id}/annul",
            json={"reason": "Directo"}, headers=org_headers,
        )
        assert resp.status_code == 422
        assert "Activos Fijos" in resp.json()["detail"]

    def test_cancel_asset_reverts_revaluations(
        self, client, org_headers, fa_category, fa_account, fa_supplier, db_session,
    ):
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        _revalue(client, org_headers, asset["id"], source_account_id=str(fa_account.id))
        _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=10000000,
            third_party_id=str(fa_supplier.id),
        )

        resp = client.post(f"{BASE_URL}/{asset['id']}/cancel", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        db_session.expire_all()
        # Cuenta: compra 630M devuelta + reval 50M devuelta → 5.000M
        acc = db_session.get(MoneyAccount, fa_account.id)
        assert acc.current_balance == Decimal("5000000000")
        # Tercero: la devaluación (nos debía 10M) revertida → 0
        tp = db_session.get(ThirdParty, fa_supplier.id)
        assert tp.current_balance == Decimal("0")
        revals = db_session.query(AssetRevaluation).filter(
            AssetRevaluation.fixed_asset_id == UUID(asset["id"]),
        ).all()
        assert len(revals) == 2
        assert all(not r.is_active for r in revals)


# ---------------------------------------------------------------------------
# Reportes: H1 (as-of golden), H2 (as-of == vivo), H2b (saldo corrido),
# H4 (cash flow + MTD), P&L intocado
# ---------------------------------------------------------------------------

def _fa_item_asof(client, org_headers, asset_id, as_of=None):
    params = {"as_of_date": as_of} if as_of else {}
    resp = client.get(
        "/api/v1/reports/balance-detailed", params=params, headers=org_headers,
    )
    assert resp.status_code == 200, resp.text
    section = resp.json()["assets"].get("fixed_assets")
    if not section:
        return None
    for item in section["items"]:
        if item["id"] == asset_id:
            return item
    return None


class TestRevaluationReports:

    def test_h1_golden_asof_no_restatement(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization, test_user,
    ):
        """Test de oro H1: NINGÚN corte previo al DÍA de la revalorización cambia
        (ancla diaria — incluido AYER, mismo mes: bug de pruebas de usuario
        'el total de activos crecía 5M en el corte del día anterior');
        el corte del día del evento y el vivo la incluyen."""
        from app.services.fixed_asset import fixed_asset as fa_service

        asset = _create_asset(client, org_headers, fa_category, fa_account)
        fa_service.apply_depreciation(
            db_session, UUID(asset["id"]), test_organization.id, test_user.id, "2026-05",
        )

        # Corte antes del mes de la revalorización
        before = _fa_item_asof(client, org_headers, asset["id"], "2026-06-30")
        assert before is not None
        assert before["current_value"] == 623700000  # 630M − 6.3M

        # Corte sin eventos ≤ marzo: reconstruye al valor de compra
        early = _fa_item_asof(client, org_headers, asset["id"], "2026-03-31")
        assert early["current_value"] == 630000000

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        # Total de activos del balance general al corte de AYER, pre-revalorización
        bs_yesterday_before = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": yesterday}, headers=org_headers,
        ).json()

        # Revalorizar HOY (+50M)
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id),
        )
        assert resp.status_code == 201
        assert resp.json()["current_value"] == 673700000

        # NO-RESTATEMENT diario: AYER (mismo mes, día anterior) NO ve la revalorización
        item_yesterday = _fa_item_asof(client, org_headers, asset["id"], yesterday)
        assert item_yesterday["current_value"] == 623700000
        assert not item_yesterday.get("revalued_amount")
        # ... y el balance general de ayer no se movió ni un peso (activo Y caja juntos)
        bs_yesterday_after = client.get(
            "/api/v1/reports/balance-sheet",
            params={"as_of_date": yesterday}, headers=org_headers,
        ).json()
        assert bs_yesterday_after["total_assets"] == bs_yesterday_before["total_assets"]
        assert bs_yesterday_after["assets"]["fixed_assets"] == bs_yesterday_before["assets"]["fixed_assets"]
        assert bs_yesterday_after["assets"]["cash_and_bank"] == bs_yesterday_before["assets"]["cash_and_bank"]

        # Cortes de meses previos: idénticos
        assert _fa_item_asof(client, org_headers, asset["id"], "2026-06-30")["current_value"] == 623700000
        assert _fa_item_asof(client, org_headers, asset["id"], "2026-03-31")["current_value"] == 630000000

        # Corte de hoy == vivo (el día del evento SÍ la incluye)
        today = date.today().isoformat()
        item_today = _fa_item_asof(client, org_headers, asset["id"], today)
        assert item_today["current_value"] == 673700000
        # H3: acc_dep al corte = compra + reval − valor = 630M + 50M − 673.7M = 6.3M
        assert item_today["accumulated_depreciation"] == 6300000
        assert item_today["revalued_amount"] == 50000000

        # Vivo (sin as_of): campo almacenado + revalued_amount
        live = _fa_item_asof(client, org_headers, asset["id"])
        assert live["current_value"] == 673700000
        assert live["accumulated_depreciation"] == 6300000
        assert live["revalued_amount"] == 50000000

    def test_h2_account_and_tp_asof_equals_live(
        self, client, org_headers, fa_category, fa_account, fa_supplier, db_session,
    ):
        """H2: los sign maps as-of incluyen los tipos nuevos — corte de hoy == vivo."""
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        _revalue(client, org_headers, asset["id"], source_account_id=str(fa_account.id))
        _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=10000000,
            third_party_id=str(fa_supplier.id),
        )

        live = client.get(
            "/api/v1/reports/balance-detailed", headers=org_headers,
        ).json()
        asof = client.get(
            "/api/v1/reports/balance-detailed",
            params={"as_of_date": date.today().isoformat()},
            headers=org_headers,
        ).json()

        def _find(data, section_key, item_id):
            section = data["assets"].get(section_key) or data["liabilities"].get(section_key)
            if not section:
                return None
            for it in section["items"]:
                if it["id"] == item_id:
                    return it
            return None

        # Cuenta: vivo == as-of (si el tipo faltara del mapa, el as-of quedaría corrido)
        live_acc = _find(live, "cash_and_bank", str(fa_account.id))
        asof_acc = _find(asof, "cash_and_bank", str(fa_account.id))
        assert live_acc is not None and asof_acc is not None
        assert live_acc["balance"] == asof_acc["balance"]

        # Tercero (nos debe 10M → activo): vivo == as-of
        found_live = found_asof = None
        for data, target in ((live, "live"), (asof, "asof")):
            for section in list(data["assets"].values()) + list(data["liabilities"].values()):
                for it in section["items"]:
                    if it["id"] == str(fa_supplier.id):
                        if target == "live":
                            found_live = it
                        else:
                            found_asof = it
        assert found_live is not None and found_asof is not None
        assert found_live["balance"] == found_asof["balance"]

    def test_h2b_statement_running_balance(
        self, client, org_headers, fa_category, fa_account, fa_supplier,
    ):
        """H2b: el saldo corrido de los DOS statements (cuenta y tercero) integra
        los tipos nuevos — sin la dirección en el mapa del endpoint quedaría corrido."""
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        resp = _revalue(
            client, org_headers, asset["id"],
            source_account_id=str(fa_account.id),
        )
        mm_id = resp.json()["revaluations"][0]["money_movement_id"]

        # Statement de cuenta: compra (−630M) → reval (−50M) → 4.320M
        st = client.get(
            f"/api/v1/money-movements/account/{fa_account.id}", headers=org_headers,
        ).json()
        rows = {r["id"]: r for r in st["items"]}
        assert str(mm_id) in rows
        assert rows[str(mm_id)]["balance_after"] == 4320000000
        assert rows[str(mm_id)]["direction"] == -1

        # Statement de tercero: devaluación a cargo del tercero → balance_after +10M
        resp = _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=10000000,
            third_party_id=str(fa_supplier.id),
        )
        tp_mm_id = [
            r["money_movement_id"] for r in resp.json()["revaluations"]
            if r["is_active"] and r["revaluation_type"] == "decrease"
        ][0]
        st = client.get(
            f"/api/v1/money-movements/third-party/{fa_supplier.id}", headers=org_headers,
        ).json()
        assert st["current_balance"] == 10000000
        tp_rows = {r["id"]: r for r in st["items"] if "id" in r}
        assert str(tp_mm_id) in tp_rows
        assert tp_rows[str(tp_mm_id)]["balance_after"] == 10000000

    def test_h4_cash_flow_and_dashboard_mtd(
        self, client, org_headers, fa_category, fa_account,
    ):
        """H4: buckets del período + frozensets (opening reconcilia) + dashboard MTD."""
        asset = _create_asset(client, org_headers, fa_category, fa_account)
        _revalue(client, org_headers, asset["id"], source_account_id=str(fa_account.id))
        _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=30000000,
            source_account_id=str(fa_account.id),
        )
        # Cuenta viva: 5.000M − 630M − 50M + 30M = 4.350M

        today = date.today().isoformat()
        cf = client.get(
            "/api/v1/reports/cash-flow",
            params={"date_from": today, "date_to": today},
            headers=org_headers,
        ).json()

        assert cf["outflows"]["asset_payments"] == 50000000  # bucket capex del período
        assert cf["inflows"]["asset_devaluation_collections"] == 30000000
        # Frozensets: opening reconstruido correcto y el statement cierra
        assert cf["opening_balance"] == 4370000000  # saldo al inicio de hoy
        assert cf["closing_balance"] == pytest.approx(
            cf["opening_balance"] + cf["net_flow"]
        )
        assert cf["closing_balance"] == 4350000000  # == saldo vivo

        dash = client.get(
            "/api/v1/reports/treasury-dashboard", headers=org_headers,
        ).json()
        assert dash["mtd_income"] == 30000000
        assert dash["mtd_expense"] == 50000000

    def test_pnl_untouched_by_revaluation(
        self, client, org_headers, fa_category, fa_account, fa_supplier,
    ):
        """Cero P&L: revalorizar no mueve ninguna línea del estado de resultados."""
        _params = {"date_from": "2026-01-01", "date_to": "2026-12-31"}
        before = client.get(
            "/api/v1/reports/profit-and-loss", params=_params, headers=org_headers,
        ).json()

        asset = _create_asset(client, org_headers, fa_category, fa_account)
        _revalue(client, org_headers, asset["id"], source_account_id=str(fa_account.id))
        _revalue(
            client, org_headers, asset["id"],
            revaluation_type="decrease", amount=10000000,
            third_party_id=str(fa_supplier.id),
        )

        after = client.get(
            "/api/v1/reports/profit-and-loss", params=_params, headers=org_headers,
        ).json()
        assert after["net_profit"] == before["net_profit"]
        assert after["operating_expenses"] == before["operating_expenses"]
        assert after["total_gross_profit"] == before["total_gross_profit"]


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestRevaluationRBAC:

    def test_viewer_cannot_revalue(
        self, client, org_headers, fa_category, fa_account, db_session, test_organization,
    ):
        from app.core.security import create_access_token
        from app.models.role import Role
        from app.models.user import User, OrganizationMember

        asset = _create_asset(client, org_headers, fa_category, fa_account)

        viewer = User(
            email="viewer-reval@test.com", hashed_password="x",
            full_name="Viewer Reval", is_active=True,
        )
        db_session.add(viewer)
        db_session.flush()
        role = db_session.query(Role).filter(
            Role.organization_id == test_organization.id,
            Role.name == "viewer",
            Role.is_system_role == True,
        ).first()
        assert role is not None
        db_session.add(OrganizationMember(
            user_id=viewer.id,
            organization_id=test_organization.id,
            role_id=role.id,
        ))
        db_session.commit()

        token = create_access_token(data={"sub": str(viewer.id)})
        resp = client.post(
            f"{BASE_URL}/{asset['id']}/revalue",
            json={
                "revaluation_type": "increase",
                "amount": 1000000,
                "source_account_id": str(fa_account.id),
            },
            headers={
                "Authorization": f"Bearer {token}",
                "X-Organization-ID": str(test_organization.id),
            },
        )
        assert resp.status_code == 403
