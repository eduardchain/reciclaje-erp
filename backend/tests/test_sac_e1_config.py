"""
Tests SAC E1 — Configuracion (plan-sac-e1-configuracion.md §8).

Cubre: ServiceTariff (append-only, D11a, tiebreaker), MaterialConversionFormula
(Anexo D por formula_type, 2 tipos, una vigente por material — CC-001/002),
Driver/Vehicle (D14 placa activa), y constraints de modelos (CHECKs +
UNIQUE NULLS NOT DISTINCT de kg_ledger_accounts, delta_kg != 0) — validos
contra el schema de create_all porque los constraints viven en los modelos (D13).
"""
import pytest
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import get_password_hash, create_access_token
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.service_tariff import ServiceTariff
from app.models.third_party import ThirdParty
from app.models.user import User, OrganizationMember
from app.models.role import Role
from tests.integration_helpers import create_material, create_material_category

TARIFFS_URL = "/api/v1/service-tariffs"
FORMULAS_URL = "/api/v1/material-conversion-formulas"
DRIVERS_URL = "/api/v1/drivers"
VEHICLES_URL = "/api/v1/vehicles"

CANONICAL = {
    "maquila_willard": "per_kg_lead",
    "maquila_intersede_cv_jm": "per_kg_lead",
    "maquila_crisol": "per_kg_lead",
    "flete_willard_bog_baq": "per_kg_battery",
    "flete_willard_planta_planta": "per_kg_lead",
}


# ---------------------------------------------------------------------------
# Fixtures / helpers locales
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_kg_ledger_flag(db_session, test_organization, test_organization2):
    """Enciende kg_ledger_enabled en ambas orgs de test.

    Desde E2 (H2 QA: re-gate de los routers E1 por flag), /service-tariffs,
    /material-conversion-formulas y /drivers|/vehicles responden 403 con el
    flag apagado — estos tests ejercitan la FUNCIONALIDAD, no el gate (el
    gate tiene sus propios tests en test_sac_e2_*). JSONB sin MutableDict:
    reasignar el dict completo (regla D3-E1).
    """
    for org in (test_organization, test_organization2):
        org.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def org2_admin_headers(db_session, test_organization2):
    """Admin PROPIO en org2 — para tests de aislamiento multi-tenant.

    (org_headers2 es test_user como VIEWER en org2: daria 403 = test de RBAC,
    no de aislamiento — advertencia del plan §8.)
    """
    user = User(
        email="admin-org2@example.com",
        hashed_password=get_password_hash("pass1234"),
        full_name="Admin Org2",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    admin_role = db_session.execute(
        select(Role).where(
            Role.organization_id == test_organization2.id, Role.name == "admin"
        )
    ).scalar_one()
    db_session.add(
        OrganizationMember(
            user_id=user.id,
            organization_id=test_organization2.id,
            role_id=admin_role.id,
        )
    )
    db_session.commit()
    token = create_access_token(data={"sub": str(user.id)})
    return {
        "Authorization": f"Bearer {token}",
        "X-Organization-ID": str(test_organization2.id),
    }


def _mat(db, org_id, code, unit="kg"):
    """Material con default_unit dado (baterias='unidad', drosses='kg')."""
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, f"Material {code}", cat.id)
    mat.default_unit = unit
    db.commit()
    return mat


def _post_tariff(client, headers, code="maquila_willard", price="2097.00", unit=None):
    return client.post(
        TARIFFS_URL,
        headers=headers,
        json={
            "tariff_code": code,
            "unit_price_cop": price,
            "unit": unit or CANONICAL[code],
        },
    )


def _post_formula(client, headers, material_id, ftype="drosses_to_lead",
                  params=None, notes=None):
    body = {
        "material_id": str(material_id),
        "formula_type": ftype,
        "parameters": params if params is not None else {"lead_percentage": 0.53},
    }
    if notes:
        body["notes"] = notes
    return client.post(FORMULAS_URL, headers=headers, json=body)


# ---------------------------------------------------------------------------
# ServiceTariff
# ---------------------------------------------------------------------------

