"""Un solo reloj de negocio — `business_today()` y sus consumidores.

El dia habil es el COLOMBIANO. Entre las 19:00 y 24:00 hora Colombia (00:00-05:00
UTC) el dia UTC ya es el siguiente, asi que preguntar la fecha con el reloj UTC
hace que un hecho de hoy quede fechado MAÑANA. Cuando esa fecha es FRONTERA de
un reporte (corte as-of, filtro de periodo), el corte del dia real no ve el
hecho — de forma permanente, no solo esa noche.

⚠️ SOBRE LA VERIFICACION. Estos tests NO dependen de la hora a la que corra la
suite, a proposito. Fuera de la franja los dos relojes coinciden y un test que
solo compare fechas pasaria con el bug puesto — seria un test que no prueba
nada 19 horas al dia. Por eso:
  - el helper se prueba con el reloj CONGELADO dentro de la franja;
  - cada consumidor se prueba parcheando `business_today` en SU modulo y
    verificando que la fecha que quedo escrita salio de ahi. Si alguien vuelve
    a poner `datetime.now(timezone.utc).date()`, el parche deja de tener efecto
    y el test revienta.
  - `test_ningun_servicio_fecha_con_el_reloj_utc` es la red de seguridad que
    cubre los 7 sitios de una sola vez.
"""
import pathlib
import re
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.models.material_cost_history import MaterialCostHistory
from app.utils.dates import business_today, business_today_noon

SERVICES_DIR = pathlib.Path(__file__).resolve().parent.parent / "app" / "services"

# 2026-08-05 02:20 UTC == 2026-08-04 21:20 en Bogota. El dia de negocio es el 4.
INSTANTE_EN_LA_FRANJA = datetime(2026, 8, 5, 2, 20, tzinfo=timezone.utc)
DIA_COLOMBIANO = date(2026, 8, 4)


def _congelar(instante):
    """Congela el reloj de `app.utils.dates` en un instante dado."""
    fake = patch("app.utils.dates.datetime")
    m = fake.start()
    m.now.side_effect = lambda tz=None: instante.astimezone(tz) if tz else instante
    m.combine = datetime.combine  # business_today_noon lo usa de verdad
    return fake


class TestHelper:
    def test_dentro_de_la_franja_devuelve_el_dia_colombiano(self):
        """🔴 El corazon del asunto: a las 21:20 de Colombia el dia UTC ya es el
        siguiente. El dia de negocio NO."""
        fake = _congelar(INSTANTE_EN_LA_FRANJA)
        try:
            assert business_today() == DIA_COLOMBIANO
            assert business_today_noon() == datetime(
                2026, 8, 4, 12, 0, tzinfo=timezone.utc
            )
        finally:
            fake.stop()

        # Y el reloj equivocado, para que quede escrito cual es la diferencia
        assert INSTANTE_EN_LA_FRANJA.date() == date(2026, 8, 5)
        assert INSTANTE_EN_LA_FRANJA.date() != DIA_COLOMBIANO

    def test_fuera_de_la_franja_los_dos_relojes_coinciden(self):
        """Por eso el bug solo se ve de noche — y por eso estos tests no pueden
        depender de la hora."""
        mediodia = datetime(2026, 8, 5, 17, 0, tzinfo=timezone.utc)  # 12:00 Bogota
        fake = _congelar(mediodia)
        try:
            assert business_today() == mediodia.date() == date(2026, 8, 5)
        finally:
            fake.stop()

    def test_noon_es_mediodia_utc(self):
        """Convencion `BusinessDate` del repo (app/utils/dates.py)."""
        assert business_today_noon().hour == 12
        assert business_today_noon().date() == business_today()


