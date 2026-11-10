"""
Tests del cargador de la carga inicial de SAC (scripts/load_sac_opening.py).

Plan: docs/planes/plan-sac-carga-inicial-ronda1.md §8 (T1-T13). Todo es PURO: el
libro se arma en memoria y el backend es un falso que anota las llamadas, asi que
no hace falta base de datos. La prueba de verdad es la ronda corrida contra la
SAC local y su informe de conciliacion; esto fija las reglas que la sostienen.

Las fechas son fijas y lejanas a proposito (corte 2020-01-31): si algun paso
tomara la fecha del reloj, T12 lo ve.
"""
import importlib.util
import pathlib
import sys
from datetime import date
from decimal import Decimal

import pytest

_SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "load_sac_opening.py"
_spec = importlib.util.spec_from_file_location("load_sac_opening", _SCRIPT)
L = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = L  # @dataclass busca el modulo aqui
_spec.loader.exec_module(L)

CORTE = date(2020, 1, 31)


# ---------------------------------------------------------------------------
# Libro sintetico
# ---------------------------------------------------------------------------

def _tercero(nombre, seccion, saldo, tipo, entra="Sí", nit=None, fila=2):
    return {"_fila": fila, "nombre": nombre, "seccion": seccion, "saldo": saldo,
            "tipo": tipo, "nit": nit, "entra": entra}


def _libro(**pestanas):
    base = {
        "Inicio": [],
        "Terceros": [],
        "Créditos": [],
        "Cuentas": [],
        "Inventario": [],
        "Kilos": [],
        "Activos fijos": [],
        "Entradas por liquidar": [],
    }
    base.update(pestanas)
    return base


def _plan(ensayo=True, **pestanas):
    return L.armar_plan(_libro(**pestanas), CORTE, ensayo=ensayo)


def _pasos(plan, tipo):
    return [p for p in plan.pasos if p.tipo == tipo]


def _inv(material, bodega, cantidad, precio, entra="Sí", fila=2, ubic="BODEGA"):
    return {"_fila": fila, "material_balance": material, "ubicacion": ubic,
            "cantidad": cantidad, "precio": precio, "material": material,
            "bodega": bodega, "entra": entra}


# ---------------------------------------------------------------------------
# T1 — solo «Sí» entra; todo lo demas llega a exclusiones con su motivo
# ---------------------------------------------------------------------------

class TestSoloEntraSi:
    def test_si_entra_y_el_resto_se_excluye_con_motivo(self):
        plan = _plan(Terceros=[
            _tercero("A", "Por cobrar", 100, "Cliente", "Sí", fila=2),
            _tercero("B", "Por cobrar", 200, "Sede (no es tercero)", "No", fila=3),
            _tercero("C", "Por pagar", -300, "Proveedor de material", "Preguntar", fila=4),
        ])
        assert [p.nombre for p in _pasos(plan, "third_party")] == ["A"]
        motivos = {e.nombre: e.motivo for e in plan.exclusiones}
        assert motivos == {
            "B": "Marcada «No» (Sede (no es tercero))",
            "C": "Marcada «Preguntar» (Proveedor de material)",
        }
        # Lo excluido conserva su monto y su rubro: es lo que explica la diferencia.
        b = next(e for e in plan.exclusiones if e.nombre == "B")
        assert (b.rubro, b.monto) == ("Cuentas por cobrar", Decimal("200"))

    def test_las_otras_pestanas_tambien_excluyen(self):
        plan = _plan(
            Cuentas=[{"_fila": 2, "nombre": "X", "saldo": 5, "tipo": "Banco", "cuenta": "X", "entra": "No"}],
            **{"Activos fijos": [{"_fila": 2, "nombre": "DEP GLOBAL", "valor": -280, "fecha": None,
                                  "vida": None, "residual": None, "depreciacion": None, "entra": "Repartir"}]},
        )
        assert {(e.pestana, e.motivo) for e in plan.exclusiones} == {
            ("Cuentas", "Marcada «No»"),
            ("Activos fijos", "Marcada «Repartir»"),
        }
        assert not _pasos(plan, "account") and not _pasos(plan, "fixed_asset")


# ---------------------------------------------------------------------------
# T2 — el signo: se lee la columna con signo, no el saldo del balance
# ---------------------------------------------------------------------------

class TestSigno:
    def test_por_pagar_carga_negativo(self):
        plan = _plan(Terceros=[_tercero("PROV", "Por pagar", "-1.234.567", "Proveedor de material")])
        (p,) = _pasos(plan, "third_party")
        assert p.esperado == Decimal("-1234567")
        assert p.payload["initial_balance"] == "-1234567"
        assert p.rubro == "Cuentas por pagar"

    def test_lo_que_se_manda_es_lo_que_se_espera(self):
        """`initial_balance` (lo que viaja) y `esperado` (contra lo que se concilia)
        se calculan por separado: si divergen, la carga escribe un numero y el
        informe lo compara contra otro. Se afirma en TODO paso con saldo."""
        plan = _plan(
            Terceros=[
                _tercero("CLI", "Por cobrar", 100, "Cliente", fila=2),
                _tercero("PROV", "Por pagar", -40, "Proveedor de material", fila=3),
                _tercero("WILLARD", "Por pagar", -9, L.TIPO_WILLARD, fila=4),
            ],
            Cuentas=[{"_fila": 2, "nombre": "BBVA", "saldo": 55, "tipo": "Banco",
                      "cuenta": "Cta Cte BBVA", "entra": "Sí"}],
            Inventario=[_inv("PLO-LIN", "Juan Mina", 3, "5.543,5")],
            **{"Créditos": [
                _credito("BANCO X", capital=500, fila=2),
                _credito("INTERESES X", intereses=70, fila=3),
            ]},
        )
        assert not plan.errores, plan.errores
        con_saldo = [p for p in plan.pasos if "initial_balance" in p.payload]
        assert len(con_saldo) == 6  # CLI, PROV, Willard, BBVA y los dos creditos
        for p in con_saldo:
            assert Decimal(p.payload["initial_balance"]) == p.esperado, p.nombre
            assert sum(p.piezas.values()) == p.esperado, p.nombre
        (inc,) = _pasos(plan, "increase")
        valor = Decimal(inc.payload["quantity"]) * Decimal(inc.payload["unit_cost"])
        assert abs(valor - inc.esperado) <= Decimal("0.01")

    def test_numeros_con_formato_es_co(self):
        assert L.a_decimal("1.234.567,89") == Decimal("1234567.89")
        assert L.a_decimal("20.158") == Decimal("20158")
        assert L.a_decimal("-") == Decimal("0")
        assert L.a_decimal(None) == Decimal("0")
        assert L.a_decimal(8520.408163265307) == Decimal("8520.408163265307")


