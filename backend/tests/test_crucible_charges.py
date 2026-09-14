"""
Tests #107 — documentos de crisol (traslado a crisoles / retorno de dross).

Lo que se vigila:
- Un documento de crisol mueve ETAPAS de la deuda intersede, no la deuda: el
  total no cambia, y no toca inventario ni pesos (salvo la maquila del
  reproceso en el retorno de dross, que gatea por flag).
- Al crisol solo entra plomo CRUDO: el clasificador es `lead_product` y nada
  mas (#103 D1). `discharge` queda reservado.
- Los avisos viajan en la RESPUESTA HTTP (#100 D4d): un warning que se calcula
  y no se entrega se ve identico a no existir.
- UN solo escritor del libro kg (F1): `KgLedgerMovement(` fuera de
  `services/kg_ledger.py` es un defecto, aunque los tests pasen.
"""
import re
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models.expense_category import ExpenseCategory
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material_kg_profile import MaterialKgProfile
from app.models.money_movement import MoneyMovement
from app.models.service_tariff import ServiceTariff
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

URL = "/api/v1/crucible-charges"
KG_URL = "/api/v1/kg-ledger"
MM_URL = "/api/v1/money-movements"
DATE = "2026-07-10T12:00:00"


# --------------------------------------------------------------- fixtures ---

