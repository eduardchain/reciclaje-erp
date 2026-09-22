"""
Tests CC-014 — deuda en plomo con Willard valorada a precio de mercado (Q-B).

Johana (18-sep, con sus palabras): "le doy un valor de acuerdo al precio del
mercado en ese momento y la tengo como un valor negativo, o sea, restando
dentro de mi inventario". Hoy lo hace a mano; esto lo pone en el balance.

Cubre: el precio append-only con vigencia por fecha de NEGOCIO (D1), la linea
negativa en el Balance General y el item en el Detallado (D5/D7), el corte
historico (D8), el signo sin abs() (D4), que la valoracion NO toca resultados
(F2 de QA) y la no-regresion de las otras seis organizaciones, que es el
punto del ciclo: sin el flag no se devuelve nada Y no se toca el libro de kg.
"""
import pytest
from datetime import timedelta
from decimal import Decimal

from tests.conftest import create_third_party_with_category
from tests.integration_helpers import create_warehouse
from app.models.material import Material
from app.utils.dates import business_today

KG_URL = "/api/v1/kg-ledger"
PRICE_URL = "/api/v1/lead-market-prices"
BS_URL = "/api/v1/reports/balance-sheet"
BD_URL = "/api/v1/reports/balance-detailed"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _enable_kg_ledger_flag(db_session, test_organization):
    """JSONB sin MutableDict: reasignar el dict completo (regla D3-E1)."""
    test_organization.settings = {"kg_ledger_enabled": True}
    db_session.commit()