# ---------------------------------------------------------------------------
# Inventario de relojes — la guarda que contesta "¿como evitamos que vuelva?"
# ---------------------------------------------------------------------------
#
# La documentacion no alcanza: la leccion de #67 estaba escrita en un docstring
# del MISMO archivo y #88 la repitio igual. Esto la hace fallar sola.
#
# Toda derivacion de "hoy" a un DIA en `app/` tiene que salir del helper. Lo
# que no salga de ahi vive aca con su razon, y si aparece algo nuevo el test
# revienta. Mismo patron que el baseline del parity check.
#
# La deuda se pago: los 19 sitios que existian (13 visibles + 6 que el regex
# con agujero no veia) estan migrados. El inventario quedo VACIO, que es la
# unica forma en que esta guarda es de verdad fuerte: cualquier reloj nuevo
# revienta, sin que nadie tenga que juzgar caso por caso si "esta bien".
#
# ⚠️ Agregar una entrada NO es la salida facil: si lo que escribes es una fecha
# de negocio, la respuesta es `business_today()`. Una excepcion aqui necesita
# una razon que sobreviva a la pregunta "¿y por que esta si?".
RELOJES_PERMITIDOS: dict[str, tuple[int, str]] = {}


# --- La misma guarda, para `tests/` -----------------------------------------
#
# 🔴 Por que existe (2026-08-13, #96). La suite estaba **roja de noche y verde de
# dia** y nadie lo sabia: no hay CI, asi que solo se ve si a alguien le toca
# correrla pasadas las 7 p.m. Esa noche fallaron 16 tests, todos por fechar un
# documento con el reloj UTC contra servicios que validan con `business_today()`.
#
# Y la clase se escapo por `tests/` DOS veces: la guarda de arriba solo mira
# `app/`. Un barrido a mano se declaro completo dos veces esa misma noche y las
# dos veces faltaban formas — cuatro maneras distintas de escribir lo mismo:
#
#     datetime.now(timezone.utc).date()      # dia UTC
#     datetime.now(timezone.utc).isoformat() # SIN .date(): el validador
#                                            # BusinessDate lo lleva al mediodia
#                                            # UTC del dia UTC. La que mas costo.
#     datetime.utcnow().isoformat()          # naive UTC
#     datetime.now().isoformat()             # naive local: da el dia correcto,
#                                            # pero por accidente de la zona de
#                                            # la maquina, no por decision
#
# Por eso este patron NO persigue la forma de la expresion sino el **sumidero**:
# un campo de fecha de negocio (`"date":` o `date=`) alimentado desde cualquier
# reloj. Da igual como se escriba el reloj — y esa es exactamente la propiedad
# que le faltaba a los barridos que fallaron.
#
# La regla, entera: **una fecha de negocio en un test sale de
# `business_today_noon()`**. Los 31 sitios que habia estan migrados y este
# inventario quedo VACIO, igual que el de `app/`.
#
# ⚠️ Timestamps de auditoria (`created_at`, `annulled_at`) NO estan cubiertos ni
# deben estarlo: esos SI son instantes y `datetime.now(timezone.utc)` es su
# respuesta correcta. La guarda mira solo el campo `date`.
RELOJES_PERMITIDOS_TESTS: dict[str, tuple[int, str]] = {}