# ---------------------------------------------------------------------------
# T3 — Willard: un solo saldo neto, con las categorias del seeder
# ---------------------------------------------------------------------------

class TestWillard:
    def _plan(self):
        return _plan(Terceros=[
            _tercero("WILLARD MAQUILAS", "Por cobrar", 1000, L.TIPO_WILLARD.upper(), fila=2),
            _tercero("WILLARD", "Por cobrar", 500, "Willard (se suman en un tercero)", fila=3),
            _tercero("MATERIALES WILLARD", "Por pagar", -900, "Willard (se suman en un tercero)", fila=4),
        ])

    def test_se_suman_en_willard_sa(self):
        plan = self._plan()
        (w,) = _pasos(plan, "third_party")
        cats_seeder = dict(L.seed.THIRD_PARTIES)[L.WILLARD]
        assert w.nombre == L.WILLARD
        assert w.esperado == Decimal("600")
        assert w.payload["categorias"] == cats_seeder
        assert w.rubro == "Cuentas por cobrar"
        assert w.piezas == {"Cuentas por cobrar": Decimal("1500"), "Cuentas por pagar": Decimal("-900")}

    def test_el_neto_se_explica_en_los_dos_rubros(self):
        exp = L.explicar_rubros(self._plan())
        assert sum(m for _, m in exp["Cuentas por pagar"]) == Decimal("-900")
        assert sum(m for _, m in exp["Cuentas por cobrar"]) == Decimal("900")

    def test_ningun_paso_usa_el_endpoint_de_balance(self):
        """`POST /third-parties/{id}/balance` mueve el saldo sin movimiento y rompe
        #55. La apertura va SOLO por `initial_balance` al crear (G1)."""
        api = FakeApi()
        L.aplicar(self._plan(), "saldos", api)
        assert api.posts and not [p for p, _ in api.posts if p.endswith("/balance")]


# ---------------------------------------------------------------------------
# T4 — fila «Sí» incompleta: se salta con --ensayo, detiene sin el
# ---------------------------------------------------------------------------

class TestIncompleta:
    def test_sin_tipo_con_ensayo_es_exclusion(self):
        plan = _plan(ensayo=True, Terceros=[_tercero("NUEVO", "Por pagar", -5, "")])
        assert not plan.errores
        (e,) = plan.exclusiones
        assert e.motivo == "«Sí» sin Tipo" and e.monto == Decimal("-5")

    def test_sin_tipo_sin_ensayo_es_error(self):
        plan = _plan(ensayo=False, Terceros=[_tercero("NUEVO", "Por pagar", -5, "")])
        assert plan.errores and "sin Tipo" in plan.errores[0]

    def test_tipo_que_no_se_carga_es_error(self):
        plan = _plan(Terceros=[_tercero("BOG", "Por cobrar", 5, "Sede (no es tercero)")])
        assert plan.errores and "que no se carga" in plan.errores[0]


# ---------------------------------------------------------------------------
# T5 — nombres repetidos
# ---------------------------------------------------------------------------

class TestRepetidos:
    def test_nombre_repetido_es_error(self):
        plan = _plan(Terceros=[
            _tercero("Juan Pérez", "Por cobrar", 1, "Cliente", fila=2),
            _tercero("JUAN PEREZ", "Por cobrar", 2, "Cliente", fila=3),
        ])
        assert any("Nombre repetido" in e for e in plan.errores)

    def test_repetido_con_no_no_cuenta(self):
        plan = _plan(Terceros=[
            _tercero("BODEGA BOGOTA", "Por cobrar", 1, "Sede (no es tercero)", "No", fila=2),
            _tercero("BODEGA BOGOTA", "Por pagar", -2, "Sede (no es tercero)", "No", fila=3),
        ])
        assert not plan.errores


# ---------------------------------------------------------------------------
# T6 — inventario: agrupa, conserva el valor, y no carga netos <= 0
# ---------------------------------------------------------------------------

class TestInventario:
    def test_agrupa_por_material_y_bodega_y_conserva_valor(self):
        plan = _plan(Inventario=[
            _inv("PLO-LIN", "Juan Mina", 100, 5543, fila=2),
            _inv("PLO-LIN", "Juan Mina", -30, 5543, fila=3),
            _inv("PLO-LIN", "Juan Mina", 50, 6000, fila=4),
        ])
        (p,) = _pasos(plan, "increase")
        assert Decimal(p.payload["quantity"]) == Decimal("120")
        valor_hojas = Decimal(100 * 5543 - 30 * 5543 + 50 * 6000)
        assert abs(p.esperado - valor_hojas) <= Decimal("1")
        assert p.payload["reason"] == L.MARCADOR
        assert p.payload["reason"].startswith("Carga inicial migracion")

    def test_neto_negativo_va_a_exclusion(self):
        plan = _plan(Inventario=[
            _inv("SCR-LSB", "Circunvalar", -14, 1950, fila=2),
        ])
        assert not _pasos(plan, "increase")
        (e,) = plan.exclusiones
        assert e.monto == Decimal("-27300") and "negativo" in e.motivo

    def test_ver_hoja_kilos_es_exclusion_con_su_motivo(self):
        plan = _plan(Inventario=[_inv("PB POSC", "", -10, 4043, entra="Ver hoja Kilos", fila=2)])
        (e,) = plan.exclusiones
        assert e.motivo.startswith("Va por Kilos") and e.monto == Decimal("-40430")


