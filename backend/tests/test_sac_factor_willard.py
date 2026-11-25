"""
Factor de Willard elegible al liquidar (plan-sac-factor-willard.md v1.3).

SCRAP SECO GRANDE es UN material y UNA cuenta con Willard; Willard lo parte
en seco pinza (59 %) y seco escurrido (56 %). La lista vive DENTRO de la
formula vigente (D1): `lead_percentage` es el defecto, y es lo unico que leen
traslado, Salidas, crisol y las pantallas. Se escoge al confirmar (D3), queda
en la linea, el snapshot lo dice (D4), la edicion D18 lo conserva (D5) y un
factor mal escogido se corrige anulando y registrando de nuevo (D6, sin
codigo nuevo: T8 lo mide con el camino que ya existe).
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.inbound_order import InboundOrder, InboundOrderLine
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.material_conversion_formula import MaterialConversionFormula
from app.services.inbound_order import WORLD_LABELS
from app.utils.dates import business_today
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import create_warehouse
from tests.test_inbound_orders import (
    FORMULAS_URL,
    INBOUND_URL,
    KG_URL,
    PNL_URL,
    _decrease,
    _inbound,
    _kg_movs,
    _mat,
    _post_formula,
    _seed_avg,
    _set_profile,
)

FACTORES = {
    "lead_percentage": 0.59,
    "label": "Seco pinza",
    "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56}],
}


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def warehouse(db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
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
def cuenta(client, org_headers, warehouse, willard_tp):
    resp = client.post(
        f"{KG_URL}/accounts", headers=org_headers,
        json={
            "code": "WILLARD-BAT-CV", "display_name": "Willard Baterias CV",
            "account_type": "willard_baterias", "warehouse_id": str(warehouse.id),
            "third_party_id": str(willard_tp.id),
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def scr(db_session, test_organization, client, org_headers):
    """SCR-SG: kg, postconsumo, compra regular (como el seeder), con factores."""
    mat = _mat(db_session, test_organization.id, "SCR-SG", unit="kg")
    _post_formula(client, org_headers, mat.id, "drosses_to_lead", FACTORES)
    _set_profile(client, org_headers, mat.id, compra_regular=True, willard_world="postconsumo")
    return mat


@pytest.fixture
def lsb(db_session, test_organization, client, org_headers):
    """SCR-LSB: kg, postconsumo, formula SIN alternativas (la de siempre)."""
    mat = _mat(db_session, test_organization.id, "SCR-LSB", unit="kg")
    _post_formula(client, org_headers, mat.id, "drosses_to_lead", {"lead_percentage": 0.5})
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


@pytest.fixture
def bat(db_session, test_organization, client, org_headers):
    mat = _mat(db_session, test_organization.id, "BAT-G1", unit="unidad")
    _post_formula(client, org_headers, mat.id, "battery_to_lead", {"kg_lead_per_unit": 2.5})
    _set_profile(client, org_headers, mat.id, willard_world="postconsumo")
    return mat


def _willard(client, headers, warehouse, willard_tp, lines, *, fecha=None, remision=None):
    """Captura + revision: la Willard queda lista para liquidar (confirm)."""
    extra = {"remission_number": remision} if remision else {}
    resp = _inbound(
        client, headers, inbound_type="willard", warehouse_id=warehouse.id,
        third_party_id=willard_tp.id, lines=lines,
        date_str=(fecha or business_today()).isoformat(), **extra,
    )
    assert resp.status_code == 201, resp.text
    oid = resp.json()["id"]
    rev = client.post(f"{INBOUND_URL}/{oid}/review", headers=headers)
    assert rev.status_code == 200, rev.text
    return oid


def _liquidar(client, headers, oid, opciones=None, expect=200):
    kwargs = {}
    if opciones is not None:
        kwargs["json"] = {"conversion_options": [
            {"material_id": str(m), "option": o} for m, o in opciones
        ]}
    resp = client.post(f"{INBOUND_URL}/{oid}/confirm", headers=headers, **kwargs)
    assert resp.status_code == expect, resp.text
    return resp.json()


def _linea(detalle, material):
    return next(l for l in detalle["lines"] if l["material_id"] == str(material.id))


def _vivos(db, oid):
    return [m for m in _kg_movs(db, oid) if m.status == "confirmed"]


def _saldo(client, headers, cuenta_id):
    accounts = client.get(f"{KG_URL}/accounts", headers=headers).json()
    return Decimal(next(a for a in accounts if a["id"] == cuenta_id)["current_balance_kg"])


def _pool(db, material):
    db.expire_all()
    m = db.get(Material, material.id)
    return m.current_stock_liquidated, m.current_average_cost


def _sin_efectos(db, oid):
    """Nada escrito: sigue revisada, cero kg y cero inventario de la orden."""
    db.expire_all()
    order = db.get(InboundOrder, oid)
    assert order.status == "reviewed"
    assert _kg_movs(db, oid) == []
    movs = db.execute(
        select(InventoryMovement).where(InventoryMovement.reference_id == oid)
    ).scalars().all()
    assert movs == []


# ---------------------------------------------------------------------------
# T1 — schema de D1 (+ O2: numeros anidados como numero JSON)
# ---------------------------------------------------------------------------

class TestSchemaFactores:
    def test_t1_valido_y_numeros_json(self, client, org_headers, db_session, scr):
        vigente = client.get(
            f"{FORMULAS_URL}/current", headers=org_headers,
            params={"material_id": str(scr.id)},
        ).json()["items"][0]
        assert vigente["parameters"] == FACTORES
        fila = db_session.get(MaterialConversionFormula, vigente["id"])
        alt = fila.parameters["alternatives"][0]
        assert isinstance(alt["lead_percentage"], float)  # O2: no Decimal/str
        assert isinstance(fila.parameters["lead_percentage"], float)

    @pytest.mark.parametrize("params", [
        # sin nombre del defecto
        {"lead_percentage": 0.59, "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56}]},
        # nombre repetido (normalizado: mayusculas y tildes)
        {"lead_percentage": 0.59, "label": "Seco pinza",
         "alternatives": [{"label": "SECO PINZÁ", "lead_percentage": 0.56}]},
        # porcentaje fuera de rango
        {"lead_percentage": 0.59, "label": "Seco pinza",
         "alternatives": [{"label": "Seco escurrido", "lead_percentage": 1.5}]},
        # igual al defecto
        {"lead_percentage": 0.59, "label": "Seco pinza",
         "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.59}]},
        # lista vacia
        {"lead_percentage": 0.59, "label": "Seco pinza", "alternatives": []},
        # mas de 5
        {"lead_percentage": 0.59, "label": "Seco pinza",
         "alternatives": [{"label": f"F{i}", "lead_percentage": 0.4 + i / 100} for i in range(6)]},
        # clave desconocida
        {"lead_percentage": 0.59, "label": "Seco pinza",
         "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56, "x": 1}]},
    ])
    def test_t1_invalidos_422(self, client, org_headers, scr, params):
        resp = client.post(
            FORMULAS_URL, headers=org_headers,
            json={"material_id": str(scr.id), "formula_type": "drosses_to_lead", "parameters": params},
        )
        assert resp.status_code == 422, resp.text

    def test_t1_baterias_no_tienen_alternativas(self, client, org_headers, bat):
        resp = client.post(
            FORMULAS_URL, headers=org_headers,
            json={"material_id": str(bat.id), "formula_type": "battery_to_lead",
                  "parameters": {"kg_lead_per_unit": 2.5, "label": "X",
                                 "alternatives": [{"label": "Y", "lead_percentage": 0.5}]}},
        )
        assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# T9 — D2: ningun escritor borra la lista sin querer
# ---------------------------------------------------------------------------

class TestCopiaDeLaLista:
    def _vigente(self, client, headers, mat):
        return client.get(
            f"{FORMULAS_URL}/current", headers=headers, params={"material_id": str(mat.id)},
        ).json()["items"][0]["parameters"]

    def test_t9_ausente_copia_de_la_vigente(self, client, org_headers, scr):
        # Lo que manda FormulasPage o el seeder: solo el porcentaje
        _post_formula(client, org_headers, scr.id, "drosses_to_lead", {"lead_percentage": 0.6})
        assert self._vigente(client, org_headers, scr) == {
            "lead_percentage": 0.6, "label": "Seco pinza",
            "alternatives": [{"label": "Seco escurrido", "lead_percentage": 0.56}],
        }

    def test_t9_null_explicito_quita(self, client, org_headers, scr):
        _post_formula(client, org_headers, scr.id, "drosses_to_lead",
                      {"lead_percentage": 0.59, "label": None, "alternatives": None})
        assert self._vigente(client, org_headers, scr) == {"lead_percentage": 0.59}

    def test_t9_copia_que_choca_422(self, client, org_headers, scr):
        # El defecto nuevo es igual a la alternativa que se copiaria
        resp = client.post(
            FORMULAS_URL, headers=org_headers,
            json={"material_id": str(scr.id), "formula_type": "drosses_to_lead",
                  "parameters": {"lead_percentage": 0.56}},
        )
        assert resp.status_code == 422, resp.text
        assert "Edite la lista" in resp.json()["detail"]
        assert self._vigente(client, org_headers, scr) == FACTORES


# ---------------------------------------------------------------------------
# T2–T5c — escoger al liquidar
# ---------------------------------------------------------------------------

class TestEscogerAlLiquidar:
    def test_t2_sin_alternativas_byte_a_byte(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, lsb,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(lsb.id), "quantity": "1000"}])
        out = _liquidar(client, org_headers, oid)  # SIN cuerpo
        (mov,) = _vivos(db_session, oid)
        formula = db_session.execute(
            select(MaterialConversionFormula).where(MaterialConversionFormula.material_id == lsb.id)
        ).scalar_one()
        assert mov.delta_kg == Decimal("500.0000")
        assert mov.conversion_formula_snapshot == {
            "formula_id": str(formula.id),
            "formula_type": "drosses_to_lead",
            "parameters": {"lead_percentage": 0.5},
        }
        assert mov.description == (
            f"Recepcion {WORLD_LABELS['postconsumo']} #{out["order_number"]} — SCR-LSB x 1000.0000 kg"
        )
        linea = _linea(out, lsb)
        assert linea["conversion_option"] is None
        assert Decimal(linea["lead_percentage_applied"]) == Decimal("0.5")
        assert linea["lead_factor_label_applied"] is None  # sin alternativas, sin nombre

    def test_t3_escurrido(self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        (mov,) = _vivos(db_session, oid)
        assert mov.delta_kg == Decimal("560.0000")
        assert mov.conversion_formula_snapshot["applied"] == {
            "label": "Seco escurrido", "lead_percentage": 0.56,
        }
        assert mov.conversion_formula_snapshot["parameters"] == FACTORES
        # Por HTTP: el detalle y el estado de cuenta kg
        detalle = client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json()
        linea = _linea(detalle, scr)
        assert linea["conversion_option"] == "Seco escurrido"
        assert Decimal(linea["lead_percentage_applied"]) == Decimal("0.56")
        assert linea["lead_factor_label_applied"] == "Seco escurrido"  # O1: del snapshot
        assert Decimal(linea["kg_lead"]) == Decimal("560")
        estado = client.get(
            f"{KG_URL}/accounts/{cuenta['id']}/movements", headers=org_headers,
        ).json()
        assert estado["movements"][-1]["description"].endswith("· Seco escurrido 56 %")
        assert _saldo(client, org_headers, cuenta["id"]) == Decimal("560")

    def test_t4_con_alternativas_sin_elegir_es_el_defecto(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        out = _liquidar(client, org_headers, oid)
        (mov,) = _vivos(db_session, oid)
        assert mov.delta_kg == Decimal("590.0000")
        assert mov.conversion_formula_snapshot["applied"] == {
            "label": "Seco pinza", "lead_percentage": 0.59,
        }
        assert mov.description.endswith("· Seco pinza 59 %")
        assert _linea(out, scr)["conversion_option"] is None
        assert _linea(out, scr)["lead_factor_label_applied"] == "Seco pinza"

    @pytest.mark.parametrize("caso", [
        "sin_alternativas", "desconocida", "no_esta", "repetido", "bateria",
    ])
    def test_t5_422_sin_escribir_nada(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta,
        scr, lsb, bat, caso,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp, [
            {"material_id": str(scr.id), "quantity": "1000"},
            {"material_id": str(lsb.id), "quantity": "200"},
            {"material_id": str(bat.id), "quantity": "10", "scale_weight_kg": "150"},
        ])
        otro = _mat(db_session, scr.organization_id, "OTRO", unit="kg")
        opciones = {
            "sin_alternativas": [(lsb.id, "Seco escurrido")],
            "desconocida": [(scr.id, "Seco mojado")],
            "no_esta": [(otro.id, "Seco escurrido")],
            "repetido": [(scr.id, "Seco escurrido"), (scr.id, "Seco pinza")],
            "bateria": [(bat.id, "Seco escurrido")],
        }[caso]
        resp = client.post(
            f"{INBOUND_URL}/{oid}/confirm", headers=org_headers,
            json={"conversion_options": [{"material_id": str(m), "option": o} for m, o in opciones]},
        )
        assert resp.status_code == 422, resp.text
        if caso == "desconocida":
            assert "Seco pinza, Seco escurrido" in resp.json()["detail"]
        _sin_efectos(db_session, oid)
        assert _saldo(client, org_headers, cuenta["id"]) == 0

    def test_t5b_que_se_guarda(self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr, lsb):
        # El defecto escogido por su nombre (escrito distinto) guarda NULL
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        out = _liquidar(client, org_headers, oid, [(scr.id, "SECO PINZA")])
        assert _linea(out, scr)["conversion_option"] is None
        assert _vivos(db_session, oid)[0].delta_kg == Decimal("590.0000")
        # Una alternativa escrita distinto guarda el nombre canonico
        oid2 = _willard(client, org_headers, warehouse, willard_tp,
                        [{"material_id": str(scr.id), "quantity": "1000"}])
        out2 = _liquidar(client, org_headers, oid2, [(scr.id, "seco ESCURRIDO")])
        assert _linea(out2, scr)["conversion_option"] == "Seco escurrido"
        assert _vivos(db_session, oid2)[0].delta_kg == Decimal("560.0000")
        db_session.expire_all()
        guardado = db_session.execute(
            select(InboundOrderLine.conversion_option).where(InboundOrderLine.inbound_order_id == oid2)
        ).scalar_one()
        assert guardado == "Seco escurrido"

    def test_t5c_listado_y_anulada(
        self, client, org_headers, warehouse, willard_tp, cuenta, scr,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        listado = client.get(INBOUND_URL, headers=org_headers).json()["items"]
        item = next(o for o in listado if o["id"] == oid)
        assert Decimal(_linea(item, scr)["lead_percentage_applied"]) == Decimal("0.56")
        resp = client.post(f"{INBOUND_URL}/{oid}/annul", headers=org_headers,
                           json={"reason": "Prueba de anulada"})
        assert resp.status_code == 200, resp.text
        linea = _linea(client.get(f"{INBOUND_URL}/{oid}", headers=org_headers).json(), scr)
        assert linea["lead_percentage_applied"] is None  # todo su kg esta anulado
        assert linea["lead_factor_label_applied"] is None
        assert linea["conversion_option"] == "Seco escurrido"


# ---------------------------------------------------------------------------
# T6–T7 — D5: la edicion D18 conserva el factor
# ---------------------------------------------------------------------------

class TestEdicionConserva:
    def test_t6_cambia_cantidad_conserva_escurrido(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        resp = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"lines": [{"material_id": str(scr.id), "quantity": "800"}]},
        )
        assert resp.status_code == 200, resp.text
        assert _linea(resp.json(), scr)["conversion_option"] == "Seco escurrido"
        (mov,) = _vivos(db_session, oid)
        assert mov.delta_kg == Decimal("448.0000")  # 800 x 0,56
        assert _saldo(client, org_headers, cuenta["id"]) == Decimal("448")

    def test_t6_solo_la_fecha_conserva_escurrido(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        # O3 de QA 1: D18 re-aplica tambien cuando cambia SOLO la fecha
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        fecha = business_today() - timedelta(days=3)
        resp = client.patch(f"{INBOUND_URL}/{oid}", headers=org_headers,
                            json={"date": fecha.isoformat()})
        assert resp.status_code == 200, resp.text
        linea = _linea(resp.json(), scr)
        assert linea["conversion_option"] == "Seco escurrido"
        assert linea["lead_factor_label_applied"] == "Seco escurrido"
        (mov,) = _vivos(db_session, oid)
        assert mov.delta_kg == Decimal("560.0000")
        assert mov.transaction_date.date() == fecha  # si re-aplico, con la fecha nueva
        assert _saldo(client, org_headers, cuenta["id"]) == Decimal("560")

    def test_t6_material_nuevo_entra_con_el_defecto(
        self, client, org_headers, db_session, test_organization, warehouse, willard_tp, cuenta, scr,
    ):
        # O3 de QA 1: el material que entra en la edicion no tiene opcion
        # guardada; con alternativas, toma el defecto (Seco pinza 59 %)
        otro = _mat(db_session, test_organization.id, "SCR-SG2", unit="kg")
        _post_formula(client, org_headers, otro.id, "drosses_to_lead", FACTORES)
        _set_profile(client, org_headers, otro.id, compra_regular=True, willard_world="postconsumo")
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        resp = client.patch(f"{INBOUND_URL}/{oid}", headers=org_headers, json={"lines": [
            {"material_id": str(scr.id), "quantity": "1000"},
            {"material_id": str(otro.id), "quantity": "500"},
        ]})
        assert resp.status_code == 200, resp.text
        assert _linea(resp.json(), scr)["conversion_option"] == "Seco escurrido"
        nueva = _linea(resp.json(), otro)
        assert nueva["conversion_option"] is None
        assert nueva["lead_factor_label_applied"] == "Seco pinza"
        assert sorted(m.delta_kg for m in _vivos(db_session, oid)) == [
            Decimal("295.0000"), Decimal("560.0000"),  # 500 x 0,59 y 1000 x 0,56
        ]
        assert _saldo(client, org_headers, cuenta["id"]) == Decimal("855")

    def test_t6_el_patch_no_acepta_el_campo(
        self, client, org_headers, warehouse, willard_tp, cuenta, scr,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        resp = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"lines": [{"material_id": str(scr.id), "quantity": "800",
                             "conversion_option": "Seco pinza"}]},
        )
        assert resp.status_code == 422, resp.text

    def test_t7_opcion_desaparecida_422_sin_cambios(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        oid = _willard(client, org_headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}])
        _liquidar(client, org_headers, oid, [(scr.id, "Seco escurrido")])
        _post_formula(client, org_headers, scr.id, "drosses_to_lead",
                      {"lead_percentage": 0.59, "label": None, "alternatives": None})
        stock_antes = _pool(db_session, scr)
        resp = client.patch(
            f"{INBOUND_URL}/{oid}", headers=org_headers,
            json={"lines": [{"material_id": str(scr.id), "quantity": "800"}]},
        )
        assert resp.status_code == 422, resp.text
        assert "ya no esta en la lista" in resp.json()["detail"]
        movs = _kg_movs(db_session, oid)
        assert [(m.status, m.delta_kg) for m in movs] == [("confirmed", Decimal("560.0000"))]
        assert _pool(db_session, scr) == stock_antes


# ---------------------------------------------------------------------------
# T8 — D6: anular y registrar de nuevo (el camino que ya existe), con valores
# ---------------------------------------------------------------------------

class TestAnularYRegistrarDeNuevo:
    """Liquidada con escurrido por error -> anular -> registrar de nuevo con la
    misma remision y la fecha original -> liquidar con pinza. Valores a mano."""

    def _corregir(self, client, headers, db, warehouse, willard_tp, scr, oid, fecha):
        resp = client.post(f"{INBOUND_URL}/{oid}/annul", headers=headers,
                           json={"reason": "Factor mal escogido"})
        assert resp.status_code == 200, resp.text
        nueva = _willard(client, headers, warehouse, willard_tp,
                         [{"material_id": str(scr.id), "quantity": "1000"}],
                         fecha=fecha, remision="16272")
        out = _liquidar(client, headers, nueva)  # pinza = el defecto
        return nueva, out

    def _comun(self, client, headers, db, cuenta, oid, nueva, out, fecha):
        (mov,) = _vivos(db, nueva)
        assert mov.delta_kg == Decimal("590.0000")
        assert mov.transaction_date.date() == fecha
        assert all(m.status == "annulled" for m in _kg_movs(db, oid))
        assert _saldo(client, headers, cuenta["id"]) == Decimal("590")
        # La remision queda dos veces: una anulada y una viva, con otro numero
        lista = client.get(INBOUND_URL, headers=headers, params={"search": "16272"}).json()["items"]
        assert sorted(o["status"] for o in lista) == ["annulled", "confirmed"]
        assert len({o["order_number"] for o in lista}) == 2

    def _primera(self, client, headers, warehouse, willard_tp, scr):
        fecha = business_today() - timedelta(days=5)
        oid = _willard(client, headers, warehouse, willard_tp,
                       [{"material_id": str(scr.id), "quantity": "1000"}],
                       fecha=fecha, remision="16272")
        _liquidar(client, headers, oid, [(scr.id, "Seco escurrido")])
        return oid, fecha

    def test_t8a_nada_entre_medio(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        _seed_avg(client, org_headers, scr.id, warehouse.id, 1000, 2000)  # 1000 @ 2000
        oid, fecha = self._primera(client, org_headers, warehouse, willard_tp, scr)
        assert _pool(db_session, scr) == (Decimal("2000"), Decimal("2000.0000"))  # 4.000.000
        nueva, out = self._corregir(client, org_headers, db_session, warehouse, willard_tp, scr, oid, fecha)
        stock, avg = _pool(db_session, scr)
        assert (stock, avg) == (Decimal("2000"), Decimal("2000.0000"))
        assert stock * avg == Decimal("4000000")  # el valor no cambia
        self._comun(client, org_headers, db_session, cuenta, oid, nueva, out, fecha)

    def test_t8b_compra_a_otro_precio_entre_medio(
        self, client, org_headers, db_session, test_organization, warehouse, willard_tp, cuenta, scr,
    ):
        _seed_avg(client, org_headers, scr.id, warehouse.id, 1000, 2000)  # 1000 @ 2000
        oid, fecha = self._primera(client, org_headers, warehouse, willard_tp, scr)
        # 2000 @ 2000. Se liquida una compra de 2000 kg a 3500:
        # (4.000.000 + 7.000.000) / 4000 = 2750
        proveedor = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Seco", "material_supplier"
        )
        db_session.commit()
        resp = client.post("/api/v1/purchases", headers=org_headers, json={
            "supplier_id": str(proveedor.id), "date": business_today().isoformat(),
            "auto_liquidate": True,
            "lines": [{"material_id": str(scr.id), "quantity": 2000, "unit_price": 3500,
                       "warehouse_id": str(warehouse.id)}],
        })
        assert resp.status_code == 201, resp.text
        stock, avg = _pool(db_session, scr)
        assert (stock, avg) == (Decimal("4000"), Decimal("2750.0000"))
        assert stock * avg == Decimal("11000000")
        nueva, out = self._corregir(client, org_headers, db_session, warehouse, willard_tp, scr, oid, fecha)
        # Anular saca 1000 a 2000 (line.unit_cost): 9.000.000 / 3000 = 3000.
        # La nueva entra al promedio de ESE dia (3000, identidad D2): 4000 @ 3000
        stock, avg = _pool(db_session, scr)
        assert (stock, avg) == (Decimal("4000"), Decimal("3000.0000"))
        assert stock * avg == Decimal("12000000")  # +1.000.000: el valor SI cambia
        self._comun(client, org_headers, db_session, cuenta, oid, nueva, out, fecha)

    def test_t8c_pool_negativo_al_anular(
        self, client, org_headers, db_session, warehouse, willard_tp, cuenta, scr,
    ):
        _seed_avg(client, org_headers, scr.id, warehouse.id, 1000, 2000)  # 1000 @ 2000
        oid, fecha = self._primera(client, org_headers, warehouse, willard_tp, scr)  # 2000 @ 2000
        _seed_avg(client, org_headers, scr.id, warehouse.id, 2000, 500)  # 4000 @ 1250
        _decrease(client, org_headers, scr.id, warehouse.id, 5000)  # -1000 @ 1250
        assert _pool(db_session, scr) == (Decimal("-1000"), Decimal("1250.0000"))
        pnl = {"date_from": "2020-01-01", "date_to": "2030-01-01"}
        antes = client.get(PNL_URL, headers=org_headers, params=pnl).json()["oversell_cost_adjustment"]
        nueva, out = self._corregir(client, org_headers, db_session, warehouse, willard_tp, scr, oid, fecha)
        # Anular: remocion a hueco (rama 3), el avg queda en 1250 y
        # adj = 1000 x (2000 - 1250) = 750.000 -> annul_cost_adjustment, 8a fuente
        db_session.expire_all()
        assert db_session.get(InboundOrder, oid).annul_cost_adjustment == Decimal("750000.00")
        despues = client.get(PNL_URL, headers=org_headers, params=pnl).json()["oversell_cost_adjustment"]
        assert despues - antes == pytest.approx(750000.0, abs=0.01)
        # La nueva entra a identidad sobre el hueco: -1000 @ 1250
        assert _pool(db_session, scr) == (Decimal("-1000"), Decimal("1250.0000"))
        self._comun(client, org_headers, db_session, cuenta, oid, nueva, out, fecha)


# ---------------------------------------------------------------------------
# T10 — los demas lectores siguen leyendo el defecto
# ---------------------------------------------------------------------------

class TestOtrosLectoresVenElDefecto:
    def test_t10_traslado_salidas_y_crisol_usan_lead_percentage(
        self, db_session, test_organization, scr,
    ):
        """O4 de QA 1: prueba los HELPERS de conversion de los tres lectores
        (con una formula que SI tiene la lista), no sus flujos HTTP. Lo que
        sostiene es que cada uno lee `lead_percentage` y nunca la lista."""
        from app.services.crucible_charge import crucible_charge_service
        from app.services.transfer import TransferService
        from app.services.willard_delivery import WillardDeliveryService

        formula = db_session.execute(
            select(MaterialConversionFormula).where(MaterialConversionFormula.material_id == scr.id)
        ).scalar_one()
        assert formula.parameters["alternatives"]  # la formula SI tiene la lista
        snapshot = {"formula_type": formula.formula_type, "parameters": formula.parameters}
        qty = Decimal("1000")
        assert TransferService._kg_from_snapshot(snapshot, qty) == Decimal("590.0000")
        assert WillardDeliveryService._kg_from_formula(formula, qty) == Decimal("590.0000")
        lead_kg, _ = crucible_charge_service._dross_lead_kg(
            db_session, db_session.get(Material, scr.id), qty, test_organization.id,
        )
        assert lead_kg == Decimal("590.000")


# ---------------------------------------------------------------------------
# T11 — el cuerpo de confirm no cambia el permiso
# ---------------------------------------------------------------------------

@pytest.fixture
def solo_ver_headers(client, db_session, test_organization):
    """Rol con purchases.view y SIN purchases.liquidate (el admin bypassa, #29)."""
    from app.core.security import create_access_token, get_password_hash
    from app.models.permission import Permission
    from app.models.role import Role, RolePermission
    from app.models.user import OrganizationMember, User

    user = User(email="solo-ver-entradas@example.com", hashed_password=get_password_hash("pass1234"),
                full_name="Solo Ver", is_active=True)
    db_session.add(user)
    db_session.flush()
    role = Role(organization_id=test_organization.id, name="solo_ver_entradas_test",
                display_name="Solo ver entradas", is_system_role=False)
    db_session.add(role)
    db_session.flush()
    (perm,) = db_session.execute(
        select(Permission).where(Permission.code == "purchases.view")
    ).scalars().all()
    db_session.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db_session.add(OrganizationMember(user_id=user.id, organization_id=test_organization.id, role_id=role.id))
    db_session.commit()
    return {
        "Authorization": f"Bearer {create_access_token(data={'sub': str(user.id)})}",
        "X-Organization-ID": str(test_organization.id),
    }


def test_t11_confirm_con_cuerpo_exige_liquidate(
    client, org_headers, solo_ver_headers, db_session, warehouse, willard_tp, cuenta, scr,
):
    oid = _willard(client, org_headers, warehouse, willard_tp,
                   [{"material_id": str(scr.id), "quantity": "1000"}])
    # Control positivo: el mismo usuario LEE la Entrada
    assert client.get(f"{INBOUND_URL}/{oid}", headers=solo_ver_headers).status_code == 200
    resp = client.post(
        f"{INBOUND_URL}/{oid}/confirm", headers=solo_ver_headers,
        json={"conversion_options": [{"material_id": str(scr.id), "option": "Seco escurrido"}]},
    )
    assert resp.status_code == 403, resp.text
    _sin_efectos(db_session, oid)