class TestInventarioDeRelojes:
    """🔴 La guarda de fondo: nadie deriva un dia del reloj sin declararlo."""

    # ⚠️ El `(?:[^()]|\([^()]*\))*` NO es adorno: con un `[^)]*` ingenuo,
    # `datetime.now(ZoneInfo("America/Bogota")).date()` SE ESCAPA — el `[^)]*`
    # no cruza el parentesis interno. Ese agujero escondio 6 sitios (5 en
    # fixed_asset.py, 1 en scheduled_expense.py) en la primera version de esta
    # guarda. Si agregas una forma nueva, PRUEBALA contra un caso anidado.
    PATRON = re.compile(
        r"date\.today\(\)"
        r"|datetime\.now\((?:[^()]|\([^()]*\))*\)\.date\(\)"
        r"|datetime\.utcnow\(\)\.date\(\)"
    )

    CASOS_QUE_DEBE_ATRAPAR = [
        "date.today()",
        "datetime.now(timezone.utc).date()",
        'datetime.now(ZoneInfo("America/Bogota")).date()',
        "datetime.now(self._BOGOTA_TZ).date()",
        "datetime.utcnow().date()",
    ]

    def test_el_patron_atrapa_las_formas_conocidas(self):
        """La guarda se prueba a si misma: un patron con un agujero es peor que
        no tener guarda, porque da una falsa sensacion de cobertura."""
        fallan = [c for c in self.CASOS_QUE_DEBE_ATRAPAR if not self.PATRON.search(c)]
        assert not fallan, f"El patron deja escapar: {fallan}"

    def test_no_hay_relojes_sin_declarar(self):
        app_dir = SERVICES_DIR.parent
        encontrados: dict[str, int] = {}
        for archivo in sorted(app_dir.rglob("*.py")):
            rel = archivo.relative_to(app_dir.parent).as_posix()
            if rel == "app/utils/dates.py":
                continue  # el helper ES la implementacion
            n = len(self.PATRON.findall(archivo.read_text()))
            if n:
                encontrados[rel] = n

        nuevos = {k: v for k, v in encontrados.items() if k not in RELOJES_PERMITIDOS}
        assert not nuevos, (
            "Derivan un DIA del reloj sin estar declarados:\n  "
            + "\n  ".join(f"{k} ({v} sitio/s)" for k, v in sorted(nuevos.items()))
            + "\n\nSi es una FECHA DE NEGOCIO, la respuesta es `business_today()` "
            "(app/utils/dates.py).\nSi de verdad es una excepcion, agregala a "
            "RELOJES_PERMITIDOS con su razon."
        )

        crecieron = {
            k: (RELOJES_PERMITIDOS[k][0], v)
            for k, v in encontrados.items()
            if k in RELOJES_PERMITIDOS and v > RELOJES_PERMITIDOS[k][0]
        }
        assert not crecieron, (
            "Archivos con deuda declarada que sumaron relojes nuevos:\n  "
            + "\n  ".join(f"{k}: {a} → {b}" for k, (a, b) in sorted(crecieron.items()))
            + "\n\nLa deuda se paga, no se amplia."
        )

        # Si alguien la baja, que actualice el inventario (mantiene la deuda honesta)
        bajaron = {
            k: (RELOJES_PERMITIDOS[k][0], encontrados.get(k, 0))
            for k in RELOJES_PERMITIDOS
            if encontrados.get(k, 0) < RELOJES_PERMITIDOS[k][0]
        }
        assert not bajaron, (
            "Deuda pagada — actualiza RELOJES_PERMITIDOS:\n  "
            + "\n  ".join(f"{k}: {a} → {b}" for k, (a, b) in sorted(bajaron.items()))
        )

    def test_toda_entrada_de_los_inventarios_tiene_razon(self):
        """Vale para los dos: `app/` y `tests/`."""
        sin_razon = [k for k, (_, r) in RELOJES_PERMITIDOS.items() if not r.strip()]
        sin_razon += [k for k, (_, r) in RELOJES_PERMITIDOS_TESTS.items() if not r.strip()]
        assert not sin_razon, f"Entradas sin razon escrita: {sin_razon}"