def _entrada(numero, material, cantidad, bodega="Circunvalar", fila=2, fecha="13/05/2019"):
    return {"_fila": fila, "numero": numero, "fecha": fecha, "origen": "COEXITO",
            "cantidad": cantidad, "material": material, "bodega": bodega}


class TestComprasPorLiquidar:
    """La compra sin liquidar ya esta en la bodega de Johana pero todavia no en el
    sistema: se descuenta de su bodega y la entrada abierta la suma al liquidarse.
    Cargarla bruta la contaria dos veces."""

    def _plan(self, cant_entrada=2, bodega_fila="Circunvalar"):
        return _plan(
            Inventario=[
                _inv("BAT-G07", "Circunvalar", 698, 20158, fila=2),
                _inv("BAT-G07", bodega_fila, -2, 20158, entra="Ver hoja Entradas", fila=3,
                     ubic="COMPRAS POR LIQUIDAR"),
            ],
            **{"Entradas por liquidar": [_entrada(14744, "BAT-G07", cant_entrada)]},
        )

    def test_se_descuenta_de_su_bodega_y_no_es_exclusion(self):
        plan = self._plan()
        assert not plan.errores, plan.errores
        (inc,) = _pasos(plan, "increase")
        assert Decimal(inc.payload["quantity"]) == Decimal("696")
        assert inc.esperado == Decimal(696 * 20158)
        assert not plan.exclusiones
        (cruce,) = [c for c in plan.cruces if "Compra sin liquidar" in c[0]]
        assert cruce[1] == cruce[2] == Decimal("2")
        (ent,) = _pasos(plan, "inbound_order")
        assert ent.payload["lineas"] == [{"codigo": "BAT-G07", "quantity": "2.000"}]

    def test_inventario_y_entradas_que_no_cuadran_es_error(self):
        plan = self._plan(cant_entrada=3)
        assert any("Inventario descuenta 2 y Entradas abre 3" in e for e in plan.errores)

    def test_entrada_sin_su_fila_en_inventario_es_error(self):
        plan = _plan(**{"Entradas por liquidar": [_entrada(1, "BAT-G3", 1)]})
        assert any("Inventario descuenta 0 y Entradas abre 1" in e for e in plan.errores)

    def test_fila_sin_bodega_es_error(self):
        plan = self._plan(bodega_fila="")
        assert any("no se sabe de qué bodega descontar" in e for e in plan.errores)

    def test_material_desconocido_o_crear_es_error(self):
        plan = _plan(Inventario=[
            _inv("NO-EXISTE", "Circunvalar", 1, 1, fila=2),
            _inv("Crear material nuevo", "Circunvalar", 1, 1, fila=3),
        ])
        assert len(plan.errores) == 2

    def test_material_nuevo_crea_categoria_y_material(self):
        plan = _plan(Inventario=[_inv("EST-PLA", "Juan Mina", 10, 115000)])
        assert [p.nombre for p in _pasos(plan, "material")] == ["EST-PLA"]
        assert [p.nombre for p in _pasos(plan, "material_category")] == ["Estaño"]
        (m,) = _pasos(plan, "material")
        assert m.payload["perfil"]["lead_product"] == "none"

    def test_bodega_de_transito_no_recibe_carga(self):
        plan = _plan(Inventario=[_inv("PLO-LIN", "Juan Mina - Transito", 10, 1)])
        assert plan.errores and "tránsito" in plan.errores[0]


# ---------------------------------------------------------------------------
# T7 — valores provisionales solo con --ensayo; --ensayo solo en local
# ---------------------------------------------------------------------------

def _activo(entra="Sí", fecha=None, vida=None, valor=1000):
    return {"_fila": 2, "nombre": "CAMION", "valor": valor, "fecha": fecha, "vida": vida,
            "residual": None, "depreciacion": None, "entra": entra}


class TestProvisional:
    def test_activo_sin_vida_util_con_ensayo_es_provisional(self):
        plan = _plan(ensayo=True, **{"Activos fijos": [_activo()]})
        (a,) = _pasos(plan, "fixed_asset")
        assert a.nombre.endswith(L.SUFIJO_PROVISIONAL)
        assert a.payload["purchase_date"] == CORTE.isoformat()
        assert a.payload["historical_load"] is True
        assert Decimal(a.payload["depreciation_rate"]) == (Decimal(100) / L.VIDA_UTIL_PROVISIONAL).quantize(Decimal("0.01"))

    def test_activo_sin_vida_util_sin_ensayo_es_error(self):
        plan = _plan(ensayo=False, **{"Activos fijos": [_activo()]})
        assert not _pasos(plan, "fixed_asset") and plan.errores

    def test_activo_completo_no_es_provisional(self):
        plan = _plan(ensayo=False, **{"Activos fijos": [_activo(fecha=date(2019, 5, 1), vida=60)]})
        (a,) = _pasos(plan, "fixed_asset")
        assert a.nombre == "CAMION" and not plan.errores

    def test_ensayo_contra_remoto_se_niega(self):
        api = L.seed.APIClient(dry_run=True, base_url="https://api.ecobalance.cc")
        with pytest.raises(SystemExit, match="solo corre contra un backend local"):
            L.validar_destino(api, ensayo=True)
        with pytest.raises(SystemExit, match="remoto no está habilitada"):
            L.validar_destino(api, ensayo=False)
        L.validar_destino(L.seed.APIClient(dry_run=True, base_url="http://localhost:8000"), ensayo=True)


# ---------------------------------------------------------------------------
# T8 — categorias: credito, intereses, empleado
# ---------------------------------------------------------------------------

def _credito(acreedor, capital=None, intereses=None, tercero=None, entra="Sí", fila=2):
    return {"_fila": fila, "acreedor": acreedor, "tercero": tercero, "capital": capital,
            "intereses": intereses, "entra": entra}


