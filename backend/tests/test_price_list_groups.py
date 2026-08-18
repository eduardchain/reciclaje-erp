"""
Tests de listas de precios por proveedor (item 7 del ciclo Entradas, SAC).

La regla la fijo Hugo (Q-21/Q-22) y es MAS conservadora que la propuesta
original: el sistema NUNCA adivina un precio.

  1. Proveedor CON lista -> el precio de su lista. Material en cero -> nada.
  2. Proveedor SIN lista -> nada.

El test mas importante del archivo es `test_sin_third_party_id_es_byte_a_byte`:
es el guardrail de no-regresion de las 3 empresas cliente.
"""
from decimal import Decimal

import pytest

from app.models.price_list import PriceList
from tests.conftest import create_third_party_with_category
from tests.integration_helpers import create_material, create_material_category

GROUPS_URL = "/api/v1/price-list-groups"
PRICES_URL = "/api/v1/price-lists"


@pytest.fixture(autouse=True)
def _enable_flag(db_session, test_organization):
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def materiales(db_session, test_organization):
    cat = create_material_category(db_session, test_organization.id, "Chatarra")
    mats = [
        create_material(db_session, test_organization.id, f"M-{i}", f"Material {i}", cat.id)
        for i in range(1, 4)
    ]
    db_session.commit()
    return mats


@pytest.fixture
def proveedor(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Lista A", "material_supplier"
    )
    db_session.commit()
    return tp


@pytest.fixture
def proveedor2(db_session, test_organization):
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Proveedor Sin Lista", "material_supplier"
    )
    db_session.commit()
    return tp