class TestInventarioDeRelojesEnTests:
    """🔴 La misma guarda, para `tests/` — el agujero por donde se escapo dos veces.

    Ver el comentario de `RELOJES_PERMITIDOS_TESTS` arriba para el porque.
    """

    # Por el SUMIDERO (el campo de fecha), no por la forma del reloj: asi cubre
    # las cuatro maneras conocidas de escribirlo y las que alguien invente.
    _RELOJ = r"(?:datetime\.now\(|datetime\.utcnow\(|_dt\.now\()"
    PATRON = re.compile(
        # (a) el sumidero directo: un campo de fecha alimentado desde un reloj
        r'(?:"date"\s*:|(?<![_a-zA-Z"])date\s*=)\s*[^,\n]*?' + _RELOJ
        # (b) la escala intermedia: una variable que SE LLAMA dia y sale de un
        #     reloj (`_today = _dt.now(_tz.utc)`), que despues alimenta el campo.
        #     Sin esta rama el sumidero no la ve, porque ahi ya no hay un `now(`.
        + r"|(?:_?(?:today|hoy|fecha|dia)\w*)\s*=\s*[^,\n]*?" + _RELOJ
    )

    CASOS_QUE_DEBE_ATRAPAR = [
        '"date": datetime.now(timezone.utc).isoformat(),',
        '"date": datetime.utcnow().isoformat(),',
        '"date": datetime.now().isoformat(),',
        "date=datetime.now(timezone.utc),",
        "date=datetime.now(tz=timezone.utc),",
        "_today = _dt.now(_tz.utc)",
    ]

    CASOS_QUE_NO_DEBE_TOCAR = [
        # timestamps de auditoria: SI son instantes
        "created_at=datetime.now(timezone.utc),",
        "annulled_at = datetime.now(timezone.utc)",
        "before = datetime.now(timezone.utc)",
        # ya migrados
        '"date": business_today_noon().isoformat(),',
        "date=business_today_noon(),",
    ]

    def test_el_patron_atrapa_y_no_se_pasa(self):
        """La guarda se prueba a si misma, en los dos sentidos: un patron con un
        agujero da falsa cobertura, y uno que agarra de mas obliga a excepciones
        que lo erosionan."""
        escapan = [c for c in self.CASOS_QUE_DEBE_ATRAPAR if not self.PATRON.search(c)]
        assert not escapan, f"El patron deja escapar: {escapan}"
        sobran = [c for c in self.CASOS_QUE_NO_DEBE_TOCAR if self.PATRON.search(c)]
        assert not sobran, f"El patron agarra de mas: {sobran}"

    def test_ningun_test_fecha_un_documento_con_el_reloj_del_sistema(self):
        tests_dir = pathlib.Path(__file__).resolve().parent
        encontrados: dict[str, int] = {}
        for archivo in sorted(tests_dir.rglob("*.py")):
            if archivo.name == pathlib.Path(__file__).name:
                continue  # este archivo contiene los casos de prueba del patron
            n = len(self.PATRON.findall(archivo.read_text()))
            if n:
                encontrados[f"tests/{archivo.name}"] = n

        nuevos = {k: v for k, v in encontrados.items() if k not in RELOJES_PERMITIDOS_TESTS}
        assert not nuevos, (
            "Tests que fechan un documento con el reloj del sistema:\n  "
            + "\n  ".join(f"{k} ({v} sitio/s)" for k, v in sorted(nuevos.items()))
            + "\n\nUna fecha de negocio en un test sale de `business_today_noon()`.\n"
            "Entre las 19:00 y 24:00 hora Colombia el reloj UTC ya es del dia "
            "siguiente y el servicio rechaza el documento por 'fecha futura'.\n"
            "Si necesitas un dia pasado: `business_today() - timedelta(days=N)`, "
            "NUNCA `now(utc) - timedelta(days=1)` (dentro de la franja eso es HOY)."
        )


class TestFrontend:
    """El frontend no tiene tests ni ESLint configurado (`npm run lint` no
    corre por falta de config), asi que su guarda vive aca — es el unico gate
    que se ejecuta de verdad."""

    # `new Date().toISOString()` da el dia UTC. Para un <input type="date">
    # eso pre-llena MAÑANA entre las 19:00 y 24:00 hora Colombia.
    PATRON = re.compile(r"new Date\(\)\.toISOString\(\)")
    PERMITIDOS = {
        "src/utils/excelExport.ts": "nombre de archivo descargado, no una fecha de negocio",
    }

    def test_ningun_formulario_deriva_su_fecha_del_dia_utc(self):
        raiz = SERVICES_DIR.parent.parent.parent / "frontend"
        if not raiz.exists():  # backend solo (CI)
            pytest.skip("frontend no disponible")
        ofensores = []
        for archivo in sorted((raiz / "src").rglob("*.ts*")):
            rel = archivo.relative_to(raiz).as_posix()
            if rel in self.PERMITIDOS:
                continue
            if self.PATRON.search(archivo.read_text()):
                ofensores.append(rel)
        assert not ofensores, (
            "Derivan una fecha del dia UTC (usa `toLocalDateInput()` de "
            "src/utils/formatters.ts):\n  " + "\n  ".join(ofensores)
        )


