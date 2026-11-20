"""
Tests del listado de entidades de impuestos — Tesorería → Impuestos y retenciones
(plan `plan-sac-impuestos-y-retenciones.md` v1.2, D1).

Lo que se vigila:

- **Pertenencia por CÓDIGO, nunca por texto** (#112 D4b). T3: un tercero normal
  con el nombre exacto de la entidad NO aparece. T4: renombrar la categoría no
  cambia nada.
- **Los signos los pone el flujo real**, no el test: la venta con IVA deja el IVA
  en negativo (le debemos a la DIAN) y las retenciones que nos practican en
  positivo (a favor); el IVA de una compra lo sube (#122).
- **Sin filtro `is_active`** (C3 invertida en v1.2): una entidad de sistema no se
  puede desactivar por la API, así que una inactiva solo existe por fuera de
  ella y puede tener saldo. T9 la deja inactiva por ORM y exige que se vea.
- **Control positivo del permiso** (#111): un rol que lee terceros en 200 y uno
  que no los lee en 403. Sin el 200, el 403 podría venir de la bandera.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.third_party import ThirdParty
from app.models.third_party_category import ThirdPartyCategory
from app.services.tax_entities import TAX_CATEGORY_CODE, resolve_tax_entity
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import (
    api_create_sale,
    create_material,
    create_material_category,
    create_warehouse,
)

URL = "/api/v1/third-parties/tax-entities"
RET_URL = "/api/v1/third-parties/retention-entities"
SALES_URL = "/api/v1/sales"
PURCHASES_URL = "/api/v1/purchases"
ADJUST_URL = "/api/v1/inventory/adjustments"
SEED_DATE = "2026-07-01T12:00:00"
SALE_DATE = "2026-07-10"

IVA = Decimal("19000.00")
RETEFUENTE = Decimal("2500.00")
ICA = Decimal("1100.00")


def _past_date() -> str:
    """Fecha de negocio pasada, con el reloj de negocio (nunca el UTC): la
    liquidación de compras rechaza fechas futuras."""
    return (business_today() - timedelta(days=2)).isoformat()


# --------------------------------------------------------------- fixtures ---

@pytest.fixture
def flag_on(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()
    return test_organization


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def customer(db_session, test_organization):
    return create_third_party_with_category(
        db_session, test_organization.id, "Baterias Willard S.A", "customer"
    )


@pytest.fixture
def supplier(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Chatarreria Uno", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def material(db_session, test_organization, client, org_headers, warehouse):
    cat = create_material_category(db_session, test_organization.id, "Plomo")
    mat = create_material(db_session, test_organization.id, "PB-PUR", "Plomo Puro", cat.id)
    mat.default_unit = "kg"
    db_session.commit()
    resp = client.post(
        f"{ADJUST_URL}/increase", headers=org_headers,
        json={
            "material_id": str(mat.id), "warehouse_id": str(warehouse.id),
            "quantity": "1000", "unit_cost": "2000", "date": SEED_DATE, "reason": "Seed",
        },
    )
    assert resp.status_code == 201, resp.text
    return mat


def _sale_with_taxes(client, headers, customer, warehouse, material):
    """Venta de 100 kg x $1.000 = $100.000 con IVA, ReteFuente e ICA Bogotá."""
    sale = api_create_sale(
        client, headers,
        customer_id=customer.id, warehouse_id=warehouse.id,
        lines=[{"material_id": material.id, "quantity": "100", "unit_price": "1000"}],
        date=SALE_DATE,
    )
    r = client.patch(
        f"{SALES_URL}/{sale['id']}/liquidate", headers=headers,
        json={
            "liquidation_date": f"{SALE_DATE}T12:00:00",
            "taxes": [
                {"tax_type": "iva", "rate": "19", "amount": str(IVA)},
                {"tax_type": "retefuente", "rate": "2.5", "amount": str(RETEFUENTE)},
                {"tax_type": "ica", "municipality": "Bogotá", "rate": "1.1",
                 "amount": str(ICA)},
            ],
        },
    )
    assert r.status_code == 200, r.text
    return sale


def _rows(client, headers):
    r = client.get(URL, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def _by_type(rows):
    return {(r["tax_type"], r["municipality"]): r for r in rows}


def _headers_for_role(db_session, org, permission_codes, email):
    """Usuario con un rol custom que tiene SOLO `permission_codes`."""
    from app.models.permission import Permission
    from app.models.role import Role, RolePermission
    from app.models.user import OrganizationMember, User

    rol = Role(
        id=uuid4(), name=f"rol-{email}", display_name=f"Rol {email}",
        organization_id=org.id, is_system_role=False,
    )
    db_session.add(rol)
    db_session.flush()
    perms = db_session.query(Permission).filter(Permission.code.in_(permission_codes)).all()
    assert len(perms) == len(permission_codes), "faltan permisos en el catalogo de test"
    for perm in perms:
        db_session.add(RolePermission(role_id=rol.id, permission_id=perm.id))
    user = User(email=email, hashed_password="x", full_name=email, is_active=True)
    db_session.add(user)
    db_session.flush()
    db_session.add(OrganizationMember(user_id=user.id, organization_id=org.id, role_id=rol.id))
    db_session.commit()
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
        "X-Organization-ID": str(org.id),
    }


# ------------------------------------------------------------------ tests ---

class TestListadoImpuestos:

    def test_t1_venta_con_impuestos_lista_tres_filas_con_su_signo(
        self, client, org_headers, flag_on, customer, warehouse, material,
    ):
        """T1: el flujo real pone los signos. IVA < 0 (le debemos a la DIAN),
        ReteFuente e ICA > 0 (nos las practicaron: a favor)."""
        _sale_with_taxes(client, org_headers, customer, warehouse, material)
        rows = _rows(client, org_headers)
        assert len(rows) == 3, rows
        # Orden: IVA, ReteFuente, ReteIVA, ICA.
        assert [r["tax_type"] for r in rows] == ["iva", "retefuente", "ica"]
        by = _by_type(rows)
        iva = by[("iva", None)]
        assert iva["current_balance"] == pytest.approx(-float(IVA))
        assert iva["label"] == "IVA"
        assert iva["name"] == "[Impuestos] IVA por Pagar"
        assert iva["is_active"] is True
        assert by[("retefuente", None)]["current_balance"] == pytest.approx(float(RETEFUENTE))
        ica = by[("ica", "Bogotá")]
        assert ica["current_balance"] == pytest.approx(float(ICA))
        assert ica["label"] == "ICA Bogotá"

    def test_t2_iva_de_compra_sube_el_iva_por_el_monto_exacto(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, supplier, warehouse, material,
    ):
        """T2: el IVA de una compra (#122) descuenta: la entidad recibe +IVA."""
        from app.schemas.document_tax import DocumentTaxCreate
        from app.services.purchase import purchase as purchase_service

        _sale_with_taxes(client, org_headers, customer, warehouse, material)
        before = _by_type(_rows(client, org_headers))[("iva", None)]["current_balance"]

        r = client.post(PURCHASES_URL, headers=org_headers, json={
            "supplier_id": str(supplier.id), "date": _past_date(),
            "lines": [{"material_id": str(material.id), "warehouse_id": str(warehouse.id),
                       "quantity": 10, "unit_price": 5000}],
        })
        assert r.status_code == 201, r.text
        iva_compra = Decimal("9500.00")
        purchase_service.liquidate(
            db_session, r.json()["id"], test_organization.id,
            liquidation_date=datetime.fromisoformat(f"{_past_date()}T12:00:00"),
            taxes_data=[DocumentTaxCreate(tax_type="iva", rate=Decimal("19"),
                                          amount=iva_compra)],
        )
        after = _by_type(_rows(client, org_headers))[("iva", None)]["current_balance"]
        assert after - before == pytest.approx(float(iva_compra))

    def test_t3_un_tercero_con_el_nombre_pero_sin_la_categoria_no_aparece(
        self, client, org_headers, db_session, test_organization, flag_on,
    ):
        """T3: el nombre no da pertenencia (#112 D4b)."""
        create_third_party_with_category(
            db_session, test_organization.id, "[Impuestos] IVA por Pagar", "customer"
        )
        db_session.commit()
        assert _rows(client, org_headers) == []

    def test_t4_renombrar_la_categoria_no_cambia_el_listado(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """T4: la categoría se reconoce por código; su nombre es renombrable."""
        _sale_with_taxes(client, org_headers, customer, warehouse, material)
        cat = db_session.execute(select(ThirdPartyCategory).where(
            ThirdPartyCategory.organization_id == test_organization.id,
            ThirdPartyCategory.system_code == TAX_CATEGORY_CODE,
        )).scalar_one()
        cat.name = "Otra cosa"
        db_session.commit()
        rows = _rows(client, org_headers)
        assert {r["tax_type"] for r in rows} == {"iva", "retefuente", "ica"}

    def test_t5_las_retenciones_practicadas_no_aparecen_aca(
        self, client, org_headers, flag_on, supplier, warehouse, material,
    ):
        """T5: '[Retenciones] X' es otra familia (pasivo de SAC). Sale en
        retention-entities, como antes, y no acá."""
        r = client.post(PURCHASES_URL, headers=org_headers, json={
            "supplier_id": str(supplier.id), "date": _past_date(),
            "lines": [{"material_id": str(material.id), "warehouse_id": str(warehouse.id),
                       "quantity": 100, "unit_price": 10000}],
        })
        assert r.status_code == 201, r.text
        liq = client.patch(f"{PURCHASES_URL}/{r.json()['id']}/liquidate", headers=org_headers,
                           json={"liquidation_date": _past_date(), "retentions": [
                               {"retention_type": "retefuente", "amount": "25000", "rate": "2.5"},
                           ]})
        assert liq.status_code == 200, liq.text
        # Control positivo: la entidad de retención existe y se lista donde siempre.
        ret = client.get(RET_URL, headers=org_headers)
        assert ret.status_code == 200, ret.text
        assert any(row["entity_id"] and row["retention_type"] == "retefuente"
                   for row in ret.json()), ret.json()
        assert _rows(client, org_headers) == []

    def test_t6_sin_bandera_403_tambien_para_admin(self, client, org_headers):
        """T6: org sin kg_ledger_enabled (como Costa y Meta) → 403."""
        r = client.get(URL, headers=org_headers)
        assert r.status_code == 403, r.text

    def test_t7_permiso_con_control_positivo(
        self, client, db_session, test_organization, flag_on,
    ):
        """T7: con third_parties.view → 200; sin él → 403. El 200 prueba que el
        403 del otro rol sale del permiso y no de la bandera."""
        con = _headers_for_role(db_session, test_organization,
                                ["third_parties.view"], "lee-terceros@test.com")
        sin = _headers_for_role(db_session, test_organization,
                                ["sales.view"], "lee-ventas@test.com")
        assert client.get(URL, headers=con).status_code == 200
        assert client.get(URL, headers=sin).status_code == 403

    def test_t8_cada_org_ve_solo_lo_suyo(
        self, client, org_headers, org_headers2, db_session,
        test_organization, test_organization2,
    ):
        """T8: dos orgs con IVA; cada una ve solo su entidad y su saldo."""
        for org, balance in ((test_organization, -100), (test_organization2, -200)):
            org.settings = {"kg_ledger_enabled": True}
            tp = resolve_tax_entity(db_session, org.id, "iva")
            tp.current_balance = Decimal(balance)
        db_session.commit()
        uno = _rows(client, org_headers)
        dos = _rows(client, org_headers2)
        assert [r["current_balance"] for r in uno] == [-100]
        assert [r["current_balance"] for r in dos] == [-200]

    def test_t9_entidad_inactiva_con_saldo_si_aparece(
        self, client, org_headers, db_session, test_organization,
        flag_on, customer, warehouse, material,
    ):
        """T9 (C3 invertida, v1.2): una entidad inactiva con saldo ≠ 0 SE VE.

        Solo se puede dejar inactiva por ORM: la API la protege (guard de
        entidad del sistema, antes del de saldo). Se fija esa premisa primero.
        El control positivo es la otra entidad, activa: el campo distingue.
        """
        _sale_with_taxes(client, org_headers, customer, warehouse, material)
        ica = db_session.execute(select(ThirdParty).where(
            ThirdParty.organization_id == test_organization.id,
            ThirdParty.name.like("[Impuestos] ICA%"),
        )).scalar_one()

        # Premisa: la API no deja desactivarla.
        r = client.delete(f"/api/v1/third-parties/{ica.id}", headers=org_headers)
        assert r.status_code == 400, r.text
        assert "sistema" in r.text

        ica.is_active = False
        db_session.commit()
        by = _by_type(_rows(client, org_headers))
        inactiva = by[("ica", "Bogotá")]
        assert inactiva["is_active"] is False
        assert inactiva["current_balance"] == pytest.approx(float(ICA))
        assert by[("iva", None)]["is_active"] is True
