"""
Tests de la columna Remision en Entradas (plan-sac-entradas-columna-remision.md v1.2).

Johana (17-nov, por Daniel) llena la remision y quiere filtrar, ordenar e
identificar por ella. El dato ya venia en el listado y el buscador ya la
encontraba (#93 D12); lo nuevo es ORDENAR TODA LA LISTA por remision en el
servidor: `sort=remission_asc|remission_desc`.

Orden natural (D2), con r = NULLIF(TRIM(remission_number), ''):
  1. vacia al final, en los dos sentidos;
  2. valor numerico (solo si r es solo digitos), NULLS explicitos;
  3. texto: lower(r) COLLATE "C" — independiente de la collation del server;
  4. desempate: order_number DESC (unico por org -> paginacion estable).

Cada test crea las entradas en un orden DISTINTO al esperado: si el endpoint
ignorara el sort y cayera a `newest` (order_number DESC), el test lo veria
(P5 de la matriz). Las asserciones leen el LISTADO por HTTP, que es lo que
pinta la pantalla.
"""
from datetime import timedelta

import pytest

from app.utils.dates import business_today
from tests.integration_helpers import create_material, create_material_category, create_warehouse

INBOUND_URL = "/api/v1/inbound-orders"
PROFILES_URL = "/api/v1/material-kg-profiles"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def wh(db_session, test_organization):
    w = create_warehouse(db_session, test_organization.id, "Circunvalar Rem")
    db_session.commit()
    return w


@pytest.fixture
def mat(db_session, test_organization, client, org_headers):
    cat = create_material_category(db_session, test_organization.id, "Cat REM")
    m = create_material(db_session, test_organization.id, "CHAT-REM", "Chatarra Rem", cat.id)
    m.default_unit = "kg"
    db_session.commit()
    resp = client.put(
        f"{PROFILES_URL}/{m.id}", headers=org_headers,
        json={"compra_regular": True, "willard_world": "none", "lead_product": "none"},
    )
    assert resp.status_code == 200, resp.text
    return m


def _fecha():
    return (business_today() - timedelta(days=2)).isoformat()


