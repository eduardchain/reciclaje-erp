"""Marca inicial de los terceros de un recolector (SAC, Green Loop; plan §9).

Decision 4 de Daniel (20-nov): «todo lo que diga green loop es green loop».
La marca sale de una REGLA sobre el nombre, corrida contra la base que se marca
(en produccion, al deploy), nunca contra una lista sacada de dev: los ids de
produccion son otros.

Uso:
    scripts/marcar_recolector.py --api-url <url> --org-id <uuid> \\
        --collector-id <uuid> [--esperado N] [--apply]

Credenciales SOLO por SEED_SU_EMAIL / SEED_SU_PASSWORD; no se imprimen (#114).

La regla. Se marca un tercero si:
  1. es de la org de --org-id (nunca por nombre: en dev hay cinco «SAC», y
     Costa tiene «Bio Green Loop- Maquila» y «Maquila Greenloop»);
  2. su nombre normalizado contiene «greenloop» o «greenlop» (NFKD, sin marcas
     diacriticas, minusculas, solo a-z);
  3. esta activo;
  4. no esta en las exclusiones: el recolector mismo (por id) y «BIOGREENLOOP»
     (por nombre normalizado exacto; decision de Daniel). Si una exclusion no
     aparece, o aparece dos veces, la corrida es una SORPRESA.

Codigos de salida:
  0  sin sorpresas (con --apply: todo lo previsto quedo marcado);
  1  un PATCH fallo (lo ya marcado queda; re-correr es idempotente);
  2  aborto antes de leer terceros o con el listado incompleto: la org no
     existe, esta inactiva o no tiene kg_ledger_enabled; el recolector no es
     valido; el listado no trajo len == total;
  3  sorpresa: no se escribe NADA, ni con --apply.
"""
from __future__ import annotations

import argparse
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seed_sac_org as seed  # noqa: E402

PATRONES = ("greenloop", "greenlop")
EXCLUIDO_POR_NOMBRE = "biogreenloop"

MOTIVO_RECOLECTOR = "es el recolector (S3: la marca no apunta a su propio tercero)"
MOTIVO_BIOGREENLOOP = "BIOGREENLOOP: decision de Daniel (20-nov), la maneja Johana"
MOTIVO_INACTIVO = "inactivo (saldo 0 y fuera de los selectores; si se reactiva, se marca a mano)"
MOTIVO_YA_MARCADO = "ya marcado con este recolector"

EXIT_OK = 0
EXIT_PATCH = 1
EXIT_ABORTO = 2
EXIT_SORPRESA = 3


# ---------------------------------------------------------------------------
# Funciones puras (T21)
# ---------------------------------------------------------------------------

def normalizar(nombre: str) -> str:
    """NFKD, sin marcas diacriticas, minusculas y solo a-z. Una sola funcion."""
    descompuesto = unicodedata.normalize("NFKD", nombre or "")
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return "".join(c for c in sin_marcas.lower() if "a" <= c <= "z")


def cumple_regla(nombre: str) -> bool:
    n = normalizar(nombre)
    return any(p in n for p in PATRONES)


def verificar_org(org: Optional[dict], org_id: str) -> list[str]:
    """Errores que abortan con exit 2. `org` es la respuesta de
    GET /organizations/{id} (None si dio 404: el backend se lo da al
    superusuario cuando la org esta inactiva)."""
    if org is None:
        return [f"la org {org_id} no existe o esta inactiva (GET /organizations/{{id}} dio 404)"]
    errores = []
    if str(org.get("id")) != str(org_id):
        errores.append(f"la respuesta trae otra org ({org.get('id')})")
    if not org.get("is_active", False):
        errores.append(f"la org «{org.get('name')}» esta inactiva")
    if not (org.get("settings") or {}).get("kg_ledger_enabled"):
        errores.append(f"la org «{org.get('name')}» no tiene kg_ledger_enabled")
    return errores


def verificar_recolector(tp: Optional[dict], org_id: str, collector_id: str) -> list[str]:
    """Las reglas de §3, antes de la primera escritura (el PATCH las repite)."""
    if tp is None:
        return [f"el recolector {collector_id} no existe en la org"]
    errores = []
    if str(tp.get("organization_id")) != str(org_id):
        errores.append(f"el recolector «{tp.get('name')}» es de otra org")
    if not tp.get("is_active", False):
        errores.append(f"el recolector «{tp.get('name')}» esta inactivo")
    if not any(c.get("behavior_type") == "service_provider" for c in tp.get("categories") or []):
        errores.append(f"el recolector «{tp.get('name')}» no es service_provider")
    if tp.get("collector_id") is not None:
        errores.append(f"el recolector «{tp.get('name')}» esta marcado con otro recolector")
    return errores


