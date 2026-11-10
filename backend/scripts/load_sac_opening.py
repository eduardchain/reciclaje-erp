#!/usr/bin/env python
"""
load_sac_opening.py — carga inicial de SAC desde el Sheet «SAC - Carga inicial».

Plan: docs/planes/plan-sac-carga-inicial-ronda1.md. El Sheet se exporta a .xlsx
(Drive) y ese archivo es la entrada. El archivo NO se commitea: tiene saldos y
nomina reales.

Una ronda local, en orden (G1 del plan — los saldos van ANTES que los maestros,
porque `initial_balance` solo se puede poner al CREAR un tercero o una cuenta, y
el seeder siembra Willard S.A y Caja Circunvalar):

    1. seed_sac_org.py --apply --reset --org-vacia
    2. load_sac_opening.py --file carga.xlsx --fase saldos --ensayo --apply
    3. seed_sac_org.py --apply                       (provision: reutiliza por nombre)
    4. load_sac_opening.py --file carga.xlsx --fase resto --ensayo --apply
    5. load_sac_opening.py --file carga.xlsx --conciliar --salida informe.md

Sin --apply, las fases imprimen el plan y no escriben nada.

Tres capas, y solo las dos ultimas hablan con el backend:
    leer_libro(path)                 -> filas por pestana, leidas POR ENCABEZADO
    armar_plan(libro, corte, ensayo) -> pasos + exclusiones + errores (PURA)
    aplicar(plan, fase, api) / conciliar(plan, api)

Reglas que este archivo hace cumplir (seccion 4 del plan):
  - Solo entran las filas con «¿Entra al sistema?» = Si. Toda otra fila va a
    `exclusiones` con su motivo: ninguna fila desaparece en silencio.
  - Una columna esperada que falta detiene la lectura y se nombra.
  - Los nombres se comparan sin mayusculas, tildes ni espacios.
  - Los terceros y cuentas que tambien define el seeder se crean con SUS datos
    (importados de seed_sac_org.py: una sola fuente).
  - --ensayo acepta valores provisionales (activos sin vida util) y salta filas
    incompletas; se niega contra un backend que no sea local.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import unicodedata
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import seed_sac_org as seed  # noqa: E402  (una sola fuente de los maestros de SAC)

# ============================================================================
# CONSTANTES
# ============================================================================

#: Marcador de los ajustes de inventario de la carga. `_calculate_profit` saca del
#: P&L los ajustes cuyo motivo empieza con "Carga inicial migracion" (#28/#49):
#: sin el, la carga apareceria como una ganancia de inventario.
MARCADOR = f"Carga inicial migracion {seed.ORG_NAME}"

RUBROS = (
    "Disponible",
    "Cuentas por cobrar",
    "Cuentas por cobrar a socios",
    "Activos fijos",
    "Inventario",
    "Cuentas por pagar",
)

#: Seccion de la pestana Terceros -> rubro del Inicio.
SECCION_RUBRO = {
    "por cobrar": "Cuentas por cobrar",
    "socio por cobrar": "Cuentas por cobrar a socios",
    "por pagar": "Cuentas por pagar",
    "sin saldo": None,
}

#: Tipo del Sheet -> categorias del sistema. Un Tipo fuera de esta lista en una
#: fila «Si» es un error: no hay a donde mandarlo.
TIPO_CATEGORIAS = {
    "cliente": ["Cliente"],
    "proveedor de material": ["Proveedor Material"],
    "proveedor de servicios": ["Proveedor Servicios"],
    "socio": ["Socios"],
    "empleado": ["Empleados"],
}
TIPO_WILLARD = "willard (se suman en un tercero)"
WILLARD = "Willard S.A"

#: Categorias de tercero que la carga crea si faltan (G2). Las de
#: `create_organization` (Proveedor Material, Cliente, Socios, Pasivo...) ya
#: existen en toda org.
CATEGORIAS_NUEVAS = {
    "Empleados": "generic",
    # El modulo de creditos exige un inversionista con "obligaci" en el nombre
    # de la categoria (financial_obligation.py:250).
    "Obligaciones Financieras": "investor",
}
CATEGORIA_CREDITO = "Obligaciones Financieras"
CATEGORIA_INTERESES = "Pasivo"

TIPO_CUENTA = {"efectivo": "cash", "banco": "bank", "digital": "digital"}

#: Materiales que la carga crea (G7). Todos en kg y `lead_product='none'`:
#: marcar uno de mas reabre el defecto de #103.
#: (codigo, nombre, categoria de material)
MATERIALES_NUEVOS = {
    "PLO-BAL": ("PLOMO BALANCIN", "Plomo"),
    "PLO-ANT": ("PLOMO ANTIMONIAL", "Plomo"),
    "EST-PLA": ("ESTAÑO PLANTA", "Estaño"),
    "TAP-MUP": ("TAPAS DE MOTO Y UPS", "Plomo"),
    "ESC-EST": ("ESCORIA DE ESTAÑO", "Estaño"),
}
UN_MATERIALES_NUEVOS = "UN1 Reciclaje Plomo"
CATEGORIA_DEPRECIACION = "Depreciación"

#: Etiquetas de la columna A de la pestana Kilos -> (cuenta kg, etapa).
KILOS_CUENTAS = {
    "willard baterias (circunvalar)": ("WILLARD-BAT-CV", None),
    "willard materiales (drosses)": ("WILL-DROSS", None),
    "intersede, etapa horno": ("INTERSEDE", "horno"),
    "intersede, etapa crisol": ("INTERSEDE", "crisol"),
}
KILOS_PRECIO = "precio ($ por kg)"
KILOS_FECHA_PRECIO = "fecha del precio"
KILOS_IGNORADAS = {"cuenta en plomo del sistema", "precio de mercado del plomo"}

#: Etiquetas del cuadre del Inicio -> rubro.
INICIO_RUBROS = {
    "disponible": "Disponible",
    "cuentas por cobrar (hoja terceros)": "Cuentas por cobrar",
    "cuentas por cobrar a socios": "Cuentas por cobrar a socios",
    "activos fijos": "Activos fijos",
    "inventario": "Inventario",
    "cuentas por pagar": "Cuentas por pagar",
}

#: Vida util provisional del ensayo (G4). Solo existe con --ensayo.
VIDA_UTIL_PROVISIONAL = 120
SUFIJO_PROVISIONAL = " (vida útil provisional)"

#: El seeder lee los terceros existentes con limit=500 (`existing_by`). Con mas,
#: Willard S.A —que ordena casi al final— quedaria fuera de la lectura y el
#: seeder crearia un SEGUNDO Willard en 0 y le colgaria las cuentas kg (#108).
TOPE_TERCEROS_SEEDER = 500

UNO = Decimal("1")
CENTAVO = Decimal("0.01")
KG_Q = Decimal("0.001")
COSTO_Q = Decimal("0.0001")  # inventory_adjustments.unit_cost es Numeric(15,4)

# Cada pestana: clave interna -> prefijo del encabezado (normalizado). Se lee por
# encabezado y no por posicion: un Sheet reorganizado no puede leerse corrido.
PESTANAS: dict[str, dict[str, str]] = {
    "Terceros": {
        "nombre": "nombre en el balance",
        "seccion": "seccion",
        "saldo": "saldo en el sistema",
        "tipo": "tipo en el sistema",
        "nit": "nit o cedula",
        "entra": "¿entra al sistema?",
    },
    "Cuentas": {
        "nombre": "nombre en el balance",
        "saldo": "saldo al",
        "tipo": "tipo",
        "cuenta": "cuenta en el sistema",
        "entra": "¿entra al sistema?",
    },
    "Inventario": {
        "material_balance": "material en el balance",
        "ubicacion": "ubicacion",
        "cantidad": "cantidad",
        "precio": "precio",
        "material": "material en el sistema",
        "bodega": "bodega en el sistema",
        "entra": "¿entra al sistema?",
    },
    "Activos fijos": {
        "nombre": "activo",
        "valor": "valor en el balance",
        "fecha": "fecha de compra",
        "vida": "vida util",
        "residual": "valor residual",
        "depreciacion": "depreciacion acumulada",
        "entra": "¿entra al sistema?",
    },
    "Créditos": {
        "acreedor": "acreedor",
        "tercero": "tercero en el sistema",
        "capital": "capital al corte",
        "intereses": "intereses causados",
        "entra": "¿entra al sistema?",
    },
    "Entradas por liquidar": {
        "numero": "numero de compra",
        "fecha": "fecha",
        "origen": "origen",
        "cantidad": "cantidad",
        "material": "material en el sistema",
        "bodega": "bodega en el sistema",
    },
}
#: Pestanas que no son tabla: se leen por etiqueta en la columna A.
PESTANAS_ETIQUETA = ("Kilos", "Inicio")


class ErrorDeLibro(Exception):
    """El archivo no tiene la forma esperada: falta una pestana o una columna."""


# ============================================================================
# NORMALIZACION Y PARSEO
# ============================================================================

def norm(texto: Any) -> str:
    """Minusculas, sin tildes y con los espacios colapsados."""
    if texto is None:
        return ""
    s = unicodedata.normalize("NFKD", str(texto))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def clave(texto: Any) -> str:
    """Llave de comparacion de nombres: sin mayusculas, tildes NI espacios
    (GREENLOOP del Sheet es el Green Loop del seeder)."""
    return norm(texto).replace(" ", "")


def a_decimal(valor: Any) -> Decimal:
    """Numero de una celda. Vacio o "-" es cero. Un texto con formato es-CO
    ("1.234.567,89") se acepta por si la celda llego como texto."""
    if valor is None:
        return Decimal("0")
    if isinstance(valor, bool):
        raise ValueError(f"valor booleano inesperado: {valor!r}")
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).strip().replace("$", "").replace(" ", "")
    if s in ("", "-", "—"):
        return Decimal("0")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3):
        # "1.234.567" o "20.158": separadores de miles es-CO
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"no es un numero: {valor!r}") from e


def a_fecha(valor: Any) -> Optional[date]:
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"no es una fecha: {valor!r}")


def texto(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    return str(valor).strip()


# ============================================================================
# LECTURA DEL LIBRO
# ============================================================================

def _leer_tabla(ws, nombre: str, spec: dict[str, str]) -> list[dict]:
    filas = list(ws.iter_rows(values_only=True))
    if not filas:
        raise ErrorDeLibro(f"La pestaña «{nombre}» está vacía")
    encabezados = [norm(h) for h in filas[0]]
    indices: dict[str, int] = {}
    faltan = []
    for key, prefijo in spec.items():
        hits = [i for i, h in enumerate(encabezados) if h.startswith(prefijo)]
        if not hits:
            faltan.append(prefijo)
        elif len(hits) > 1:
            raise ErrorDeLibro(
                f"En «{nombre}» hay {len(hits)} columnas que empiezan con «{prefijo}»: "
                "no sé cuál leer"
            )
        else:
            indices[key] = hits[0]
    if faltan:
        raise ErrorDeLibro(
            f"En «{nombre}» faltan columnas: {', '.join('«' + f + '»' for f in faltan)}"
        )
    out = []
    for n, fila in enumerate(filas[1:], start=2):
        if fila is None or all(v is None or (isinstance(v, str) and not v.strip()) for v in fila):
            continue
        reg = {"_fila": n}
        for key, i in indices.items():
            reg[key] = fila[i] if i < len(fila) else None
        out.append(reg)
    return out


def _leer_etiquetas(ws) -> list[dict]:
    out = []
    for n, fila in enumerate(ws.iter_rows(values_only=True), start=1):
        if not fila or fila[0] is None:
            continue
        out.append({"_fila": n, "etiqueta": fila[0], "valores": list(fila[1:])})
    return out


def leer_libro(path: str) -> dict[str, list[dict]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    libro: dict[str, list[dict]] = {}
    nombres = {norm(n): n for n in wb.sheetnames}
    for nombre, spec in PESTANAS.items():
        real = nombres.get(norm(nombre))
        if real is None:
            raise ErrorDeLibro(f"Falta la pestaña «{nombre}»")
        libro[nombre] = _leer_tabla(wb[real], nombre, spec)
    for nombre in PESTANAS_ETIQUETA:
        real = nombres.get(norm(nombre))
        if real is None:
            raise ErrorDeLibro(f"Falta la pestaña «{nombre}»")
        libro[nombre] = _leer_etiquetas(wb[real])
    return libro


# ============================================================================
# EL PLAN (puro: no habla con el backend)
# ============================================================================

@dataclass
class Paso:
    fase: str           # "saldos" | "resto"
    tipo: str           # third_party | account | material | increase | ...
    nombre: str         # identidad legible (nombre, codigo, codigo@bodega)
    payload: dict
    rubro: Optional[str] = None
    #: Lo que el sistema tiene que mostrar despues (con el signo del sistema:
    #: + nos debe / activo, - le debemos).
    esperado: Optional[Decimal] = None
    #: Piezas por rubro cuando una entidad suma filas de varios rubros (Willard).
    piezas: dict = field(default_factory=dict)
    origen: str = ""    # "Terceros fila 12", para el informe


@dataclass
class Exclusion:
    pestana: str
    fila: int
    nombre: str
    rubro: Optional[str]
    monto: Decimal      # con el signo del sistema (pasivo negativo)
    motivo: str
    #: Rubro donde el sistema IGUAL muestra este dinero por otro camino (la deuda en
    #: plomo, una cuenta de dinero). Mismo rubro que `rubro` = no es una diferencia;
    #: otro rubro = un traslado, que explica las dos puntas. None = no entra.
    en_el_sistema: Optional[str] = None


@dataclass
class Plan:
    corte: date
    ensayo: bool
    pasos: list[Paso] = field(default_factory=list)
    exclusiones: list[Exclusion] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    #: Totales del balance de Johana por rubro (pestana Inicio), signo del sistema.
    johana: dict[str, Decimal] = field(default_factory=dict)
    #: Montos que una pestana manda a otra ("Ver hoja Creditos"), para cruzarlos.
    traspasos: list[tuple[str, str, int, Decimal, Optional[str]]] = field(default_factory=list)
    #: Cruces internos del Sheet: (descripcion, a, b).
    cruces: list[tuple[str, Decimal, Decimal]] = field(default_factory=list)
    #: Compras sin liquidar por (codigo, bodega): lo que Inventario descuenta (con
    #: su signo, negativo) y lo que Entradas abre. Tienen que ser opuestos exactos.
    por_liquidar_inventario: dict[tuple[str, str], Decimal] = field(default_factory=dict)
    #: Cuentas de dinero cargadas, por clave del nombre en el balance: (saldo, cuenta).
    cuentas_cargadas: dict[str, tuple[Decimal, str]] = field(default_factory=dict)
    por_liquidar_entradas: dict[tuple[str, str], Decimal] = field(default_factory=dict)

    def de(self, fase: str) -> list[Paso]:
        return [p for p in self.pasos if p.fase == fase]


def _entra(valor: Any) -> str:
    return norm(valor)


def _seeder_terceros() -> dict[str, tuple[str, list[str]]]:
    return {clave(n): (n, cats) for n, cats in seed.THIRD_PARTIES}


def _seeder_cuentas() -> dict[str, dict]:
    return {clave(a["name"]): a for a in seed.ACCOUNTS}


def _seeder_materiales() -> set[str]:
    return {clave(m[0]) for m in seed.MATERIALS}


def _seeder_bodegas() -> dict[str, str]:
    # Las de transito no reciben una carga de inventario.
    return {clave(w[0]): w[0] for w in seed.WAREHOUSES if not w[2]}


def _cuantos(x: Decimal, q: Decimal = CENTAVO) -> Decimal:
    return x.quantize(q, rounding=ROUND_HALF_UP)


def _incompleta(plan: Plan, pestana: str, fila: int, nombre: str, rubro, monto, que: str):
    """Fila «Si» a la que le falta un dato: con --ensayo se salta y se informa;
    sin el, detiene la carga."""
    if plan.ensayo:
        plan.exclusiones.append(Exclusion(pestana, fila, nombre, rubro, monto, f"«Sí» sin {que}"))
    else:
        plan.errores.append(f"{pestana} fila {fila} ({nombre}): «Sí» sin {que}")


def _plan_inicio(plan: Plan, filas: list[dict]) -> None:
    for f in filas:
        etiqueta = norm(f["etiqueta"])
        for prefijo, rubro in INICIO_RUBROS.items():
            if etiqueta.startswith(prefijo):
                total = a_decimal(f["valores"][0] if f["valores"] else None)
                # El Inicio da las cuentas por pagar en positivo.
                plan.johana[rubro] = -total if rubro == "Cuentas por pagar" else total
                break


def _plan_terceros(plan: Plan, filas: list[dict]) -> None:
    del_seeder = _seeder_terceros()
    willard = Paso(
        fase="saldos", tipo="third_party", nombre=WILLARD, payload={}, esperado=Decimal("0"),
        origen="Terceros (filas Willard sumadas)",
    )
    hay_willard = False
    for f in filas:
        nombre, fila = texto(f["nombre"]), f["_fila"]
        if not nombre:
            continue
        seccion = norm(f["seccion"])
        if seccion not in SECCION_RUBRO:
            plan.errores.append(f"Terceros fila {fila} ({nombre}): sección «{f['seccion']}» desconocida")
            continue
        rubro = SECCION_RUBRO[seccion]
        try:
            saldo = a_decimal(f["saldo"])
        except ValueError as e:
            plan.errores.append(f"Terceros fila {fila} ({nombre}): {e}")
            continue
        entra = _entra(f["entra"])
        tipo = norm(f["tipo"])

        if entra == "ver hoja creditos":
            plan.traspasos.append(("Créditos", nombre, fila, saldo, rubro))
            continue
        if entra == "ver hoja cuentas":
            plan.traspasos.append(("Cuentas", nombre, fila, saldo, rubro))
            continue
        if entra != "si":
            motivo = f"Marcada «{texto(f['entra']) or 'vacío'}»"
            if texto(f["tipo"]):
                motivo += f" ({texto(f['tipo'])})"
            plan.exclusiones.append(Exclusion("Terceros", fila, nombre, rubro, saldo, motivo))
            continue

        if tipo == TIPO_WILLARD:
            hay_willard = True
            willard.esperado += saldo
            if rubro:
                willard.piezas[rubro] = willard.piezas.get(rubro, Decimal("0")) + saldo
            continue
        if not tipo:
            _incompleta(plan, "Terceros", fila, nombre, rubro, saldo, "Tipo")
            continue
        if tipo not in TIPO_CATEGORIAS:
            plan.errores.append(
                f"Terceros fila {fila} ({nombre}): «Sí» con Tipo «{texto(f['tipo'])}», que no se carga"
            )
            continue

        cats = TIPO_CATEGORIAS[tipo]
        nombre_sistema = nombre
        seeder = del_seeder.get(clave(nombre))
        if seeder:
            nombre_sistema, cats_seeder = seeder
            if cats_seeder != cats:
                plan.avisos.append(
                    f"Terceros fila {fila} ({nombre}): el seeder lo define como {cats_seeder}; "
                    f"se usa eso y no {cats}"
                )
            cats = cats_seeder
        payload = {"name": nombre_sistema, "initial_balance": str(saldo), "categorias": cats}
        nit = texto(f["nit"])
        if nit:
            payload["identification_number"] = nit
        plan.pasos.append(Paso(
            "saldos", "third_party", nombre_sistema, payload, rubro, saldo,
            {rubro: saldo} if rubro else {}, f"Terceros fila {fila}",
        ))

    if hay_willard:
        _, cats = _seeder_terceros()[clave(WILLARD)]
        willard.payload = {
            "name": WILLARD, "initial_balance": str(willard.esperado), "categorias": cats,
        }
        willard.rubro = "Cuentas por cobrar" if willard.esperado >= 0 else "Cuentas por pagar"
        plan.pasos.append(willard)


def _plan_creditos(plan: Plan, filas: list[dict]) -> None:
    vistos: dict[str, Decimal] = {}
    for f in filas:
        acreedor, fila = texto(f["acreedor"]), f["_fila"]
        if not acreedor:
            continue
        nombre = texto(f["tercero"]) or acreedor
        try:
            capital = a_decimal(f["capital"])
            intereses = a_decimal(f["intereses"])
        except ValueError as e:
            plan.errores.append(f"Créditos fila {fila} ({acreedor}): {e}")
            continue
        monto = capital if capital else intereses
        vistos[clave(acreedor)] = -monto
        if capital and intereses:
            plan.errores.append(
                f"Créditos fila {fila} ({acreedor}): trae capital E intereses; van a terceros "
                "distintos, sepárelos en dos filas"
            )
            continue
        if _entra(f["entra"]) != "si":
            plan.exclusiones.append(Exclusion(
                "Créditos", fila, acreedor, "Cuentas por pagar", -monto,
                f"Marcada «{texto(f['entra']) or 'vacío'}»",
            ))
            continue
        if not monto:
            plan.avisos.append(f"Créditos fila {fila} ({acreedor}): sin capital ni intereses, no se carga")
            continue
        categoria = CATEGORIA_CREDITO if capital else CATEGORIA_INTERESES
        plan.pasos.append(Paso(
            "saldos", "third_party", nombre,
            {"name": nombre, "initial_balance": str(-monto), "categorias": [categoria]},
            "Cuentas por pagar", -monto, {"Cuentas por pagar": -monto}, f"Créditos fila {fila}",
        ))

    # Cruce: lo que Terceros manda a Creditos tiene que estar alla, por el mismo monto.
    for destino, nombre, fila, saldo, _ in plan.traspasos:
        if destino != "Créditos":
            continue
        en_creditos = vistos.get(clave(nombre))
        if en_creditos is None:
            plan.errores.append(
                f"Terceros fila {fila} ({nombre}) dice «Ver hoja Créditos» y no está en Créditos"
            )
        elif _cuantos(en_creditos) != _cuantos(saldo):
            plan.errores.append(
                f"{nombre}: Terceros fila {fila} dice {saldo} y Créditos dice {en_creditos}"
            )
        else:
            plan.cruces.append((f"Crédito {nombre}: Terceros vs Créditos", saldo, en_creditos))


def _plan_cuentas(plan: Plan, filas: list[dict]) -> None:
    del_seeder = _seeder_cuentas()
    for f in filas:
        nombre_bal, fila = texto(f["nombre"]), f["_fila"]
        if not nombre_bal:
            continue
        try:
            saldo = a_decimal(f["saldo"])
        except ValueError as e:
            plan.errores.append(f"Cuentas fila {fila} ({nombre_bal}): {e}")
            continue
        if _entra(f["entra"]) != "si":
            plan.exclusiones.append(Exclusion(
                "Cuentas", fila, nombre_bal, "Disponible", saldo,
                f"Marcada «{texto(f['entra']) or 'vacío'}»",
            ))
            continue
        nombre = texto(f["cuenta"])
        if not nombre:
            _incompleta(plan, "Cuentas", fila, nombre_bal, "Disponible", saldo, "cuenta en el sistema")
            continue
        if norm(nombre).startswith("crear"):
            plan.errores.append(
                f"Cuentas fila {fila} ({nombre_bal}): «{nombre}» — la columna lleva solo el "
                "nombre de la cuenta (G10); si existe o no lo decide el cargador"
            )
            continue
        tipo = TIPO_CUENTA.get(norm(f["tipo"]))
        if tipo is None:
            plan.errores.append(f"Cuentas fila {fila} ({nombre_bal}): tipo «{f['tipo']}» desconocido")
            continue
        seeder = del_seeder.get(clave(nombre))
        if seeder:
            if seeder["account_type"] != tipo:
                plan.errores.append(
                    f"Cuentas fila {fila}: «{nombre}» es {seeder['account_type']} en el seeder y "
                    f"{tipo} en el Sheet"
                )
                continue
            nombre = seeder["name"]
        if saldo < 0:
            plan.errores.append(
                f"Cuentas fila {fila} ({nombre}): saldo negativo; el sistema no abre una cuenta en negativo"
            )
            continue
        plan.pasos.append(Paso(
            "saldos", "account", nombre,
            {"name": nombre, "account_type": tipo, "initial_balance": str(saldo)},
            "Disponible", saldo, {"Disponible": saldo}, f"Cuentas fila {fila}",
        ))
        plan.cuentas_cargadas[clave(nombre_bal)] = (saldo, nombre)


def _codigo_material(plan: Plan, codigo: str, pestana: str, fila: int) -> Optional[str]:
    """Codigo canonico, o None si es desconocido (y queda el error)."""
    if norm(codigo).startswith("crear"):
        plan.errores.append(
            f"{pestana} fila {fila}: «{codigo}» — la columna lleva el código del material (G7/G10)"
        )
        return None
    c = clave(codigo)
    if c in _seeder_materiales():
        return next(m[0] for m in seed.MATERIALS if clave(m[0]) == c)
    for nuevo in MATERIALES_NUEVOS:
        if clave(nuevo) == c:
            return nuevo
    plan.errores.append(
        f"{pestana} fila {fila}: el material «{codigo}» no está en el seeder ni en MATERIALES_NUEVOS"
    )
    return None


def _bodega(plan: Plan, nombre: str, pestana: str, fila: int) -> Optional[str]:
    b = _seeder_bodegas().get(clave(nombre))
    if b is None:
        plan.errores.append(f"{pestana} fila {fila}: la bodega «{nombre}» no existe (o es de tránsito)")
    return b


def _plan_inventario(plan: Plan, filas: list[dict]) -> set[str]:
    """Devuelve los codigos de materiales nuevos que hacen falta."""
    grupos: "OrderedDict[tuple[str, str], dict]" = OrderedDict()
    nuevos: set[str] = set()
    for f in filas:
        nombre, fila = texto(f["material_balance"]), f["_fila"]
        if not nombre:
            continue
        etiqueta = f"{nombre} / {texto(f['ubicacion'])}"
        try:
            cantidad = a_decimal(f["cantidad"])
            precio = a_decimal(f["precio"])
        except ValueError as e:
            plan.errores.append(f"Inventario fila {fila} ({etiqueta}): {e}")
            continue
        valor = cantidad * precio
        entra = _entra(f["entra"])
        # Compra sin liquidar: el material ya esta en la bodega de Johana, pero la
        # compra todavia no. Se DESCUENTA de su bodega, porque la entrada abierta lo
        # suma al liquidarse; cargarlo bruto lo contaria dos veces.
        por_liquidar = entra == "ver hoja entradas"
        if entra != "si" and not por_liquidar:
            if entra == "ver hoja kilos":
                motivo = "Va por Kilos: el sistema la muestra como deuda en plomo valorada"
            else:
                motivo = f"Marcada «{texto(f['entra']) or 'vacío'}»"
            plan.exclusiones.append(Exclusion(
                "Inventario", fila, etiqueta, "Inventario", valor, motivo,
                en_el_sistema="Inventario" if entra == "ver hoja kilos" else None,
            ))
            continue
        if por_liquidar and not (texto(f["material"]) and texto(f["bodega"])):
            plan.errores.append(
                f"Inventario fila {fila} ({etiqueta}): «Ver hoja Entradas» sin material o bodega; "
                "no se sabe de qué bodega descontar la compra"
            )
            continue
        if not texto(f["material"]) or not texto(f["bodega"]):
            _incompleta(plan, "Inventario", fila, etiqueta, "Inventario", valor, "material o bodega")
            continue
        codigo = _codigo_material(plan, texto(f["material"]), "Inventario", fila)
        bodega = _bodega(plan, texto(f["bodega"]), "Inventario", fila)
        if codigo is None or bodega is None:
            continue
        if codigo in MATERIALES_NUEVOS:
            nuevos.add(codigo)
        if por_liquidar:
            k = (codigo, bodega)
            plan.por_liquidar_inventario[k] = plan.por_liquidar_inventario.get(k, Decimal("0")) + cantidad
        g = grupos.setdefault((codigo, bodega), {"cantidad": Decimal("0"), "valor": Decimal("0"), "filas": []})
        g["cantidad"] += cantidad
        g["valor"] += valor
        g["filas"].append(fila)

    for (codigo, bodega), g in grupos.items():
        filas_txt = ", ".join(str(n) for n in g["filas"])
        if g["cantidad"] <= 0:
            plan.exclusiones.append(Exclusion(
                "Inventario", g["filas"][0], f"{codigo} @ {bodega} (filas {filas_txt})",
                "Inventario", g["valor"],
                f"Saldo neto {g['cantidad']}: un saldo inicial negativo o en cero no se carga como entrada",
            ))
            continue
        cantidad = g["cantidad"].quantize(KG_Q, rounding=ROUND_HALF_UP)
        costo = (g["valor"] / g["cantidad"]).quantize(COSTO_Q, rounding=ROUND_HALF_UP)
        esperado = _cuantos(cantidad * costo)
        plan.pasos.append(Paso(
            "resto", "increase", f"{codigo} @ {bodega}",
            {"codigo": codigo, "bodega": bodega, "quantity": str(cantidad),
             "unit_cost": str(costo), "date": plan.corte.isoformat(), "reason": MARCADOR,
             "notes": f"Carga inicial al {plan.corte.isoformat()} (Inventario filas {filas_txt})"},
            "Inventario", esperado, {"Inventario": esperado}, f"Inventario filas {filas_txt}",
        ))
    return nuevos


def _plan_kilos(plan: Plan, filas: list[dict]) -> None:
    precio: Optional[Decimal] = None
    fecha_precio: Optional[date] = None
    willard_kg = Decimal("0")
    codigos_kg = {k[0] for k in seed.KG_ACCOUNTS}
    for f in filas:
        etiqueta, fila = norm(f["etiqueta"]), f["_fila"]
        valores = f["valores"]
        # columna C = indice 1 de `valores` (A es la etiqueta)
        celda = valores[1] if len(valores) > 1 else None
        if etiqueta in KILOS_IGNORADAS:
            continue
        if etiqueta == KILOS_PRECIO:
            precio = a_decimal(celda) or None
            continue
        if etiqueta == KILOS_FECHA_PRECIO:
            fecha_precio = a_fecha(celda)
            continue
        if etiqueta not in KILOS_CUENTAS:
            plan.errores.append(f"Kilos fila {fila}: etiqueta «{f['etiqueta']}» desconocida")
            continue
        codigo, etapa = KILOS_CUENTAS[etiqueta]
        if codigo not in codigos_kg:
            plan.errores.append(f"Kilos fila {fila}: la cuenta {codigo} no la siembra el seeder")
            continue
        kg = a_decimal(celda)
        if not kg:
            plan.avisos.append(f"Kilos fila {fila} ({f['etiqueta']}): sin dato, no se carga")
            continue
        kg = kg.quantize(KG_Q, rounding=ROUND_HALF_UP)
        if codigo.startswith("WILL"):
            willard_kg += kg
        payload = {
            "codigo": codigo, "delta_kg": str(kg), "transaction_date": plan.corte.isoformat(),
            "reason": f"Saldo inicial al {plan.corte.isoformat()} (carga inicial)",
            "description": f"Saldo inicial en kilos al {plan.corte.isoformat()}: carga inicial, "
                           f"Kilos fila {fila} ({texto(f['etiqueta'])})",
        }
        if etapa:
            payload["stage"] = etapa
        plan.pasos.append(Paso(
            "resto", "kg_movement", f"{codigo}{' / ' + etapa if etapa else ''}", payload,
            None, kg, {}, f"Kilos fila {fila}",
        ))
    if precio:
        vigencia = fecha_precio or plan.corte
        if fecha_precio is None:
            plan.avisos.append("Kilos: el precio del plomo no trae fecha; rige desde el corte (G8)")
        plan.pasos.append(Paso(
            "resto", "lead_price", "precio de mercado del plomo",
            {"price_per_kg": str(precio), "effective_date": vigencia.isoformat()},
            None, precio, {}, "Kilos",
        ))
        valor = _cuantos(-(willard_kg * precio))
        plan.pasos.append(Paso(
            "resto", "lead_debt", "deuda en plomo con Willard (valorada)", {},
            "Inventario", valor, {"Inventario": valor}, "Kilos",
        ))
        # Cruce: la fila del inventario que va por Kilos tiene que valer lo mismo.
        en_inventario = sum(
            (e.monto for e in plan.exclusiones if e.pestana == "Inventario" and e.motivo.startswith("Va por Kilos")),
            Decimal("0"),
        )
        plan.cruces.append(("Inventario «Ver hoja Kilos» vs deuda en plomo valorada", _cuantos(en_inventario), valor))


def _plan_activos(plan: Plan, filas: list[dict]) -> None:
    inicio_dep = (plan.corte.replace(day=1) + timedelta(days=32)).replace(day=1)
    for f in filas:
        nombre, fila = texto(f["nombre"]), f["_fila"]
        if not nombre:
            continue
        try:
            valor = a_decimal(f["valor"])
            residual = a_decimal(f["residual"])
            dep = a_decimal(f["depreciacion"])
            vida = int(a_decimal(f["vida"]))
            fecha = a_fecha(f["fecha"])
        except ValueError as e:
            plan.errores.append(f"Activos fijos fila {fila} ({nombre}): {e}")
            continue
        if _entra(f["entra"]) != "si":
            plan.exclusiones.append(Exclusion(
                "Activos fijos", fila, nombre, "Activos fijos", valor,
                f"Marcada «{texto(f['entra']) or 'vacío'}»",
            ))
            continue
        if valor <= 0:
            plan.errores.append(f"Activos fijos fila {fila} ({nombre}): valor {valor} no positivo")
            continue
        nombre_sistema = nombre
        notas = f"Carga inicial al {plan.corte.isoformat()}."
        if not fecha or vida <= 0:
            if not plan.ensayo:
                plan.errores.append(
                    f"Activos fijos fila {fila} ({nombre}): sin fecha de compra o vida útil "
                    "(solo el ensayo acepta valores provisionales, G4)"
                )
                continue
            fecha = fecha or plan.corte
            vida = vida if vida > 0 else VIDA_UTIL_PROVISIONAL
            nombre_sistema = nombre + SUFIJO_PROVISIONAL
            notas += " ENSAYO: vida útil y fecha provisionales, no aplicar depreciación."
        if dep > valor - residual:
            plan.errores.append(
                f"Activos fijos fila {fila} ({nombre}): depreciación {dep} mayor que la base {valor - residual}"
            )
            continue
        # Tasa MENSUAL (cuota = valor x tasa / 100) y la columna es Numeric(5,2):
        # se manda ya redondeada a lo que se va a guardar, no 0,8333 para que la
        # base lo corte a 0,83 en silencio.
        tasa = (Decimal("100") / Decimal(vida)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
        esperado = valor - dep
        plan.pasos.append(Paso(
            "resto", "fixed_asset", nombre_sistema,
            {"name": nombre_sistema, "purchase_date": fecha.isoformat(),
             "purchase_value": str(valor), "salvage_value": str(residual),
             "depreciation_rate": str(tasa),
             "depreciation_start_date": max(inicio_dep, fecha).isoformat(),
             "accumulated_depreciation": str(dep), "historical_load": True, "notes": notas},
            "Activos fijos", esperado, {"Activos fijos": esperado}, f"Activos fijos fila {fila}",
        ))


def _plan_entradas(plan: Plan, filas: list[dict]) -> set[str]:
    ordenes: "OrderedDict[str, dict]" = OrderedDict()
    nuevos: set[str] = set()
    for f in filas:
        numero, fila = texto(f["numero"]), f["_fila"]
        if not numero:
            continue
        try:
            cantidad = a_decimal(f["cantidad"])
            fecha = a_fecha(f["fecha"])
        except ValueError as e:
            plan.errores.append(f"Entradas fila {fila} ({numero}): {e}")
            continue
        codigo = _codigo_material(plan, texto(f["material"]), "Entradas", fila)
        bodega = _bodega(plan, texto(f["bodega"]), "Entradas", fila)
        if codigo is None or bodega is None or fecha is None:
            if fecha is None:
                plan.errores.append(f"Entradas fila {fila} ({numero}): sin fecha")
            continue
        if cantidad <= 0:
            plan.errores.append(f"Entradas fila {fila} ({numero}): cantidad {cantidad} no positiva")
            continue
        if codigo in MATERIALES_NUEVOS:
            nuevos.add(codigo)
        o = ordenes.setdefault(numero, {
            "fecha": fecha, "bodega": bodega, "origen": texto(f["origen"]), "lineas": [], "filas": [],
        })
        if o["fecha"] != fecha or o["bodega"] != bodega:
            plan.errores.append(f"Entradas: la compra {numero} trae fechas o bodegas distintas entre filas")
            continue
        if any(ln["codigo"] == codigo for ln in o["lineas"]):
            plan.errores.append(f"Entradas: la compra {numero} repite el material {codigo}")
            continue
        o["lineas"].append({"codigo": codigo, "quantity": str(cantidad.quantize(KG_Q))})
        o["filas"].append(fila)
        k = (codigo, bodega)
        plan.por_liquidar_entradas[k] = plan.por_liquidar_entradas.get(k, Decimal("0")) + cantidad
    for numero, o in ordenes.items():
        plan.pasos.append(Paso(
            "resto", "inbound_order", f"Compra {numero}",
            {"inbound_type": "purchase", "bodega": o["bodega"], "date": o["fecha"].isoformat(),
             "remission_number": numero, "lineas": o["lineas"],
             "notes": f"Compra {numero} del sistema anterior, sin liquidar al corte "
                      f"{plan.corte.isoformat()}. Origen en el balance: {o['origen']}."},
            None, Decimal(len(o["lineas"])), {}, f"Entradas filas {', '.join(map(str, o['filas']))}",
        ))
    return nuevos


def _cruzar_traspasos_a_cuentas(plan: Plan) -> None:
    """Un tercero del balance que en el sistema es una cuenta de dinero (EFECTIVO
    INGRID = Caja Green Loop): tiene que estar en Cuentas, cargado, por el mismo
    monto. Johana lo tiene en su rubro; el sistema, en Disponible: es un traslado."""
    for destino, nombre, fila, saldo, rubro in plan.traspasos:
        if destino != "Cuentas":
            continue
        cargada = plan.cuentas_cargadas.get(clave(nombre))
        if cargada is None:
            plan.errores.append(
                f"Terceros fila {fila} ({nombre}) dice «Ver hoja Cuentas» y en Cuentas no hay una "
                "fila «Sí» con ese nombre en el balance"
            )
        elif _cuantos(cargada[0]) != _cuantos(saldo):
            plan.errores.append(
                f"{nombre}: Terceros fila {fila} dice {saldo} y Cuentas dice {cargada[0]}"
            )
        else:
            plan.exclusiones.append(Exclusion(
                "Terceros", fila, nombre, rubro, saldo,
                f"Va por Cuentas: se carga como la cuenta de dinero «{cargada[1]}»",
                en_el_sistema="Disponible",
            ))
            plan.cruces.append((f"{nombre}: Terceros vs Cuentas", saldo, cargada[0]))


def _cruzar_compras_por_liquidar(plan: Plan) -> None:
    """Lo que Inventario descuenta por compras sin liquidar tiene que ser EXACTO lo
    que Entradas abre, por material y bodega. Si no, al liquidar las entradas el
    stock del sistema se separa del de Johana justo por la diferencia."""
    for k in sorted(set(plan.por_liquidar_inventario) | set(plan.por_liquidar_entradas)):
        descuenta = -plan.por_liquidar_inventario.get(k, Decimal("0"))
        abre = plan.por_liquidar_entradas.get(k, Decimal("0"))
        etiqueta = f"{k[0]} @ {k[1]}"
        if descuenta.quantize(KG_Q) != abre.quantize(KG_Q):
            plan.errores.append(
                f"Compras sin liquidar de {etiqueta}: Inventario descuenta {descuenta} y "
                f"Entradas abre {abre}"
            )
        else:
            plan.cruces.append((f"Compra sin liquidar {etiqueta}: Inventario vs Entradas", descuenta, abre))


def armar_plan(libro: dict[str, list[dict]], corte: date, ensayo: bool) -> Plan:
    plan = Plan(corte=corte, ensayo=ensayo)
    _plan_inicio(plan, libro["Inicio"])
    _plan_terceros(plan, libro["Terceros"])
    _plan_creditos(plan, libro["Créditos"])
    _plan_cuentas(plan, libro["Cuentas"])
    _cruzar_traspasos_a_cuentas(plan)
    nuevos = _plan_inventario(plan, libro["Inventario"])
    _plan_kilos(plan, libro["Kilos"])
    _plan_activos(plan, libro["Activos fijos"])
    nuevos |= _plan_entradas(plan, libro["Entradas por liquidar"])
    _cruzar_compras_por_liquidar(plan)

    # Maestros que la carga necesita: van antes de lo que los usa.
    maestros: list[Paso] = []
    for nombre, behavior in CATEGORIAS_NUEVAS.items():
        maestros.append(Paso("saldos", "tp_category", nombre, {"name": nombre, "behavior_type": behavior}))
    cats_material = sorted({MATERIALES_NUEVOS[c][1] for c in nuevos} - set(seed.MATERIAL_CATEGORIES))
    resto: list[Paso] = []
    for cat in cats_material:
        resto.append(Paso("resto", "material_category", cat, {"name": cat}))
    for codigo in sorted(nuevos):
        nombre, cat = MATERIALES_NUEVOS[codigo]
        resto.append(Paso("resto", "material", codigo, {
            "code": codigo, "name": nombre, "default_unit": "kg", "categoria": cat,
            "un": UN_MATERIALES_NUEVOS,
            "perfil": {"compra_regular": True, "willard_world": "none", "lead_product": "none"},
        }))
    if any(p.tipo == "fixed_asset" for p in plan.pasos):
        resto.append(Paso("resto", "expense_category", CATEGORIA_DEPRECIACION, {
            "name": CATEGORIA_DEPRECIACION, "is_direct_expense": False, "pnl_section": "operativo",
        }))
    plan.pasos = maestros + resto + plan.pasos

    # Nombres repetidos entre lo que se crea: detienen la carga.
    for tipo in ("third_party", "account", "fixed_asset"):
        vistos: dict[str, str] = {}
        for p in plan.pasos:
            if p.tipo != tipo:
                continue
            k = clave(p.nombre)
            if k in vistos:
                plan.errores.append(f"Nombre repetido ({tipo}): «{p.nombre}» ({vistos[k]} y {p.origen})")
            vistos[k] = p.origen
    n_terceros = sum(1 for p in plan.pasos if p.tipo == "third_party") + len(seed.THIRD_PARTIES)
    if n_terceros >= TOPE_TERCEROS_SEEDER:
        plan.errores.append(
            f"Quedarían {n_terceros} terceros y el seeder solo lee {TOPE_TERCEROS_SEEDER}: "
            "crearía un segundo Willard S.A"
        )
    return plan


# ============================================================================
# APLICAR (habla con el backend)
# ============================================================================

def _items(data: Any) -> list[dict]:
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    return data if isinstance(data, list) else []


#: Tope de `limit` de cada listado (`le=` de su Query, leido del endpoint). Pedir
#: mas da 422 — es el defecto de #108, que dejo los selectores vacios. Una ruta
#: que no esta aca no se puede listar: falla en voz alta en vez de adivinar.
TOPES = {
    "/third-parties": 5000,
    "/money-accounts": 500,
    "/fixed-assets/": 200,
    "/inbound-orders": 1000,
    "/inventory/adjustments": 1000,
    "/materials": 500,
    "/material-categories": 500,
    "/business-units": 500,
    "/warehouses": 500,
    "/kg-ledger/accounts": 500,  # sin paginacion: el parametro se ignora
}


def _todos(api, path: str, limit: Optional[int] = None) -> list[dict]:
    tope = TOPES[path]
    datos = api.get(path, {"limit": min(limit or tope, tope)})
    items = _items(datos)
    total = datos.get("total") if isinstance(datos, dict) else None
    if limit is None and total is not None and total > len(items):
        raise SystemExit(f"{path}: hay {total} filas y el listado trae {len(items)}")
    return items


def ubicar_org(api) -> str:
    orgs = api.get("/system/organizations")
    activas = [o for o in orgs if o["name"] == seed.ORG_NAME and o.get("is_active", True)]
    if len(activas) != 1:
        raise SystemExit(f"Esperaba UNA org activa «{seed.ORG_NAME}» y hay {len(activas)}")
    api.org_id = activas[0]["id"]
    return activas[0]["id"]


def _precondiciones(api, fase: str) -> None:
    if fase == "saldos":
        terceros = _todos(api, "/third-parties", 10)
        cuentas = _todos(api, "/money-accounts", 10)
        bodegas = _todos(api, "/warehouses", 10)
        if terceros or cuentas or bodegas:
            raise SystemExit(
                "La fase «saldos» necesita una org VACÍA (seed_sac_org.py --reset --org-vacia): "
                f"hay {len(terceros)} terceros, {len(cuentas)} cuentas y {len(bodegas)} bodegas. "
                "Si el seeder ya corrió, el saldo de Willard S.A y de Caja Circunvalar no se puede poner."
            )
        return
    bodegas = {clave(w["name"]) for w in _todos(api, "/warehouses")}
    faltan = [w for k, w in _seeder_bodegas().items() if k not in bodegas]
    cuentas_kg = {a["code"] for a in _todos(api, "/kg-ledger/accounts")}
    faltan += [c for c, *_ in seed.KG_ACCOUNTS if c not in cuentas_kg]
    if faltan:
        raise SystemExit(
            f"La fase «resto» necesita los maestros del seeder (falta: {', '.join(faltan)}). "
            "Corra seed_sac_org.py --apply sin --reset."
        )
    for path, que in (("/inventory/adjustments", "ajustes de inventario"),
                      ("/fixed-assets/", "activos fijos"),
                      ("/inbound-orders", "entradas")):
        if _todos(api, path, 5):
            raise SystemExit(f"La org ya tiene {que}: la fase «resto» exige una org sin operaciones")
    resumen = api.get("/kg-ledger/summary")
    if any(Decimal(str(a["balance_kg"])) != 0 for a in resumen["accounts"]):
        raise SystemExit("El libro de kilos ya tiene saldos: la fase «resto» no corre dos veces")


def _verificar_referencias(plan: Plan, fase: str, cats_tp, bodegas, materiales, cats_mat, uns,
                           cuentas_kg) -> None:
    """Toda categoria, bodega, material, UN y cuenta kg que un paso nombra tiene que
    existir en la org o nacer en un paso ANTERIOR de la misma fase. Se mira antes
    de la primera escritura: un faltante a mitad del bucle dejaria la org cargada a
    medias, y el KeyError no diria que falta."""
    nacen = {"tp_category": set(cats_tp), "material_category": set(cats_mat), "material": set(materiales)}
    faltan: list[str] = []

    def pide(que: str, nombre: str, existe: bool, paso: Paso) -> None:
        if not existe:
            faltan.append(f"{que} «{nombre}» (lo pide {paso.origen}: {paso.nombre})")

    for p in plan.de(fase):
        b = p.payload
        if p.tipo in nacen:
            nacen[p.tipo].add(p.nombre)
        if p.tipo == "third_party":
            for c in b["categorias"]:
                pide("Categoría de tercero", c, c in nacen["tp_category"], p)
        elif p.tipo == "material":
            pide("Categoría de material", b["categoria"], b["categoria"] in nacen["material_category"], p)
            pide("Unidad de negocio", b["un"], b["un"] in uns, p)
        elif p.tipo == "increase":
            pide("Material", b["codigo"], b["codigo"] in nacen["material"], p)
            pide("Bodega", b["bodega"], b["bodega"] in bodegas, p)
        elif p.tipo == "kg_movement":
            pide("Cuenta kg", b["codigo"], b["codigo"] in cuentas_kg, p)
        elif p.tipo == "inbound_order":
            pide("Bodega", b["bodega"], b["bodega"] in bodegas, p)
            for ln in b["lineas"]:
                pide("Material", ln["codigo"], ln["codigo"] in nacen["material"], p)
    if faltan:
        raise SystemExit("No se escribió nada. Faltan en la organización:\n  " + "\n  ".join(faltan))


def aplicar(plan: Plan, fase: str, api) -> None:
    _precondiciones(api, fase)
    cats_tp = {c["name"]: c["id"] for c in _items(api.get("/third-party-categories/flat"))}
    bodegas = {w["name"]: w["id"] for w in _todos(api, "/warehouses")}
    materiales = {m["code"]: m["id"] for m in _todos(api, "/materials")}
    cats_mat = {c["name"]: c["id"] for c in _todos(api, "/material-categories")}
    uns = {b["name"]: b["id"] for b in _todos(api, "/business-units")}
    cuentas_kg = {a["code"]: a["id"] for a in _todos(api, "/kg-ledger/accounts")} if fase == "resto" else {}
    cat_dep: Optional[str] = None
    _verificar_referencias(plan, fase, cats_tp, bodegas, materiales, cats_mat, uns, cuentas_kg)

    hechos = 0
    for p in plan.de(fase):
        body = dict(p.payload)
        if p.tipo == "tp_category":
            if p.nombre in cats_tp:
                continue
            r = api.post("/third-party-categories", body, label=p.nombre)
            cats_tp[p.nombre] = r["id"]
        elif p.tipo == "third_party":
            body["category_ids"] = [cats_tp[c] for c in body.pop("categorias")]
            api.post("/third-parties/", body, label=p.nombre)
        elif p.tipo == "account":
            api.post("/money-accounts/", body, label=p.nombre)
        elif p.tipo == "material_category":
            r = api.post("/material-categories/", body, label=p.nombre)
            cats_mat[p.nombre] = r["id"]
        elif p.tipo == "material":
            perfil = body.pop("perfil")
            body["category_id"] = cats_mat[body.pop("categoria")]
            body["business_unit_id"] = uns[body.pop("un")]
            r = api.post("/materials/", body, label=p.nombre)
            materiales[p.nombre] = r["id"]
            api.put(f"/material-kg-profiles/{r['id']}", perfil, label=f"perfil-{p.nombre}")
        elif p.tipo == "expense_category":
            r = api.post("/expense-categories/", body, label=p.nombre)
            cat_dep = r["id"]
        elif p.tipo == "increase":
            body["material_id"] = materiales[body.pop("codigo")]
            body["warehouse_id"] = bodegas[body.pop("bodega")]
            api.post("/inventory/adjustments/increase", body, label=p.nombre)
        elif p.tipo == "kg_movement":
            body["account_id"] = cuentas_kg[body.pop("codigo")]
            api.post("/kg-ledger/movements", body, label=p.nombre)
        elif p.tipo == "lead_price":
            api.post("/lead-market-prices", body, label=p.nombre)
        elif p.tipo == "lead_debt":
            continue  # no se escribe: es lo que el balance tiene que mostrar
        elif p.tipo == "fixed_asset":
            body["expense_category_id"] = cat_dep
            api.post("/fixed-assets/", body, label=p.nombre)
        elif p.tipo == "inbound_order":
            body["warehouse_id"] = bodegas[body.pop("bodega")]
            body["lines"] = [
                {"material_id": materiales[ln["codigo"]], "quantity": ln["quantity"]}
                for ln in body.pop("lineas")
            ]
            api.post("/inbound-orders", body, label=p.nombre)
        else:
            raise SystemExit(f"Paso de tipo desconocido: {p.tipo}")
        hechos += 1
    logging.info(f"  fase «{fase}»: {hechos} escrituras")

    if fase == "saldos":
        total = api.get("/third-parties", {"limit": 1}).get("total", 0)
        if total + len(seed.THIRD_PARTIES) >= TOPE_TERCEROS_SEEDER:
            raise SystemExit(
                f"Hay {total} terceros y el seeder solo lee {TOPE_TERCEROS_SEEDER}: NO corra la "
                "provisión, crearía un segundo Willard S.A"
            )


# ============================================================================
# CONCILIAR
# ============================================================================

@dataclass
class Comparacion:
    entidad: str
    rubro: Optional[str]
    esperado: Decimal
    sistema: Optional[Decimal]
    tolerancia: Decimal

    @property
    def diferencia(self) -> Optional[Decimal]:
        return None if self.sistema is None else self.sistema - self.esperado

    @property
    def cuadra(self) -> bool:
        return self.sistema is not None and abs(self.diferencia) <= self.tolerancia


def comparar_entidades(plan: Plan, sistema: dict) -> tuple[list[Comparacion], list[tuple[str, Decimal]]]:
    """Chequeo 1: lo cargado contra el sistema, entidad por entidad.

    `sistema` trae lo leido del backend: terceros/cuentas/activos por clave de
    nombre, inventario por (codigo, bodega) con cantidad y por codigo con valor,
    kg por cuenta/etapa, deuda en plomo valorada y conteo de entradas. Devuelve
    las comparaciones y las entidades del sistema con saldo que el plan NO cargo.
    """
    comps: list[Comparacion] = []
    vistos = {"terceros": set(), "cuentas": set(), "activos": set(), "materiales": set()}
    valor_material: dict[str, Decimal] = {}
    for p in plan.pasos:
        if p.tipo == "third_party":
            k = clave(p.nombre)
            vistos["terceros"].add(k)
            comps.append(Comparacion(f"Tercero {p.nombre}", p.rubro, p.esperado,
                                     sistema["terceros"].get(k), UNO))
        elif p.tipo == "account":
            k = clave(p.nombre)
            vistos["cuentas"].add(k)
            comps.append(Comparacion(f"Cuenta {p.nombre}", p.rubro, p.esperado,
                                     sistema["cuentas"].get(k), UNO))
        elif p.tipo == "fixed_asset":
            k = clave(p.nombre)
            vistos["activos"].add(k)
            comps.append(Comparacion(f"Activo {p.nombre}", p.rubro, p.esperado,
                                     sistema["activos"].get(k), UNO))
        elif p.tipo == "increase":
            codigo, bodega = p.payload["codigo"], p.payload["bodega"]
            vistos["materiales"].add(codigo)
            valor_material[codigo] = valor_material.get(codigo, Decimal("0")) + p.esperado
            comps.append(Comparacion(
                f"Cantidad {codigo} @ {bodega}", None, Decimal(p.payload["quantity"]),
                sistema["stock_bodega"].get((codigo, clave(bodega))), KG_Q,
            ))
        elif p.tipo == "kg_movement":
            k = p.payload["codigo"] + (f"/{p.payload['stage']}" if "stage" in p.payload else "")
            comps.append(Comparacion(f"Kilos {k}", None, p.esperado, sistema["kg"].get(k), KG_Q))
        elif p.tipo == "lead_price":
            comps.append(Comparacion("Precio del plomo vigente", None, p.esperado,
                                     sistema.get("precio_plomo"), CENTAVO))
        elif p.tipo == "lead_debt":
            comps.append(Comparacion("Deuda en plomo con Willard (valorada)", p.rubro, p.esperado,
                                     sistema.get("deuda_plomo"), UNO))
    for codigo, valor in valor_material.items():
        comps.append(Comparacion(f"Valor de {codigo}", "Inventario", valor,
                                 sistema["valor_material"].get(codigo), UNO))
    n_entradas = sum(1 for p in plan.pasos if p.tipo == "inbound_order")
    if n_entradas:
        comps.append(Comparacion("Entradas abiertas", None, Decimal(n_entradas),
                                 sistema.get("entradas"), Decimal("0")))

    sobrantes: list[tuple[str, Decimal]] = []
    for grupo, etiqueta in (("terceros", "Tercero"), ("cuentas", "Cuenta"), ("activos", "Activo")):
        for k, (nombre, saldo) in sistema[f"{grupo}_nombres"].items():
            if k not in vistos[grupo] and abs(saldo) > UNO:
                sobrantes.append((f"{etiqueta} {nombre}", saldo))
    for codigo, valor in sistema["valor_material"].items():
        if codigo not in vistos["materiales"] and abs(valor) > UNO:
            sobrantes.append((f"Material {codigo}", valor))
    return comps, sobrantes


def rubros_del_sistema(balance: dict) -> tuple[dict[str, Decimal], Decimal]:
    """Rubros del Inicio leidos del Balance General. Devuelve tambien lo que no
    quedo en ningun rubro (total de activos menos la suma): tiene que dar cero, o
    hay una seccion del balance que este mapa no conoce."""
    a = {k: Decimal(str(v)) for k, v in balance["assets"].items() if isinstance(v, (int, float))}
    deuda = balance["assets"].get("lead_debt_willard") or {}
    valor_deuda = Decimal(str(deuda.get("value") or 0))
    r = {
        "Disponible": a.get("cash_and_bank", Decimal("0")),
        "Cuentas por cobrar": sum((a.get(k, Decimal("0")) for k in (
            "accounts_receivable", "advances", "loans_receivable", "prepaid_expenses",
            "tax_advances", "provision_funds")), Decimal("0")),
        "Cuentas por cobrar a socios": a.get("investor_receivable", Decimal("0")),
        "Activos fijos": a.get("fixed_assets", Decimal("0")),
        "Inventario": a.get("inventory", Decimal("0")) + valor_deuda,
        "Cuentas por pagar": -Decimal(str(balance["total_liabilities"])),
    }
    activos = sum((r[k] for k in RUBROS if k != "Cuentas por pagar"), Decimal("0"))
    return r, Decimal(str(balance["total_assets"])) - activos


def explicar_rubros(plan: Plan) -> dict[str, list[tuple[str, Decimal]]]:
    """Todo lo que separa el total de Johana del sistema, por rubro y con nombre."""
    exp: dict[str, list[tuple[str, Decimal]]] = {r: [] for r in RUBROS}
    for e in plan.exclusiones:
        if not (e.rubro and e.monto) or e.en_el_sistema == e.rubro:
            continue  # mismo rubro por otro camino: no separa a Johana del sistema
        desc = f"{e.pestana} fila {e.fila} {e.nombre}: {e.motivo}"
        exp[e.rubro].append((desc, e.monto))
        if e.en_el_sistema:
            exp[e.en_el_sistema].append((f"{desc} (Johana lo tiene en {e.rubro})", -e.monto))
    for p in plan.pasos:
        # Una entidad que suma filas de dos rubros (Willard) queda NETA en uno solo.
        if len(p.piezas) > 1:
            destino = p.rubro
            for rubro, pieza in p.piezas.items():
                if rubro != destino:
                    exp[rubro].append((f"{p.nombre}: se carga neto en un solo tercero ({destino})", pieza))
                    exp[destino].append((f"{p.nombre}: absorbe la pieza de {rubro}", -pieza))
    return exp


def leer_sistema(api, plan: Plan) -> dict:
    terceros = _todos(api, "/third-parties")
    cuentas = _todos(api, "/money-accounts")
    activos = _todos(api, "/fixed-assets/")
    stock = _items(api.get("/inventory/stock"))
    s: dict[str, Any] = {
        "terceros": {clave(t["name"]): Decimal(str(t["current_balance"])) for t in terceros},
        "terceros_nombres": {clave(t["name"]): (t["name"], Decimal(str(t["current_balance"]))) for t in terceros},
        "cuentas": {clave(c["name"]): Decimal(str(c["current_balance"])) for c in cuentas},
        "cuentas_nombres": {clave(c["name"]): (c["name"], Decimal(str(c["current_balance"]))) for c in cuentas},
        "activos": {clave(f["name"]): Decimal(str(f["current_value"])) for f in activos
                    if f.get("status") != "cancelled"},
        "activos_nombres": {clave(f["name"]): (f["name"], Decimal(str(f["current_value"]))) for f in activos
                            if f.get("status") != "cancelled"},
        "valor_material": {m["material_code"]: Decimal(str(m["total_value"])) for m in stock},
        "stock_bodega": {},
        "kg": {},
    }
    codigos = {p.payload["codigo"] for p in plan.pasos if p.tipo == "increase"}
    for m in stock:
        if m["material_code"] in codigos:
            det = api.get(f"/inventory/stock/{m['material_id']}")
            for w in det["warehouses"]:
                s["stock_bodega"][(m["material_code"], clave(w["warehouse_name"]))] = Decimal(str(w["stock"]))
    resumen = api.get("/kg-ledger/summary")
    for a in resumen["accounts"]:
        s["kg"][a["code"]] = Decimal(str(a["balance_kg"]))
    s["kg"]["INTERSEDE/horno"] = Decimal(str(resumen["intersede_horno_kg"]))
    s["kg"]["INTERSEDE/crisol"] = Decimal(str(resumen["intersede_crisol_kg"]))
    actual = api.get("/lead-market-prices/current")
    s["precio_plomo"] = Decimal(str(actual["price_per_kg"])) if actual else None
    s["balance"] = api.get("/reports/balance-sheet")
    s["balance_corte"] = api.get("/reports/balance-sheet", {"as_of_date": plan.corte.isoformat()})
    deuda = s["balance"]["assets"].get("lead_debt_willard") or {}
    s["deuda_plomo"] = Decimal(str(deuda["value"])) if deuda.get("value") is not None else None
    s["entradas"] = Decimal(str(api.get("/inbound-orders", {"limit": 1}).get("total", 0)))
    hoy = datetime.now(ZoneInfo("America/Bogota")).date()
    pyg = api.get("/reports/profit-and-loss", {"date_from": "2000-01-01", "date_to": hoy.isoformat()})
    s["utilidad"] = Decimal(str(pyg["net_profit"]))
    return s


def _plata(x: Optional[Decimal]) -> str:
    if x is None:
        return "—"
    return f"{x:,.0f}".replace(",", ".")


def diferencias_balance(vivo: dict, corte: dict, prefijo: str = "") -> list[tuple[str, Any, Any]]:
    """Campos numericos del balance vivo que el balance al corte no repite."""
    out = []
    for k, v in vivo.items():
        w = corte.get(k) if isinstance(corte, dict) else None
        ruta = f"{prefijo}{k}"
        if isinstance(v, dict):
            out += diferencias_balance(v, w or {}, ruta + ".")
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if w is None or abs(Decimal(str(v)) - Decimal(str(w))) > UNO:
                out.append((ruta, v, w))
    return out


def informe(plan: Plan, s: dict, fuente: str) -> tuple[str, int]:
    comps, sobrantes = comparar_entidades(plan, s)
    malas = [c for c in comps if not c.cuadra]
    rubros, sin_rubro = rubros_del_sistema(s["balance"])
    exp = explicar_rubros(plan)
    l: list[str] = []
    l.append(f"# Conciliación de la carga inicial — corte {plan.corte.isoformat()}\n")
    l.append(f"Fuente: {fuente}\n")

    l.append("## Chequeo 1 — lo cargado contra el sistema, entidad por entidad\n")
    l.append(f"{len(comps)} entidades comparadas; **{len(malas)} con diferencia**.\n")
    if malas:
        l.append("| Entidad | Esperado | Sistema | Diferencia |\n|---|---:|---:|---:|")
        for c in malas:
            l.append(f"| {c.entidad} | {_plata(c.esperado)} | {_plata(c.sistema)} | {_plata(c.diferencia)} |")
        l.append("")
    l.append(f"Entidades del sistema con saldo que la carga no puso: **{len(sobrantes)}**.\n")
    for nombre, saldo in sobrantes:
        l.append(f"- {nombre}: {_plata(saldo)}")

    l.append("\n## Chequeo 2 — Johana contra el sistema, por rubro\n")
    l.append("Signo del sistema: activos en positivo, cuentas por pagar en negativo.\n")
    l.append("| Rubro | Johana | Sistema | Diferencia | Explicado | Sin explicar |\n|---|---:|---:|---:|---:|---:|")
    rubros_malos = 0
    for r in RUBROS:
        j = plan.johana.get(r)
        sis = rubros[r]
        dif = None if j is None else j - sis
        explicado = sum((m for _, m in exp[r]), Decimal("0"))
        resto = None if dif is None else dif - explicado
        if resto is None or abs(resto) > UNO:
            rubros_malos += 1  # sin total de Johana tampoco se puede dar por bueno
        l.append(f"| {r} | {_plata(j)} | {_plata(sis)} | {_plata(dif)} | {_plata(explicado)} | {_plata(resto)} |")
    l.append(f"\nActivos del balance que no cayeron en ningún rubro: {_plata(sin_rubro)} (tiene que ser 0).\n")
    for r in RUBROS:
        if exp[r]:
            l.append(f"\n### {r}: lo que explica la diferencia\n")
            for desc, m in exp[r]:
                l.append(f"- {_plata(m)} — {desc}")

    l.append("\n## Invariantes\n")
    l.append(f"- Utilidad neta acumulada hasta hoy: **{_plata(s['utilidad'])}** (tiene que ser 0: la carga no toca resultados).")
    d_corte = diferencias_balance(s["balance"], s["balance_corte"])
    d_corte = [d for d in d_corte if d[0] != "as_of_date"]
    l.append(f"- Balance al corte ({plan.corte.isoformat()}) contra el balance de hoy: **{len(d_corte)} campos distintos**"
             " (sin operaciones después de la carga, tendrían que coincidir).")
    for ruta, v, w in d_corte:
        l.append(f"  - {ruta}: hoy {_plata(Decimal(str(v)))} · al corte {_plata(None if w is None else Decimal(str(w)))}")
    b = s["balance"]
    l.append(f"- Activos {_plata(Decimal(str(b['total_assets'])))} − pasivos {_plata(Decimal(str(b['total_liabilities'])))}"
             f" = patrimonio {_plata(Decimal(str(b['equity'])))}. Es tautológico (el patrimonio es residual, #110): se imprime para leerlo, no es un chequeo.")

    l.append("\n## Cruces internos del Sheet\n")
    for desc, a, c in plan.cruces:
        marca = "cuadra" if abs(a - c) <= UNO else "NO CUADRA"
        l.append(f"- {desc}: {_plata(a)} vs {_plata(c)} — {marca}")
    if plan.avisos:
        l.append("\n## Avisos de la lectura\n")
        for a in plan.avisos:
            l.append(f"- {a}")

    # Todo lo que el informe marca como malo es una falla: un chequeo que se
    # imprime y no se cuenta sale verde con el defecto adentro (paso en la
    # ronda 1: dos rubros sin explicar y «0 fallas»).
    cruces_malos = sum(1 for _, a, c in plan.cruces if abs(a - c) > UNO)
    fallas = len(malas) + len(sobrantes) + (0 if abs(s["utilidad"]) <= UNO else 1)
    fallas += 0 if abs(sin_rubro) <= UNO else 1
    fallas += rubros_malos + cruces_malos + len(d_corte)
    l.insert(2, f"**Resultado: {fallas} {'falla' if fallas == 1 else 'fallas'}.** Cuenta como falla: una "
                "entidad con diferencia, un saldo que la carga no puso, un rubro sin explicar, un cruce "
                "que no cuadra, un campo distinto entre el corte y hoy, utilidad distinta de 0 o un "
                "activo fuera de los rubros.\n")
    return "\n".join(l) + "\n", fallas


# ============================================================================
# MAIN
# ============================================================================

def _resumen_plan(plan: Plan, fase: Optional[str]) -> None:
    pasos = plan.de(fase) if fase else plan.pasos
    conteo: dict[str, int] = {}
    for p in pasos:
        conteo[p.tipo] = conteo.get(p.tipo, 0) + 1
    logging.info(f"Plan ({fase or 'todas las fases'}): " + ", ".join(f"{k} {v}" for k, v in conteo.items()))
    logging.info(f"Exclusiones: {len(plan.exclusiones)}")
    for e in plan.exclusiones:
        logging.info(f"  - {e.pestana} fila {e.fila} {e.nombre} [{_plata(e.monto)}]: {e.motivo}")
    for a in plan.avisos:
        logging.warning(f"  aviso: {a}")
    for e in plan.errores:
        logging.error(f"  ERROR: {e}")


def validar_destino(api, ensayo: bool) -> None:
    """--ensayo acepta valores provisionales: nunca contra un backend remoto. Y
    la carga remota (produccion) no existe en la ronda 1: es otro plan."""
    if ensayo and not api.is_local:
        raise SystemExit(f"--ensayo solo corre contra un backend local, no contra {api.base_url}")
    if not api.is_local:
        raise SystemExit("La carga contra un backend remoto no está habilitada en este plan (ronda 1)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Carga inicial de SAC desde el Sheet exportado")
    parser.add_argument("--file", required=True, help="Sheet exportado a .xlsx")
    parser.add_argument("--corte", required=True, help="Fecha de corte del balance (YYYY-MM-DD)")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--fase", choices=("saldos", "resto"))
    grupo.add_argument("--conciliar", action="store_true")
    parser.add_argument("--apply", action="store_true", help="Escribir (default: solo imprime el plan)")
    parser.add_argument("--ensayo", action="store_true", help="Ensayo local: acepta valores provisionales")
    parser.add_argument("--salida", help="Archivo del informe de conciliación")
    parser.add_argument("--api-url", default=seed.BASE_URL)
    # Por variable de entorno, como el seeder: en la linea de comandos la clave
    # quedaria a la vista de `ps` y en el historial.
    parser.add_argument("--superuser-email", default=os.environ.get("SEED_SU_EMAIL"))
    parser.add_argument("--superuser-password", default=os.environ.get("SEED_SU_PASSWORD"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    api = seed.APIClient(dry_run=False, base_url=args.api_url)
    validar_destino(api, args.ensayo)

    corte = date.fromisoformat(args.corte)
    sha = hashlib.sha256(Path(args.file).read_bytes()).hexdigest()
    try:
        libro = leer_libro(args.file)
    except ErrorDeLibro as e:
        raise SystemExit(f"El archivo no tiene la forma esperada: {e}")
    plan = armar_plan(libro, corte, ensayo=args.ensayo)
    logging.info(f"Archivo {args.file} sha256={sha}")
    _resumen_plan(plan, args.fase)
    if plan.errores:
        raise SystemExit(f"{len(plan.errores)} errores en el Sheet: no se escribe nada")

    if not (args.apply or args.conciliar):
        logging.info("Simulación: no se escribió nada (use --apply)")
        return
    if not args.superuser_email or not args.superuser_password:
        raise SystemExit("Faltan credenciales: SEED_SU_EMAIL / SEED_SU_PASSWORD en el entorno")
    api.login(args.superuser_email, args.superuser_password)
    org = ubicar_org(api)
    logging.info(f"Org {seed.ORG_NAME} = {org} en {args.api_url}")

    if args.fase:
        aplicar(plan, args.fase, api)
        return
    s = leer_sistema(api, plan)
    texto_informe, fallas = informe(plan, s, f"{args.file} (sha256 {sha})")
    if args.salida:
        Path(args.salida).write_text(texto_informe, encoding="utf-8")
        logging.info(f"Informe en {args.salida}")
    else:
        print(texto_informe)
    logging.info(f"Fallas de conciliación: {fallas}")
    if fallas:
        raise SystemExit(4)


if __name__ == "__main__":
    main()
