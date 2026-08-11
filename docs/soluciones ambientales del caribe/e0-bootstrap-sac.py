#!/usr/bin/env python3
"""E0 SAC — bootstrap de la organizacion SAC en un entorno EcoBalance (dev o prod).

Crea: org + usuarios con roles provisionales + 6 bodegas + 4 UN + categorias/materiales
(unidades correctas del Anexo C — critico para E1) + cuentas $0 + categorias de gasto
base + 3 terceros de PRUEBA. Todo dato de negocio es DE JUGUETE: se limpia con
/migrate-client --reset-org antes del corte (S4).

Uso:
  export E0_SU_EMAIL='superuser@...' E0_SU_PASSWORD='...'
  # Ensayo dev:
  E0_API_URL=http://localhost:8000 python3 e0_sac_bootstrap.py            # dry-run
  E0_API_URL=http://localhost:8000 python3 e0_sac_bootstrap.py --apply
  # Prod (solo tras OK del ensayo):
  E0_API_URL=https://api.ecobalance.cc python3 e0_sac_bootstrap.py        # dry-run
  E0_API_URL=https://api.ecobalance.cc python3 e0_sac_bootstrap.py --apply
"""
import os
import sys

import requests

API = os.environ.get("E0_API_URL", "http://localhost:8000").rstrip("/")
SU_EMAIL = os.environ.get("E0_SU_EMAIL")
SU_PASSWORD = os.environ.get("E0_SU_PASSWORD")
APPLY = "--apply" in sys.argv

# ============================ CONFIG (editar antes de correr) ============================

ORG_NAME = "SAC"

# El admin inicial lo crea el endpoint de sistema (password temporal "123456" si es nuevo)
ORG_ADMIN = {"email": "johana@sac.com", "full_name": "Johana"}

# Usuarios adicionales: se registran (password temporal) y se agregan con rol de sistema
TEMP_PASSWORD = "Sac2026*cambiar"  # min 8 chars; cada quien la cambia al primer ingreso
USERS = [
    {"email": "hugo@sac.com", "full_name": "Hugo Armando Bedoya", "role": "admin"},
]

WAREHOUSES = [
    ("Circunvalar", "Sede fisica — Barranquilla"),
    ("Juan Mina", "Sede fisica — Barranquilla (planta: horno y crisol)"),
    ("Bogota", "Sede fisica — acopio y compras"),
    ("Circunvalar - Molino", "Bodega virtual — proceso de molino"),
    ("Juan Mina - Transito", "Bodega virtual — material en camino Circunvalar -> Juan Mina"),
    ("Circunvalar - Transito", "Bodega virtual — material en camino Bogota -> Circunvalar"),
]

BUSINESS_UNITS = [
    ("UN1 Reciclaje Plomo", "Compra y proceso de chatarra propia"),
    ("UN2 Maquila Willard", "Postconsumo y drosses Willard"),
    ("UN3 Reventa DP", "Reventa / pasa mano"),
    ("UN4 Proyectos Especiales", "Eco Alloys y otros"),
]

MATERIAL_CATEGORIES = ["Baterias", "Drosses", "Chatarra", "Producto Terminado"]