@dataclass
class Plan:
    a_marcar: list[dict] = field(default_factory=list)
    excluidos: list[tuple[dict, str]] = field(default_factory=list)
    saltados: list[tuple[dict, str]] = field(default_factory=list)
    informativos: list[tuple[dict, str]] = field(default_factory=list)
    sorpresas: list[str] = field(default_factory=list)
    cumplen: int = 0
    activos: int = 0

    @property
    def ya_marcados(self) -> int:
        return sum(1 for _, m in self.saltados if m == MOTIVO_YA_MARCADO)

    @property
    def inactivos(self) -> int:
        return sum(1 for _, m in self.saltados if m == MOTIVO_INACTIVO)


def armar_plan(
    terceros: list[dict], org_id: str, collector_id: str, esperado: Optional[int] = None,
) -> Plan:
    """El plan entero, antes de la primera escritura."""
    plan = Plan()
    vistos_recolector = 0
    vistos_bio = 0
    collector_id = str(collector_id)
    for tp in terceros:
        tp_id = str(tp["id"])
        nombre = tp.get("name") or ""
        marca = tp.get("collector_id")
        marca = str(marca) if marca is not None else None
        if str(tp.get("organization_id")) != str(org_id):
            plan.sorpresas.append(f"el listado trajo un tercero de otra org: «{nombre}» ({tp_id})")
            continue
        if not cumple_regla(nombre):
            if marca == collector_id:
                plan.informativos.append(
                    (tp, "marcado con este recolector fuera de la regla (a mano): no se desmarca"))
            continue
        plan.cumplen += 1
        if tp.get("is_active", False):
            plan.activos += 1
        if tp_id == collector_id:
            vistos_recolector += 1
            plan.excluidos.append((tp, MOTIVO_RECOLECTOR))
        elif normalizar(nombre) == EXCLUIDO_POR_NOMBRE:
            vistos_bio += 1
            plan.excluidos.append((tp, MOTIVO_BIOGREENLOOP))
        elif not tp.get("is_active", False):
            plan.saltados.append((tp, MOTIVO_INACTIVO))
        elif marca == collector_id:
            plan.saltados.append((tp, MOTIVO_YA_MARCADO))
        elif marca is not None:
            plan.sorpresas.append(
                f"«{nombre}» ({tp_id}) esta marcado con OTRO recolector ({marca}): no se pisa")
        else:
            plan.a_marcar.append(tp)
    if vistos_recolector != 1:
        plan.sorpresas.append(
            f"el recolector aparece {vistos_recolector} veces entre los que cumplen la regla "
            "(se esperaba 1): su nombre cambio o no es el que se cree")
    if vistos_bio != 1:
        plan.sorpresas.append(
            f"«BIOGREENLOOP» aparece {vistos_bio} veces entre los que cumplen la regla "
            "(se esperaba 1): si cambio de nombre, quedaria marcado sin que nadie lo viera")
    if esperado is not None and len(plan.a_marcar) != esperado:
        plan.sorpresas.append(
            f"a marcar: {len(plan.a_marcar)}, y la prediccion escrita era {esperado}")
    return plan


def imprimir(plan: Plan, out=print) -> None:
    out(f"cumplen la regla: {plan.cumplen} (activos: {plan.activos})")
    motivos: dict[str, int] = {}
    for _, m in plan.excluidos:
        motivos[m] = motivos.get(m, 0) + 1
    for m, n in motivos.items():
        out(f"excluidos — {m}: {n}")
    out(f"inactivos saltados: {plan.inactivos}")
    out(f"ya marcados: {plan.ya_marcados}")
    out(f"a marcar: {len(plan.a_marcar)}")
    out("--- a marcar ---")
    for tp in sorted(plan.a_marcar, key=lambda t: normalizar(t.get("name") or "")):
        out(f"  {tp['id']}  {tp.get('name')}")
    out("--- excluidos y saltados, con su motivo ---")
    for tp, m in plan.excluidos + plan.saltados:
        out(f"  {tp['id']}  {tp.get('name')}  — {m}")
    if plan.informativos:
        out("--- informativo ---")
        for tp, m in plan.informativos:
            out(f"  {tp['id']}  {tp.get('name')}  — {m}")
    if plan.sorpresas:
        out("--- SORPRESAS (no se escribe nada) ---")
        for s in plan.sorpresas:
            out(f"  {s}")