@pytest.fixture
def wh_cv(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    db_session.commit()
    return wh


@pytest.fixture
def wh_jm(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Juan Mina")
    db_session.commit()
    return wh


@pytest.fixture(autouse=True)
def _flags(db_session, test_organization, wh_cv, wh_jm):
    """Maquila interna ENCENDIDA (O3 de QA): aqui el par del retorno de dross
    gatea por FLAG, y el test OFF (T5b) lo apaga explicito."""
    test_organization.settings = {
        "kg_ledger_enabled": True,
        "two_step_transfers_enabled": True,
        "internal_maquila_enabled": True,
        "willard_sede_facturacion": str(wh_cv.id),
        "willard_sede_drosses": str(wh_jm.id),
    }
    db_session.commit()


@pytest.fixture
def acc_intersede(db_session, test_organization):
    acc = KgLedgerAccount(
        organization_id=test_organization.id,
        code="INTERSEDE",
        display_name="Intersede",
        account_type="intersede",
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def acc_drosses(db_session, test_organization):
    from tests.conftest import create_third_party_with_category

    willard = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A", "customer"
    )
    acc = KgLedgerAccount(
        organization_id=test_organization.id,
        code="WILL-DROSS",
        display_name="Willard Drosses",
        account_type="willard_drosses",
        third_party_id=willard.id,
        is_active=True,
    )
    db_session.add(acc)
    db_session.commit()
    return acc


@pytest.fixture
def tarifa_maquila(db_session, test_organization, test_user):
    t = ServiceTariff(
        organization_id=test_organization.id,
        tariff_code="maquila_intersede_cv_jm",
        unit_price_cop=Decimal("1500"),
        unit="per_kg_lead",
        created_by=test_user.id,
    )
    db_session.add(t)
    db_session.commit()
    return t


def _mat(db, org_id, code, name, lead=None):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, name, cat.id)
    mat.default_unit = "kg"
    if lead is not None:
        db.add(MaterialKgProfile(organization_id=org_id, material_id=mat.id, lead_product=lead))
    db.commit()
    return mat


@pytest.fixture
def mat_crudo(db_session, test_organization):
    return _mat(db_session, test_organization.id, "PB-CRU", "Plomo Crudo", "crudo")


@pytest.fixture
def mat_puro(db_session, test_organization):
    return _mat(db_session, test_organization.id, "PB-PUR", "Plomo Puro", "puro")


@pytest.fixture
def mat_dross(db_session, test_organization):
    """Sin perfil kg: el dross del crisol no es plomo entregable."""
    return _mat(db_session, test_organization.id, "DROSS-CRI", "Dross de crisol")


# ---------------------------------------------------------------- helpers ---

def _manual(client, headers, account_id, kg, stage=None, date=DATE, expect=201):
    body = {
        "account_id": str(account_id),
        "delta_kg": str(kg),
        "transaction_date": date,
        "description": "seed",
        "reason": "seed de prueba",
    }
    if stage is not None:
        body["stage"] = stage
    r = client.post(f"{KG_URL}/movements", headers=headers, json=body)
    assert r.status_code == expect, r.text
    return r


def _summary(client, headers):
    r = client.get(f"{KG_URL}/summary", headers=headers)
    assert r.status_code == 200, r.text
    j = r.json()
    return (
        Decimal(str(j["intersede_horno_kg"])),
        Decimal(str(j["intersede_crisol_kg"])),
        Decimal(str(j["total_intersede_kg"])),
    )


def _charge(client, headers, wh, mat, kg, event_type="charge", expect=201, date=DATE):
    r = client.post(
        URL,
        headers=headers,
        json={
            "event_type": event_type,
            "warehouse_id": str(wh.id),
            "material_id": str(mat.id),
            "quantity_kg": str(kg),
            "date": date,
        },
    )
    assert r.status_code == expect, r.text
    return r.json()


def _kg_rows(db, source_id, status="confirmed"):
    return db.execute(
        select(KgLedgerMovement).where(
            KgLedgerMovement.source_type == "crucible_charge",
            KgLedgerMovement.source_id == source_id,
            KgLedgerMovement.status == status,
        )
    ).scalars().all()


def _mms(db, org_id, mtype, status="confirmed"):
    return db.execute(
        select(MoneyMovement).where(
            MoneyMovement.organization_id == org_id,
            MoneyMovement.movement_type == mtype,
            MoneyMovement.status == status,
        )
    ).scalars().all()


def _count(db, model, org_id):
    return db.execute(
        select(func.count()).select_from(model).where(model.organization_id == org_id)
    ).scalar_one()


# ------------------------------------------------------------------ tests ---

class TestDocumentosDeCrisol:

    def test_traslado_a_crisoles_mueve_etapas_no_deuda(
        self, client, org_headers, db_session, test_organization, wh_jm, acc_intersede, mat_crudo,
    ):
        """T2 — Hugo (28-ago): "los saldos no va a afectar sino el del traslado
        que haces de un horno a otro horno". Horno −30, crisol +30, total
        IGUAL; cero inventario, cero pesos; primer consecutivo = 1."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        org = test_organization.id
        inv_before = _count(db_session, InventoryMovement, org)
        mm_before = _count(db_session, MoneyMovement, org)

        out = _charge(client, org_headers, wh_jm, mat_crudo, 30)

        assert out["charge_number"] == 1
        assert out["label"] == "Crisol #1"
        assert out["event_type"] == "charge"
        assert out["status"] == "confirmed"
        assert out["warnings"] == []
        horno, crisol, total = _summary(client, org_headers)
        assert (horno, crisol, total) == (Decimal("70"), Decimal("30"), Decimal("100"))
        assert _count(db_session, InventoryMovement, org) == inv_before
        assert _count(db_session, MoneyMovement, org) == mm_before
        rows = _kg_rows(db_session, out["id"])
        assert sorted((r.stage, r.delta_kg) for r in rows) == [
            ("crisol", Decimal("30.0000")), ("horno", Decimal("-30.0000")),
        ]

    def test_charge_solo_con_crudo(
        self, client, org_headers, wh_jm, acc_intersede, mat_puro, mat_dross, mat_crudo,
    ):
        """T3 — el clasificador es `lead_product` (#103 D1): puro → 422 que lo
        nombra; sin marca → 422; `discharge` (reservado) → 422."""
        r = client.post(URL, headers=org_headers, json={
            "event_type": "charge", "warehouse_id": str(wh_jm.id),
            "material_id": str(mat_puro.id), "quantity_kg": "10", "date": DATE,
        })
        assert r.status_code == 422, r.text
        assert "PB-PUR" in r.json()["detail"]
        assert "puro" in r.json()["detail"].lower()

        r = client.post(URL, headers=org_headers, json={
            "event_type": "charge", "warehouse_id": str(wh_jm.id),
            "material_id": str(mat_dross.id), "quantity_kg": "10", "date": DATE,
        })
        assert r.status_code == 422, r.text
        assert "DROSS-CRI" in r.json()["detail"]

        r = client.post(URL, headers=org_headers, json={
            "event_type": "discharge", "warehouse_id": str(wh_jm.id),
            "material_id": str(mat_crudo.id), "quantity_kg": "10", "date": DATE,
        })
        assert r.status_code == 422, r.text

    def test_charge_deja_horno_negativo_avisa(
        self, client, org_headers, wh_jm, acc_intersede, mat_crudo,
    ):
        """T4 — avisa, no bloquea (#17/#76), y el aviso viaja en la RESPUESTA."""
        _manual(client, org_headers, acc_intersede.id, 10, stage="horno")
        out = _charge(client, org_headers, wh_jm, mat_crudo, 30)
        assert out["status"] == "confirmed"
        assert len(out["warnings"]) == 1
        assert "horno" in out["warnings"][0]
        assert "-20" in out["warnings"][0]
        horno, crisol, total = _summary(client, org_headers)
        assert (horno, crisol, total) == (Decimal("-20"), Decimal("30"), Decimal("10"))

    def test_dross_return_emite_par_con_flag(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, acc_intersede, mat_crudo, mat_dross, tarifa_maquila,
    ):
        """T5a — Johana (3-sep, fila 10): el dross vuelve al horno grande y
        "genera una nueva maquila". Crisol −5, horno +5, par $1.500×5 con la
        categoria del traslado, gasto en CV / ingreso en planta, enlazado."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _charge(client, org_headers, wh_jm, mat_crudo, 30)

        out = _charge(client, org_headers, wh_jm, mat_dross, 5, event_type="dross_return")

        assert out["charge_number"] == 2
        assert Decimal(str(out["maquila_amount"])) == Decimal("7500.00")
        horno, crisol, total = _summary(client, org_headers)
        assert (horno, crisol, total) == (Decimal("75"), Decimal("25"), Decimal("100"))
        org = test_organization.id
        exp = _mms(db_session, org, "internal_maquila_expense")
        inc = _mms(db_session, org, "internal_maquila_income")
        assert len(exp) == 1 and len(inc) == 1
        assert exp[0].amount == Decimal("7500.00") == inc[0].amount
        assert exp[0].warehouse_id == wh_cv.id
        assert inc[0].warehouse_id == wh_jm.id
        assert exp[0].transfer_pair_id == inc[0].id and inc[0].transfer_pair_id == exp[0].id
        assert exp[0].source_type == "crucible_charge" and str(exp[0].source_id) == out["id"]
        cat = db_session.get(ExpenseCategory, exp[0].expense_category_id)
        assert cat.name == "Maquila Intersede"
        assert exp[0].account_id is None and exp[0].third_party_id is None

    def test_dross_return_sin_flag_mueve_kg_sin_par(
        self, client, org_headers, db_session, test_organization,
        wh_cv, wh_jm, acc_intersede, mat_crudo, mat_dross, tarifa_maquila,
    ):
        """T5b — el par OFF: los kg se mueven igual y no hay pesos. Sin este
        contraste 'el gate funciona' y 'lo apague para todos' se ven identicos
        (#94/#99)."""
        test_organization.settings = {
            **test_organization.settings, "internal_maquila_enabled": False,
        }
        db_session.commit()
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _charge(client, org_headers, wh_jm, mat_crudo, 30)

        out = _charge(client, org_headers, wh_jm, mat_dross, 5, event_type="dross_return")

        assert Decimal(str(out["maquila_amount"])) == 0
        assert _summary(client, org_headers) == (Decimal("75"), Decimal("25"), Decimal("100"))
        org = test_organization.id
        assert _mms(db_session, org, "internal_maquila_expense") == []
        assert _mms(db_session, org, "internal_maquila_income") == []

    def test_anular_documento_de_crisol(
        self, client, org_headers, db_session, test_organization,
        wh_jm, acc_intersede, mat_crudo, mat_dross, tarifa_maquila,
    ):
        """T6 — anular revierte kg y par por `(source_type, source_id)`; el par
        NO se anula desde Tesoreria (422 que manda al modulo correcto, D10)."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _charge(client, org_headers, wh_jm, mat_crudo, 30)
        out = _charge(client, org_headers, wh_jm, mat_dross, 5, event_type="dross_return")
        org = test_organization.id
        exp = _mms(db_session, org, "internal_maquila_expense")[0]

        r = client.post(f"{MM_URL}/{exp.id}/annul", headers=org_headers, json={"reason": "prueba"})
        assert r.status_code == 422, r.text
        assert "Salidas de Plomo → Crisol" in r.json()["detail"]
        assert "Traslados" not in r.json()["detail"]

        r = client.post(f"{URL}/{out['id']}/annul", headers=org_headers, json={"reason": "capturado dos veces"})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "annulled"
        assert r.json()["annulled_reason"] == "capturado dos veces"
        assert Decimal(str(r.json()["maquila_amount"])) == 0
        # el estado vuelve al de despues del traslado a crisoles
        assert _summary(client, org_headers) == (Decimal("70"), Decimal("30"), Decimal("100"))
        assert _kg_rows(db_session, out["id"]) == []
        assert len(_kg_rows(db_session, out["id"], status="annulled")) == 2
        db_session.expire_all()
        assert _mms(db_session, org, "internal_maquila_expense") == []
        assert len(_mms(db_session, org, "internal_maquila_expense", status="annulled")) == 1
        assert len(_mms(db_session, org, "internal_maquila_income", status="annulled")) == 1

        r = client.post(f"{URL}/{out['id']}/annul", headers=org_headers, json={"reason": "otra vez"})
        assert r.status_code == 400

    def test_manual_intersede_exige_stage_y_otras_lo_rechazan(
        self, client, org_headers, acc_intersede, acc_drosses,
    ):
        """T13 — el escritor unico valida en los dos sentidos (422)."""
        _manual(client, org_headers, acc_intersede.id, 10, stage=None, expect=422)
        _manual(client, org_headers, acc_drosses.id, 10, stage="horno", expect=422)
        _manual(client, org_headers, acc_intersede.id, 10, stage="crisol", expect=201)
        _manual(client, org_headers, acc_drosses.id, 10, stage=None, expect=201)

    def test_documento_de_crisol_solo_desde_planta(
        self, client, org_headers, wh_cv, wh_jm, acc_intersede, mat_crudo,
    ):
        """T14 — calco de D8 (#100): el crisol vive en planta; desde otra sede
        moveria la etapa de plomo que nunca estuvo ahi."""
        r = client.post(URL, headers=org_headers, json={
            "event_type": "charge", "warehouse_id": str(wh_cv.id),
            "material_id": str(mat_crudo.id), "quantity_kg": "10", "date": DATE,
        })
        assert r.status_code == 400, r.text
        assert "Juan Mina" in r.json()["detail"]
        assert "Circunvalar" in r.json()["detail"]

    def test_statement_intersede_lleva_etapa(
        self, client, org_headers, wh_jm, acc_intersede, mat_crudo,
    ):
        """T16 — cada fila del estado de cuenta intersede trae `stage` por API."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _charge(client, org_headers, wh_jm, mat_crudo, 30)
        r = client.get(
            f"{KG_URL}/accounts/{acc_intersede.id}/movements",
            headers=org_headers,
            params={"date_from": "2026-07-01"},
        )
        assert r.status_code == 200, r.text
        rows = r.json()["movements"]
        assert len(rows) == 3
        assert all(row["stage"] in ("horno", "crisol") for row in rows)
        assert sorted(row["stage"] for row in rows) == ["crisol", "horno", "horno"]

    def test_ningun_escritor_de_kg_fuera_del_servicio(self):
        """T18 (F1) — guarda: `KgLedgerMovement(` en `app/` SOLO en el
        escritor unico. Un escritor directo se salta la validacion de etapa y
        los tests de ese flujo pasan igual — por eso es una guarda y no un test
        de comportamiento (calco de `TestGuarda`, #106)."""
        app_dir = Path(__file__).resolve().parents[1] / "app"
        pattern = re.compile(r"(?<!class )\bKgLedgerMovement\(")
        hits = sorted(
            str(p.relative_to(app_dir.parent))
            for p in app_dir.rglob("*.py")
            if pattern.search(p.read_text())
        )
        assert hits == ["app/services/kg_ledger.py"], hits