class TestCategorias:
    def test_credito_intereses_y_empleado(self):
        plan = _plan(
            Terceros=[_tercero("PEPE", "Por cobrar", 10, "Empleado")],
            **{"Créditos": [
                _credito("ABDEL", capital=500, tercero="ABDEL - Crédito", fila=2),
                _credito("INTERESES ABDEL", intereses=70, tercero="ABDEL - Intereses", fila=3),
            ]},
        )
        cats = {p.nombre: p.payload["categorias"] for p in _pasos(plan, "third_party")}
        assert cats == {
            "PEPE": ["Empleados"],
            "ABDEL - Crédito": ["Obligaciones Financieras"],
            "ABDEL - Intereses": ["Pasivo"],
        }
        montos = {p.nombre: p.esperado for p in _pasos(plan, "third_party")}
        assert montos["ABDEL - Crédito"] == Decimal("-500")
        assert montos["ABDEL - Intereses"] == Decimal("-70")

    def test_las_categorias_nuevas_cumplen_lo_que_el_sistema_exige(self):
        # financial_obligation.py: investor + "obligaci" en el nombre
        assert L.CATEGORIAS_NUEVAS[L.CATEGORIA_CREDITO] == "investor"
        assert "obligaci" in L.CATEGORIA_CREDITO.lower()
        assert L.CATEGORIAS_NUEVAS["Empleados"] == "generic"
        # "Pasivo" la siembra create_organization: no se crea
        assert L.CATEGORIA_INTERESES not in L.CATEGORIAS_NUEVAS

    def test_credito_sin_nombre_en_el_sistema_usa_el_del_balance(self):
        plan = _plan(**{"Créditos": [_credito("LEASING 1", capital=9)]})
        assert [p.nombre for p in _pasos(plan, "third_party")] == ["LEASING 1"]

    def test_terceros_ver_hoja_creditos_cruza_con_creditos(self):
        plan = _plan(
            Terceros=[_tercero("ABDEL", "Por pagar", -500, "Crédito (ver hoja Créditos)", "Ver hoja Créditos")],
            **{"Créditos": [_credito("ABDEL", capital=500)]},
        )
        assert not plan.errores and plan.cruces

    def test_terceros_y_creditos_con_montos_distintos_es_error(self):
        plan = _plan(
            Terceros=[_tercero("ABDEL", "Por pagar", -500, "Crédito (ver hoja Créditos)", "Ver hoja Créditos")],
            **{"Créditos": [_credito("ABDEL", capital=400)]},
        )
        assert any("Terceros fila" in e and "Créditos dice" in e for e in plan.errores)

    def test_ver_hoja_creditos_sin_fila_en_creditos_es_error(self):
        plan = _plan(Terceros=[
            _tercero("FANTASMA", "Por pagar", -1, "Crédito (ver hoja Créditos)", "Ver hoja Créditos"),
        ])
        assert any("no está en Créditos" in e for e in plan.errores)


# ---------------------------------------------------------------------------
# T9 — se lee por encabezado: una columna que falta detiene y se nombra
# ---------------------------------------------------------------------------

def _xlsx(tmp_path, quitar=None):
    from openpyxl import Workbook

    wb = Workbook()
    wb.remove(wb.active)
    encabezados = {
        "Terceros": ["Nombre en el balance", "Sección", "Saldo al 31-oct ($)",
                     "Saldo en el sistema ($): + nos debe", "Tipo en el sistema",
                     "NIT o cédula", "¿Entra al sistema?"],
        "Cuentas": ["Nombre en el balance", "Saldo al 31-oct ($)", "Tipo",
                    "Cuenta en el sistema", "Sede", "¿Entra al sistema?"],
        "Inventario": ["Material en el balance", "Ubicación (columna del balance)", "Cantidad (kg)",
                       "Precio ($ por kg)", "Valor ($)", "Material en el sistema",
                       "Bodega en el sistema", "¿Entra al sistema?"],
        "Activos fijos": ["Activo", "Valor en el balance ($)", "Fecha de compra", "Vida útil (meses)",
                          "Valor residual ($)", "Depreciación acumulada al corte ($)", "Sede",
                          "¿Entra al sistema?"],
        "Créditos": ["Acreedor (como está en el balance)", "Tercero en el sistema", "Capital al corte ($)",
                     "Intereses causados sin pagar ($)", "¿Entra al sistema?"],
        "Entradas por liquidar": ["Número de compra", "Fecha", "Origen", "Material en el balance",
                                  "Cantidad", "Material en el sistema", "Bodega en el sistema"],
    }
    for nombre, cols in encabezados.items():
        ws = wb.create_sheet(nombre)
        ws.append([c for c in cols if c != quitar])
    wb.create_sheet("Kilos").append(["Cuenta en plomo del sistema", "Qué es", "Kilos"])
    wb.create_sheet("Inicio").append(["Carga inicial de SAC"])
    t = wb["Terceros"]
    # C (saldo del balance) y D (con signo) DISTINTAS: si son iguales, leer la
    # columna equivocada no se ve.
    t.append(["ACME", "Por pagar", 10, -10, "Proveedor de material", None, "Sí"])
    p = tmp_path / "carga.xlsx"
    wb.save(p)
    return p


class TestEncabezados:
    def test_libro_completo_se_lee_por_encabezado(self, tmp_path):
        libro = L.leer_libro(str(_xlsx(tmp_path)))
        (fila,) = libro["Terceros"]
        assert (fila["nombre"], fila["saldo"], fila["entra"]) == ("ACME", -10, "Sí")

    def test_columna_faltante_detiene_y_se_nombra(self, tmp_path):
        with pytest.raises(L.ErrorDeLibro, match="«saldo en el sistema»"):
            L.leer_libro(str(_xlsx(tmp_path, quitar="Saldo en el sistema ($): + nos debe")))

    def test_columna_nueva_de_creditos_es_obligatoria(self, tmp_path):
        with pytest.raises(L.ErrorDeLibro, match="«tercero en el sistema»"):
            L.leer_libro(str(_xlsx(tmp_path, quitar="Tercero en el sistema")))