class TestServiceTariff:
    def test_create_all_five_codes(self, client, org_headers):
        prices = {
            "maquila_willard": "2097.00",
            "maquila_intersede_cv_jm": "1500.00",
            "maquila_crisol": "300.00",
            "flete_willard_bog_baq": "216.00",
            "flete_willard_planta_planta": "37.00",
        }
        for code, price in prices.items():
            resp = _post_tariff(client, org_headers, code, price)
            assert resp.status_code == 201, f"{code}: {resp.text}"
            data = resp.json()
            assert data["tariff_code"] == code
            assert Decimal(str(data["unit_price_cop"])) == Decimal(price)
            assert data["unit"] == CANONICAL[code]

        resp = client.get(f"{TARIFFS_URL}/current", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 5

    def test_current_returns_latest_per_code(self, client, org_headers):
        _post_tariff(client, org_headers, "maquila_willard", "2097.00")
        _post_tariff(client, org_headers, "maquila_willard", "2200.00")

        current = client.get(f"{TARIFFS_URL}/current", headers=org_headers).json()
        assert current["total"] == 1
        assert Decimal(str(current["items"][0]["unit_price_cop"])) == Decimal("2200.00")

        historic = client.get(
            TARIFFS_URL, headers=org_headers, params={"tariff_code": "maquila_willard"}
        ).json()
        assert historic["total"] == 2
        # Historico mas reciente primero
        assert Decimal(str(historic["items"][0]["unit_price_cop"])) == Decimal("2200.00")
        assert historic["items"][0]["created_by_name"] is not None

    def test_current_tiebreaker_by_id_on_equal_created_at(
        self, client, org_headers, db_session, test_organization, test_user
    ):
        """Invariante 2: con created_at empatado (batch), gana el mayor id."""
        from datetime import datetime, timezone

        ts = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        rows = []
        for price in ("100.00", "200.00"):
            row = ServiceTariff(
                organization_id=test_organization.id,
                tariff_code="maquila_crisol",
                unit_price_cop=Decimal(price),
                unit="per_kg_lead",
                created_by=test_user.id,
                created_at=ts,
                updated_at=ts,
            )
            db_session.add(row)
            rows.append(row)
        db_session.commit()

        expected = max(rows, key=lambda r: str(r.id))
        current = client.get(f"{TARIFFS_URL}/current", headers=org_headers).json()
        crisol = [i for i in current["items"] if i["tariff_code"] == "maquila_crisol"]
        assert len(crisol) == 1
        assert crisol[0]["id"] == str(expected.id)

    def test_invalid_code_422(self, client, org_headers):
        resp = client.post(
            TARIFFS_URL,
            headers=org_headers,
            json={"tariff_code": "maquila_falsa", "unit_price_cop": "100", "unit": "per_kg_lead"},
        )
        assert resp.status_code == 422

    def test_price_not_positive_422(self, client, org_headers):
        for price in ("0", "-100"):
            resp = _post_tariff(client, org_headers, "maquila_willard", price)
            assert resp.status_code == 422, price

    def test_unit_incoherent_with_code_422(self, client, org_headers):
        """D11a: un error de unidad factura mal en E4 silenciosamente."""
        resp = _post_tariff(
            client, org_headers, "maquila_willard", unit="per_kg_battery"
        )
        assert resp.status_code == 422
        assert "per_kg_lead" in resp.json()["detail"]

        resp = _post_tariff(
            client, org_headers, "flete_willard_bog_baq", unit="per_kg_lead"
        )
        assert resp.status_code == 422

    def test_unauthenticated_401(self, client):
        assert client.get(TARIFFS_URL).status_code == 401
        assert client.post(TARIFFS_URL, json={}).status_code == 401

    def test_rbac_viewer_denied(self, client, org_headers2):
        """tariffs.view NO esta asignado a roles de sistema (D4) — viewer 403."""
        assert client.get(TARIFFS_URL, headers=org_headers2).status_code == 403
        assert _post_tariff(client, org_headers2).status_code == 403

    def test_multitenant_isolation(self, client, org_headers, org2_admin_headers):
        _post_tariff(client, org_headers)
        resp = client.get(TARIFFS_URL, headers=org2_admin_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_append_only_no_mutation_routes(self, client, org_headers):
        """Invariante 1: PATCH/DELETE a coleccion -> 405; a /{id} -> 404."""
        assert client.patch(TARIFFS_URL, headers=org_headers, json={}).status_code == 405
        assert client.delete(TARIFFS_URL, headers=org_headers).status_code == 405
        assert client.patch(
            f"{TARIFFS_URL}/{uuid4()}", headers=org_headers, json={}
        ).status_code == 404
        assert client.delete(
            f"{TARIFFS_URL}/{uuid4()}", headers=org_headers
        ).status_code == 404


# ---------------------------------------------------------------------------
# MaterialConversionFormula
# ---------------------------------------------------------------------------

class TestMaterialConversionFormula:
    def test_create_battery_formula(self, client, org_headers, db_session, test_organization):
        mat = _mat(db_session, test_organization.id, "BAT-07", unit="unidad")
        # Sin material_reference (opcional — ejemplos §11.1.3 no lo traen)
        resp = _post_formula(
            client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5}
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["parameters"] == {"kg_lead_per_unit": 2.5}
        assert data["material_code"] == "BAT-07"
        assert data["material_unit"] == "unidad"

        # Con material_reference valido
        mat2 = _mat(db_session, test_organization.id, "BAT-08", unit="unidad")
        resp = _post_formula(
            client, org_headers, mat2.id, "battery_to_lead",
            {"kg_lead_per_unit": 2.8, "material_reference": "08"},
        )
        assert resp.status_code == 201
        assert resp.json()["parameters"]["material_reference"] == "08"

    def test_create_drosses_formula(self, client, org_headers, db_session, test_organization):
        mat = _mat(db_session, test_organization.id, "JAMICHE", unit="kg")
        resp = _post_formula(
            client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.53}
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["parameters"] == {"lead_percentage": 0.53}

    def test_scrap_type_rejected_422(self, client, org_headers, db_session, test_organization):
        """CC-002: scrap_with_terminal_to_lead se elimino — scrap-con-borne es
        un material mas con su % (drosses_to_lead)."""
        mat = _mat(db_session, test_organization.id, "SEC", unit="kg")
        resp = _post_formula(
            client, org_headers, mat.id, "scrap_with_terminal_to_lead",
            {"scrap_factor": 0.56, "terminal_weight_kg": 50},
        )
        assert resp.status_code == 422

    def test_current_one_vigente_per_material(
        self, client, org_headers, db_session, test_organization
    ):
        """CC-001: una sola formula vigente por material (sin subtipo). Una nueva
        version reemplaza la vigente; el historico las conserva todas."""
        mat = _mat(db_session, test_organization.id, "SECO-PINZA", unit="kg")
        _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.56})
        _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.59})

        current = client.get(f"{FORMULAS_URL}/current", headers=org_headers).json()
        assert current["total"] == 1
        assert current["items"][0]["parameters"]["lead_percentage"] == 0.59  # la mas reciente

        # Historico completo: 2 versiones
        assert client.get(FORMULAS_URL, headers=org_headers).json()["total"] == 2

    def test_invalid_parameters_422(self, client, org_headers, db_session, test_organization):
        mat_kg = _mat(db_session, test_organization.id, "DROSS-X", unit="kg")
        mat_un = _mat(db_session, test_organization.id, "BAT-X", unit="unidad")
        cases = [
            (mat_kg.id, "drosses_to_lead", {}),                            # vacio
            (mat_kg.id, "drosses_to_lead", {"lead_percentage": 1.2}),      # > 1
            (mat_un.id, "battery_to_lead", {"kg_lead_per_unit": 0}),       # <= 0
            (mat_un.id, "battery_to_lead",
             {"kg_lead_per_unit": 2.5, "material_reference": "9"}),        # ref fuera de Literal
            (mat_kg.id, "drosses_to_lead",
             {"lead_percentage": 0.5, "extra_key": 1}),                    # extra=forbid
        ]
        for mid, ftype, params in cases:
            resp = _post_formula(client, org_headers, mid, ftype, params)
            assert resp.status_code == 422, f"{ftype} {params}: {resp.status_code}"

    def test_custom_type_not_enabled_422(self, client, org_headers, db_session, test_organization):
        """D11b: custom bloqueado en Fase 1 (sanitizer AST no implementado)."""
        mat = _mat(db_session, test_organization.id, "CUST", unit="kg")
        resp = _post_formula(client, org_headers, mat.id, "custom", {"expr": "x*2"})
        assert resp.status_code == 422
        assert "custom" in resp.text.lower()

    def test_unit_incoherence_422_all_types(
        self, client, org_headers, db_session, test_organization
    ):
        """D11c: battery->unidad, drosses->kg. El tipo se deriva de la unidad;
        el servicio rechaza el incoherente."""
        mat_kg = _mat(db_session, test_organization.id, "CHATARRA", unit="kg")
        mat_un = _mat(db_session, test_organization.id, "BAT-U", unit="unidad")

        resp = _post_formula(client, org_headers, mat_kg.id, "battery_to_lead",
                             {"kg_lead_per_unit": 2.5})
        assert resp.status_code == 422 and "unidad" in resp.json()["detail"]

        resp = _post_formula(client, org_headers, mat_un.id, "drosses_to_lead",
                             {"lead_percentage": 0.5})
        assert resp.status_code == 422

    def test_material_other_org_404(
        self, client, org_headers, db_session, test_organization2
    ):
        mat_org2 = _mat(db_session, test_organization2.id, "AJENO", unit="kg")
        resp = _post_formula(client, org_headers, mat_org2.id)
        assert resp.status_code == 404

    def test_auth_rbac_and_append_only(self, client, org_headers, org_headers2):
        assert client.get(FORMULAS_URL).status_code == 401
        assert client.get(FORMULAS_URL, headers=org_headers2).status_code == 403
        assert client.patch(FORMULAS_URL, headers=org_headers, json={}).status_code == 405
        assert client.delete(FORMULAS_URL, headers=org_headers).status_code == 405
        assert client.patch(
            f"{FORMULAS_URL}/{uuid4()}", headers=org_headers, json={}
        ).status_code == 404