def _precio_general(db_session, org_id, material_id, purchase, sale=0):
    """Precio de la lista GENERAL (price_list_group_id NULL) — lo de siempre."""
    row = PriceList(
        material_id=material_id,
        purchase_price=Decimal(str(purchase)),
        sale_price=Decimal(str(sale)),
        organization_id=org_id,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _crear_lista(client, org_headers, name="Lista A", **kwargs):
    resp = client.post(GROUPS_URL, json={"name": name, **kwargs}, headers=org_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _asignar(client, org_headers, group_id, tp_ids):
    resp = client.put(
        f"{GROUPS_URL}/{group_id}/members",
        json={"third_party_ids": [str(i) for i in tp_ids]},
        headers=org_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _precio_de_lista(client, org_headers, group_id, material_id, purchase):
    resp = client.post(
        PRICES_URL,
        json={
            "material_id": str(material_id),
            "purchase_price": purchase,
            "price_list_group_id": str(group_id),
        },
        headers=org_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _resolver(client, org_headers, third_party_id=None):
    url = f"{PRICES_URL}/current"
    if third_party_id is not None:
        url += f"?third_party_id={third_party_id}"
    resp = client.get(url, headers=org_headers)
    assert resp.status_code == 200, resp.text
    return {i["material_id"]: i["purchase_price"] for i in resp.json()["items"]}


# ---------------------------------------------------------------------------
# El resolutor (D3) — las tres reglas de Hugo
# ---------------------------------------------------------------------------

class TestResolutor:

    def test_proveedor_con_lista_usa_su_precio_no_el_general(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)

        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 1500)
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        precios = _resolver(client, org_headers, proveedor.id)
        assert precios[str(m.id)] == 1500  # el de SU lista, no los 1000 generales

    def test_material_en_cero_no_sugiere_y_NO_cae_al_general(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        """🔴 El corazon de D3: el cero es una DECISION, no un hueco a rellenar."""
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)

        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 0)
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        precios = _resolver(client, org_headers, proveedor.id)
        assert str(m.id) not in precios, "no debe caer a la lista general"

    def test_proveedor_sin_lista_no_sugiere_nada(
        self, client, org_headers, db_session, test_organization, materiales, proveedor, proveedor2
    ):
        """
        ⚠️ La org TIENE listas y este proveedor no esta en ninguna — que es el
        caso real de D3. Sin crear la lista, el test pasaba por la razon
        equivocada: sin ninguna lista en la org el parametro es inerte (D10) y
        se devuelve la general.
        """
        _precio_general(db_session, test_organization.id, materiales[0].id, 1000)
        grupo = _crear_lista(client, org_headers)["group"]
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        assert _resolver(client, org_headers, proveedor2.id) == {}

    def test_devuelve_ausencia_nunca_cero(
        self, client, org_headers, db_session, test_organization, materiales, proveedor, proveedor2
    ):
        """
        Un $0 sugerido seria un precio AFIRMADO que nadie eligio. Quien consume
        esto no tiene que saber interpretar un cero.
        """
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 0)
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        for tp in (proveedor, proveedor2):
            for valor in _resolver(client, org_headers, tp.id).values():
                assert valor != 0

    def test_lista_desactivada_deja_al_proveedor_sin_sugerencia(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        """
        ⚠️ Se deja OTRA lista activa a proposito. Desactivar la unica lista de
        la org es un caso distinto — ahi la funcionalidad queda apagada entera
        y se vuelve a la general (D10, con su propio test). Aca se prueba lo que
        dice el titulo: que desactivar la lista DE ESTE proveedor no lo hace
        caer a la general.
        """
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        _crear_lista(client, org_headers, "Otra que sigue viva")

        grupo = _crear_lista(client, org_headers, "La del proveedor")["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 1500)
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        resp = client.patch(
            f"{GROUPS_URL}/{grupo['id']}", json={"is_active": False}, headers=org_headers
        )
        assert resp.status_code == 200

        # Coherente con D3: sin lista vigente, nada. NO cae al general.
        assert _resolver(client, org_headers, proveedor.id) == {}

    def test_vigente_es_el_mas_reciente_DENTRO_de_su_lista(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        """Append-only por lista (#35): el ultimo de OTRA lista no manda."""
        m = materiales[0]
        grupo_a = _crear_lista(client, org_headers, "Lista A")["group"]
        grupo_b = _crear_lista(client, org_headers, "Lista B")["group"]

        _precio_de_lista(client, org_headers, grupo_a["id"], m.id, 1000)
        _precio_de_lista(client, org_headers, grupo_b["id"], m.id, 9999)  # despues
        _precio_de_lista(client, org_headers, grupo_a["id"], m.id, 1200)  # el vigente de A

        _asignar(client, org_headers, grupo_a["id"], [proveedor.id])
        assert _resolver(client, org_headers, proveedor.id)[str(m.id)] == 1200


# ---------------------------------------------------------------------------
# 🔴 No-regresion: el seam de D4
# ---------------------------------------------------------------------------

class TestNoRegresion:

    def test_sin_third_party_id_es_byte_a_byte(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        """
        🔴 EL TEST MAS IMPORTANTE DEL ARCHIVO.

        Es lo que llaman las 3 empresas cliente y las 6 pantallas de ventas y
        cruces. Con listas creadas y precios cargados en ellas, la respuesta sin
        parametro tiene que ser IDENTICA a la de antes de que las listas
        existieran.
        """
        m0, m1 = materiales[0], materiales[1]
        _precio_general(db_session, test_organization.id, m0.id, 1000)
        _precio_general(db_session, test_organization.id, m1.id, 2000)
        esperado = {str(m0.id): 1000, str(m1.id): 2000}

        assert _resolver(client, org_headers) == esperado

        # Ahora se crea una lista con precios MUY distintos y proveedores dentro
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m0.id, 77777)
        _precio_de_lista(client, org_headers, grupo["id"], m1.id, 88888)
        _asignar(client, org_headers, grupo["id"], [proveedor.id])

        assert _resolver(client, org_headers) == esperado, (
            "la lista general se contamino con precios de una lista de proveedor"
        )

    def test_org_sin_listas_ignora_el_parametro_y_devuelve_la_general(
        self, client, org_headers, db_session, test_organization, materiales, proveedor
    ):
        """
        🔴 D10 — EL OTRO GUARDRAIL DE LAS 3 EMPRESAS CLIENTE, y el que faltaba.

        Las 3 pantallas de compras que llaman al resolutor son COMPARTIDAS: en
        cuanto pasan el proveedor, una org que no usa listas cae en este camino.
        Sin D10 devolveria vacio y Costa/Biogreen/MetaRecycling se quedarian
        **sin ninguna sugerencia de precio en compras**.

        Ningun otro test del archivo lo cubria: todos crean una lista primero.
        """
        m0, m1 = materiales[0], materiales[1]
        _precio_general(db_session, test_organization.id, m0.id, 1000)
        _precio_general(db_session, test_organization.id, m1.id, 2000)

        # Cero listas en la org: el parametro no puede cambiar nada
        assert _resolver(client, org_headers, proveedor.id) == {
            str(m0.id): 1000, str(m1.id): 2000
        }

    def test_al_crear_la_primera_lista_la_regla_se_activa(
        self, client, org_headers, db_session, test_organization, materiales, proveedor2
    ):
        """La contracara de D10: con una lista viva, D3 manda. Es exactamente lo
        que el dialogo de creacion le advierte al usuario."""
        _precio_general(db_session, test_organization.id, materiales[0].id, 1000)
        assert _resolver(client, org_headers, proveedor2.id) != {}

        _crear_lista(client, org_headers, "La primera")
        assert _resolver(client, org_headers, proveedor2.id) == {}

    def test_desactivar_todas_las_listas_vuelve_al_comportamiento_historico(
        self, client, org_headers, db_session, test_organization, materiales, proveedor2
    ):
        """Coherente con D10: sin listas EN JUEGO, la funcionalidad esta apagada."""
        _precio_general(db_session, test_organization.id, materiales[0].id, 1000)
        grupo = _crear_lista(client, org_headers, "Unica")["group"]
        assert _resolver(client, org_headers, proveedor2.id) == {}

        client.patch(f"{GROUPS_URL}/{grupo['id']}", json={"is_active": False}, headers=org_headers)
        assert _resolver(client, org_headers, proveedor2.id) == {str(materiales[0].id): 1000}

    def test_tabla_sin_grupo_no_ve_precios_de_lista(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        """D7: la pantalla de Precios en modo tabla (#35) no se toca."""
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 77777)

        resp = client.get(f"{PRICES_URL}/table", headers=org_headers)
        assert resp.status_code == 200
        fila = next(i for i in resp.json()["items"] if i["material_id"] == str(m.id))
        assert fila["purchase_price"] == 1000

    def test_historial_por_material_separa_general_de_lista(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        _precio_general(db_session, test_organization.id, m.id, 1100)
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 77777)

        resp = client.get(f"{PRICES_URL}/material/{m.id}", headers=org_headers)
        assert resp.status_code == 200
        precios = [float(i["purchase_price"]) for i in resp.json()["items"]]
        assert sorted(precios) == [1000.0, 1100.0]
        assert 77777.0 not in precios

    def test_listado_generico_no_mezcla_listas(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        """`get_multi` hereda el `IS NULL` de `_base_query` (§4)."""
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], m.id, 77777)

        resp = client.get(PRICES_URL, headers=org_headers)
        assert resp.status_code == 200
        assert all(float(i["purchase_price"]) != 77777.0 for i in resp.json()["items"])

    def test_get_por_pk_SI_devuelve_una_fila_de_lista(
        self, client, org_headers, materiales
    ):
        """
        §4: la unica lectura sin filtro, y a proposito. Una fila pedida por su
        identificador es esa fila; filtrarla por grupo solo podria esconderla.
        """
        grupo = _crear_lista(client, org_headers)["group"]
        creado = _precio_de_lista(client, org_headers, grupo["id"], materiales[0].id, 1500)

        resp = client.get(f"{PRICES_URL}/{creado['id']}", headers=org_headers)
        assert resp.status_code == 200
        assert float(resp.json()["purchase_price"]) == 1500.0


# ---------------------------------------------------------------------------
# La tabla por lista (Q-21: TODOS los materiales)
# ---------------------------------------------------------------------------

class TestTablaPorLista:

    def test_trae_todos_los_materiales_activos_con_precio_o_vacios(
        self, client, org_headers, materiales
    ):
        grupo = _crear_lista(client, org_headers)["group"]
        _precio_de_lista(client, org_headers, grupo["id"], materiales[0].id, 1500)

        resp = client.get(f"{GROUPS_URL}/{grupo['id']}/table", headers=org_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]

        # Q-21: el catalogo COMPLETO, no un subconjunto disperso
        assert {i["material_id"] for i in items} >= {str(m.id) for m in materiales}
        con_precio = {i["material_id"]: i["purchase_price"] for i in items}
        assert con_precio[str(materiales[0].id)] == 1500
        assert con_precio[str(materiales[1].id)] is None

    def test_no_ve_los_precios_de_la_general(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        m = materiales[0]
        _precio_general(db_session, test_organization.id, m.id, 1000)
        grupo = _crear_lista(client, org_headers)["group"]

        resp = client.get(f"{GROUPS_URL}/{grupo['id']}/table", headers=org_headers)
        fila = next(i for i in resp.json()["items"] if i["material_id"] == str(m.id))
        assert fila["purchase_price"] is None


# ---------------------------------------------------------------------------
# Membresia exclusiva (D2 — la base la hace cumplir)
# ---------------------------------------------------------------------------

class TestMembresia:

    def test_un_tercero_no_puede_estar_en_dos_listas(
        self, client, org_headers, proveedor
    ):
        a = _crear_lista(client, org_headers, "Lista A")["group"]
        b = _crear_lista(client, org_headers, "Lista B")["group"]

        _asignar(client, org_headers, a["id"], [proveedor.id])
        items = _asignar(client, org_headers, b["id"], [proveedor.id])["items"]

        fila = next(i for i in items if i["third_party_id"] == str(proveedor.id))
        assert fila["current_group_id"] == b["id"], "asignar a otra lista debe MOVER"

        # y en A ya no esta
        listas = client.get(GROUPS_URL, headers=org_headers).json()["items"]
        assert next(g for g in listas if g["id"] == a["id"])["member_count"] == 0

    def test_el_selector_muestra_la_lista_actual_antes_de_guardar(
        self, client, org_headers, proveedor, proveedor2
    ):
        a = _crear_lista(client, org_headers, "Lista A")["group"]
        _asignar(client, org_headers, a["id"], [proveedor.id])

        resp = client.get(f"{GROUPS_URL}/suppliers", headers=org_headers)
        assert resp.status_code == 200
        por_id = {i["third_party_id"]: i for i in resp.json()["items"]}
        assert por_id[str(proveedor.id)]["current_group_name"] == "Lista A"
        assert por_id[str(proveedor2.id)]["current_group_id"] is None

    def test_tercero_de_otra_org_rechazado(
        self, client, org_headers, db_session, test_organization2
    ):
        ajeno = create_third_party_with_category(
            db_session, test_organization2.id, "Ajeno", "material_supplier"
        )
        db_session.commit()
        grupo = _crear_lista(client, org_headers)["group"]

        resp = client.put(
            f"{GROUPS_URL}/{grupo['id']}/members",
            json={"third_party_ids": [str(ajeno.id)]},
            headers=org_headers,
        )
        assert resp.status_code == 404

    def test_nombre_duplicado_rechazado(self, client, org_headers):
        _crear_lista(client, org_headers, "Lista A")
        resp = client.post(GROUPS_URL, json={"name": "  lista a  "}, headers=org_headers)
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# 🟢 El sembrado del dia uno (Q-26)
# ---------------------------------------------------------------------------

class TestSembrado:

    def test_siembra_precios_generales_y_asigna_proveedores(
        self, client, org_headers, db_session, test_organization, materiales, proveedor, proveedor2
    ):
        """
        Sin esto, el dia que se enciende la funcion TODOS los proveedores
        pierden el precio sugerido de golpe (D3), con un campo vacio como unico
        sintoma. Con esto, el dia uno se comporta igual que hoy.
        """
        m0, m1 = materiales[0], materiales[1]
        _precio_general(db_session, test_organization.id, m0.id, 1000)
        _precio_general(db_session, test_organization.id, m1.id, 2000)

        res = _crear_lista(
            client, org_headers, "General inicial",
            seed_from_general=True, assign_all_suppliers=True,
        )
        assert res["seeded_prices"] == 2
        assert res["assigned_suppliers"] == 2
        assert res["skipped_suppliers"] == 0

        # 🔴 La prueba de que el dia uno no cambia nada para el usuario
        for tp in (proveedor, proveedor2):
            assert _resolver(client, org_headers, tp.id) == {
                str(m0.id): 1000, str(m1.id): 2000
            }

    def test_no_roba_proveedores_de_otra_lista(
        self, client, org_headers, proveedor, proveedor2
    ):
        """El sembrado es una red de seguridad, no una reasignacion masiva."""
        a = _crear_lista(client, org_headers, "Lista A")["group"]
        _asignar(client, org_headers, a["id"], [proveedor.id])

        res = _crear_lista(
            client, org_headers, "General inicial", assign_all_suppliers=True
        )
        assert res["assigned_suppliers"] == 1   # solo el que no tenia lista
        assert res["skipped_suppliers"] == 1

        listas = {g["id"]: g for g in client.get(GROUPS_URL, headers=org_headers).json()["items"]}
        assert listas[a["id"]]["member_count"] == 1

    def test_no_siembra_los_materiales_sin_precio(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        """Un cero de la general no es una decision de nadie sobre esta lista."""
        _precio_general(db_session, test_organization.id, materiales[0].id, 1000)
        _precio_general(db_session, test_organization.id, materiales[1].id, 0)

        res = _crear_lista(client, org_headers, "L", seed_from_general=True)
        assert res["seeded_prices"] == 1

    def test_sin_flags_la_lista_nace_vacia(self, client, org_headers, materiales):
        res = _crear_lista(client, org_headers, "Vacia")
        assert res["seeded_prices"] == 0
        assert res["assigned_suppliers"] == 0


# ---------------------------------------------------------------------------
# 🔴 D6 — el gate de BACKEND, que es lo que sostiene la premisa de D1
# ---------------------------------------------------------------------------

class TestGateDeBackend:

    def test_sin_flag_el_router_de_listas_responde_403(
        self, client, org_headers, db_session, test_organization
    ):
        """
        403 INCLUSO para admins. Sin esto, un admin de una org cliente podria
        llegar por API, crear una lista y escribir `price_list_group_id` — y la
        premisa "esa columna esta en NULL para siempre", de la que cuelga toda
        la no-regresion, dejaria de ser cierta.
        """
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()

        assert client.get(GROUPS_URL, headers=org_headers).status_code == 403
        assert client.post(GROUPS_URL, json={"name": "X"}, headers=org_headers).status_code == 403

    def test_sin_flag_los_precios_normales_siguen_funcionando(
        self, client, org_headers, db_session, test_organization, materiales
    ):
        """El gate NO puede tocar el camino de las 3 empresas cliente."""
        test_organization.settings = {"kg_ledger_enabled": False}
        db_session.commit()
        _precio_general(db_session, test_organization.id, materiales[0].id, 1000)

        assert client.get(f"{PRICES_URL}/current", headers=org_headers).status_code == 200
        assert client.get(f"{PRICES_URL}/table", headers=org_headers).status_code == 200
        assert client.post(
            PRICES_URL,
            json={"material_id": str(materiales[1].id), "purchase_price": 500},
            headers=org_headers,
        ).status_code == 201

    def test_no_se_puede_escribir_un_grupo_de_otra_org(
        self, client, org_headers, db_session, test_organization2, materiales
    ):
        """
        La barrera estructural: `POST /price-lists` valida que la lista exista
        EN ESTA ORG. Una org sin la funcion no puede tener listas, asi que no
        puede escribir un valor distinto de NULL — no por un chequeo de flag que
        alguien pueda olvidar, sino porque no existe el id que tendria que
        mandar.
        """
        from app.models.price_list_group import PriceListGroup
        ajeno = PriceListGroup(name="De otra org", organization_id=test_organization2.id)
        db_session.add(ajeno)
        db_session.commit()

        resp = client.post(
            PRICES_URL,
            json={
                "material_id": str(materiales[0].id),
                "purchase_price": 999,
                "price_list_group_id": str(ajeno.id),
            },
            headers=org_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# RBAC (D5 — sin permisos nuevos)
# ---------------------------------------------------------------------------

class TestRBAC:

    def test_viewer_no_puede_crear_ni_editar_listas(
        self, client, org_headers2, db_session, test_organization2
    ):
        """
        `org_headers2` es el mismo usuario como VIEWER en org2.

        ⚠️ El flag se prende en org2 A PROPOSITO: sin eso el 403 lo daria el
        gate de D6 y el test pasaria por la razon equivocada, sin probar nada
        de RBAC. Por eso ademas se verifica el MENSAJE — es lo unico que
        distingue las dos negativas, que comparten codigo de estado.
        """
        test_organization2.settings = {"kg_ledger_enabled": True}
        db_session.commit()

        resp = client.post(GROUPS_URL, json={"name": "X"}, headers=org_headers2)
        assert resp.status_code == 403
        assert "Modulo no habilitado" not in resp.json()["detail"], (
            "el 403 vino del flag, no del permiso: el test no probo RBAC"
        )

    def test_viewer_si_puede_leer_las_listas(
        self, client, org_headers2, db_session, test_organization2
    ):
        """`materials.view_prices` lo tiene el viewer (D5: sin permisos nuevos)."""
        test_organization2.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        assert client.get(GROUPS_URL, headers=org_headers2).status_code == 200