# ---------------------------------------------------------------------------
# T10 — conciliacion
# ---------------------------------------------------------------------------

def _sistema_que_cuadra(plan):
    s = {k: {} for k in ("terceros", "cuentas", "activos", "terceros_nombres", "cuentas_nombres",
                         "activos_nombres", "valor_material", "stock_bodega", "kg")}
    for p in plan.pasos:
        if p.tipo == "third_party":
            s["terceros"][L.clave(p.nombre)] = p.esperado
            s["terceros_nombres"][L.clave(p.nombre)] = (p.nombre, p.esperado)
        elif p.tipo == "account":
            s["cuentas"][L.clave(p.nombre)] = p.esperado
            s["cuentas_nombres"][L.clave(p.nombre)] = (p.nombre, p.esperado)
        elif p.tipo == "increase":
            c = p.payload["codigo"]
            s["valor_material"][c] = s["valor_material"].get(c, Decimal("0")) + p.esperado
            s["stock_bodega"][(c, L.clave(p.payload["bodega"]))] = Decimal(p.payload["quantity"])
    return s


class TestConciliacion:
    def _plan(self):
        return _plan(
            Terceros=[
                _tercero("A", "Por cobrar", 100, "Cliente", fila=2),
                _tercero("B", "Por pagar", -40, "Proveedor de material", fila=3),
                _tercero("C", "Por cobrar", 7, "Sede (no es tercero)", "No", fila=4),
            ],
            Inventario=[_inv("PLO-LIN", "Juan Mina", 10, 5)],
        )

    def test_todo_cuadra(self):
        plan = self._plan()
        comps, sobrantes = L.comparar_entidades(plan, _sistema_que_cuadra(plan))
        assert comps and all(c.cuadra for c in comps) and not sobrantes

    def test_una_diferencia_sembrada_sale_sin_explicar(self):
        plan = self._plan()
        s = _sistema_que_cuadra(plan)
        s["terceros"][L.clave("A")] = Decimal("90")
        comps, _ = L.comparar_entidades(plan, s)
        (mala,) = [c for c in comps if not c.cuadra]
        assert mala.entidad == "Tercero A" and mala.diferencia == Decimal("-10")

    def test_un_tercero_ausente_no_cuadra(self):
        plan = self._plan()
        s = _sistema_que_cuadra(plan)
        del s["terceros"][L.clave("B")]
        comps, _ = L.comparar_entidades(plan, s)
        assert [c.entidad for c in comps if not c.cuadra] == ["Tercero B"]

    def test_saldo_que_la_carga_no_puso_es_sobrante(self):
        plan = self._plan()
        s = _sistema_que_cuadra(plan)
        s["terceros_nombres"]["intruso"] = ("Intruso", Decimal("55"))
        _, sobrantes = L.comparar_entidades(plan, s)
        assert sobrantes == [("Tercero Intruso", Decimal("55"))]

    def test_johana_es_cargado_mas_excluido(self):
        plan = self._plan()
        exp = L.explicar_rubros(plan)
        cargado_cxc = sum(p.esperado for p in _pasos(plan, "third_party") if p.rubro == "Cuentas por cobrar")
        excluido_cxc = sum(m for _, m in exp["Cuentas por cobrar"])
        assert cargado_cxc + excluido_cxc == Decimal("107")

    def _informe(self, johana_cxc, corte_distinto=False):
        plan = _plan(Terceros=[_tercero("A", "Por cobrar", 100, "Cliente")])
        plan.johana = {r: Decimal("0") for r in L.RUBROS}
        plan.johana["Cuentas por cobrar"] = Decimal(johana_cxc)
        s = _sistema_que_cuadra(plan)
        s["balance"] = {"assets": {"accounts_receivable": 100}, "total_assets": 100,
                        "total_liabilities": 0, "equity": 100}
        s["balance_corte"] = {**s["balance"], "assets": {"accounts_receivable": 90 if corte_distinto else 100}}
        s["utilidad"] = Decimal("0")
        return L.informe(plan, s, "libro de prueba")

    def test_informe_sin_diferencias_da_cero_fallas(self):
        texto, fallas = self._informe(100)
        assert fallas == 0 and "**Resultado: 0 fallas.**" in texto

    def test_rubro_sin_explicar_es_una_falla(self):
        """El gate de la ronda 1 calculaba «Sin explicar» y no lo contaba: dos
        rubros con diferencia y «0 fallas»."""
        texto, fallas = self._informe(150)
        assert fallas == 1
        assert "| Cuentas por cobrar | 150 | 100 | 50 | 0 | 50 |" in texto

    def test_rubro_sin_total_de_johana_es_una_falla(self):
        plan = _plan(Terceros=[_tercero("A", "Por cobrar", 100, "Cliente")])  # sin Inicio
        s = _sistema_que_cuadra(plan)
        s["balance"] = s["balance_corte"] = {"assets": {"accounts_receivable": 100}, "total_assets": 100,
                                             "total_liabilities": 0, "equity": 100}
        s["utilidad"] = Decimal("0")
        _, fallas = L.informe(plan, s, "libro de prueba")
        assert fallas == len(L.RUBROS)

    def test_corte_distinto_de_hoy_es_una_falla(self):
        _, fallas = self._informe(100, corte_distinto=True)
        assert fallas == 1

    def test_ver_hoja_kilos_no_explica_una_diferencia(self):
        """La deuda en plomo el sistema la muestra DENTRO de Inventario: listarla
        tambien como exclusion la contaba dos veces (ronda 1: +183,6 M sin explicar)."""
        plan = _plan(Inventario=[_inv("PB POSC", "", -10, 4043, entra="Ver hoja Kilos")])
        assert L.explicar_rubros(plan)["Inventario"] == []

    def test_rubros_del_sistema_detecta_seccion_sin_mapa(self):
        balance = {
            "assets": {"cash_and_bank": 10, "accounts_receivable": 5, "inventory": 3,
                       "fixed_assets": 0, "investor_receivable": 0, "seccion_nueva": 4,
                       "lead_debt_willard": {"value": -1}},
            "total_assets": 21, "total_liabilities": 6,
        }
        rubros, sin_rubro = L.rubros_del_sistema(balance)
        assert rubros["Inventario"] == Decimal("2")
        assert rubros["Cuentas por pagar"] == Decimal("-6")
        assert sin_rubro == Decimal("4")  # la seccion nueva no cayo en ningun rubro


