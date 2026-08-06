"""
Tests KgLedger (SAC E2 bloque 1, plan-sac-e2-kgledger-inbound.md §8).

Cubre: gate por flag (D10, incl. re-gate E1 H2 QA), CRUD de cuentas con
coherencia tipo↔FKs (D6), movimientos manuales auditados (D1/D15),
anulacion D16, statement con apertura real de ventana (#55 desde dia cero),
summary con as_of, test de oro statement==summary, RBAC D4 y aislamiento
multi-tenant.
"""
import pytest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.kg_ledger import KgLedgerMovement
from tests.integration_helpers import create_warehouse
from tests.conftest import create_third_party_with_category
from app.utils.dates import business_today

KG_URL = "/api/v1/kg-ledger"


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_kg_ledger_flag(db_session, test_organization, test_organization2):
    """Flag ON en ambas orgs (el gate tiene sus tests explicitos abajo).

    JSONB sin MutableDict: reasignar el dict completo (regla D3-E1).
    """
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Planta Barranquilla")
    db_session.commit()
    return wh


@pytest.fixture
def willard_tp(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A.", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def willard_account(client, org_headers, warehouse, willard_tp):
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "WILLARD-BAT-BAQ",
            "display_name": "Willard Baterias BAQ",
            "account_type": "willard_baterias",
            "warehouse_id": str(warehouse.id),
            "third_party_id": str(willard_tp.id),
            "tolerance_kg": "50",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def intersede_account(client, org_headers):
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "INTERSEDE-CV-JM",
            "display_name": "Intersede CV-JM",
            "account_type": "intersede",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _manual(client, org_headers, account_id, delta, date_str, desc="Ajuste", reason="Cuadre"):
    return client.post(
        f"{KG_URL}/movements",
        headers=org_headers,
        json={
            "account_id": account_id,
            "delta_kg": str(delta),
            "transaction_date": date_str,
            "description": desc,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# Gate por flag (D10 + H2 QA)
# ---------------------------------------------------------------------------

class TestFlagGate:
    def test_flag_off_403_even_for_admin(
        self, client, org_headers, db_session, test_organization
    ):
        test_organization.settings = {}
        db_session.commit()
        resp = client.get(f"{KG_URL}/accounts", headers=org_headers)
        assert resp.status_code == 403
        assert "habilitado" in resp.json()["detail"]

    def test_flag_off_403_on_e1_routers(
        self, client, org_headers, db_session, test_organization
    ):
        """H2 QA E2: los routers E1 quedaron re-gated por el mismo flag."""
        test_organization.settings = {}
        db_session.commit()
        for url in (
            "/api/v1/service-tariffs",
            "/api/v1/material-conversion-formulas",
            "/api/v1/drivers",
            "/api/v1/vehicles",
        ):
            resp = client.get(url, headers=org_headers)
            assert resp.status_code == 403, f"{url}: {resp.status_code}"

    def test_flag_on_allows_access(self, client, org_headers):
        resp = client.get(f"{KG_URL}/accounts", headers=org_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cuentas (D6)
# ---------------------------------------------------------------------------

class TestKgAccounts:
    def test_create_willard_baterias_happy(self, willard_account, warehouse, willard_tp):
        assert willard_account["account_type"] == "willard_baterias"
        assert willard_account["warehouse_name"] == "Planta Barranquilla"
        assert willard_account["third_party_name"] == "Willard S.A."
        assert Decimal(willard_account["current_balance_kg"]) == 0
        assert willard_account["is_active"] is True

    def test_willard_requires_third_party(self, client, org_headers, warehouse):
        resp = client.post(
            f"{KG_URL}/accounts",
            headers=org_headers,
            json={
                "code": "WILLARD-DROSS",
                "display_name": "Willard Drosses",
                "account_type": "willard_drosses",
            },
        )
        assert resp.status_code == 422
        assert "tercero" in resp.json()["detail"]

    def test_internal_forbids_third_party(self, client, org_headers, willard_tp):
        resp = client.post(
            f"{KG_URL}/accounts",
            headers=org_headers,
            json={
                "code": "INTERSEDE-X",
                "display_name": "Intersede X",
                "account_type": "intersede",
                "third_party_id": str(willard_tp.id),
            },
        )
        assert resp.status_code == 422
        assert "no llevan tercero" in resp.json()["detail"]

    def test_warehouse_required_types(self, client, org_headers, willard_tp):
        # willard_baterias y crisol exigen sede
        for acc_type, code in (("willard_baterias", "WB-X"), ("crisol", "CRISOL-X")):
            payload = {
                "code": code,
                "display_name": code,
                "account_type": acc_type,
            }
            if acc_type == "willard_baterias":
                payload["third_party_id"] = str(willard_tp.id)
            resp = client.post(f"{KG_URL}/accounts", headers=org_headers, json=payload)
            assert resp.status_code == 422, f"{acc_type}: {resp.text}"
            assert "sede" in resp.json()["detail"]

    def test_duplicate_code_422(self, client, org_headers, intersede_account):
        resp = client.post(
            f"{KG_URL}/accounts",
            headers=org_headers,
            json={
                "code": "INTERSEDE-CV-JM",
                "display_name": "Otra",
                "account_type": "intersede",
            },
        )
        assert resp.status_code == 422
        assert "codigo" in resp.json()["detail"]

    def test_duplicate_type_warehouse_422(self, client, org_headers, intersede_account):
        """Misma cuenta logica (tipo + sede NULL org-wide) no se duplica."""
        resp = client.post(
            f"{KG_URL}/accounts",
            headers=org_headers,
            json={
                "code": "INTERSEDE-2",
                "display_name": "Intersede duplicada",
                "account_type": "intersede",
            },
        )
        assert resp.status_code == 422
        assert "misma cuenta logica" in resp.json()["detail"]

    def test_invalid_account_type_422(self, client, org_headers):
        resp = client.post(
            f"{KG_URL}/accounts",
            headers=org_headers,
            json={"code": "X", "display_name": "X", "account_type": "banco"},
        )
        assert resp.status_code == 422  # Literal del schema

    def test_update_metadata_and_immutability(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        resp = client.patch(
            f"{KG_URL}/accounts/{acc_id}",
            headers=org_headers,
            json={"display_name": "Intersede Renombrada", "tolerance_kg": "25"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Intersede Renombrada"
        assert Decimal(resp.json()["tolerance_kg"]) == 25
        # account_type inmutable: extra=forbid -> 422 de Pydantic
        resp = client.patch(
            f"{KG_URL}/accounts/{acc_id}",
            headers=org_headers,
            json={"account_type": "crisol"},
        )
        assert resp.status_code == 422

    def test_deactivate_with_balance_422(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        today = business_today().isoformat()
        assert _manual(client, org_headers, acc_id, 100, today).status_code == 201
        resp = client.patch(
            f"{KG_URL}/accounts/{acc_id}", headers=org_headers, json={"is_active": False}
        )
        assert resp.status_code == 422
        assert "saldo distinto de cero" in resp.json()["detail"]
        # Devolver a cero y desactivar OK
        assert _manual(client, org_headers, acc_id, -100, today).status_code == 201
        resp = client.patch(
            f"{KG_URL}/accounts/{acc_id}", headers=org_headers, json={"is_active": False}
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_list_excludes_inactive_by_default(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        client.patch(
            f"{KG_URL}/accounts/{acc_id}", headers=org_headers, json={"is_active": False}
        )
        codes = [a["code"] for a in client.get(f"{KG_URL}/accounts", headers=org_headers).json()]
        assert "INTERSEDE-CV-JM" not in codes
        codes = [
            a["code"]
            for a in client.get(
                f"{KG_URL}/accounts", headers=org_headers, params={"include_inactive": True}
            ).json()
        ]
        assert "INTERSEDE-CV-JM" in codes


# ---------------------------------------------------------------------------
# Movimientos manuales (D1/D15/D16)
# ---------------------------------------------------------------------------

class TestManualMovements:
    def test_create_happy_noon_utc(self, client, org_headers, intersede_account, db_session):
        today = business_today().isoformat()
        resp = _manual(
            client, org_headers, intersede_account["id"], "150.5", today,
            desc="Conteo fisico", reason="Diferencia bascula",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert Decimal(body["delta_kg"]) == Decimal("150.5")
        assert body["source_type"] == "manual_adjustment"
        assert body["status"] == "confirmed"
        assert "Conteo fisico — Motivo: Diferencia bascula" in body["description"]
        # BusinessDate: mediodia UTC
        mov = db_session.get(KgLedgerMovement, body["id"])
        assert mov.transaction_date.astimezone(timezone.utc).hour == 12
        # Saldo vivo refleja el movimiento
        accounts = client.get(f"{KG_URL}/accounts", headers=org_headers).json()
        acc = next(a for a in accounts if a["id"] == intersede_account["id"])
        assert Decimal(acc["current_balance_kg"]) == Decimal("150.5")

    def test_delta_zero_422(self, client, org_headers, intersede_account):
        today = business_today().isoformat()
        resp = _manual(client, org_headers, intersede_account["id"], 0, today)
        assert resp.status_code == 422

    def test_future_date_422(self, client, org_headers, intersede_account):
        future = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()
        resp = _manual(client, org_headers, intersede_account["id"], 10, future)
        assert resp.status_code == 422

    def test_inactive_account_422(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        client.patch(f"{KG_URL}/accounts/{acc_id}", headers=org_headers, json={"is_active": False})
        today = business_today().isoformat()
        resp = _manual(client, org_headers, acc_id, 10, today)
        assert resp.status_code == 422
        assert "inactiva" in resp.json()["detail"]

    def test_annul_happy_with_audit(self, client, org_headers, intersede_account):
        today = business_today().isoformat()
        mov = _manual(client, org_headers, intersede_account["id"], 80, today).json()
        resp = client.post(
            f"{KG_URL}/movements/{mov['id']}/annul",
            headers=org_headers,
            json={"reason": "Digitado dos veces"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "annulled"
        assert body["annulled_reason"] == "Digitado dos veces"
        assert body["annulled_at"] is not None
        # El saldo vuelve a 0 (los anulados no cuentan)
        accounts = client.get(f"{KG_URL}/accounts", headers=org_headers).json()
        acc = next(a for a in accounts if a["id"] == intersede_account["id"])
        assert Decimal(acc["current_balance_kg"]) == 0

    def test_annul_business_movement_422(
        self, client, org_headers, intersede_account, db_session, test_organization, test_user
    ):
        """D16: movimientos de negocio se anulan desde su documento origen."""
        mov = KgLedgerMovement(
            organization_id=test_organization.id,
            account_id=intersede_account["id"],
            delta_kg=Decimal("300"),
            transaction_date=datetime.now(timezone.utc),
            source_type="postconsumo_receipt",
            created_by=test_user.id,
            status="confirmed",
        )
        db_session.add(mov)
        db_session.commit()
        resp = client.post(
            f"{KG_URL}/movements/{mov.id}/annul",
            headers=org_headers,
            json={"reason": "x"},
        )
        assert resp.status_code == 422
        assert "documento origen" in resp.json()["detail"]

    def test_annul_already_annulled_422(self, client, org_headers, intersede_account):
        today = business_today().isoformat()
        mov = _manual(client, org_headers, intersede_account["id"], 40, today).json()
        client.post(
            f"{KG_URL}/movements/{mov['id']}/annul", headers=org_headers, json={"reason": "a"}
        )
        resp = client.post(
            f"{KG_URL}/movements/{mov['id']}/annul", headers=org_headers, json={"reason": "b"}
        )
        assert resp.status_code == 422
        assert "ya esta anulado" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Statement (#55 desde el dia cero)
# ---------------------------------------------------------------------------

class TestStatement:
    def test_opening_balance_reflects_pre_window(self, client, org_headers, intersede_account):
        """Fix #55: lo confirmado ANTES de la ventana acumula en la apertura."""
        acc_id = intersede_account["id"]
        old = (datetime.now(timezone.utc) - timedelta(days=120)).date().isoformat()
        today = business_today().isoformat()
        assert _manual(client, org_headers, acc_id, 500, old).status_code == 201
        assert _manual(client, org_headers, acc_id, 200, today).status_code == 201

        resp = client.get(f"{KG_URL}/accounts/{acc_id}/movements", headers=org_headers)
        assert resp.status_code == 200
        body = resp.json()
        # Default 90 dias: el de hace 120 queda fuera pero abre la ventana
        assert Decimal(body["opening_balance_kg"]) == 500
        assert len(body["movements"]) == 1
        assert Decimal(body["movements"][0]["balance_after_kg"]) == 700
        assert Decimal(body["current_balance_kg"]) == 700

    def test_explicit_window_lists_all(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        old = (datetime.now(timezone.utc) - timedelta(days=120)).date()
        today = business_today()
        _manual(client, org_headers, acc_id, 500, old.isoformat())
        _manual(client, org_headers, acc_id, 200, today.isoformat())

        resp = client.get(
            f"{KG_URL}/accounts/{acc_id}/movements",
            headers=org_headers,
            params={"date_from": (old - timedelta(days=1)).isoformat()},
        )
        body = resp.json()
        assert Decimal(body["opening_balance_kg"]) == 0
        assert [Decimal(m["balance_after_kg"]) for m in body["movements"]] == [500, 700]

    def test_date_to_inclusive_of_noon(self, client, org_headers, intersede_account):
        """date_to incluye eventos del mismo dia (mediodia UTC BusinessDate)."""
        acc_id = intersede_account["id"]
        d1 = (datetime.now(timezone.utc) - timedelta(days=10)).date()
        d2 = (datetime.now(timezone.utc) - timedelta(days=5)).date()
        _manual(client, org_headers, acc_id, 100, d1.isoformat())
        _manual(client, org_headers, acc_id, 50, d2.isoformat())

        resp = client.get(
            f"{KG_URL}/accounts/{acc_id}/movements",
            headers=org_headers,
            params={"date_from": d1.isoformat(), "date_to": d1.isoformat()},
        )
        body = resp.json()
        assert len(body["movements"]) == 1
        assert Decimal(body["movements"][0]["delta_kg"]) == 100
        # current sigue siendo el saldo VIVO total, no el de la ventana
        assert Decimal(body["current_balance_kg"]) == 150

    def test_annulled_never_moves_balance(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        today = business_today().isoformat()
        _manual(client, org_headers, acc_id, 100, today)
        bad = _manual(client, org_headers, acc_id, 999, today).json()
        client.post(
            f"{KG_URL}/movements/{bad['id']}/annul", headers=org_headers, json={"reason": "err"}
        )

        # Default (confirmed): el anulado no se lista ni mueve el corrido
        body = client.get(f"{KG_URL}/accounts/{acc_id}/movements", headers=org_headers).json()
        assert len(body["movements"]) == 1
        assert Decimal(body["current_balance_kg"]) == 100

        # status_filter=all: se lista pero el saldo corrido lo ignora
        body = client.get(
            f"{KG_URL}/accounts/{acc_id}/movements",
            headers=org_headers,
            params={"status_filter": "all"},
        ).json()
        assert len(body["movements"]) == 2
        annulled_row = next(m for m in body["movements"] if m["status"] == "annulled")
        assert Decimal(annulled_row["balance_after_kg"]) == 100

    def test_statement_account_not_found_404(self, client, org_headers):
        from uuid import uuid4
        resp = client.get(f"{KG_URL}/accounts/{uuid4()}/movements", headers=org_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Summary + test de oro
# ---------------------------------------------------------------------------

class TestSummary:
    def test_totals_by_type_willard_grouped(
        self, client, org_headers, willard_account, intersede_account
    ):
        today = business_today().isoformat()
        _manual(client, org_headers, willard_account["id"], 1200, today)
        _manual(client, org_headers, intersede_account["id"], 340, today)

        body = client.get(f"{KG_URL}/summary", headers=org_headers).json()
        assert Decimal(body["total_willard_kg"]) == 1200
        assert Decimal(body["total_intersede_kg"]) == 340
        assert Decimal(body["total_intra_horno_kg"]) == 0
        assert Decimal(body["total_crisol_kg"]) == 0
        will = next(a for a in body["accounts"] if a["account_id"] == willard_account["id"])
        assert will["last_movement_at"] is not None

    def test_gold_summary_equals_statement(
        self, client, org_headers, willard_account, intersede_account
    ):
        """Test de oro bloque 1: saldo del summary == saldo corrido final del
        statement, por cuenta — dos caminos de calculo, un solo numero."""
        today = business_today()
        old = (today - timedelta(days=200)).isoformat()
        for acc in (willard_account, intersede_account):
            _manual(client, org_headers, acc["id"], "111.25", old)
            _manual(client, org_headers, acc["id"], "-11.25", today.isoformat())
            mov = _manual(client, org_headers, acc["id"], 999, today.isoformat()).json()
            client.post(
                f"{KG_URL}/movements/{mov['id']}/annul",
                headers=org_headers,
                json={"reason": "ruido"},
            )

        summary = client.get(f"{KG_URL}/summary", headers=org_headers).json()
        for acc in (willard_account, intersede_account):
            stmt = client.get(
                f"{KG_URL}/accounts/{acc['id']}/movements", headers=org_headers
            ).json()
            summ_row = next(a for a in summary["accounts"] if a["account_id"] == acc["id"])
            expected = Decimal(stmt["current_balance_kg"])
            assert Decimal(summ_row["balance_kg"]) == expected == Decimal("100")
            # apertura + deltas listados == saldo vivo (ventana consistente)
            listed = sum(Decimal(m["delta_kg"]) for m in stmt["movements"])
            assert Decimal(stmt["opening_balance_kg"]) + listed == expected

    def test_summary_as_of(self, client, org_headers, intersede_account):
        acc_id = intersede_account["id"]
        d_old = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        today = business_today()
        _manual(client, org_headers, acc_id, 400, d_old.isoformat())
        _manual(client, org_headers, acc_id, 100, today.isoformat())

        body = client.get(
            f"{KG_URL}/summary",
            headers=org_headers,
            params={"as_of": (d_old + timedelta(days=1)).isoformat()},
        ).json()
        row = next(a for a in body["accounts"] if a["account_id"] == acc_id)
        assert Decimal(row["balance_kg"]) == 400
        assert Decimal(body["total_intersede_kg"]) == 400


# ---------------------------------------------------------------------------
# RBAC (D4) + aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestRbacAndIsolation:
    def test_viewer_without_kg_perms_403(self, client, org_headers2):
        """D4: los roles de sistema NO ganan permisos kg_ledger — viewer 403."""
        resp = client.get(f"{KG_URL}/accounts", headers=org_headers2)
        assert resp.status_code == 403

    def test_multi_tenant_isolation(
        self, client, org_headers, intersede_account, db_session,
        test_organization2, test_user,
    ):
        """La cuenta de org1 no existe para org2 (admin propio de org2)."""
        from app.core.security import get_password_hash
        from sqlalchemy import select
        from app.models.user import User, OrganizationMember
        from app.models.role import Role
        from app.core.security import create_access_token

        user2 = User(
            email="admin-org2-kg@example.com",
            hashed_password=get_password_hash("pass1234"),
            full_name="Admin Org2",
            is_active=True,
        )
        db_session.add(user2)
        db_session.flush()
        admin_role = db_session.execute(
            select(Role).where(
                Role.organization_id == test_organization2.id, Role.name == "admin"
            )
        ).scalar_one()
        db_session.add(
            OrganizationMember(
                user_id=user2.id,
                organization_id=test_organization2.id,
                role_id=admin_role.id,
            )
        )
        db_session.commit()
        headers2 = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(user2.id)})}",
            "X-Organization-ID": str(test_organization2.id),
        }

        # Listado de org2 no incluye la cuenta de org1
        codes = [a["code"] for a in client.get(f"{KG_URL}/accounts", headers=headers2).json()]
        assert "INTERSEDE-CV-JM" not in codes
        # Statement por id cruzado -> 404
        resp = client.get(
            f"{KG_URL}/accounts/{intersede_account['id']}/movements", headers=headers2
        )
        assert resp.status_code == 404