# ---------------------------------------------------------------------------
# Driver / Vehicle
# ---------------------------------------------------------------------------

class TestFleet:
    def test_driver_crud_happy(self, client, org_headers):
        resp = client.post(DRIVERS_URL, headers=org_headers,
                           json={"name": "Pedro Perez", "phone": "3001234567"})
        assert resp.status_code == 201, resp.text
        driver_id = resp.json()["id"]

        listing = client.get(DRIVERS_URL, headers=org_headers).json()
        assert listing["total"] == 1

        resp = client.patch(f"{DRIVERS_URL}/{driver_id}", headers=org_headers,
                            json={"document_id": "CC 123456"})
        assert resp.status_code == 200
        assert resp.json()["document_id"] == "CC 123456"

    def test_vehicle_crud_happy(self, client, org_headers):
        resp = client.post(VEHICLES_URL, headers=org_headers,
                           json={"plate": "ABC123", "vehicle_type": "camion",
                                 "display_name": "Camion 1"})
        assert resp.status_code == 201, resp.text
        vehicle_id = resp.json()["id"]

        resp = client.patch(f"{VEHICLES_URL}/{vehicle_id}", headers=org_headers,
                            json={"display_name": "Camion Grande"})
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Camion Grande"

    def test_required_fields_422(self, client, org_headers):
        assert client.post(DRIVERS_URL, headers=org_headers,
                           json={"name": ""}).status_code == 422
        assert client.post(VEHICLES_URL, headers=org_headers,
                           json={"plate": ""}).status_code == 422
        assert client.post(VEHICLES_URL, headers=org_headers,
                           json={"plate": "XYZ", "vehicle_type": "moto"}).status_code == 422

    def test_duplicate_active_plate_422(self, client, org_headers):
        """D14: unicidad de placa ACTIVA en servicio (case-insensitive)."""
        client.post(VEHICLES_URL, headers=org_headers, json={"plate": "abc123"})
        resp = client.post(VEHICLES_URL, headers=org_headers, json={"plate": "ABC123"})
        assert resp.status_code == 422
        assert "ABC123" in resp.json()["detail"]

    def test_inactive_plate_reusable(self, client, org_headers):
        """D14: la placa de un vehiculo INACTIVO se puede reusar (re-digitacion)."""
        resp = client.post(VEHICLES_URL, headers=org_headers, json={"plate": "DEF456"})
        v1 = resp.json()["id"]
        client.patch(f"{VEHICLES_URL}/{v1}", headers=org_headers,
                     json={"is_active": False})
        resp = client.post(VEHICLES_URL, headers=org_headers, json={"plate": "DEF456"})
        assert resp.status_code == 201

        # Reactivar el viejo chocaria con el nuevo activo -> 422
        resp = client.patch(f"{VEHICLES_URL}/{v1}", headers=org_headers,
                            json={"is_active": True})
        assert resp.status_code == 422

    def test_same_plate_other_org_201(self, client, org_headers, org2_admin_headers):
        client.post(VEHICLES_URL, headers=org_headers, json={"plate": "GHI789"})
        resp = client.post(VEHICLES_URL, headers=org2_admin_headers,
                           json={"plate": "GHI789"})
        assert resp.status_code == 201

    def test_soft_delete_hides_from_default_list(self, client, org_headers):
        resp = client.post(DRIVERS_URL, headers=org_headers, json={"name": "Temporal"})
        did = resp.json()["id"]
        client.patch(f"{DRIVERS_URL}/{did}", headers=org_headers,
                     json={"is_active": False})

        assert client.get(DRIVERS_URL, headers=org_headers).json()["total"] == 0
        assert client.get(DRIVERS_URL, headers=org_headers,
                          params={"include_inactive": True}).json()["total"] == 1

    def test_unauthenticated_401(self, client):
        assert client.get(DRIVERS_URL).status_code == 401
        assert client.get(VEHICLES_URL).status_code == 401

    def test_rbac_viewer_denied(self, client, org_headers2):
        """config.view_fleet NO esta en roles de sistema (D4) — viewer 403."""
        assert client.get(DRIVERS_URL, headers=org_headers2).status_code == 403
        assert client.post(VEHICLES_URL, headers=org_headers2,
                           json={"plate": "NOP"}).status_code == 403

    def test_multitenant_isolation(self, client, org_headers, org2_admin_headers):
        client.post(DRIVERS_URL, headers=org_headers, json={"name": "Solo Org1"})
        assert client.get(DRIVERS_URL, headers=org2_admin_headers).json()["total"] == 0