class TestTrasladoACuentas:
    """Un tercero del balance que en el sistema es una cuenta de dinero (EFECTIVO
    INGRID = Caja Green Loop): Johana lo tiene en Cuentas por cobrar y el sistema
    en Disponible. Es un traslado, y explica las dos puntas."""

    def _plan(self, saldo_cuenta=66, entra_cuenta="Sí"):
        return _plan(
            Terceros=[_tercero("EFECTIVO INGRID", "Por cobrar", 66, "Otro", "Ver hoja Cuentas")],
            Cuentas=[{"_fila": 2, "nombre": "EFECTIVO INGRID", "saldo": saldo_cuenta, "tipo": "Efectivo",
                      "cuenta": "Caja Green Loop", "entra": entra_cuenta}],
        )

    def test_explica_las_dos_puntas(self):
        plan = self._plan()
        assert not plan.errores, plan.errores
        exp = L.explicar_rubros(plan)
        assert [m for _, m in exp["Cuentas por cobrar"]] == [Decimal("66")]
        assert [m for _, m in exp["Disponible"]] == [Decimal("-66")]
        assert [p.nombre for p in _pasos(plan, "account")] == ["Caja Green Loop"]
        assert not _pasos(plan, "third_party")

    def test_monto_distinto_es_error(self):
        plan = self._plan(saldo_cuenta=60)
        assert any("Terceros fila 2 dice 66 y Cuentas dice 60" in e for e in plan.errores)

    def test_sin_cuenta_cargada_es_error(self):
        plan = self._plan(entra_cuenta="No")
        assert any("no hay una fila «Sí» con ese nombre" in e for e in plan.errores)


# ---------------------------------------------------------------------------
# T11 — precondiciones: una fase no corre sobre una org que no le corresponde
# ---------------------------------------------------------------------------

# Las que siembra create_organization en toda org nueva
CATEGORIAS_POR_DEFECTO = ["Proveedor Material", "Proveedor Servicios", "Cliente", "Socios",
                          "Genérico", "Provisión", "Pasivo"]


class FakeApi:
    """Backend falso: responde los GET con lo que se le cargue y anota los POST."""

    def __init__(self, gets=None):
        self.gets = {"/third-party-categories/flat": {"items": [
            {"name": n, "id": f"cat-{n}"} for n in CATEGORIAS_POR_DEFECTO]}}
        self.gets.update(gets or {})
        self.posts: list[tuple[str, dict]] = []
        self.puts: list[tuple[str, dict]] = []
        self.is_local = True
        self.base_url = "http://localhost:8000"
        self._n = 0

    def get(self, path, params=None):
        if path in self.gets:
            return self.gets[path]
        if path == "/kg-ledger/summary":
            return {"accounts": []}
        if path == "/third-parties" and params == {"limit": 1}:
            return {"items": [], "total": 0}
        return {"items": [], "total": 0}

    def post(self, path, body, label=""):
        self._n += 1
        self.posts.append((path, body))
        return {"id": f"id-{self._n}"}

    def put(self, path, body, label=""):
        self.puts.append((path, body))
        return {}


class TestPrecondiciones:
    def test_saldos_se_niega_si_la_org_no_esta_vacia(self):
        api = FakeApi({"/warehouses": {"items": [{"name": "Circunvalar", "id": "w"}], "total": 1}})
        with pytest.raises(SystemExit, match="org VACÍA"):
            L.aplicar(_plan(), "saldos", api)
        assert not api.posts

    def test_resto_se_niega_sin_los_maestros_del_seeder(self):
        with pytest.raises(SystemExit, match="maestros del seeder"):
            L.aplicar(_plan(), "resto", FakeApi())

    def test_resto_se_niega_si_ya_hay_carga(self):
        bodegas = [{"name": w[0], "id": w[0]} for w in L.seed.WAREHOUSES]
        cuentas = [{"code": c[0], "id": c[0]} for c in L.seed.KG_ACCOUNTS]
        api = FakeApi({
            "/warehouses": {"items": bodegas, "total": len(bodegas)},
            "/kg-ledger/accounts": cuentas,
            "/inventory/adjustments": {"items": [{"id": "x"}], "total": 1},
        })
        with pytest.raises(SystemExit, match="sin operaciones"):
            L.aplicar(_plan(), "resto", api)
        assert not api.posts

    def test_referencia_faltante_detiene_antes_de_escribir(self):
        """Una categoria que la org no tiene ni nace en la fase: SystemExit que la
        nombra, y CERO escrituras (antes era un KeyError a mitad del bucle)."""
        api = FakeApi({"/third-party-categories/flat": {"items": [{"name": "Cliente", "id": "c"}]}})
        plan = _plan(Terceros=[
            _tercero("A", "Por cobrar", 1, "Cliente", fila=2),
            _tercero("B", "Por pagar", -1, "Proveedor de material", fila=3),
        ])
        with pytest.raises(SystemExit, match="Categoría de tercero «Proveedor Material»"):
            L.aplicar(plan, "saldos", api)
        assert api.posts == []

    def test_listado_incompleto_falla_en_voz_alta(self):
        api = FakeApi({"/warehouses": {"items": [{"name": "a"}], "total": 3}})
        with pytest.raises(SystemExit, match="hay 3 filas"):
            L._todos(api, "/warehouses")