def _entrada(client, headers, wh, mat, remision):
    """Entrada tipo compra (#93: sin proveedor al capturar) con la remision dada.
    `remision=None` = sin remision; se manda tal cual (el schema no hace strip)."""
    body = {
        "inbound_type": "purchase",
        "warehouse_id": str(wh.id),
        "date": _fecha(),
        "lines": [{"material_id": str(mat.id), "quantity": "100", "scale_weight_kg": "100"}],
    }
    if remision is not None:
        body["remission_number"] = remision
    resp = client.post(INBOUND_URL, headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _listado(client, headers, **params):
    resp = client.get(INBOUND_URL, headers=headers, params={"limit": 100, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ids(items):
    return [it["id"] for it in items]


# Orden de creacion DESORDENADO a proposito (ni el esperado ni su inverso).
SET_T2 = ["100", "B-2", "9", None, "A-1", "0012", "  ", "10"]
ASC_T2 = ["9", "10", "0012", "100", "A-1", "B-2"]


@pytest.fixture
def set_t2(client, org_headers, wh, mat):
    creadas = [_entrada(client, org_headers, wh, mat, r) for r in SET_T2]
    por_rem = {c["remission_number"]: c for c in creadas if c["remission_number"] not in (None, "  ")}
    vacias = sorted(
        (c for c in creadas if c["remission_number"] in (None, "  ")),
        key=lambda c: c["order_number"], reverse=True,
    )
    return creadas, por_rem, vacias


class TestListadoTraeLaRemision:
    def test_t1_el_listado_trae_la_remision_y_el_orden_de_siempre(self, client, org_headers, wh, mat):
        a = _entrada(client, org_headers, wh, mat, "R-1")
        b = _entrada(client, org_headers, wh, mat, None)

        body = _listado(client, org_headers)

        assert _ids(body["items"]) == [b["id"], a["id"]]  # newest = order_number DESC
        rem = {it["id"]: it["remission_number"] for it in body["items"]}
        assert rem == {a["id"]: "R-1", b["id"]: None}


class TestOrdenPorRemision:
    def test_t2_asc_orden_natural_y_vacias_al_final(self, client, org_headers, set_t2):
        _, por_rem, vacias = set_t2
        body = _listado(client, org_headers, sort="remission_asc")
        esperado = [por_rem[r]["id"] for r in ASC_T2] + [v["id"] for v in vacias]
        assert _ids(body["items"]) == esperado

    def test_t3_desc_invierte_el_valor_pero_no_las_vacias(self, client, org_headers, set_t2):
        _, por_rem, vacias = set_t2
        body = _listado(client, org_headers, sort="remission_desc")
        esperado = [por_rem[r]["id"] for r in reversed(ASC_T2)] + [v["id"] for v in vacias]
        assert _ids(body["items"]) == esperado

    def test_t4_la_paginacion_no_repite_ni_salta(self, client, org_headers, set_t2):
        completa = _listado(client, org_headers, sort="remission_asc")
        assert completa["total"] == len(SET_T2)
        paginas = []
        for skip in range(0, len(SET_T2), 3):
            pag = _listado(client, org_headers, sort="remission_asc", skip=skip, limit=3)
            assert pag["total"] == len(SET_T2)
            paginas.extend(_ids(pag["items"]))
        assert paginas == _ids(completa["items"])
        assert len(set(paginas)) == len(SET_T2)

    def test_t5_misma_remision_desempata_por_numero_desc(self, client, org_headers, wh, mat):
        """N5 + correccion de QA a la v1.1: tres «R-7» creadas en orden
        ascendente y una «R-9» creada AL FINAL. Por remision asc la «R-9» va
        ultima; `newest` la pondria primera — eso es lo que discrimina P5."""
        r7 = [_entrada(client, org_headers, wh, mat, "R-7") for _ in range(3)]
        r9 = _entrada(client, org_headers, wh, mat, "R-9")
        r7_desc = [o["id"] for o in sorted(r7, key=lambda o: o["order_number"], reverse=True)]

        asc = _listado(client, org_headers, sort="remission_asc")
        desc = _listado(client, org_headers, sort="remission_desc")

        assert _ids(asc["items"]) == r7_desc + [r9["id"]]
        assert _ids(desc["items"]) == [r9["id"]] + r7_desc

    def test_t6_ordena_y_filtra_a_la_vez(self, client, org_headers, wh, mat):
        c = _entrada(client, org_headers, wh, mat, "R-30")
        _entrada(client, org_headers, wh, mat, "X-1")
        a = _entrada(client, org_headers, wh, mat, "R-4")
        b = _entrada(client, org_headers, wh, mat, "R-20")
        for o in (a, b, c):
            rev = client.post(f"{INBOUND_URL}/{o['id']}/review", headers=org_headers)
            assert rev.status_code == 200, rev.text
        _entrada(client, org_headers, wh, mat, "R-1")  # registrada: el filtro la saca

        revisadas = _listado(client, org_headers, sort="remission_asc", display_status="reviewed")
        # «R-4», «R-20», «R-30» son TEXTO (no solo digitos): r-20 < r-30 < r-4
        assert _ids(revisadas["items"]) == [b["id"], c["id"], a["id"]]

        buscadas = _listado(client, org_headers, sort="remission_desc", search="R-")
        assert [it["remission_number"] for it in buscadas["items"]] == ["R-4", "R-30", "R-20", "R-1"]

    def test_t7_sort_desconocido_da_422(self, client, org_headers):
        resp = client.get(INBOUND_URL, headers=org_headers, params={"sort": "remission"})
        assert resp.status_code == 422, resp.text

    def test_t8_el_texto_no_se_ordena_por_bytes_de_mayusculas(self, client, org_headers, wh, mat):
        """C3: por bytes, «B» (0x42) va antes que «a» (0x61). Con lower() la
        «a-2» va primero. Se crean en ese orden para que `newest` dé «B-1»
        primero y no coincida con lo esperado (P5)."""
        a2 = _entrada(client, org_headers, wh, mat, "a-2")
        b1 = _entrada(client, org_headers, wh, mat, "B-1")
        body = _listado(client, org_headers, sort="remission_asc")
        assert _ids(body["items"]) == [a2["id"], b1["id"]]