class TestNoRegresion:
    def test_ningun_servicio_fecha_con_el_reloj_utc(self):
        """🔴 Red de seguridad sobre los 7 sitios a la vez.

        `MaterialCostHistory.transaction_date` es frontera de corte
        (`reports.py`: `transaction_date <= cutoff_date`), y las reversiones
        pasan el filtro de status — quedan decididas UNICAMENTE por su fecha.
        Fecharlas con el dia UTC las manda a mañana en la franja.
        """
        ofensores = []
        patron = re.compile(
            r"transaction_date\s*=\s*datetime\.now\(timezone\.utc\)\.date\(\)"
        )
        patron_var = re.compile(
            r"^\s*today\s*=\s*datetime\.now\(timezone\.utc\)\.date\(\)", re.MULTILINE
        )
        for archivo in sorted(SERVICES_DIR.glob("*.py")):
            texto = archivo.read_text()
            for m in patron.finditer(texto):
                linea = texto[: m.start()].count("\n") + 1
                ofensores.append(f"{archivo.name}:{linea} (transaction_date)")
            for m in patron_var.finditer(texto):
                linea = texto[: m.start()].count("\n") + 1
                ofensores.append(f"{archivo.name}:{linea} (today = ...)")

        assert not ofensores, (
            "Fechan con el reloj UTC en vez de `business_today()`:\n  "
            + "\n  ".join(ofensores)
        )

    def test_una_sola_implementacion_de_hoy(self):
        """Habia TRES implementaciones de "hoy" y dos usaban el reloj UTC.
        Ahora todas delegan en `app/utils/dates`."""
        ofensores = []
        for archivo in sorted(SERVICES_DIR.glob("*.py")):
            texto = archivo.read_text()
            # normalizacion a mediodia construida sobre now(utc)
            if re.search(
                r"datetime\.now\(timezone\.utc\)[^\n]*\n?\s*.*replace\(hour=12", texto
            ):
                ofensores.append(archivo.name)
        assert not ofensores, (
            "Normalizan a mediodia sobre el reloj UTC (deben usar "
            f"`business_today_noon()`): {ofensores}"
        )


class TestLaFechaEscritaSaleDelHelper:
    """Cada consumidor: se parchea `business_today` en SU modulo y se verifica
    que la fecha que quedo en la BD salio de ahi. Si alguien vuelve al reloj
    UTC, el parche no tiene efecto y esto revienta — a cualquier hora."""

    SENTINELA = date(2019, 3, 7)  # una fecha que no puede salir de ningun reloj

    def test_cancelar_compra_liquidada(
        self, client, org_headers, db_session, test_organization,
    ):
        from tests.integration_helpers import (
            create_material, create_material_category, create_warehouse,
        )
        from tests.conftest import create_third_party_with_category

        wh = create_warehouse(db_session, test_organization.id, "Bodega Reloj")
        cat = create_material_category(db_session, test_organization.id, "Cat Reloj")
        mat = create_material(db_session, test_organization.id, "RELOJ-1", "Chatarra", cat.id)
        sup = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Reloj", "material_supplier"
        )
        db_session.commit()

        ayer = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        resp = client.post(
            "/api/v1/purchases/", headers=org_headers,
            json={
                "supplier_id": str(sup.id), "date": ayer,
                "lines": [{
                    "material_id": str(mat.id), "warehouse_id": str(wh.id),
                    "quantity": "100", "unit_price": "1000",
                }],
            },
        )
        assert resp.status_code == 201, resp.text
        pid = resp.json()["id"]

        assert client.patch(
            f"/api/v1/purchases/{pid}/liquidate", headers=org_headers,
            json={"lines": [], "liquidation_date": ayer},
        ).status_code == 200

        with patch("app.services.purchase.business_today", return_value=self.SENTINELA):
            assert client.patch(
                f"/api/v1/purchases/{pid}/cancel", headers=org_headers,
            ).status_code == 200

        db_session.expire_all()
        fila = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.material_id == mat.id,
                MaterialCostHistory.source_type == "purchase_cancellation",
            )
        ).scalar_one()
        assert fila.transaction_date == self.SENTINELA, (
            "El checkpoint de la cancelacion no se fecho con `business_today()`"
        )

    def test_anular_ajuste_de_inventario(
        self, client, org_headers, db_session, test_organization,
    ):
        from tests.integration_helpers import (
            create_material, create_material_category, create_warehouse,
        )

        wh = create_warehouse(db_session, test_organization.id, "Bodega Reloj Aj")
        cat = create_material_category(db_session, test_organization.id, "Cat Reloj Aj")
        mat = create_material(db_session, test_organization.id, "RELOJ-2", "Chatarra", cat.id)
        db_session.commit()

        ayer = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        resp = client.post(
            "/api/v1/inventory/adjustments/increase", headers=org_headers,
            json={
                "material_id": str(mat.id), "warehouse_id": str(wh.id),
                "quantity": "50", "unit_cost": "2000",
                "date": ayer, "reason": "Prueba reloj",
            },
        )
        assert resp.status_code == 201, resp.text
        aid = resp.json()["id"]

        with patch(
            "app.services.inventory_adjustment.business_today",
            return_value=self.SENTINELA,
        ):
            r = client.post(
                f"/api/v1/inventory/adjustments/{aid}/annul", headers=org_headers,
                json={"reason": "Prueba reloj"},
            )
            assert r.status_code == 200, r.text

        db_session.expire_all()
        fila = db_session.execute(
            select(MaterialCostHistory).where(
                MaterialCostHistory.material_id == mat.id,
                MaterialCostHistory.source_type == "adjustment_annulment",
            )
        ).scalar_one()
        assert fila.transaction_date == self.SENTINELA