# (code, name, categoria, UN, default_unit) — unidades del Anexo C:
# baterias en UNIDAD, drosses/scrap/producto en KG (critico para las formulas de E1)
MATERIALS = [
    ("BAT-07", "Bateria ref 07", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-08", "Bateria ref 08", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-1", "Bateria ref 1", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-2", "Bateria ref 2", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-3", "Bateria ref 3", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-4", "Bateria ref 4", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("BAT-5", "Bateria ref 5", "Baterias", "UN2 Maquila Willard", "unidad"),
    ("JAMICHE", "Jamiche", "Drosses", "UN2 Maquila Willard", "kg"),
    ("SEC", "SEC (escurrido/pinza)", "Drosses", "UN2 Maquila Willard", "kg"),
    ("DROSS-MOTO", "Dross moto", "Drosses", "UN2 Maquila Willard", "kg"),
    ("DROSS-UPS", "Dross UPS", "Drosses", "UN2 Maquila Willard", "kg"),
    ("DROSS-ESTACIONARIA", "Dross estacionaria", "Drosses", "UN2 Maquila Willard", "kg"),
    ("DROSS-VASOS", "Dross vasos", "Drosses", "UN2 Maquila Willard", "kg"),
    ("DROSS-SECA", "Dross seca", "Drosses", "UN2 Maquila Willard", "kg"),
    ("CHATARRA", "Chatarra de plomo", "Chatarra", "UN1 Reciclaje Plomo", "kg"),
    ("RETAL", "Retal (insumo horno)", "Chatarra", "UN1 Reciclaje Plomo", "kg"),
    ("BORNES", "Bornes", "Chatarra", "UN1 Reciclaje Plomo", "kg"),
    ("PLOMO-CRUDO", "Plomo crudo en lingote", "Producto Terminado", "UN1 Reciclaje Plomo", "kg"),
    ("PLOMO-PURO", "Plomo refinado", "Producto Terminado", "UN1 Reciclaje Plomo", "kg"),
]

MONEY_ACCOUNTS = [
    ("Caja Circunvalar", "cash"),
    ("Caja Juan Mina", "cash"),
    ("Caja Bogota", "cash"),
    ("Banco Principal", "bank"),
]

EXPENSE_CATEGORIES = [
    ("Nomina", False), ("Arriendos", False), ("Servicios Publicos", False),
    ("Transporte y Fletes", True), ("Combustibles", True),
    ("Insumos de Planta", True), ("Mantenimiento", False), ("Papeleria y Otros", False),
]

# (nombre, behavior_type de la categoria default a asignar)
THIRD_PARTIES_PRUEBA = [
    ("PRUEBA - Proveedor de Chatarra", "material_supplier"),
    ("PRUEBA - Cliente Nacional", "customer"),
    ("PRUEBA - Transportes del Caribe", "service_provider"),
]

# =========================================================================================

S = requests.Session()
CREATED, SKIPPED = [], []


def die(msg):
    print(f"\n✗ ABORTA: {msg}")
    sys.exit(1)


def step(label, fn):
    """Ejecuta un paso; en dry-run solo lo anuncia."""
    if APPLY:
        result = fn()
        CREATED.append(label)
        print(f"  ✓ {label}")
        return result
    print(f"  [dry-run] {label}")
    return None


def post(path, payload, org_id=None):
    headers = {}
    if org_id:
        headers["X-Organization-ID"] = str(org_id)
    r = S.post(f"{API}/api/v1{path}", json=payload, headers=headers)
    if r.status_code not in (200, 201):
        die(f"POST {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def get(path, org_id=None, params=None):
    headers = {"X-Organization-ID": str(org_id)} if org_id else {}
    r = S.get(f"{API}/api/v1{path}", headers=headers, params=params or {})
    if r.status_code != 200:
        die(f"GET {path} -> {r.status_code}: {r.text[:300]}")
    return r.json()


def existing_values(path, org_id, field):
    """Set de valores ya existentes (maneja respuesta paginada {'items':[...]} o lista plana)."""
    data = get(path, org_id, params={"limit": 500})
    items = data.get("items", data) if isinstance(data, dict) else data
    return {str(i[field]).strip().lower() for i in items if i.get(field)}


def seed(label, key, existing, fn):
    """Crea solo si no existe (resume-safe)."""
    if key.strip().lower() in existing:
        SKIPPED.append(label)
        print(f"  ~ {label} (ya existia)")
        return None
    return step(label, fn)


def main():
    mode = "APPLY" if APPLY else "DRY-RUN"
    print(f"\n=== E0 SAC bootstrap — {mode} contra {API} ===\n")
    if not SU_EMAIL or not SU_PASSWORD:
        die("faltan E0_SU_EMAIL / E0_SU_PASSWORD en el entorno")
    if "PENDIENTE" in ORG_ADMIN["email"]:
        die("edita ORG_ADMIN y USERS en el CONFIG antes de correr")

    # 1. Login superuser
    r = S.post(f"{API}/api/v1/auth/login/json", json={"email": SU_EMAIL, "password": SU_PASSWORD})
    if r.status_code != 200:
        die(f"login superuser fallo: {r.status_code} {r.text[:200]}")
    S.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    print(f"✓ Login superuser OK ({SU_EMAIL})")

    # 2. Org (si ya existe: reanuda con E0_RESUME=1, si no aborta)
    orgs = get("/system/organizations")
    match = [o for o in orgs if o["name"].strip().lower() == ORG_NAME.lower()]
    if match and os.environ.get("E0_RESUME") != "1":
        die(f"la org '{ORG_NAME}' ya existe (id {match[0]['id']}) — para reanudar: E0_RESUME=1")
    if match:
        org = match[0]
        print(f"~ Org '{ORG_NAME}' ya existe ({org['id']}) — modo RESUME: solo se crea lo que falte")
    else:
        print(f"✓ No existe org '{ORG_NAME}' — se creara con admin {ORG_ADMIN['email']}")
        org = step(f"Crear org '{ORG_NAME}' + admin {ORG_ADMIN['email']}",
                   lambda: post("/system/organizations", {
                       "name": ORG_NAME,
                       "admin_email": ORG_ADMIN["email"],
                       "admin_full_name": ORG_ADMIN["full_name"],
                   }))
    if not APPLY:
        print(f"\n[dry-run] validacion de config OK: {len(USERS)+1} usuarios, "
              f"{len(WAREHOUSES)} bodegas, {len(BUSINESS_UNITS)} UN, {len(MATERIALS)} materiales, "
              f"{len(MONEY_ACCOUNTS)} cuentas, {len(EXPENSE_CATEGORIES)} cat. gasto, "
              f"{len(THIRD_PARTIES_PRUEBA)} terceros PRUEBA.\nCorre con --apply para ejecutar.")
        return
    org_id = org["id"]

    # 3. Roles de sistema de la org
    roles = get(f"/system/organizations/{org_id}/roles")
    role_by_name = {r["name"]: r["id"] for r in roles}

    # 4. Usuarios adicionales: registrar + agregar a la org
    all_users = get("/system/users")
    by_email = {u["email"].lower(): u for u in all_users}
    for u in USERS:
        existing_user = by_email.get(u["email"].lower())
        if existing_user:
            user_id = existing_user["id"]
            already = any(str(m["organization_id"]) == str(org_id)
                          for m in existing_user.get("memberships", []))
            if already:
                SKIPPED.append(f"{u['email']} ya era miembro")
                print(f"  ~ {u['email']} ya era miembro")
                continue
        else:
            reg = post("/auth/register", {
                "email": u["email"], "password": TEMP_PASSWORD, "full_name": u["full_name"],
            })
            user_id = reg["user"]["id"]
        role_id = role_by_name.get(u["role"]) or die(f"rol '{u['role']}' no existe en la org")
        step(f"Agregar {u['email']} como {u['role']}",
             lambda uid=user_id, rid=role_id: post(f"/system/users/{uid}/add-to-org",
                                                   {"organization_id": org_id, "role_id": rid}))

    # 5. Maestros (superuser bypasa membership con X-Organization-ID; todo resume-safe)
    have = existing_values("/warehouses", org_id, "name")
    for name, desc in WAREHOUSES:
        seed(f"Bodega {name}", name, have,
             lambda n=name, d=desc: post("/warehouses", {"name": n, "description": d}, org_id))

    bus = get("/business-units", org_id, params={"limit": 500})
    bus = bus.get("items", bus) if isinstance(bus, dict) else bus
    bu_ids = {b["name"]: b["id"] for b in bus}
    for name, desc in BUSINESS_UNITS:
        r = seed(f"UN {name}", name, {k.lower() for k in bu_ids},
                 lambda n=name, d=desc: post("/business-units", {"name": n, "description": d}, org_id))
        if r:
            bu_ids[name] = r["id"]

    cats = get("/material-categories", org_id, params={"limit": 500})
    cats = cats.get("items", cats) if isinstance(cats, dict) else cats
    cat_ids = {c["name"]: c["id"] for c in cats}
    for name in MATERIAL_CATEGORIES:
        r = seed(f"Cat. material {name}", name, {k.lower() for k in cat_ids},
                 lambda n=name: post("/material-categories", {"name": n}, org_id))
        if r:
            cat_ids[name] = r["id"]

    have = existing_values("/materials", org_id, "code")
    for code, name, cat, un, unit in MATERIALS:
        seed(f"Material {code} ({unit})", code, have,
             lambda c=code, n=name, ct=cat, u=un, dt=unit: post("/materials", {
                 "code": c, "name": n, "category_id": cat_ids[ct],
                 "business_unit_id": bu_ids[u], "default_unit": dt,
             }, org_id))

    have = existing_values("/money-accounts", org_id, "name")
    for name, acc_type in MONEY_ACCOUNTS:
        seed(f"Cuenta {name}", name, have, lambda n=name, t=acc_type: post("/money-accounts", {
            "name": n, "account_type": t, "initial_balance": 0,
        }, org_id))

    have = existing_values("/expense-categories", org_id, "name")
    for name, is_direct in EXPENSE_CATEGORIES:
        seed(f"Cat. gasto {name}", name, have, lambda n=name, d=is_direct: post("/expense-categories", {
            "name": n, "is_direct_expense": d,
        }, org_id))

    tp_cats = get("/third-party-categories/flat", org_id)["items"]
    cat_by_behavior = {}
    for c in tp_cats:
        cat_by_behavior.setdefault(c["behavior_type"], c["id"])
    have = existing_values("/third-parties", org_id, "name")
    for name, behavior in THIRD_PARTIES_PRUEBA:
        cid = cat_by_behavior.get(behavior) or die(f"no hay categoria de tercero con behavior {behavior}")
        seed(f"Tercero {name}", name, have, lambda n=name, ci=cid: post("/third-parties", {
            "name": n, "initial_balance": 0, "category_ids": [ci],
        }, org_id))

    # 6. Resumen
    print(f"\n=== E0 COMPLETADO — org {org_id} ===")
    print(f"  Creados: {len(CREATED)} | Saltados: {len(SKIPPED)}")
    for s in SKIPPED:
        print(f"  ~ {s}")
    print(f"""
CHECKLIST DE ACCESOS (entregar a SAC):
  URL: https://app.ecobalance.cc
  {ORG_ADMIN['email']} — admin — password temporal: 123456
  {chr(10).join(f"  {u['email']} — {u['role']} — password temporal: {TEMP_PASSWORD}" for u in USERS)}
  ⚠ Cada usuario DEBE cambiar su password al primer ingreso (menu usuario > Cambiar contrasena).
""")


if __name__ == "__main__":
    main()