# ---------------------------------------------------------------------------
# Corrida (el cliente HTTP se inyecta: los tests usan un doble)
# ---------------------------------------------------------------------------

class Cliente:
    """Las tres llamadas que hace el script, sobre el APIClient del seeder."""

    def __init__(self, api: "seed.APIClient"):
        self.api = api

    def usar_org(self, org_id: str) -> None:
        """Desde aca las llamadas van con X-Organization-ID de la org."""
        self.api.org_id = str(org_id)

    def get_opcional(self, path: str) -> Optional[dict]:
        url = f"{self.api.base_url}{seed.API_PREFIX}{path}"
        r = self.api.session.get(url, headers=self.api._headers())
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise SystemExit(f"GET {path} fallo [{r.status_code}]: {r.text[:300]}")
        return r.json()

    def listar_terceros(self) -> list[dict]:
        # `list_all` pagina hasta el total y se detiene si no llega (#115).
        return self.api.list_all("/third-parties")

    def patch(self, path: str, body: dict) -> dict:
        return self.api.patch(path, body, label="marca de recolector")


def ejecutar(cliente, org_id: str, collector_id: str, apply: bool,
             esperado: Optional[int], out=print) -> int:
    org = cliente.get_opcional(f"/organizations/{org_id}")
    errores = verificar_org(org, org_id)
    if errores:
        for e in errores:
            out(f"ABORTA: {e}")
        return EXIT_ABORTO
    cliente.usar_org(org_id)
    recolector = cliente.get_opcional(f"/third-parties/{collector_id}")
    errores = verificar_recolector(recolector, org_id, collector_id)
    if errores:
        for e in errores:
            out(f"ABORTA: {e}")
        return EXIT_ABORTO
    out(f"org: «{org['name']}» ({org_id}) · recolector: «{recolector['name']}» ({collector_id})")
    try:
        terceros = cliente.listar_terceros()
    except SystemExit as exc:
        out(f"ABORTA: listado de terceros incompleto: {exc}")
        return EXIT_ABORTO
    out(f"terceros leidos: {len(terceros)}")

    plan = armar_plan(terceros, org_id, collector_id, esperado)
    imprimir(plan, out)
    if plan.sorpresas:
        out(f"EXIT={EXIT_SORPRESA}: hay sorpresas; no se escribio nada")
        return EXIT_SORPRESA
    if not apply:
        out("dry-run: no se escribio nada (con --apply se marcan los de arriba)")
        return EXIT_OK
    escritos = 0
    for tp in plan.a_marcar:
        try:
            cliente.patch(f"/third-parties/{tp['id']}", {"collector_id": str(collector_id)})
        except SystemExit as exc:
            out(f"PATCH fallo en «{tp.get('name')}» ({tp['id']}): {exc}")
            out(f"marcados antes de fallar: {escritos}. Re-correr es idempotente.")
            return EXIT_PATCH
        escritos += 1
    out(f"marcados: {escritos}")
    return EXIT_OK


def main() -> None:
    parser = argparse.ArgumentParser(description="Marca inicial de los terceros de un recolector")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--org-id", required=True)
    parser.add_argument("--collector-id", required=True)
    parser.add_argument("--esperado", type=int, default=None,
                        help="Cuantos se espera marcar; si no coincide, exit 3 sin escribir")
    parser.add_argument("--apply", action="store_true", help="Escribir (default: dry-run)")
    args = parser.parse_args()
    email = os.environ.get("SEED_SU_EMAIL")
    password = os.environ.get("SEED_SU_PASSWORD")
    if not email or not password:
        raise SystemExit("Faltan credenciales: SEED_SU_EMAIL / SEED_SU_PASSWORD en el entorno")
    api = seed.APIClient(dry_run=False, base_url=args.api_url)
    if not api.is_local:
        print(f"*** DESTINO REMOTO: {args.api_url} ***")
    api.login(email, password)
    code = ejecutar(Cliente(api), args.org_id, args.collector_id, args.apply, args.esperado)
    print(f"EXIT={code}")
    sys.exit(code)


if __name__ == "__main__":
    main()