# ---------------------------------------------------------------------------
# Constraints de modelos (kg_ledger — corren contra create_all, D13)
# ---------------------------------------------------------------------------

class TestKgLedgerConstraints:
    def _account(self, org_id, **overrides):
        base = dict(
            organization_id=org_id,
            code=f"TEST-{uuid4().hex[:8].upper()}",
            display_name="Cuenta Test",
            account_type="intersede",
            warehouse_id=None,
            third_party_id=None,
        )
        base.update(overrides)
        return KgLedgerAccount(**base)

    def test_check_willard_requires_third_party(self, db_session, test_organization):
        db_session.add(self._account(test_organization.id, account_type="willard_drosses"))
        with pytest.raises(IntegrityError, match="ck_kg_ledger_accounts_willard_tp"):
            db_session.flush()
        db_session.rollback()

    def test_check_intersede_rejects_third_party(self, db_session, test_organization):
        tp = ThirdParty(
            name="TP Kg", organization_id=test_organization.id,
            current_balance=Decimal("0"), initial_balance=Decimal("0"),
        )
        db_session.add(tp)
        db_session.flush()
        db_session.add(
            self._account(test_organization.id, account_type="intersede",
                          third_party_id=tp.id)
        )
        with pytest.raises(IntegrityError, match="ck_kg_ledger_accounts_intersede_tp"):
            db_session.flush()
        db_session.rollback()

    def test_unique_nulls_not_distinct(self, db_session, test_organization):
        """Dos cuentas org-wide del mismo tipo con warehouse NULL -> el UNIQUE
        NULLS NOT DISTINCT las colisiona (PG15+, v0.5 §11.1.1)."""
        db_session.add(self._account(test_organization.id))
        db_session.flush()
        db_session.add(self._account(test_organization.id))
        with pytest.raises(IntegrityError, match="ix_kg_ledger_account_org_type"):
            db_session.flush()
        db_session.rollback()

    def test_check_delta_kg_nonzero(self, db_session, test_organization, test_user):
        from datetime import datetime, timezone

        acc = self._account(test_organization.id)
        db_session.add(acc)
        db_session.flush()
        db_session.add(
            KgLedgerMovement(
                organization_id=test_organization.id,
                account_id=acc.id,
                delta_kg=Decimal("0"),
                transaction_date=datetime(2026, 7, 1, 12, tzinfo=timezone.utc),
                source_type="manual_adjustment",
                created_by=test_user.id,
            )
        )
        with pytest.raises(IntegrityError, match="ck_kg_ledger_movements_delta_nonzero"):
            db_session.flush()
        db_session.rollback()
