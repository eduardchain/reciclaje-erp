"""Archivar la org SAC antes de una carga, y darla de baja despues, sin dejar
a ningun usuario sin acceso.

Por que existe: el cargador de la carga inicial (load_sac_opening.py) necesita
una org VACIA, y el seeder solo la recrea con --reset, que esta prohibido
contra un servidor remoto. La razon de esa prohibicion es real: dar de baja
una org (DELETE /system/organizations/{id}) DESACTIVA a los usuarios que no
pertenecen a otra org, y reactivarlos solo se puede por la base de datos, que
en produccion no se toca.

Este script evita eso con el orden:

  1. --modo archivar: renombra la org activa «SAC» a «SAC (archivada <fecha>)».
     Los usuarios conservan su membresia; nadie pierde acceso.
  2. seed_sac_org.py --org-vacia (sin --reset) crea la «SAC» nueva y agrega a
     los usuarios; despues van el cargador y la provision.
  3. --modo baja --org-id <la archivada>: antes de dar de baja, verifica que
     cada miembro de la archivada tambien pertenezca a la «SAC» activa, sin
     excepcion para superusuarios (el backend tampoco la hace). Si falta
     alguno, se detiene y lo nombra; con
     --copiar-miembros lo agrega a la nueva con el rol del mismo nombre. Asi la
     baja no desactiva a nadie, y el script lo comprueba en la respuesta.

Para volver atras, --modo restaurar --org-id <la archivada> le devuelve el
nombre «SAC» y la deja activa, aunque ya este dada de baja (la pantalla de
Sistema renombra pero no reactiva). Exige que no haya otra «SAC» activa.

Antes de los tres, --modo revisar (solo lectura, nunca escribe) lista lo que
la «SAC» nueva NO va a heredar de la vieja: miembros que el seeder no vuelve a
agregar, tarifas vigentes distintas de las del seeder, centros Willard, precios
del plomo y documentos ya registrados. Archivar no borra nada (la vieja queda
intacta, renombrada), pero lo que el cliente configuro en ella no pasa solo.

Sin --apply solo imprime lo que haria. Credenciales por SEED_SU_EMAIL /
SEED_SU_PASSWORD, nunca en la linea de comandos.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import unicodedata
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seed_sac_org as seed  # noqa: E402

PREFIJO_ARCHIVADA = f"{seed.ORG_NAME} (archivada"


def nombre_archivada(ahora: datetime) -> str:
    return f"{PREFIJO_ARCHIVADA} {ahora.strftime('%Y-%m-%d %H%M')})"


def _orgs(api) -> list[dict]:
    # Con las dadas de baja: sin `include_inactive` el backend no las lista, y
    # `restaurar` no encontraria justo la org que tiene que reactivar (lo
    # encontro el ensayo contra el alias: «No existe la org»). Quien necesita
    # solo las activas las filtra (org_activa).
    return api.get("/system/organizations", {"include_inactive": True})


def org_activa(api) -> dict:
    """La org activa que se llama exactamente «SAC». Una sola, o se detiene."""
    activas = [o for o in _orgs(api) if o["name"] == seed.ORG_NAME and o.get("is_active", True)]
    if len(activas) != 1:
        raise SystemExit(
            f"Se esperaba UNA org activa «{seed.ORG_NAME}» y hay {len(activas)}. No se sigue."
        )
    return activas[0]


def miembros(usuarios: list[dict], org_id: str) -> list[dict]:
    return [u for u in usuarios
            if any(str(m["organization_id"]) == str(org_id) for m in u.get("memberships", []))]


def rol_en(usuario: dict, org_id: str) -> str:
    for m in usuario.get("memberships", []):
        if str(m["organization_id"]) == str(org_id):
            return m["role_name"]
    raise KeyError(org_id)


def archivar(api, apply: bool, ahora: datetime) -> dict:
    org = org_activa(api)
    nuevo = nombre_archivada(ahora)
    gente = miembros(api.get("/system/users"), org["id"])
    logging.info(f"Org a archivar: {org['name']} id={org['id']} ({len(gente)} miembros)")
    for u in gente:
        logging.info(f"  {u['email']} ({rol_en(u, org['id'])})")
    if not apply:
        logging.info(f"Simulación: se renombraría a «{nuevo}» (use --apply)")
        return org
    r = api.patch(f"/system/organizations/{org['id']}", {"name": nuevo}, label="archivar")
    if r.get("name") != nuevo or not r.get("is_active", True):
        raise SystemExit(f"El renombre no quedó como se esperaba: {r}")
    logging.info(f"Archivada: «{nuevo}». Sigue activa y sus usuarios conservan el acceso.")
    return r


def dar_de_baja(api, org_id: str, apply: bool, copiar: bool) -> None:
    orgs = {str(o["id"]): o for o in _orgs(api)}
    vieja = orgs.get(str(org_id))
    if vieja is None:
        raise SystemExit(f"No existe la org {org_id}.")
    if not vieja["name"].startswith(PREFIJO_ARCHIVADA):
        raise SystemExit(
            f"La org {org_id} se llama «{vieja['name']}»: solo se da de baja una org "
            f"archivada («{PREFIJO_ARCHIVADA} …»). No se sigue."
        )
    if not vieja.get("is_active", True):
        raise SystemExit(f"La org «{vieja['name']}» ya está dada de baja.")
    nueva = org_activa(api)
    usuarios = api.get("/system/users")
    en_nueva = {u["id"] for u in miembros(usuarios, nueva["id"])}
    # SIN excepcion para superusuarios (B2 de QA, 10-nov): el backend
    # (delete_system_organization) desactiva a TODO miembro sin otra membresia,
    # superusuario o no. Si fuera la cuenta con la que se corre, quedaria afuera
    # y reactivarla exigiria tocar la base de produccion.
    faltan = [u for u in miembros(usuarios, org_id) if u["id"] not in en_nueva]
    logging.info(
        f"Baja de «{vieja['name']}» ({org_id}). Org activa «{nueva['name']}» = {nueva['id']}."
    )
    if faltan:
        lista = ", ".join(f"{u['email']} ({rol_en(u, org_id)})" for u in faltan)
        if not copiar:
            raise SystemExit(
                f"{len(faltan)} miembro(s) de la archivada no están en la «{seed.ORG_NAME}» "
                f"activa y quedarían DESACTIVADOS: {lista}. Agréguelos o use --copiar-miembros."
            )
        roles = {r["name"]: r["id"] for r in
                 api.get(f"/system/organizations/{nueva['id']}/roles")}
        sin_rol = [u["email"] for u in faltan if rol_en(u, org_id) not in roles]
        if sin_rol:
            raise SystemExit(
                f"La org nueva no tiene el rol de: {', '.join(sin_rol)}. No se sigue."
            )
        for u in faltan:
            logging.info(f"  Copiar {u['email']} con rol {rol_en(u, org_id)}")
            if apply:
                api.post(f"/system/users/{u['id']}/add-to-org",
                         {"organization_id": nueva["id"], "role_id": roles[rol_en(u, org_id)]},
                         label=f"copiar-{u['email']}")
    if not apply:
        logging.info("Simulación: no se dio de baja nada (use --apply)")
        return
    url = f"{api.base_url}{seed.API_PREFIX}/system/organizations/{org_id}"
    r = api.session.delete(url, headers=api._headers())
    if r.status_code >= 400:
        raise SystemExit(f"DELETE falló [{r.status_code}]: {r.text[:300]}")
    huerfanos = r.json().get("orphaned_users_deactivated")
    logging.info(f"Dada de baja. Usuarios desactivados: {huerfanos}")
    if huerfanos != 0:
        raise SystemExit(
            f"La baja desactivó {huerfanos} usuario(s): revisar /system/users de inmediato."
        )


def restaurar(api, org_id: str, apply: bool) -> dict:
    """Devuelve una org archivada a «SAC» y la deja activa: la vuelta atras.

    Sirve en dos momentos (C1 de QA, 10-nov):
      - la ronda fallo en el paso 2, con la vieja ya archivada y la nueva sin
        crear: no queda ninguna «SAC» activa y los usuarios no tienen donde
        trabajar;
      - despues de la baja, si hay que volver a la anterior: la pantalla de
        Sistema → Organizaciones renombra pero NO reactiva, y el PATCH si
        acepta `is_active`.
    Solo toca una org cuyo nombre empieza con «SAC (archivada»: un id
    equivocado no puede renombrar a otra empresa. Y exige que no haya otra
    «SAC» activa, porque dos con el mismo nombre confundirian al seeder y al
    cargador; esa se archiva primero.
    """
    orgs = {str(o["id"]): o for o in _orgs(api)}
    org = orgs.get(str(org_id))
    if org is None:
        raise SystemExit(f"No existe la org {org_id}.")
    if not org["name"].startswith(PREFIJO_ARCHIVADA):
        raise SystemExit(
            f"La org {org_id} se llama «{org['name']}»: solo se restaura una org "
            f"archivada («{PREFIJO_ARCHIVADA} …»). No se sigue."
        )
    otras = [o for o in orgs.values()
             if o["name"] == seed.ORG_NAME and o.get("is_active", True)]
    if otras:
        raise SystemExit(
            f"Ya hay una org activa «{seed.ORG_NAME}» ({otras[0]['id']}). Archívela primero "
            "(--modo archivar --apply) y después restaure esta."
        )
    estado = "activa" if org.get("is_active", True) else "dada de baja"
    logging.info(f"Org a restaurar: «{org['name']}» id={org['id']} ({estado})")
    if not apply:
        logging.info(f"Simulación: se renombraría a «{seed.ORG_NAME}» y quedaría activa (use --apply)")
        return org
    r = api.patch(f"/system/organizations/{org['id']}",
                  {"name": seed.ORG_NAME, "is_active": True}, label="restaurar")
    if r.get("name") != seed.ORG_NAME or not r.get("is_active", False):
        raise SystemExit(f"La restauración no quedó como se esperaba: {r}")
    logging.info(
        f"Restaurada: «{seed.ORG_NAME}», activa. Cada usuario tiene que volver a elegirla "
        "en el selector."
    )
    return r


#: Documentos que una org puede tener registrados: (ruta, etiqueta). Quedan en
#: la archivada; la nueva nace sin ellos.
DOCUMENTOS = [
    ("/purchases", "compras"), ("/sales", "ventas"), ("/double-entries", "doble partidas"),
    ("/inbound-orders", "entradas"), ("/willard-deliveries", "salidas de plomo"),
    ("/crucible-charges", "documentos de crisol"), ("/money-movements", "movimientos de tesorería"),
    ("/transfers", "traslados"), ("/inventory/adjustments", "ajustes de inventario"),
    ("/inventory/transformations", "transformaciones"), ("/fixed-assets/", "activos fijos"),
]

#: Lo que el seeder no siembra nunca: si existe, lo creo alguien a mano.
SIN_SEMBRAR = [
    ("/drivers", "conductores"), ("/vehicles", "vehículos"),
    ("/price-list-groups", "listas de precios por proveedor (#98)"),
]


def _catalogos(is_local: bool) -> list[tuple[str, str, set[str], str]]:
    """(ruta, campo, lo que siembra el seeder EN ESTE DESTINO, etiqueta). Lo que
    sobra lo creo alguien, o es algo que el seeder ya no siembra aca: contra un
    remoto los PRUEBA-* no se siembran (Daniel, 10-nov), asi que si la org
    activa los tiene, la nueva nace sin ellos y hay que avisarlo."""
    terceros = seed.THIRD_PARTIES + (seed.THIRD_PARTIES_LOCAL if is_local else [])
    return [
        ("/materials", "code", {m[0] for m in seed.MATERIALS}, "materiales"),
        ("/warehouses", "name", {w[0] for w in seed.WAREHOUSES}, "bodegas"),
        ("/money-accounts", "name", {a["name"] for a in seed.ACCOUNTS}, "cuentas de dinero"),
        ("/third-parties", "name", {t[0] for t in terceros}, "terceros"),
        ("/expense-categories/flat", "name", {c[0] for c in seed.EXPENSE_CATEGORIES}, "categorías de gasto"),
        ("/business-units", "name", set(seed.BUSINESS_UNITS), "unidades de negocio"),
        ("/material-categories", "name", set(seed.MATERIAL_CATEGORIES), "categorías de material"),
    ]


def _cuantos(respuesta) -> int:
    if isinstance(respuesta, dict):
        return int(respuesta.get("total", len(respuesta.get("items", []))))
    return len(respuesta)


def _norm(texto) -> str:
    sin = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode()
    return sin.strip().lower()


def _lista(nombres, limite: int = 10) -> str:
    nombres = sorted(nombres)
    resto = len(nombres) - limite
    return ", ".join(nombres[:limite]) + (f" y {resto} más" if resto > 0 else "")


def _numero(x) -> Decimal:
    return Decimal(str(x))


def revisar(api) -> list[str]:
    """Solo lectura. Devuelve lo que la «SAC» nueva no heredaria de la activa.

    Archivar no borra nada: todo esto queda en la org archivada. Pero la nueva
    nace con lo que siembran el seeder y la carga, y nada mas. Cada aviso es algo
    que Daniel decide antes de escribir (C3 de QA, 10-nov).
    """
    org = org_activa(api)
    avisos: list[str] = []

    def leer(ruta, params=None):
        try:
            return api.get(ruta, params)
        except SystemExit as e:  # APIClient.get corta con SystemExit ante un 4xx/5xx
            avisos.append(f"No se pudo leer {ruta}: {e}")
            return None

    def todas(ruta) -> list[dict]:
        """El listado completo (pagina hasta el total y corta si no llega, N1)."""
        try:
            return seed.APIClient.list_all(api, ruta)
        except SystemExit as e:
            avisos.append(f"No se pudo leer completo {ruta}: {e}")
            return []

    # -- Usuarios: que existan los del seeder, y quien queda afuera de la nueva
    usuarios = api.get("/system/users")
    emails = {u["email"].lower() for u in usuarios}
    for u in seed.USERS:
        if u["email"].lower() not in emails:
            avisos.append(f"Usuario del seeder {u['email']} no existe en el servidor: el seeder se "
                          "va a detener (no crea usuarios contra un remoto). Créelo antes con una clave propia")
    del_seeder = {u["email"].lower() for u in seed.USERS}
    roles_seeder = {"admin", seed.BASCULA_ROLE["name"], seed.REVISOR_ROLE["name"]}
    gente = miembros(usuarios, org["id"])
    logging.info(f"Org «{org['name']}» id={org['id']}: {len(gente)} miembros")
    for u in gente:
        rol = rol_en(u, org["id"])
        su = " (superusuario)" if u.get("is_superuser") else ""
        if u["email"].lower() in del_seeder:
            nota = "el seeder lo vuelve a agregar"
        else:
            # Sin excepcion para superusuarios (B2): la baja tambien los desactiva.
            nota = "el seeder NO lo agrega: la baja va a necesitar --copiar-miembros"
            avisos.append(f"Miembro {u['email']}{su} ({rol}) no está en el seeder: --copiar-miembros en la baja")
        if rol not in roles_seeder:
            avisos.append(f"Miembro {u['email']} tiene el rol «{rol}», que la org nueva no va a tener")
        logging.info(f"  {u['email']}{su} ({rol}): {nota}")

    api.org_id = org["id"]
    try:
        # -- Documentos y lo que el seeder no siembra nunca
        for ruta, etiqueta in DOCUMENTOS + SIN_SEMBRAR:
            r = leer(ruta, {"limit": 1})
            if r is not None and _cuantos(r) > 0:
                avisos.append(f"La org tiene {_cuantos(r)} {etiqueta}: quedan en la archivada, la nueva nace sin ellos")

        # -- Catalogos: lo que alguien creo a mano, y saldos que no son de la carga
        for ruta, campo, sembrado, etiqueta in _catalogos(api.is_local):
            filas = [f for f in todas(ruta) if f.get("is_active", True) and not f.get("system_code")]
            extra = {str(f[campo]) for f in filas} - sembrado
            if extra:
                avisos.append(f"{len(extra)} {etiqueta} que el seeder no siembra: {_lista(extra)}")
            if ruta in ("/third-parties", "/money-accounts"):
                con_saldo = [f["name"] for f in filas if _numero(f.get("current_balance") or 0) != 0]
                if con_saldo:
                    avisos.append(f"{len(con_saldo)} {etiqueta} con saldo distinto de 0: {_lista(con_saldo)}")

        # -- Tarifas vigentes contra las del seeder
        sembradas = {t["tariff_code"]: _numero(t["unit_price_cop"]) for t in seed.TARIFFS}
        for t in todas("/service-tariffs/current"):
            codigo, precio = t["tariff_code"], _numero(t["unit_price_cop"])
            if sembradas.get(codigo) != precio:
                avisos.append(f"Tarifa {codigo} vigente en {precio}; la nueva nace con "
                              f"{sembradas.get(codigo, 'nada (el seeder no la siembra)')}")

        # -- Formulas vigentes y perfiles kg contra MATERIALS
        por_codigo = {m[0]: m for m in seed.MATERIALS}
        distintas = []
        for f in todas("/material-conversion-formulas/current"):
            m = por_codigo.get(f["material_code"])
            valores = list((f.get("parameters") or {}).values())
            param = _numero(valores[0]) if len(valores) == 1 else None
            if m is None or m[6] != f["formula_type"] or m[7] is None or param != _numero(m[7]):
                distintas.append(f"{f['material_code']} ({f['formula_type']} {f.get('parameters')})")
        if distintas:
            avisos.append(f"{len(distintas)} fórmulas vigentes distintas de las del seeder: {_lista(distintas)}")
        perfiles = []
        for p in todas("/material-kg-profiles"):
            m = por_codigo.get(p["material_code"])
            vivo = (p["willard_world"], bool(p["compra_regular"]), p["lead_product"])
            if m is None or vivo != (m[4], m[5], m[8]):
                perfiles.append(f"{p['material_code']} {vivo}")
        if perfiles:
            avisos.append(f"{len(perfiles)} perfiles kg distintos de los del seeder: {_lista(perfiles)}")

        # -- Retenciones: tarifas configuradas y entidades con saldo
        sembradas_ret = {(r["retention_type"], _norm(r.get("municipality")), _norm(r.get("concept")),
                          _numero(r["rate_pct"])) for r in seed.RETENTION_CONFIGS}
        filas_ret = todas("/third-parties/retention-entities")
        vivas = {(r["retention_type"], _norm(r.get("municipality")), _norm(r.get("concept")),
                  _numero(r["rate_pct"])) for r in filas_ret if r.get("config_id") and r.get("is_active", True)}
        if vivas != sembradas_ret:
            def ret(t):
                tipo, municipio, concepto, tasa = t
                return " ".join(x for x in (tipo, municipio, concepto, f"{tasa}%") if x)
            avisos.append(f"Tarifas de retención distintas de las del seeder: de más "
                          f"{_lista(map(ret, vivas - sembradas_ret)) or '—'}; de menos "
                          f"{_lista(map(ret, sembradas_ret - vivas)) or '—'}")
        con_saldo = [r["name"] for r in filas_ret if r.get("entity_id") and _numero(r.get("current_balance") or 0) != 0]
        if con_saldo:
            avisos.append(f"{len(con_saldo)} entidades de retención con saldo: {_lista(con_saldo)}")

        # -- Precios del plomo y saldos del libro de kilos
        precios = [p for p in todas("/lead-market-prices") if not p.get("annulled_at")]
        if precios:
            avisos.append(f"La org tiene {len(precios)} precio(s) del plomo cargados; la nueva nace con el de la carga")
        kg = leer("/kg-ledger/summary") or {}
        con_kg = [a["code"] for a in kg.get("accounts", []) if _numero(a.get("balance_kg") or 0) != 0]
        if con_kg:
            avisos.append(f"{len(con_kg)} cuentas kg con saldo: {_lista(con_kg)}")

        # -- Roles custom: los que no siembra el seeder, y permisos cambiados
        sembrados = {r["name"]: set(r["permission_codes"]) for r in (seed.BASCULA_ROLE, seed.REVISOR_ROLE)}
        for r in todas("/roles"):
            if r.get("is_system_role"):
                continue
            if r["name"] not in sembrados:
                avisos.append(f"Rol custom «{r['name']}» no lo crea el seeder")
                continue
            detalle = leer(f"/roles/{r['id']}") or {}
            vivos = {p["code"] for p in detalle.get("permissions", [])}
            if detalle and vivos != sembrados[r["name"]]:
                avisos.append(f"Rol «{r['name']}»: permisos distintos de los del seeder (de más: "
                              f"{_lista(vivos - sembrados[r['name']]) or '—'}; de menos: "
                              f"{_lista(sembrados[r['name']] - vivos) or '—'})")

        # -- Settings de la org contra los que deja el seeder (sedes por NOMBRE)
        detalle = leer(f"/organizations/{org['id']}") or {}
        vivos = detalle.get("settings") or {}
        bodegas = {w["name"]: w["id"] for w in todas("/warehouses")}
        nombre_de = {v: k for k, v in bodegas.items()}

        def legible(v):
            return f"bodega {nombre_de[v]}" if isinstance(v, str) and v in nombre_de else repr(v)
        try:
            esperados = seed.settings_de_la_org(bodegas)
        except KeyError as e:
            avisos.append(f"No se pudieron comparar los settings: la org no tiene la bodega {e}")
            esperados = None
        if esperados is not None:
            for clave in sorted(set(vivos) | set(esperados)):
                if vivos.get(clave) != esperados.get(clave):
                    avisos.append(f"Setting {clave} = {legible(vivos.get(clave))}; la nueva nace con "
                                  f"{legible(esperados.get(clave))}")
    finally:
        api.org_id = None

    logging.info("")
    if avisos:
        logging.info(f"Lo que la «{seed.ORG_NAME}» nueva NO hereda ({len(avisos)}):")
        for a in avisos:
            logging.info(f"  - {a}")
    else:
        logging.info(f"La «{seed.ORG_NAME}» nueva no pierde nada de la activa.")
    return avisos


def main() -> None:
    parser = argparse.ArgumentParser(description="Archivar / dar de baja la org SAC")
    parser.add_argument("--modo", choices=("revisar", "archivar", "baja", "restaurar"),
                        required=True)
    parser.add_argument("--org-id", help="Con --modo baja o restaurar: la org archivada")
    parser.add_argument("--copiar-miembros", action="store_true",
                        help="Con --modo baja: agrega a la nueva los miembros que le falten")
    parser.add_argument("--apply", action="store_true", help="Escribir (default: solo imprime)")
    parser.add_argument("--api-url", default=seed.BASE_URL)
    parser.add_argument("--superuser-email", default=os.environ.get("SEED_SU_EMAIL"))
    parser.add_argument("--superuser-password", default=os.environ.get("SEED_SU_PASSWORD"))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.modo in ("baja", "restaurar") and not args.org_id:
        raise SystemExit(f"--modo {args.modo} necesita --org-id")
    if not args.superuser_email or not args.superuser_password:
        raise SystemExit("Faltan credenciales: SEED_SU_EMAIL / SEED_SU_PASSWORD en el entorno")
    api = seed.APIClient(dry_run=False, base_url=args.api_url)
    if not api.is_local:
        logging.warning(f"*** DESTINO REMOTO: {args.api_url} ***")
    api.login(args.superuser_email, args.superuser_password)
    if args.modo == "revisar":
        revisar(api)
    elif args.modo == "archivar":
        archivar(api, args.apply, datetime.now(ZoneInfo("America/Bogota")))
    elif args.modo == "restaurar":
        restaurar(api, args.org_id, args.apply)
    else:
        dar_de_baja(api, args.org_id, args.apply, args.copiar_miembros)


if __name__ == "__main__":
    main()