class TestValidadoresConUnSoloReloj:
    """🔴 Los guards de "fecha no futura" topan con el MISMO reloj con que se
    acuñan las fechas. Antes eran dos relojes distintos y producian un estado
    imposible."""

    def test_compra_de_manana_se_rechaza_al_crear(
        self, client, org_headers, db_session, test_organization,
    ):
        """El bug: `now(utc).date()` aceptaba una fecha de negocio de MAÑANA
        entre las 19:00 y 24:00 hora Colombia — y la compra quedaba en un estado
        imposible (ver el test siguiente). Ahora el tope es el dia de negocio.

        Se parchea el helper en el modulo de compras con un dia PASADO: cualquier
        fecha de hoy queda "en el futuro" respecto de ese tope. Si alguien vuelve
        al reloj UTC, el parche no tiene efecto, la compra se crea y esto revienta.
        """
        from tests.integration_helpers import (
            create_material, create_material_category, create_warehouse,
        )
        from tests.conftest import create_third_party_with_category

        wh = create_warehouse(db_session, test_organization.id, "Bodega Futuro")
        cat = create_material_category(db_session, test_organization.id, "Cat Futuro")
        mat = create_material(db_session, test_organization.id, "FUT-1", "Chatarra", cat.id)
        sup = create_third_party_with_category(
            db_session, test_organization.id, "Proveedor Futuro", "material_supplier"
        )
        db_session.commit()

        hoy = business_today().isoformat()
        anteayer = business_today() - timedelta(days=2)

        with patch("app.services.purchase.business_today", return_value=anteayer):
            resp = client.post(
                "/api/v1/purchases/", headers=org_headers,
                json={
                    "supplier_id": str(sup.id), "date": hoy,
                    "lines": [{
                        "material_id": str(mat.id), "warehouse_id": str(wh.id),
                        "quantity": "10", "unit_price": "1000",
                    }],
                },
            )

        assert resp.status_code == 400, (
            "La fecha se comparo contra un reloj distinto al parcheado — el "
            f"validador no esta usando business_today(). Respuesta: {resp.text}"
        )
        assert "futura" in resp.json()["detail"].lower()

    def test_los_dos_validadores_de_compra_usan_el_mismo_reloj(self):
        """🔴 El estado imposible, clavado como propiedad del codigo.

        Con dos relojes, una compra creada de noche con fecha de mañana pasaba
        el guard de creacion (UTC vs UTC) y despues NO se podia liquidar nunca:
        la liquidacion exige `liq >= fecha_doc` (= mañana) y `liq <= hoy`, un
        intervalo vacio, con dos mensajes que se contradicen.

        La unica defensa estructural es que ambos guards lean la MISMA funcion.
        """
        fuente = (SERVICES_DIR / "purchase.py").read_text()
        assert "if obj_in.date.date() > business_today():" in fuente, (
            "El validador de fecha de compra dejo de usar business_today()"
        )
        assert "if liq_date > business_today():" in fuente, (
            "El validador de fecha de liquidacion dejo de usar business_today()"
        )
        # Y que no haya quedado ningun otro reloj en el archivo
        assert not TestInventarioDeRelojes.PATRON.search(fuente), (
            "purchase.py volvio a derivar un dia fuera del helper"
        )
