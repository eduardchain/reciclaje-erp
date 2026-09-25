"""
Tests #107 — documentos de crisol (traslado a crisoles / retorno de dross).

Lo que se vigila:
- #109 SUPERSEDE dos cosas de #107 (respuestas del cliente, 16 y 18-sep):
  (a) el TRASLADO a crisoles sigue siendo neto cero sobre la deuda, pero el
  RETORNO de dross ya no: se digitan kg de DROSS, el crisol baja esos kg y el
  horno sube solo el plomo (70 % por formula) -> la deuda total baja la
  diferencia, y es intencional; (b) los dos documentos MUEVEN INVENTARIO via
  una transformacion enlazada (crudo -> puro 1:1; puro -> crudo con merma).
- Escalas (F1): todo se cuantiza a 0,001 ANTES de calcular; el inventario
  guarda tres decimales y el libro kg cuatro.
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
from uuid import UUID

import pytest
from sqlalchemy import func, select

from app.models.expense_category import ExpenseCategory
from app.models.inventory_movement import InventoryMovement
from app.models.kg_ledger import KgLedgerAccount, KgLedgerMovement
from app.models.material import Material
from app.models.material_conversion_formula import MaterialConversionFormula
from app.models.material_kg_profile import MaterialKgProfile
from app.models.material_transformation import MaterialTransformation
from app.models.money_movement import MoneyMovement
from app.models.plant_process import CrucibleCharge
from app.models.service_tariff import ServiceTariff
from tests.integration_helpers import (
    create_material,
    create_material_category,
    create_warehouse,
)

URL = "/api/v1/crucible-charges"
TR_URL = "/api/v1/inventory/transformations"
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


def _mat(db, org_id, code, name, lead=None, stock=None, cost=None):
    cat = create_material_category(db, org_id, f"Cat {code}")
    mat = create_material(db, org_id, code, name, cat.id)
    mat.default_unit = "kg"
    if stock is not None:
        # Stock de partida directo en el material: aqui se prueba lo que el
        # documento MUEVE (deltas), no como llego el saldo inicial.
        mat.current_stock = Decimal(stock)
        mat.current_stock_liquidated = Decimal(stock)
        mat.current_average_cost = Decimal(cost or "0")
    if lead is not None:
        db.add(MaterialKgProfile(organization_id=org_id, material_id=mat.id, lead_product=lead))
    db.commit()
    return mat


def _formula(db, org_id, user_id, mat, pct):
    f = MaterialConversionFormula(
        organization_id=org_id,
        material_id=mat.id,
        formula_type="drosses_to_lead",
        parameters={"lead_percentage": pct},
        created_by=user_id,
    )
    db.add(f)
    db.commit()
    return f


@pytest.fixture
def mat_puro(db_session, test_organization):
    return _mat(db_session, test_organization.id, "PB-PUR", "Plomo Puro", "puro",
                stock="500", cost="2500")


@pytest.fixture
def mat_crudo(db_session, test_organization, mat_puro):
    """Pide `mat_puro` a proposito (#109): un traslado a crisoles necesita saber
    QUE material entra al inventario, y lo decide `lead_product`. El test que
    prueba la ausencia (T14) arma su crudo a mano."""
    return _mat(db_session, test_organization.id, "PB-CRU", "Plomo Crudo", "crudo",
                stock="1000", cost="2000")


@pytest.fixture
def mat_dross(db_session, test_organization, test_user):
    """Sin perfil kg (no es plomo entregable) y CON formula: 70 % de plomo,
    factor fijo (Hugo 16-sep). De ahi sale cuanto sube el horno."""
    mat = _mat(db_session, test_organization.id, "DROSS-CRI", "Dross de crisol")
    _formula(db_session, test_organization.id, test_user.id, mat, 0.70)
    return mat


@pytest.fixture
def mat_dross_sin_formula(db_session, test_organization):
    return _mat(db_session, test_organization.id, "DROSS-X", "Dross sin formula")


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


def _charge(client, headers, wh, mat, kg, event_type="charge", expect=201, date=DATE, **extra):
    r = client.post(
        URL,
        headers=headers,
        json={
            "event_type": event_type,
            "warehouse_id": str(wh.id),
            "material_id": str(mat.id),
            "quantity_kg": str(kg),
            "date": date,
            **extra,
        },
    )
    assert r.status_code == expect, r.text
    return r.json()


def _stock(db, mat):
    db.expire_all()
    m = db.get(Material, mat.id)
    return m.current_stock_liquidated, m.current_average_cost


def _inv_rows(db, transformation_id):
    return db.execute(
        select(InventoryMovement).where(InventoryMovement.reference_id == transformation_id)
    ).scalars().all()


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
        IGUAL; cero pesos; primer consecutivo = 1. 🔴 #109 invierte UN assert:
        el documento SI mueve inventario (dos movimientos: crudo sale, puro
        entra) — el detalle lo fija `test_charge_convierte_inventario_1_a_1`."""
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
        assert _count(db_session, InventoryMovement, org) == inv_before + 2
        assert _count(db_session, MoneyMovement, org) == mm_before
        assert Decimal(str(out["lead_kg"])) == Decimal("30")
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
        "genera una nueva maquila". 🔴 #109 (Hugo 16-sep): los 5 kg son DROSS
        al 70 % -> crisol −5, horno +3,5, la deuda total baja 1,5 (intencional,
        18-sep) y el par va sobre el PLOMO: $1.500×3,5, con la categoria del
        traslado, gasto en CV / ingreso en planta, enlazado."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _charge(client, org_headers, wh_jm, mat_crudo, 30)

        out = _charge(client, org_headers, wh_jm, mat_dross, 5, event_type="dross_return")

        assert out["charge_number"] == 2
        assert Decimal(str(out["maquila_amount"])) == Decimal("5250.00")
        horno, crisol, total = _summary(client, org_headers)
        assert (horno, crisol, total) == (Decimal("73.5"), Decimal("25"), Decimal("98.5"))
        org = test_organization.id
        exp = _mms(db_session, org, "internal_maquila_expense")
        inc = _mms(db_session, org, "internal_maquila_income")
        assert len(exp) == 1 and len(inc) == 1
        assert exp[0].amount == Decimal("5250.00") == inc[0].amount
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
        assert _summary(client, org_headers) == (Decimal("73.5"), Decimal("25"), Decimal("98.5"))
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


# ---------------------------------------------------------------------- #
# #109 — correcciones del cierre con el cliente (16 y 18-sep)             #
# ---------------------------------------------------------------------- #
def _transform(client, headers, wh, source, dest, qty, expect=201):
    r = client.post(
        TR_URL,
        headers=headers,
        json={
            "source_material_id": str(source.id),
            "source_warehouse_id": str(wh.id),
            "source_quantity": str(qty),
            "waste_quantity": "0",
            "cost_distribution": "proportional_weight",
            "lines": [{
                "destination_material_id": str(dest.id),
                "destination_warehouse_id": str(wh.id),
                "quantity": str(qty),
            }],
            "date": DATE,
            "reason": "prueba de transformacion manual",
        },
    )
    assert r.status_code == expect, r.text
    return r.json()


class TestDosCantidadesEInventario:
    """Los numeros salen de la reunion del 18-sep con Johana (transcripcion
    local). Con sus palabras: crisol −20 (L433), horno +14 (L451, L505), "Salen
    20 del crisol, entran 14 al horno grande" (L649), "la deuda total cambiaría
    en 6 kilos" (L517) y traslado a crisoles 1:1 (L555, L579). Que sean 20 "de
    puro" y 14 "de crudo" lo dijo Daniel y ella respondio "Correcto" (L639-641).
    20 kg de dross al 70 % = 14 kg de plomo."""

    def test_dross_return_mueve_dross_y_plomo(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_dross,
    ):
        """T6 — `lead_kg` se lee de la RESPUESTA HTTP (trampa #95: el endpoint
        arma el response campo por campo; con el ORM el test pasa y la pantalla
        miente)."""
        _manual(client, org_headers, acc_intersede.id, 100, stage="horno")
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")

        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")

        assert Decimal(str(out["quantity_kg"])) == Decimal("20")
        assert Decimal(str(out["lead_kg"])) == Decimal("14")
        got = client.get(f"{URL}/{out['id']}", headers=org_headers).json()
        assert Decimal(str(got["lead_kg"])) == Decimal("14")
        horno, crisol, total = _summary(client, org_headers)
        assert (horno, crisol, total) == (Decimal("114"), Decimal("30"), Decimal("144"))
        deltas = {r.stage: r.delta_kg for r in _kg_rows(db_session, out["id"])}
        assert deltas == {"crisol": Decimal("-20"), "horno": Decimal("14")}

    def test_dross_return_maquila_sobre_plomo(
        self, client, org_headers, db_session, test_organization,
        wh_jm, acc_intersede, mat_crudo, mat_dross, tarifa_maquila,
    ):
        """T7 — Hugo (16-sep): la maquila del reproceso se cobra sobre el plomo
        que vuelve al horno. 14 × $1.500 = $21.000, no 20 × $1.500 = $30.000."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")
        assert Decimal(str(out["maquila_amount"])) == Decimal("21000.00")
        exp = _mms(db_session, test_organization.id, "internal_maquila_expense")
        assert [m.amount for m in exp] == [Decimal("21000.00")]

    def test_dross_return_sin_formula_422(
        self, client, org_headers, db_session, test_organization,
        wh_jm, acc_intersede, mat_crudo, mat_dross_sin_formula,
    ):
        """T8 (F2) — sin formula NO se cae a 1:1: subir el horno por los kg de
        dross es justo el defecto que este ciclo corrige. 422 que nombra el
        material y no deja nada escrito."""
        before = _count(db_session, KgLedgerMovement, test_organization.id)
        r = client.post(URL, headers=org_headers, json={
            "event_type": "dross_return", "warehouse_id": str(wh_jm.id),
            "material_id": str(mat_dross_sin_formula.id), "quantity_kg": "20", "date": DATE,
        })
        assert r.status_code == 422, r.text
        assert "DROSS-X" in r.json()["detail"]
        assert "formula" in r.json()["detail"]
        assert _count(db_session, KgLedgerMovement, test_organization.id) == before

    def test_dross_return_rechaza_material_de_willard(
        self, client, org_headers, db_session, test_organization, test_user,
        wh_jm, acc_intersede, mat_crudo,
    ):
        """T20 (C2 de QA) — la formula CALCULA, no clasifica. En SAC 16
        materiales tienen `drosses_to_lead` y 15 son lo que MANDA Willard; con
        GUARRU (41 %) un retorno bajaba el crisol 20 y subia el horno 8,2 sin
        error. El predicado es el MUNDO Willard del perfil — el mismo de la
        pantalla —, leido de la RESPUESTA HTTP, y no deja nada escrito.

        El contraste es la mitad del test (leccion #99), y son TRES casos: mundo
        Willard -> 422; perfil con mundo 'none' -> 201 (lo que bloquea es el
        mundo, no tener fila de perfil); SIN fila de perfil -> 201 (mismo
        predicado que la pantalla: sin perfil = 'none')."""
        org = test_organization.id
        guarru = _mat(db_session, org, "GUARRU", "Guarru seco")
        db_session.add(MaterialKgProfile(
            organization_id=org, material_id=guarru.id, willard_world="drosses",
        ))
        _formula(db_session, org, test_user.id, guarru, 0.41)
        # El dominio tiene DOS mundos Willard y en SAC 2 de los 15 materiales
        # con esta formula son postconsumo: probar solo 'drosses' dejaria pasar
        # un guard escrito como `== "drosses"`.
        ceniza = _mat(db_session, org, "CENIZA", "Ceniza de postconsumo")
        db_session.add(MaterialKgProfile(
            organization_id=org, material_id=ceniza.id, willard_world="postconsumo",
        ))
        _formula(db_session, org, test_user.id, ceniza, 0.50)
        propio = _mat(db_session, org, "DROSS-2", "Dross de crisol 2")
        db_session.add(MaterialKgProfile(
            organization_id=org, material_id=propio.id, willard_world="none",
        ))
        _formula(db_session, org, test_user.id, propio, 0.70)
        sin_perfil = _mat(db_session, org, "DROSS-3", "Dross de crisol 3")
        _formula(db_session, org, test_user.id, sin_perfil, 0.70)
        db_session.commit()
        assert db_session.execute(
            select(func.count()).select_from(MaterialKgProfile).where(
                MaterialKgProfile.material_id == sin_perfil.id
            )
        ).scalar() == 0
        _manual(client, org_headers, acc_intersede.id, 100, stage="crisol")

        tablas = (KgLedgerMovement, InventoryMovement, CrucibleCharge, MoneyMovement,
                  MaterialTransformation)
        before = {t: _count(db_session, t, org) for t in tablas}
        for mat, mundo in ((guarru, "drosses"), (ceniza, "postconsumo")):
            r = client.post(URL, headers=org_headers, json={
                "event_type": "dross_return", "warehouse_id": str(wh_jm.id),
                "material_id": str(mat.id), "quantity_kg": "20", "date": DATE,
            })
            assert r.status_code == 422, r.text
            detail = r.json()["detail"]
            assert mat.code in detail
            assert "Willard" in detail and mundo in detail
            # Nada escrito: ni kg, ni inventario, ni documento, ni par, ni transformacion.
            assert {t: _count(db_session, t, org) for t in tablas} == before

        out = _charge(client, org_headers, wh_jm, propio, 20, event_type="dross_return")
        assert Decimal(str(out["lead_kg"])) == Decimal("14")
        out = _charge(client, org_headers, wh_jm, sin_perfil, 10, event_type="dross_return")
        assert Decimal(str(out["lead_kg"])) == Decimal("7")

    def test_dross_return_snapshot_de_formula(
        self, client, org_headers, db_session, test_organization, test_user,
        wh_jm, acc_intersede, mat_crudo, mat_dross,
    ):
        """T9 — las formulas son append-only: cambiar la vigente DESPUES no
        puede re-presentar un documento ya registrado."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")
        _formula(db_session, test_organization.id, test_user.id, mat_dross, 0.50)

        got = client.get(f"{URL}/{out['id']}", headers=org_headers).json()
        assert Decimal(str(got["lead_kg"])) == Decimal("14")
        listed = client.get(URL, headers=org_headers).json()
        rows = listed["items"] if isinstance(listed, dict) else listed
        assert [Decimal(str(x["lead_kg"])) for x in rows if x["id"] == out["id"]] == [Decimal("14")]
        # y el siguiente documento SI usa la nueva
        nuevo = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")
        assert Decimal(str(nuevo["lead_kg"])) == Decimal("10")

    def test_charge_convierte_inventario_1_a_1(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro,
    ):
        """T10 — Johana (18-sep, L555 + L579): "En el crisol no hay ninguna
        transformación," / "salen 200 de crudo, ingresan 200 de puro". El puro
        entra AL COSTO DEL CRUDO, que es diseño nuestro (el valor se
        conserva; la refinacion se cobra aparte, $300/kg al vender)."""
        _manual(client, org_headers, acc_intersede.id, 500, stage="horno")
        valor_antes = Decimal("1000") * Decimal("2000") + Decimal("500") * Decimal("2500")

        out = _charge(client, org_headers, wh_jm, mat_crudo, 200)

        assert Decimal(str(out["lead_kg"])) == Decimal("200")
        assert out["transformation_id"] and out["transformation_number"] >= 1
        assert out["inventory_out"]["material_code"] == "PB-CRU"
        assert Decimal(str(out["inventory_out"]["quantity"])) == Decimal("200")
        assert out["inventory_in"]["material_code"] == "PB-PUR"
        assert Decimal(str(out["inventory_in"]["quantity"])) == Decimal("200")

        crudo_qty, crudo_avg = _stock(db_session, mat_crudo)
        puro_qty, puro_avg = _stock(db_session, mat_puro)
        assert (crudo_qty, puro_qty) == (Decimal("800"), Decimal("700"))
        assert crudo_avg == Decimal("2000")
        # (500×2.500 + 200×2.000) / 700
        assert abs(puro_avg - Decimal("2357.1429")) < Decimal("0.001")
        assert abs(crudo_qty * crudo_avg + puro_qty * puro_avg - valor_antes) < Decimal("1")

        tr = db_session.get(MaterialTransformation, UUID(out["transformation_id"]))
        assert tr.cost_distribution == "proportional_weight"
        assert (tr.value_difference or Decimal("0")) == 0
        assert tr.waste_quantity == 0 and tr.waste_value == 0
        assert tr.lines[0].unit_cost == Decimal("2000")
        assert "Crisol #" in tr.reason

    def test_dross_return_mueve_inventario_con_merma(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro, mat_dross,
    ):
        """T11 — Johana (18-sep, L649): "Salen 20 del crisol, entran 14 al horno
        grande". Que sean 20 de PURO y 14 de CRUDO lo dijo Daniel (L639) y ella
        respondio "Correcto" (L641). Los 6 kg son merma valorada al promedio del
        puro, que es diseño nuestro."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")

        assert out["inventory_out"]["material_code"] == "PB-PUR"
        assert Decimal(str(out["inventory_out"]["quantity"])) == Decimal("20")
        assert out["inventory_in"]["material_code"] == "PB-CRU"
        assert Decimal(str(out["inventory_in"]["quantity"])) == Decimal("14")
        assert _stock(db_session, mat_puro)[0] == Decimal("480")
        assert _stock(db_session, mat_crudo)[0] == Decimal("1014")
        tr = db_session.get(MaterialTransformation, UUID(out["transformation_id"]))
        assert tr.source_quantity == Decimal("20")
        assert tr.waste_quantity == Decimal("6")
        assert tr.waste_value == Decimal("6") * Decimal("2500")

    def test_anular_documento_revierte_inventario(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro, mat_dross,
    ):
        """T12 — round-trip al origen: cantidad Y valor."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")

        r = client.post(f"{URL}/{out['id']}/annul", headers=org_headers, json={"reason": "error"})
        assert r.status_code == 200, r.text

        crudo_qty, crudo_avg = _stock(db_session, mat_crudo)
        puro_qty, puro_avg = _stock(db_session, mat_puro)
        assert (crudo_qty, puro_qty) == (Decimal("1000"), Decimal("500"))
        assert abs(crudo_avg - Decimal("2000")) < Decimal("0.01")
        assert abs(puro_avg - Decimal("2500")) < Decimal("0.01")
        tr = db_session.get(MaterialTransformation, UUID(out["transformation_id"]))
        assert tr.status == "annulled"
        assert "Crisol #" in (tr.annulled_reason or "")

    def test_transformacion_de_crisol_no_se_anula_directo(
        self, client, org_headers, db_session, test_organization,
        wh_jm, acc_intersede, mat_crudo, mat_puro,
    ):
        """T13 — la transformacion es de un documento de crisol: anularla sola
        dejaria el inventario revertido y la etapa de la deuda movida. 400 que
        NOMBRA el documento (con seis transformaciones en pantalla, "pertenece
        a otro modulo" obliga a adivinar). Contraste: una normal SI se anula —
        sin el, 'el guard funciona' y 'ya nada se anula' se ven identicos."""
        _manual(client, org_headers, acc_intersede.id, 500, stage="horno")
        out = _charge(client, org_headers, wh_jm, mat_crudo, 200)

        r = client.post(
            f"{TR_URL}/{out['transformation_id']}/annul",
            headers=org_headers, json={"reason": "por fuera"},
        )
        assert r.status_code == 400, r.text
        assert f"Crisol #{out['charge_number']}" in r.json()["detail"]
        assert _stock(db_session, mat_puro)[0] == Decimal("700")

        org = test_organization.id
        hierro = _mat(db_session, org, "FE-01", "Hierro", stock="100", cost="500")
        viruta = _mat(db_session, org, "FE-02", "Viruta")
        normal = _transform(client, org_headers, wh_jm, hierro, viruta, 10)
        r = client.post(f"{TR_URL}/{normal['id']}/annul", headers=org_headers, json={"reason": "ok"})
        assert r.status_code == 200, r.text

    def test_guard_de_dueno_aguanta_dos_documentos_con_la_misma_transformacion(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro,
    ):
        """T21 (C3 de QA) — `crucible_charges.transformation_id` NO es UNIQUE. Por
        el flujo de hoy es imposible que dos documentos confirmados enlacen la
        misma transformacion, pero si pasara (un arreglo a mano, un bug futuro)
        `scalar_one_or_none()` responderia 500 y el usuario perderia el mensaje
        que le dice DONDE anular. Se fuerza el caso por ORM: el clon copia todas
        las columnas del original (pasa el CHECK de `lead_kg`) y toma el numero
        siguiente a mano — no usa `next_number()`, que solo vive en `app/`."""
        _manual(client, org_headers, acc_intersede.id, 500, stage="horno")
        out = _charge(client, org_headers, wh_jm, mat_crudo, 200)
        src = db_session.execute(
            select(CrucibleCharge).where(CrucibleCharge.id == UUID(out["id"]))
        ).scalar_one()
        copia = {
            c.key: getattr(src, c.key) for c in CrucibleCharge.__table__.columns
            if c.key not in ("id", "charge_number", "created_at", "updated_at")
        }
        db_session.add(CrucibleCharge(**copia, charge_number=src.charge_number + 1))
        db_session.commit()
        assert db_session.execute(
            select(func.count()).select_from(CrucibleCharge).where(
                CrucibleCharge.transformation_id == src.transformation_id,
                CrucibleCharge.status == "confirmed",
            )
        ).scalar() == 2

        r = client.post(
            f"{TR_URL}/{out['transformation_id']}/annul",
            headers=org_headers, json={"reason": "por fuera"},
        )
        assert r.status_code == 400, r.text
        assert f"Crisol #{out['charge_number']}" in r.json()["detail"]
        assert _stock(db_session, mat_puro)[0] == Decimal("700")

    def test_charge_sin_material_puro_marcado_422(
        self, client, org_headers, db_session, test_organization, wh_jm, acc_intersede,
    ):
        """T14 — el destino lo decide `lead_product`, no un nombre: cero -> 422
        que dice donde marcarlo; dos -> 422 que los lista; explicito -> 201."""
        org = test_organization.id
        crudo = _mat(db_session, org, "PB-CRU", "Plomo Crudo", "crudo", stock="1000", cost="2000")
        _manual(client, org_headers, acc_intersede.id, 500, stage="horno")

        r = _charge(client, org_headers, wh_jm, crudo, 10, expect=422)
        assert "plomo puro" in r["detail"] and "Materiales (kg)" in r["detail"]

        p1 = _mat(db_session, org, "PB-PUR", "Plomo Puro", "puro")
        p2 = _mat(db_session, org, "PB-PU2", "Plomo Puro 99", "puro")
        r = _charge(client, org_headers, wh_jm, crudo, 10, expect=422)
        assert "PB-PUR" in r["detail"] and "PB-PU2" in r["detail"]
        assert "puro_material_id" in r["detail"]

        out = _charge(client, org_headers, wh_jm, crudo, 10, puro_material_id=str(p2.id))
        assert out["inventory_in"]["material_code"] == "PB-PU2"
        assert _stock(db_session, p1)[0] == 0
        _charge(client, org_headers, wh_jm, crudo, 10, expect=422, puro_material_id=str(crudo.id))

    def test_locks_en_orden(
        self, client, org_headers, wh_jm, acc_intersede, mat_crudo, mat_dross, tarifa_maquila,
    ):
        """T15 — el flujo con MAS locks (documento 14 -> movimiento 30 ->
        transformacion 41) corre bajo el helper real: un orden cruzado levanta
        `LockOrderError` y esto seria un 500 (#106 D4)."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, 20, event_type="dross_return")
        assert Decimal(str(out["maquila_amount"])) == Decimal("21000.00")
        assert out["transformation_id"]

    def test_cantidad_fea_cierra_en_todas_las_escalas(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro, mat_dross,
    ):
        """T18 (F1) — el inventario guarda 3 decimales y el libro kg 4: se
        cuantiza UNA vez, antes de calcular. 33,333 × 0,70 = 23,3331 -> 23,333
        en el documento, en el inventario y en el libro."""
        _manual(client, org_headers, acc_intersede.id, 50, stage="crisol")
        out = _charge(client, org_headers, wh_jm, mat_dross, "33.333", event_type="dross_return")

        assert Decimal(str(out["lead_kg"])) == Decimal("23.333")
        inv = _inv_rows(db_session, UUID(out["transformation_id"]))
        entra = sum(m.quantity for m in inv if m.material_id == mat_crudo.id)
        sale = sum(m.quantity for m in inv if m.material_id == mat_puro.id)
        assert entra == Decimal("23.333") == _stock(db_session, mat_crudo)[0] - Decimal("1000")
        assert sale == Decimal("-33.333") == _stock(db_session, mat_puro)[0] - Decimal("500")
        deltas = {r.stage: r.delta_kg for r in _kg_rows(db_session, out["id"])}
        assert deltas == {"crisol": Decimal("-33.333"), "horno": Decimal("23.333")}

        r = _charge(client, org_headers, wh_jm, mat_dross, "0.0004", event_type="dross_return", expect=422)
        assert "0,001" in str(r["detail"])

    def test_anular_charge_con_puro_vendido_avisa_en_la_respuesta(
        self, client, org_headers, db_session, wh_jm, acc_intersede, mat_crudo, mat_puro,
    ):
        """T19 — anular avisa y no bloquea (#76). El aviso se lee del HTTP: un
        warning que se calcula y no viaja se ve identico a funcionar (#100)."""
        _manual(client, org_headers, acc_intersede.id, 500, stage="horno")
        out = _charge(client, org_headers, wh_jm, mat_crudo, 200)
        puro = db_session.get(Material, mat_puro.id)
        puro.current_stock = Decimal("100")            # se vendieron 600 de los 700
        puro.current_stock_liquidated = Decimal("100")
        db_session.commit()

        r = client.post(f"{URL}/{out['id']}/annul", headers=org_headers, json={"reason": "error"})

        assert r.status_code == 200, r.text
        assert r.json()["status"] == "annulled"
        avisos = r.json()["warnings"]
        assert len(avisos) == 1
        assert "PB-PUR" in avisos[0] and "-100" in avisos[0]
        assert _stock(db_session, mat_puro)[0] == Decimal("-100")


class TestGuardConversionDePlomo:
    """#109 D5 — con el crisol moviendo inventario, registrar ADEMAS la
    transformacion manual crudo<->puro lo duplica. El guard va detras de
    `kg_ledger_enabled`; el PAR con/sin flag es la red (#99): sin el contraste
    'el guard funciona' y 'lo prendi para las 7 orgs' se ven identicos."""

    def test_org_sin_flag_transforma_crudo_a_puro(
        self, client, org_headers, db_session, test_organization, wh_jm, mat_crudo, mat_puro,
    ):
        test_organization.settings = {}
        db_session.commit()
        _transform(client, org_headers, wh_jm, mat_crudo, mat_puro, 10, expect=201)

    def test_con_flag_bloquea_y_manda_al_crisol(
        self, client, org_headers, db_session, wh_jm, mat_crudo, mat_puro,
    ):
        r = _transform(client, org_headers, wh_jm, mat_crudo, mat_puro, 10, expect=400)
        assert "Salidas de Plomo → Crisol" in r["detail"]
        assert _stock(db_session, mat_crudo)[0] == Decimal("1000")
        r = _transform(client, org_headers, wh_jm, mat_puro, mat_crudo, 10, expect=400)
        assert "Crisol" in r["detail"]

    def test_con_flag_el_horno_grande_pasa(
        self, client, org_headers, db_session, test_organization, wh_jm, mat_crudo,
    ):
        """Bateria/scrap -> crudo es el horno grande: NO es del crisol y sigue
        siendo una transformacion manual (recetas = T1, pendiente)."""
        scrap = _mat(db_session, test_organization.id, "SCRAP-01", "Scrap de plomo",
                     stock="100", cost="800")
        _transform(client, org_headers, wh_jm, scrap, mat_crudo, 10, expect=201)