# ---------------------------------------------------------------------------
# T12 — todas las fechas de negocio son el corte, nunca el reloj
# ---------------------------------------------------------------------------

class TestFechas:
    def test_todos_los_pasos_llevan_el_corte(self):
        plan = _plan(
            Inventario=[
                _inv("PLO-LIN", "Juan Mina", 10, 5, fila=2),
                _inv("BAT-G3", "Circunvalar", 5, 46361, fila=3),
                _inv("BAT-G3", "Circunvalar", -1, 46361, entra="Ver hoja Entradas", fila=4),
            ],
            Kilos=[
                {"_fila": 2, "etiqueta": "Willard baterías (Circunvalar)", "valores": [None, 100]},
                {"_fila": 3, "etiqueta": "Intersede, etapa horno", "valores": [None, 7]},
                {"_fila": 4, "etiqueta": "Precio ($ por kg)", "valores": [None, 4043]},
            ],
            **{"Activos fijos": [_activo()],
               "Entradas por liquidar": [{"_fila": 2, "numero": 13586, "fecha": "08/01/2019",
                                          "origen": "GREENLOOP", "cantidad": 1,
                                          "material": "BAT-G3", "bodega": "Circunvalar"}]},
        )
        assert not plan.errores, plan.errores
        fechas = {}
        for p in plan.pasos:
            for k in ("date", "transaction_date", "effective_date", "purchase_date"):
                if k in p.payload:
                    fechas.setdefault(p.tipo, set()).add(p.payload[k])
        assert fechas == {
            "increase": {"2020-01-31"},
            "kg_movement": {"2020-01-31"},
            "lead_price": {"2020-01-31"},
            "fixed_asset": {"2020-01-31"},
            "inbound_order": {"2019-01-08"},  # la entrada conserva su fecha propia
        }

    def test_kilos_valora_la_deuda_con_willard_y_cruza_con_inventario(self):
        plan = _plan(
            Inventario=[_inv("PB POSC", "", -100, 4043, entra="Ver hoja Kilos")],
            Kilos=[
                {"_fila": 2, "etiqueta": "Willard baterías (Circunvalar)", "valores": [None, 100]},
                {"_fila": 3, "etiqueta": "Intersede, etapa crisol", "valores": [None, 5]},
                {"_fila": 4, "etiqueta": "Precio ($ por kg)", "valores": [None, 4043]},
            ],
        )
        (deuda,) = _pasos(plan, "lead_debt")
        assert deuda.esperado == Decimal("-404300")  # solo Willard, no intersede
        (cruce,) = [c for c in plan.cruces if "Kilos" in c[0]]
        assert cruce[1] == cruce[2] == Decimal("-404300")
        etapas = {p.payload.get("stage") for p in _pasos(plan, "kg_movement")}
        assert etapas == {None, "crisol"}
        # El endpoint exige motivo Y descripcion (extra="forbid", los dos min_length=1)
        assert all(p.payload["reason"] and p.payload["description"] for p in _pasos(plan, "kg_movement"))

    def test_etiqueta_de_kilos_desconocida_es_error(self):
        plan = _plan(Kilos=[{"_fila": 2, "etiqueta": "Horno grande", "valores": [None, 5]}])
        assert plan.errores and "desconocida" in plan.errores[0]


# ---------------------------------------------------------------------------
# T13 — lo que tambien define el seeder se crea con los datos del seeder
# ---------------------------------------------------------------------------

class TestSeeder:
    def test_greenloop_es_green_loop(self):
        plan = _plan(Terceros=[_tercero("GREENLOOP", "Sin saldo", 0, "Proveedor de servicios")])
        (p,) = _pasos(plan, "third_party")
        assert p.nombre == "Green Loop"
        assert p.payload["categorias"] == dict(L.seed.THIRD_PARTIES)["Green Loop"]

    def test_caja_del_seeder_conserva_su_tipo(self):
        plan = _plan(Cuentas=[{"_fila": 2, "nombre": "EFECTIVO", "saldo": 75, "tipo": "Efectivo",
                               "cuenta": "caja circunvalar", "entra": "Sí"}])
        (c,) = _pasos(plan, "account")
        assert (c.nombre, c.payload["account_type"]) == ("Caja Circunvalar", "cash")

    def test_caja_del_seeder_con_otro_tipo_es_error(self):
        plan = _plan(Cuentas=[{"_fila": 2, "nombre": "EFECTIVO", "saldo": 75, "tipo": "Banco",
                               "cuenta": "Caja Circunvalar", "entra": "Sí"}])
        assert plan.errores and "en el seeder" in plan.errores[0]

    def test_cuenta_con_instruccion_en_la_celda_es_error(self):
        plan = _plan(Cuentas=[{"_fila": 2, "nombre": "CTA", "saldo": 1, "tipo": "Banco",
                               "cuenta": "Crear: Cta Cte BBVA", "entra": "Sí"}])
        assert plan.errores and "G10" in plan.errores[0]

    def test_saldos_crea_terceros_con_las_categorias_por_id(self):
        api = FakeApi({"/third-party-categories/flat": {"items": [
            {"name": n, "id": f"cat-{n}"} for n in ("Cliente", "Proveedor Material", "Pasivo")
        ]}})
        plan = _plan(Terceros=[_tercero("A", "Por cobrar", 100, "Cliente")])
        L.aplicar(plan, "saldos", api)
        creados = [b for p, b in api.posts if p == "/third-parties/"]
        assert creados == [{"name": "A", "initial_balance": "100", "category_ids": ["cat-Cliente"]}]
        # Las categorias nuevas se crean ANTES que los terceros que las usan
        rutas = [p for p, _ in api.posts]
        assert rutas.index("/third-party-categories") < rutas.index("/third-parties/")


# ---------------------------------------------------------------------------
# Contrato con el backend: lo que `aplicar` manda valida contra el schema REAL
# del endpoint, y no trae claves que el schema no tenga (con `extra` por defecto
# Pydantic las IGNORA: el dato se pierde sin error). Nacio de la ronda 1: los
# movimientos de kilos no llevaban `description` y los 55 tests puros pasaban.
# ---------------------------------------------------------------------------