@pytest.fixture
def willard_account(client, org_headers, db_session, test_organization):
    wh = create_warehouse(db_session, test_organization.id, "Circunvalar")
    tp = create_third_party_with_category(
        db_session, test_organization.id, "Willard S.A.", "material_supplier"
    )
    db_session.commit()
    resp = client.post(
        f"{KG_URL}/accounts",
        headers=org_headers,
        json={
            "code": "WILLARD-BAT-CV",
            "display_name": "Willard Baterias Circunvalar",
            "account_type": "willard_baterias",
            "warehouse_id": str(wh.id),
            "third_party_id": str(tp.id),
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


@pytest.fixture
def inventario_en_la_seccion(client, org_headers, db_session, test_organization):
    """Un material con stock REAL dentro de `inventory_liquidated`.

    🔴 Sin esto, el assert "balance 0 no mueve el total de la seccion" que
    pidio C1 compara `0 == 0`: en el escenario de este archivo la seccion no
    tiene mas nada, asi que un item que SI moviera el total pasaria igual. Es
    el smoke vacuo de #98 escrito dentro del test que debia cerrarlo.

    Va por la API y con fecha vieja a proposito: el camino as_of lee
    InventoryMovements, no `Material.current_stock`, asi que un material
    creado por ORM daria 0 al corte y el agujero seguiria abierto en T7.
    """
    mat = Material(
        code="CU-TEST",
        name="Cobre de prueba",
        default_unit="kg",
        current_stock=Decimal("0"),
        current_stock_liquidated=Decimal("0"),
        current_stock_transit=Decimal("0"),
        current_average_cost=Decimal("0"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(mat)
    wh = create_warehouse(db_session, test_organization.id, "Bodega inventario")
    db_session.commit()

    resp = client.post(
        "/api/v1/inventory/adjustments/increase",
        headers=org_headers,
        json={
            "material_id": str(mat.id),
            "warehouse_id": str(wh.id),
            "quantity": 10.0,
            "unit_cost": 1000.0,
            "date": str(business_today() - timedelta(days=40)),
            "reason": "Stock para que la seccion tenga un total real",
        },
    )
    assert resp.status_code == 201, resp.text
    return mat


def _otros_items(sec):
    """Suma de la seccion SIN el item de la deuda, y cuantos son.

    Devolver el conteo es lo que impide que el assert vuelva a ser vacuo: si
    algun dia la fixture deja de sembrar, el test lo dice en vez de pasar.
    """
    otros = [i for i in sec["items"] if i["id"] != "lead-debt-willard"]
    return sum(i["balance"] for i in otros), len(otros)


def _kg(client, org_headers, account_id, delta, date_str, stage=None):
    """Movimiento manual en el libro de kg."""
    payload = {
        "account_id": account_id,
        "delta_kg": str(delta),
        "transaction_date": date_str,
        "description": "Carga de prueba",
        "reason": "Fixture CC-014",
    }
    if stage is not None:
        payload["stage"] = stage
    resp = client.post(f"{KG_URL}/movements", headers=org_headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _price(client, org_headers, value, effective_date, expect=201):
    resp = client.post(
        PRICE_URL,
        headers=org_headers,
        json={"price_per_kg": str(value), "effective_date": effective_date},
    )
    assert resp.status_code == expect, resp.text
    return resp.json()


def _bs(client, org_headers, as_of=None):
    params = {"as_of_date": as_of} if as_of else None
    resp = client.get(BS_URL, headers=org_headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _bd(client, org_headers, as_of=None):
    params = {"as_of_date": as_of} if as_of else None
    resp = client.get(BD_URL, headers=org_headers, params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _lead_item(detallado):
    sec = detallado["assets"].get("inventory_liquidated")
    if not sec:
        return None, None
    item = next((i for i in sec["items"] if i["id"] == "lead-debt-willard"), None)
    return item, sec


def _ayer():
    return str(business_today() - timedelta(days=1))


# ---------------------------------------------------------------------------
# T1/T2 — la linea en el General y el item en el Detallado
# ---------------------------------------------------------------------------

class TestValoracionEnElBalance:
    def test_t1_linea_negativa_y_total_de_activos(
        self, client, org_headers, willard_account
    ):
        """100 kg x $2.400 dan -$240.000 y el total de activos baja exactamente eso."""
        _kg(client, org_headers, willard_account["id"], 100, _ayer())

        antes = _bs(client, org_headers)
        ld_antes = antes["assets"]["lead_debt_willard"]
        assert ld_antes["kg"] == 100.0
        assert ld_antes["value"] is None, "sin precio no se inventa un valor"

        _price(client, org_headers, 2400, _ayer())

        despues = _bs(client, org_headers)
        ld = despues["assets"]["lead_debt_willard"]
        assert ld["kg"] == 100.0
        assert ld["price"] == 2400.0
        assert ld["value"] == -240_000.0
        assert despues["assets"]["total"] == pytest.approx(antes["assets"]["total"] - 240_000, abs=0.01)
        assert despues["total_assets"] == pytest.approx(antes["total_assets"] - 240_000, abs=0.01)

    def test_t2_item_dentro_de_inventario_en_el_detallado(
        self, client, org_headers, willard_account
    ):
        """D7: es un item de la seccion de inventario, no una seccion nueva."""
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        antes = _bd(client, org_headers)
        sec_antes = antes["assets"].get("inventory_liquidated")
        total_antes = sec_antes["total"] if sec_antes else 0.0

        _price(client, org_headers, 2400, _ayer())
        item, sec = _lead_item(_bd(client, org_headers))

        assert item is not None
        assert item["code"] == "WILLARD", "sin WILLARD se lee como un costo de material"
        assert "precio de mercado" in item["name"]
        assert item["stock"] == 100.0
        assert item["avg_cost"] == 2400.0
        assert item["balance"] == -240_000.0
        assert sec["total"] == pytest.approx(total_antes - 240_000, abs=0.01)

    def test_t2b_no_nace_una_seccion_nueva(
        self, client, org_headers, willard_account, db_session, test_organization
    ):
        """D7: el mismo juego de secciones con y sin flag.

        Es la promesa que hace que la captura del Detallado del golden salga
        identica en las tres organizaciones cliente: ni una seccion nueva, ni
        una clave nueva, ni una lista mas larga.
        """
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        _price(client, org_headers, 2400, _ayer())
        con_flag = _bd(client, org_headers)

        test_organization.settings = {}
        db_session.commit()
        sin_flag = _bd(client, org_headers)

        assert set(con_flag["assets"]) == set(sin_flag["assets"])
        assert set(con_flag["liabilities"]) == set(sin_flag["liabilities"])
        assert set(con_flag.keys()) == set(sin_flag.keys())

    def test_t2c_el_id_del_item_es_un_centinela_no_un_uuid(
        self, client, org_headers, willard_account
    ):
        """El frontend linkea cada item de inventario a sus movimientos por
        `material_id`. Este item no es un material, asi que su id es un
        centinela y la pantalla lo excluye del link por ese id. Si alguien lo
        cambiara a un UUID el link apuntaria a un material inexistente.
        """
        from uuid import UUID
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        _price(client, org_headers, 2400, _ayer())
        item, _ = _lead_item(_bd(client, org_headers))
        assert item["id"] == "lead-debt-willard"
        with pytest.raises(ValueError):
            UUID(item["id"])


# ---------------------------------------------------------------------------
# T3/T4/T5 — el precio: append-only, validaciones, vigencia
# ---------------------------------------------------------------------------

class TestPrecioAppendOnly:
    def test_t3_sin_patch_ni_delete(self, client, org_headers):
        creado = _price(client, org_headers, 2400, _ayer())
        assert client.patch(PRICE_URL, headers=org_headers, json={}).status_code == 405
        assert client.delete(PRICE_URL, headers=org_headers).status_code == 405
        assert client.patch(
            f"{PRICE_URL}/{creado['id']}", headers=org_headers, json={}
        ).status_code == 404
        assert client.delete(
            f"{PRICE_URL}/{creado['id']}", headers=org_headers
        ).status_code == 404

    def test_t4_precio_no_positivo_y_fecha_futura_422(self, client, org_headers):
        _price(client, org_headers, 0, _ayer(), expect=422)
        _price(client, org_headers, -100, _ayer(), expect=422)
        manana = str(business_today() + timedelta(days=1))
        _price(client, org_headers, 2400, manana, expect=422)

    def test_t4b_el_dia_de_hoy_si_se_acepta(self, client, org_headers):
        """El borde: hoy NO es futuro. Con el reloj de negocio, no el UTC."""
        _price(client, org_headers, 2400, str(business_today()))

    def test_t5_dos_precios_el_mismo_dia_gana_el_ultimo(
        self, client, org_headers, willard_account
    ):
        """`now()` de PG es transaccional y empata: el desempate es por id."""
        _kg(client, org_headers, willard_account["id"], 10, _ayer())
        _price(client, org_headers, 2400, _ayer())
        _price(client, org_headers, 2500, _ayer())
        assert _bs(client, org_headers)["assets"]["lead_debt_willard"]["price"] == 2500.0

    def test_t5b_gana_la_fecha_de_vigencia_no_la_de_carga(
        self, client, org_headers, willard_account
    ):
        """D1: el precio de septiembre cargado en octubre NO pisa al de octubre.

        Es el reverso del caso que motivo la fecha de vigencia y prueba que la
        vigencia se decide por `effective_date`, no por `created_at`.
        """
        _kg(client, org_headers, willard_account["id"], 10, str(business_today() - timedelta(days=30)))
        _price(client, org_headers, 2500, _ayer())                                   # cargado 1o, mas reciente
        _price(client, org_headers, 2400, str(business_today() - timedelta(days=20)))  # cargado 2o, mas viejo
        assert _bs(client, org_headers)["assets"]["lead_debt_willard"]["price"] == 2500.0


# ---------------------------------------------------------------------------
# T6/T7/T8/T12 — corte historico
# ---------------------------------------------------------------------------

class TestCorteHistorico:
    def test_t6_kilos_y_precio_de_cada_fecha(
        self, client, org_headers, willard_account
    ):
        """Cada corte usa los kilos de esa fecha y el precio vigente de esa fecha."""
        hace30 = str(business_today() - timedelta(days=30))
        hace10 = str(business_today() - timedelta(days=10))
        _kg(client, org_headers, willard_account["id"], 100, hace30)
        _kg(client, org_headers, willard_account["id"], 50, hace10)
        _price(client, org_headers, 2000, hace30)
        _price(client, org_headers, 3000, hace10)

        viejo = _bs(client, org_headers, as_of=str(business_today() - timedelta(days=20)))
        assert viejo["assets"]["lead_debt_willard"]["kg"] == 100.0
        assert viejo["assets"]["lead_debt_willard"]["price"] == 2000.0
        assert viejo["assets"]["lead_debt_willard"]["value"] == -200_000.0

        hoy = _bs(client, org_headers)
        assert hoy["assets"]["lead_debt_willard"]["kg"] == 150.0
        assert hoy["assets"]["lead_debt_willard"]["price"] == 3000.0
        assert hoy["assets"]["lead_debt_willard"]["value"] == -450_000.0

    def test_t6b_el_precio_del_dia_del_corte_entra(
        self, client, org_headers, willard_account
    ):
        """La frontera: `effective_date` a mediodia UTC vs `cutoff_dt` 00:00 del
        dia siguiente. Un precio fechado EL dia del corte cuenta."""
        hace5 = str(business_today() - timedelta(days=5))
        _kg(client, org_headers, willard_account["id"], 10, hace5)
        _price(client, org_headers, 2400, hace5)
        corte = _bs(client, org_headers, as_of=hace5)
        assert corte["assets"]["lead_debt_willard"]["value"] == -24_000.0

    def test_t7_corte_anterior_al_primer_precio(
        self, client, org_headers, willard_account, inventario_en_la_seccion
    ):
        """Kilos si, valor no: y el total de activos no se mueve."""
        hace30 = str(business_today() - timedelta(days=30))
        _kg(client, org_headers, willard_account["id"], 100, hace30)
        _price(client, org_headers, 2400, _ayer())

        corte = _bs(client, org_headers, as_of=str(business_today() - timedelta(days=15)))
        ld = corte["assets"]["lead_debt_willard"]
        assert ld["kg"] == 100.0
        assert ld["price"] is None and ld["price_date"] is None and ld["value"] is None
        assert corte["assets"]["total"] == pytest.approx(
            corte["total_assets"], abs=0.01
        )
        # C1 de QA: en el Detallado el item EXISTE, con los kilos y sin precio.
        item, sec = _lead_item(_bd(client, org_headers, as_of=str(business_today() - timedelta(days=15))))
        assert item is not None, "un balance que esconde la deuda es peor que uno que la muestra sin valorar"
        assert item["avg_cost"] is None, "avg_cost=0 se leeria como un precio de cero pesos"
        assert item["balance"] == 0.0
        assert "SIN PRECIO DE MERCADO CARGADO" in item["name"]
        otros, cuantos = _otros_items(sec)
        assert cuantos >= 1 and otros != 0, (
            "la seccion tiene que traer inventario real: contra una seccion vacia "
            "este assert compara 0 == 0 y no prueba nada (#98)"
        )
        assert sec["total"] == pytest.approx(otros, abs=0.01), (
            "balance 0 no puede mover el total de la seccion"
        )

    def test_t8_kilos_sin_ningun_precio_cargado(
        self, client, org_headers, willard_account, inventario_en_la_seccion
    ):
        """C1 de QA: los kilos sin valorar se avisan en las DOS pantallas.

        El aviso vivia solo en el General y el Detallado es el documento que
        Johana exporta — la falla de #100 D4d y #109 F4 por la puerta que
        faltaba. Con `avg_cost` en None ni la pantalla ni el Excel pintan la
        linea "kg x $" (las dos exigen stock y avg_cost no nulos), asi que los
        kilos tienen que ir DENTRO del nombre o no aparecen en ningun lado.
        """
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        ld = _bs(client, org_headers)["assets"]["lead_debt_willard"]
        assert ld["kg"] == 100.0
        assert ld["value"] is None

        item, sec = _lead_item(_bd(client, org_headers))
        assert item is not None
        assert item["code"] == "WILLARD"
        assert "SIN PRECIO DE MERCADO CARGADO" in item["name"]
        assert "100 kg" in item["name"], "sin avg_cost los kilos solo caben en el nombre"
        assert item["stock"] == 100.0
        assert item["avg_cost"] is None
        assert item["balance"] == 0.0
        otros, cuantos = _otros_items(sec)
        assert cuantos >= 1 and otros != 0, (
            "la seccion tiene que traer inventario real: contra una seccion vacia "
            "este assert compara 0 == 0 y no prueba nada (#98)"
        )
        assert sec["total"] == pytest.approx(otros, abs=0.01), (
            "balance 0 no puede mover el total de la seccion"
        )

    def test_t8b_sin_kilos_y_sin_precio_no_hay_item(
        self, client, org_headers, willard_account
    ):
        """El contraste de C1: el item aparece cuando hay algo que decir.

        Sin kilos y sin precio no hay deuda ni aviso que dar, igual que los
        materiales con stock 0 que la seccion ya filtra. Sin este test, "el
        item existe cuando falta el precio" y "el item existe siempre" se ven
        identicos.
        """
        assert _bs(client, org_headers)["assets"]["lead_debt_willard"]["kg"] == 0.0
        item, _ = _lead_item(_bd(client, org_headers))
        assert item is None

    def test_t12_cuenta_desactivada_antes_del_corte_sigue_contando(
        self, client, org_headers, willard_account, db_session
    ):
        """F4: ni `balances()` ni la lista de CUENTAS filtran por is_active.

        Si se filtrara en la lista, el agujero que `balances()` evita volveria
        a entrar por la otra puerta: la cuenta existia al corte y tenia saldo.
        """
        hace10 = str(business_today() - timedelta(days=10))
        _kg(client, org_headers, willard_account["id"], 100, hace10)
        _price(client, org_headers, 2400, hace10)

        # La desactivamos AHORA, despues del movimiento y antes de preguntar
        from uuid import UUID
        from app.models.kg_ledger import KgLedgerAccount
        acc = db_session.get(KgLedgerAccount, UUID(willard_account["id"]))
        acc.is_active = False
        db_session.commit()

        corte = _bs(client, org_headers, as_of=str(business_today() - timedelta(days=5)))
        assert corte["assets"]["lead_debt_willard"]["kg"] == 100.0
        assert corte["assets"]["lead_debt_willard"]["value"] == -240_000.0
        # y en vivo tambien: desactivar no borra el saldo
        assert _bs(client, org_headers)["assets"]["lead_debt_willard"]["kg"] == 100.0


# ---------------------------------------------------------------------------
# T9 — no-regresion de las otras seis organizaciones
# ---------------------------------------------------------------------------

class TestNoRegresion:
    def test_t9_sin_flag_es_none_y_no_se_toca_el_libro_de_kg(
        self, client, org_headers, db_session, test_organization, monkeypatch
    ):
        """🔴 El corazon del ciclo.

        No alcanza con que el campo llegue None: el balance de una organizacion
        sin el flag no puede adquirir una dependencia al libro de kilos. El
        `monkeypatch` revienta si alguien llama a `balances()`, asi que este
        test falla si el corte por flag se mueve una linea mas abajo.
        """
        from app.services import kg_ledger as kg_mod

        def _explota(*a, **kw):
            raise AssertionError(
                "sin kg_ledger_enabled el balance NO puede consultar el libro de kilos"
            )

        monkeypatch.setattr(kg_mod.KgLedgerService, "balances", _explota)

        test_organization.settings = {}
        db_session.commit()

        cuerpo = _bs(client, org_headers)
        assert cuerpo["assets"]["lead_debt_willard"] is None
        # y el historico por el mismo camino
        assert _bs(client, org_headers, as_of=_ayer())["assets"]["lead_debt_willard"] is None
        # el Detallado tampoco trae el item
        item, _ = _lead_item(_bd(client, org_headers))
        assert item is None

    def test_t9b_el_resto_del_balance_no_cambia(
        self, client, org_headers, db_session, test_organization
    ):
        """Con y sin flag, todo lo que no es la clave nueva es identico."""
        con_flag = _bs(client, org_headers)
        test_organization.settings = {}
        db_session.commit()
        sin_flag = _bs(client, org_headers)

        a1 = dict(con_flag["assets"]); a2 = dict(sin_flag["assets"])
        a1.pop("lead_debt_willard"); a2.pop("lead_debt_willard")
        assert a1 == a2
        for k in ("total_assets", "liabilities", "total_liabilities", "equity",
                  "accumulated_profit", "distributed_profit"):
            assert con_flag[k] == sin_flag[k], k


# ---------------------------------------------------------------------------
# T10 — el signo
# ---------------------------------------------------------------------------

class TestSigno:
    def test_t10_saldo_negativo_del_libro_da_linea_positiva(
        self, client, org_headers, willard_account
    ):
        """D4: sin abs(). Si Willard le debiera plomo a SAC, la linea suma."""
        _kg(client, org_headers, willard_account["id"], -80, _ayer())
        _price(client, org_headers, 2400, _ayer())
        ld = _bs(client, org_headers)["assets"]["lead_debt_willard"]
        assert ld["kg"] == -80.0
        assert ld["value"] == 192_000.0

    def test_t10b_solo_cuentas_willard(
        self, client, org_headers, willard_account, intersede_account
    ):
        """D3/D9: intersede es deuda interna y no entra. Q-44 sigue abierta."""
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        _kg(client, org_headers, intersede_account["id"], 500, _ayer(), stage="horno")
        _price(client, org_headers, 2400, _ayer())
        ld = _bs(client, org_headers)["assets"]["lead_debt_willard"]
        assert ld["kg"] == 100.0, "los 500 kg de intersede no pueden entrar"
        assert ld["value"] == -240_000.0


# ---------------------------------------------------------------------------
# T11 — RBAC y flag en el router del precio
# ---------------------------------------------------------------------------

class TestRbac:
    def test_t11_sin_permiso_403(self, client, org_headers2):
        """El viewer de la otra org no tiene tariffs.* (politica D4 de E1)."""
        assert client.get(PRICE_URL, headers=org_headers2).status_code == 403

    def test_t11b_sin_flag_403_aunque_sea_admin(
        self, client, org_headers, db_session, test_organization
    ):
        test_organization.settings = {}
        db_session.commit()
        assert client.get(PRICE_URL, headers=org_headers).status_code == 403
        resp = client.post(
            PRICE_URL, headers=org_headers,
            json={"price_per_kg": "2400", "effective_date": _ayer()},
        )
        assert resp.status_code == 403

    def test_t11c_aislamiento_entre_organizaciones(
        self, client, org_headers, db_session, test_organization2
    ):
        """El precio de una org no lo ve la otra."""
        test_organization2.settings = {"kg_ledger_enabled": True}
        db_session.commit()
        _price(client, org_headers, 2400, _ayer())
        assert client.get(PRICE_URL, headers=org_headers).json()["total"] == 1


# ---------------------------------------------------------------------------
# T13 — la valoracion NO pasa por resultados (F2 de QA)
# ---------------------------------------------------------------------------

class TestNoTocaResultados:
    def test_t13_utilidad_intacta_y_patrimonio_absorbe(
        self, client, org_headers, willard_account
    ):
        """🔴 El patrimonio absorbe la valoracion entera, sin pasar por el P&L.

        La version anterior de este test comparaba activos contra pasivos mas
        patrimonio y era TAUTOLOGICA: `equity` es residual en los cuatro
        caminos del balance, asi que cuadra con cualquier numero, incluido uno
        equivocado. Lo que hay que probar es que la utilidad no se entera.
        """
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        antes = _bs(client, org_headers)
        _price(client, org_headers, 2400, _ayer())
        despues = _bs(client, org_headers)

        assert despues["accumulated_profit"] == antes["accumulated_profit"]
        assert despues["distributed_profit"] == antes["distributed_profit"]
        assert despues["equity"] == pytest.approx(antes["equity"] - 240_000, abs=0.01)
        assert despues["total_liabilities"] == antes["total_liabilities"]

    def test_t13b_el_detallado_cuadra_con_el_general(
        self, client, org_headers, willard_account
    ):
        _kg(client, org_headers, willard_account["id"], 100, _ayer())
        _price(client, org_headers, 2400, _ayer())
        general = _bs(client, org_headers)
        detallado = _bd(client, org_headers)
        assert detallado["total_assets"] == pytest.approx(general["total_assets"], abs=0.01)
        assert detallado["equity"] == pytest.approx(general["equity"], abs=0.01)
        assert detallado["verification"]["is_balanced"] is True