import uuid  # noqa: E402

from app.schemas.expense_category import ExpenseCategoryCreate  # noqa: E402
from app.schemas.fixed_asset import FixedAssetCreate  # noqa: E402
from app.schemas.inbound_order import InboundOrderCreate  # noqa: E402
from app.schemas.inventory_adjustment import IncreaseCreate  # noqa: E402
from app.schemas.kg_ledger import KgLedgerMovementManualCreate  # noqa: E402
from app.schemas.lead_market_price import LeadMarketPriceCreate  # noqa: E402
from app.schemas.material import MaterialCategoryCreate, MaterialCreate  # noqa: E402
from app.schemas.material_kg_profile import MaterialKgProfileUpsert  # noqa: E402
from app.schemas.money_account import MoneyAccountCreate  # noqa: E402
from app.schemas.third_party import ThirdPartyCreate  # noqa: E402
from app.schemas.third_party_category import ThirdPartyCategoryCreate  # noqa: E402

CONTRATO = {
    "/third-party-categories": ThirdPartyCategoryCreate,
    "/third-parties/": ThirdPartyCreate,
    "/money-accounts/": MoneyAccountCreate,
    "/material-categories/": MaterialCategoryCreate,
    "/materials/": MaterialCreate,
    "/material-kg-profiles/": MaterialKgProfileUpsert,
    "/expense-categories/": ExpenseCategoryCreate,
    "/inventory/adjustments/increase": IncreaseCreate,
    "/kg-ledger/movements": KgLedgerMovementManualCreate,
    "/lead-market-prices": LeadMarketPriceCreate,
    "/fixed-assets/": FixedAssetCreate,
    "/inbound-orders": InboundOrderCreate,
}


def _uid(nombre):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, nombre))


class FakeApiUuid(FakeApi):
    def __init__(self, gets=None):
        super().__init__({"/third-party-categories/flat": {"items": [
            {"name": n, "id": _uid(n)} for n in CATEGORIAS_POR_DEFECTO]}} | (gets or {}))

    def post(self, path, body, label=""):
        super().post(path, body, label)
        return {"id": _uid(f"{path}{len(self.posts)}")}


def _org_provisionada():
    def lista(nombres, campo="name"):
        return {"items": [{campo: n, "id": _uid(n)} for n in nombres], "total": len(nombres)}
    return {
        "/warehouses": lista([w[0] for w in L.seed.WAREHOUSES]),
        "/kg-ledger/accounts": [{"code": c[0], "id": _uid(c[0])} for c in L.seed.KG_ACCOUNTS],
        "/materials": lista([m[0] for m in L.seed.MATERIALS], "code"),
        "/material-categories": lista(L.seed.MATERIAL_CATEGORIES),
        "/business-units": lista(L.seed.BUSINESS_UNITS),
    }


def _plan_completo():
    """Una fila por cada camino que escribe, en las dos fases."""
    return _plan(
        Terceros=[
            _tercero("CLI", "Por cobrar", 100, "Cliente", nit="900.1", fila=2),
            _tercero("WILLARD", "Por pagar", -9, L.TIPO_WILLARD, fila=3),
        ],
        Cuentas=[{"_fila": 2, "nombre": "BBVA", "saldo": 55, "tipo": "Banco",
                  "cuenta": "Cta Cte BBVA", "entra": "Sí"}],
        Inventario=[
            _inv("PLO-LIN", "Juan Mina", 10, 5543, fila=2),
            _inv("EST-PLA", "Juan Mina", 3, 115000, fila=3),
            _inv("BAT-G3", "Circunvalar", 5, 46361, fila=4),
            _inv("BAT-G3", "Circunvalar", -1, 46361, entra="Ver hoja Entradas", fila=5),
        ],
        Kilos=[
            {"_fila": 2, "etiqueta": "Willard baterías (Circunvalar)", "valores": [None, 100]},
            {"_fila": 3, "etiqueta": "Intersede, etapa horno", "valores": [None, 7]},
            {"_fila": 4, "etiqueta": "Precio ($ por kg)", "valores": [None, 4043]},
        ],
        **{"Créditos": [_credito("BANCO X", capital=500), _credito("INT X", intereses=7, fila=3)],
           "Activos fijos": [_activo(), _activo(fecha=date(2019, 5, 1), vida=60) | {"nombre": "MOLINO", "_fila": 3}],
           "Entradas por liquidar": [_entrada(13586, "BAT-G3", 1)]},
    )


class TestContratoConElBackend:
    def _enviado(self):
        plan = _plan_completo()
        assert not plan.errores, plan.errores
        api = FakeApiUuid()
        L.aplicar(plan, "saldos", api)
        api_resto = FakeApiUuid(_org_provisionada())
        L.aplicar(plan, "resto", api_resto)
        envios = api.posts + api_resto.posts + api_resto.puts
        return envios

    def test_cada_camino_que_escribe_tiene_su_contrato(self):
        rutas = {next(k for k in CONTRATO if p.startswith(k)) if any(p.startswith(k) for k in CONTRATO)
                 else p for p, _ in self._enviado()}
        assert rutas == set(CONTRATO), f"sin contrato: {rutas - set(CONTRATO)}; nunca usado: {set(CONTRATO) - rutas}"

    @pytest.mark.parametrize("ruta", list(CONTRATO))
    def test_el_cuerpo_valida_y_no_pierde_claves(self, ruta):
        schema = CONTRATO[ruta]
        cuerpos = [b for p, b in self._enviado() if p.startswith(ruta)]
        assert cuerpos, f"ningún envío a {ruta}"
        for b in cuerpos:
            sobran = set(b) - set(schema.model_fields)
            assert not sobran, f"{ruta}: {sorted(sobran)} no existen en {schema.__name__} (se pierden sin error)"
            schema.model_validate(b)
