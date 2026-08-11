#!/usr/bin/env python
"""
seed_sac_org.py — Recrea la organizacion SAC en dev con SOLO maestros
(sin compras/ventas/transacciones), para renacer despues de replicate_prod.sh.

Que crea:
  - Org "SAC" + settings completos (kg_ledger + two_step_transfers + maquila ON,
    sedes deterministas Willard apuntando a las bodegas NUEVAS).
  - Usuarios: hugo@sac.com (admin, dueno de la org), johana@sac.com (admin),
    yurani@sac.com (admin) y erwin@sac.com (rol custom bascula_sac).
  - 6 bodegas (3 receptoras + Molino en la sede Circunvalar + 2 transito).
  - 4 UNs, 4 cuentas de dinero ($0), 8 categorias de gasto, 6 categorias de material.
  - Los 37 materiales del listado de Daniel (2026-07-23) + perfil kg + formula
    de conversion (battery_to_lead / drosses_to_lead) donde aplica.
  - 5 terceros (Willard S.A, Green Loop, 3 PRUEBA-*).
  - 4 cuentas kg (WILLARD-BAT-CV, WILL-BAT-JM, WILL-DROSS, INTERSEDE).
  - 2 tarifas (comision_green_loop $100 per_kg_material,
    maquila_intersede_cv_jm $1.500 per_kg_lead).
  - 3 configs de retencion (retefuente 2.5%, reteiva 2.0%, ICA Barranquilla 0.7%).

Uso (default dry-run):
    ./venv/bin/python scripts/seed_sac_org.py --superuser-email <su> --superuser-password <pwd>
    ./venv/bin/python scripts/seed_sac_org.py --apply --superuser-email <su> --superuser-password <pwd>
    ./venv/bin/python scripts/seed_sac_org.py --apply --reset ...   # borra la org SAC previa

Reglas:
  - Todo via API REST (jamas SQL directo). SOLO contra dev (localhost:8000).
  - Credenciales por CLI o env (SEED_SU_EMAIL / SEED_SU_PASSWORD); nunca hardcoded.
  - Los 4 usuarios quedan con --users-password (default 12345678), incluso los
    que ya existian: _force_known_passwords los unifica por ORM. Eso es DEV-ONLY
    — en produccion se usa el endpoint de reseteo del superusuario.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests

_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

ORG_NAME = "SAC"

# El PRIMERO es el dueno de la org (admin_email de /system/organizations).
# OJO: los usuarios son GLOBALES (no por org) — /auth/register falla si el
# email existe y el endpoint de org reutiliza al usuario sin tocar su clave.
# Por eso en dev forzamos las claves por ORM (_force_known_passwords); en
# prod se hace con el endpoint de reseteo del superusuario, NUNCA por BD.
USERS = [
    {"key": "hugo", "email": "hugo@sac.com",
     "full_name": "Hugo Armando Bedoya", "role": "admin"},
    {"key": "johana", "email": "johana@sac.com",
     "full_name": "Johana", "role": "admin"},
    {"key": "yurani", "email": "yurani@sac.com",
     "full_name": "Yurani", "role": "admin"},
    {"key": "erwin", "email": "erwin@sac.com",
     "full_name": "Erwin", "role": "bascula_sac"},
]

# Rol custom de bascula: captura y edita entradas, NO liquida ni anula
BASCULA_ROLE = {
    "name": "bascula_sac",
    "display_name": "Bascula SAC",
    "description": "Captura y edicion de entradas en patio, sin liquidar ni anular",
    "permission_codes": [
        "config.manage_fleet", "config.view_fleet", "formulas.view",
        "kg_ledger.view", "materials.view", "purchases.create",
        "purchases.edit", "purchases.view", "third_parties.view",
        "warehouses.view",
    ],
}

# #93 D10: rol de revision de entradas (confirma cantidades, habilita liquidar).
# Custom y NO de sistema: un sexto rol de sistema apareceria en Costa/Biogreen.
# R5: el sembrado lo crea ANTES del deploy — sin nadie con purchases.review,
# 'revisada' frenaria la operacion.
REVISOR_ROLE = {
    "name": "revisor_inventario",
    "display_name": "Revisor de Inventario",
    "description": "Revisa entradas (confirma cantidades pesadas) y consulta compras e inventario",
    "permission_codes": [
        "purchases.view", "purchases.review", "materials.view",
        "third_parties.view", "warehouses.view", "kg_ledger.view",
    ],
}

BUSINESS_UNITS = [
    "UN1 Reciclaje Plomo",
    "UN2 Maquila Willard",
    "UN3 Reventa DP",
    "UN4 Proyectos Especiales",
]

# (name, is_receiving, is_transit, transit_target_name, sede_name)
#
# `sede_name` agrupa bodegas que son "un solo inventario" (Johana, 2026-08-11:
# Circunvalar y su molino lo son). Un traslado DENTRO de una sede se completa al
# registrarlo —no se pesa al salir ni al llegar— y no genera deuda de plomo ni
# maquila. Cruzar de sede si: dos pasos, transito y efectos.
#
# Por eso el molino NO necesita bodega de transito: nada llega a el cruzando de
# sede. Solo las sedes reales (JM, CV) tienen la suya.
WAREHOUSES: list[tuple[str, bool, bool, Optional[str], Optional[str]]] = [
    ("Circunvalar", True, False, None, None),
    ("Juan Mina", True, False, None, None),
    ("Bogota", True, False, None, None),
    ("Circunvalar - Molino", False, False, None, "Circunvalar"),
    ("Juan Mina - Transito", False, True, "Juan Mina", None),
    ("Circunvalar - Transito", False, True, "Circunvalar", None),
]

ACCOUNTS = [
    {"name": "Caja Circunvalar", "account_type": "cash", "initial_balance": "0"},
    {"name": "Caja Juan Mina", "account_type": "cash", "initial_balance": "0"},
    {"name": "Caja Bogota", "account_type": "cash", "initial_balance": "0"},
    {"name": "Banco Principal", "account_type": "bank", "initial_balance": "0"},
]

# (name, is_direct_expense) — "Comisiones de recoleccion" NO va: es entidad de
# sistema get-or-create al liquidar con recolector (#83)
# (nombre, is_direct_expense, pnl_section) — pnl_section solo vive en raices (#71)
EXPENSE_CATEGORIES = [
    ("Arriendos", False, "operativo"),
    ("Combustibles", True, "operativo"),
    ("Insumos de Planta", True, "operativo"),
    ("Mantenimiento", False, "operativo"),
    ("Nomina", False, "operativo"),
    ("Papeleria y Otros", False, "operativo"),
    ("Servicios Publicos", False, "operativo"),
    ("Transporte y Fletes", True, "operativo"),
    # Ajustes reunion 2026-08-03 (D). Ojo: el P&L ya manda los intereses de
    # obligaciones a la seccion financiera por FUENTE (#71, reports.py:909) —
    # esta categoria es para el Reporte de Gastos (#44), que agrupa por
    # categoria, y para gastos financieros manuales (comision bancaria, 4x1000)
    # registrados como `expense` suelto, donde no hay fuente que los salve.
    ("Gastos Financieros", False, "financiero"),
]

MATERIAL_CATEGORIES = ["Baterías", "Scrap", "Plomo", "Chatarra", "Aluminio", "Drosses"]

# Listado de Daniel 2026-07-23.
# (code, name, category, unit, willard_world, compra_regular, formula_type, param)
#   formula battery_to_lead -> param = kg_lead_per_unit
#   formula drosses_to_lead -> param = lead_percentage (fraccion 0-1)
# UN: MR* (drosses de maquila) -> UN2 Maquila Willard; resto -> UN1 Reciclaje
# Plomo (asignacion declarada, reclasificable en Config sin migracion).
MATERIALS: list[tuple[str, str, str, str, str, bool, Optional[str], Optional[float]]] = [
    # --- Baterias (unidad, postconsumo, compra regular tambien) ---
    ("BAT-G07", "BATERIAS GRUPO 0,7", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 5.1),
    ("BAT-G08", "BATERIAS GRUPO 0,8", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 6.5),
    ("BAT-G1", "BATERIAS GRUPO 1", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 7.3),
    ("BAT-G2", "BATERIAS GRUPO 2", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 9.3),
    ("BAT-G3", "BATERIAS GRUPO 3", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 11.3),
    ("BAT-G4", "BATERIAS GRUPO 4", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 16.9),
    ("BAT-G5", "BATERIAS GRUPO 5", "Baterías", "unidad", "postconsumo", True, "battery_to_lead", 22.9),
    # --- Scrap ---
    ("SCR-MOTO", "SCRAP MOTO", "Scrap", "kg", "postconsumo", True, "drosses_to_lead", 0.49),
    ("SCR-SG", "SCRAP SECO GRANDE", "Scrap", "kg", "postconsumo", True, "drosses_to_lead", 0.59),
    ("SCR-SP", "SCRAP SECO PEQUEÑO", "Scrap", "kg", "none", True, None, None),
    ("SCR-LSB", "SCRAP LIMPIO SIN BORNE", "Scrap", "kg", "none", True, None, None),
    ("SCR-LCB", "SCRAP LIMPIO CON BORNE", "Scrap", "kg", "none", True, None, None),
    # --- Plomo / producto ---
    ("PLO-LIN", "PLOMO LINGOTES", "Plomo", "kg", "none", True, None, None),
    ("PLO-RET", "PLOMO RETAL", "Plomo", "kg", "none", True, None, None),
    ("PLO-CAS", "PLOMO CASCARA", "Plomo", "kg", "none", True, None, None),
    ("CAJ-PLA", "CAJAS PLÁSTICAS", "Plomo", "kg", "none", True, None, None),
    ("CAJ-ACR", "CAJAS ACRILICAS", "Plomo", "kg", "none", True, None, None),
    ("POL-DUC", "POLVODUCTO", "Plomo", "kg", "none", True, None, None),
    ("PP-MOL", "PP MOLIDO", "Plomo", "kg", "none", True, None, None),
    ("TAP-BOR", "TAPAS CON BORNE", "Plomo", "kg", "none", True, None, None),
    ("GUA-RRU", "GUARRÚ", "Plomo", "kg", "none", True, None, None),
    ("LOD-01", "LODO", "Plomo", "kg", "none", True, None, None),
    # --- Chatarra / Aluminio ---
    ("HIE-CHA", "HIERRO CHATARRA", "Chatarra", "kg", "none", True, None, None),
    ("ALU-01", "ALUMINIO", "Aluminio", "kg", "none", True, None, None),
    # --- Drosses Willard (maquila, NO compra regular) — % plomo como fraccion ---
    ("MR01", "GUARRU HUMEDO", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.41),
    ("MR02", "GUARRU SECO", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.72),
    ("MR04", "JAMICHE", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.53),
    ("MR07", "CENIZAS DE COBRE", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.35),
    ("MR08", "CENIZAS DURAS", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.43),
    ("MR09", "OXIDO DE PLOMO RECHAZADO", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.83),
    ("MR10", "MEZCLA DAÑADA", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.71),
    ("MR13", "MALLA EMPASTADA", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.60),
    ("MR18", "CENIZAS DE SODA SOLA", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.26),
    ("MR19", "CENIZAS DE SODA ROJA", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.26),
    ("MR20", "CENIZAS DE 1ERA LAVADA DE MP", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.26),
    ("MR21", "CENIZAS DE METALES PESADOS", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.26),
    ("MR23", "CENIZAS DE OXIDACIÓN", "Drosses", "kg", "drosses", False, "drosses_to_lead", 0.65),
]

# (name, default_tp_category_name)
THIRD_PARTIES = [
    ("Willard S.A", "Proveedor Material"),
    ("PRUEBA - Proveedor de Chatarra", "Proveedor Material"),
    ("Green Loop", "Proveedor Servicios"),
    ("PRUEBA - Transportes del Caribe", "Proveedor Servicios"),
    ("PRUEBA - Cliente Nacional", "Cliente"),
]

# SOLO en modo local con --reset (nunca contra produccion). El reparto de una
# Entrada es multi-proveedor por naturaleza — con un unico proveedor de material
# no se puede probar. Ojo: Willard S.A NO sirve para esto, es titular de las
# cuentas kg y el guard de #80 lo rechaza como proveedor de compra.
THIRD_PARTIES_LOCAL = [
    ("PRUEBA - Chatarreria Bogota", "Proveedor Material"),
    ("PRUEBA - Reciclados del Norte", "Proveedor Material"),
    ("PRUEBA - Metales del Atlantico", "Proveedor Material"),
]

# (code, display_name, account_type, warehouse_name|None, titular_name|None)
KG_ACCOUNTS = [
    ("WILLARD-BAT-CV", "Willard Baterias CV", "willard_baterias", "Circunvalar", "Willard S.A"),
    ("WILL-BAT-JM", "Willard Baterías Juan Mina", "willard_baterias", "Juan Mina", "Willard S.A"),
    ("WILL-DROSS", "Willard Drosses", "willard_drosses", None, "Willard S.A"),
    ("INTERSEDE", "Transito Intersede (kg)", "intersede", None, None),
]

TARIFFS = [
    # #93 D11: kg_per_unit=14 — "14 kg por unidad, sea cual sea la unidad"
    # (Hugo); base de la comision con unidades mezcladas, versionado con el precio
    {"tariff_code": "comision_green_loop", "unit_price_cop": "100",
     "unit": "per_kg_material", "kg_per_unit": "14"},
    {"tariff_code": "maquila_intersede_cv_jm", "unit_price_cop": "1500", "unit": "per_kg_lead"},
]

RETENTION_CONFIGS = [
    {"retention_type": "retefuente", "rate_pct": "2.5"},
    {"retention_type": "reteiva", "rate_pct": "2.0"},
    {"retention_type": "ica", "municipality": "Barranquilla", "rate_pct": "0.7"},
]

WILLARD_DISTRIBUTION_CENTERS = ["baq", "bog", "monteria", "santa_marta", "motocosta"]


# ============================================================================
# API CLIENT (patron de seed_demo_org.py)
# ============================================================================

class APIClient:
    def __init__(self, dry_run: bool = True, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        # Local = el ORM del .env apunta a la MISMA BD que este backend. Solo
        # ahi son validos --reset y el forzado de claves por ORM.
        self.is_local = "localhost" in self.base_url or "127.0.0.1" in self.base_url
        self.token: Optional[str] = None
        self.org_id: Optional[str] = None
        self.session = requests.Session()
        self._dry_id_counter = 0

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        if self.org_id:
            h["X-Organization-ID"] = str(self.org_id)
        return h

    def login(self, email: str, password: str) -> None:
        r = self.session.post(
            f"{self.base_url}{API_PREFIX}/auth/login/json",
            json={"email": email, "password": password},
        )
        if r.status_code != 200:
            raise SystemExit(f"Login failed [{r.status_code}]: {r.text[:300]}")
        self.token = r.json()["access_token"]

    def _fake_id(self) -> str:
        self._dry_id_counter += 1
        return f"00000000-0000-0000-0000-{self._dry_id_counter:012d}"

    def _request(self, method: str, path: str, body: Optional[dict], label: str) -> dict:
        if self.dry_run:
            logging.debug(f"[DRY] {method} {path}  ({label})")
            fake = {"id": self._fake_id()}
            if body:
                fake.update({k: v for k, v in body.items() if k != "lines"})
            return fake
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.request(method, url, json=body, headers=self._headers())
        if r.status_code >= 400:
            raise SystemExit(
                f"{method} {path} failed [{r.status_code}]: {r.text[:500]}\nbody={body}"
            )
        return r.json() if r.text else {}

    def post(self, path: str, body: dict, label: str = "") -> dict:
        return self._request("POST", path, body, label)

    def put(self, path: str, body: dict, label: str = "") -> dict:
        return self._request("PUT", path, body, label)

    def patch(self, path: str, body: dict, label: str = "") -> dict:
        return self._request("PATCH", path, body, label)

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.get(url, headers=self._headers(), params=params)
        if r.status_code >= 400:
            raise SystemExit(f"GET {path} failed [{r.status_code}]: {r.text[:300]}")
        return r.json()

    def post_tolerating(self, path: str, body: dict, ok_codes: tuple[int, ...],
                        label: str = "") -> Optional[dict]:
        """POST que acepta ciertos errores como 'ya existe' (idempotencia)."""
        if self.dry_run:
            logging.debug(f"[DRY] POST {path}  ({label})")
            return {"id": self._fake_id()}
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.post(url, json=body, headers=self._headers())
        if r.status_code in ok_codes:
            return None
        if r.status_code >= 400:
            raise SystemExit(
                f"POST {path} failed [{r.status_code}]: {r.text[:500]}\nbody={body}"
            )
        return r.json() if r.text else {}

    def existing_by(self, path: str, key: str) -> dict[str, dict]:
        """Mapa {valor_de_key: item} de lo que YA existe (idempotencia).

        En dry-run devuelve vacio: no hay org real contra la cual consultar.
        Tolera respuestas paginadas ({items: [...]}) y listas planas.
        """
        if self.dry_run:
            return {}
        data = self.get(path, {"limit": 500})
        items = data["items"] if isinstance(data, dict) and "items" in data else data
        return {it[key]: it for it in items if it.get(key) is not None}

    def delete(self, path: str) -> None:
        if self.dry_run:
            return
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.delete(url, headers=self._headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise SystemExit(f"DELETE {path} failed [{r.status_code}]: {r.text[:300]}")


# ============================================================================
# SEEDER
# ============================================================================

class SacSeeder:
    def __init__(self, api: APIClient, users_password: str):
        self.api = api
        self.users_password = users_password
        self.warehouses: dict[str, str] = {}
        self.business_units: dict[str, str] = {}
        self.material_categories: dict[str, str] = {}
        self.materials: dict[str, str] = {}
        self.third_parties: dict[str, str] = {}
        self.tp_categories: dict[str, str] = {}
        # True = la org ya existia y se esta COMPLETANDO (unico modo valido
        # contra produccion). False = org creada desde cero.
        self.provisioning = False

    # ---------------- ORG + USUARIOS ----------------

    def create_or_reset_org(self, reset: bool) -> None:
        logging.info("[1] Org SAC")
        existing = self._find_existing_org()
        if existing and reset:
            logging.info(f"  Soft-delete de org previa {existing['id']}")
            self.api.delete(f"/system/organizations/{existing['id']}")
            self._reactivate_sac_users()
            existing = None

        if existing:
            # MODO PROVISION (el unico valido contra produccion): se completa
            # la org que ya existe. Nada se borra: --reset contra prod dejaria
            # a los usuarios existentes desactivados como huerfanos y el
            # endpoint que recrea la org NO los reactiva.
            self.api.org_id = existing["id"]
            self.provisioning = True
            logging.info(
                f"  Org existente {existing['id']} — modo PROVISION idempotente"
            )
            return

        owner = USERS[0]
        self._pre_register_user(owner)
        r = self.api.post(
            "/system/organizations",
            {"name": ORG_NAME, "admin_email": owner["email"],
             "admin_full_name": owner["full_name"]},
            label="org",
        )
        self.api.org_id = r["id"]
        logging.info(f"  Org creada id={r['id']} admin={owner['email']}")

    def _find_existing_org(self) -> Optional[dict]:
        if self.api.dry_run:
            return None
        orgs = self.api.get("/system/organizations")
        return next(
            (o for o in orgs if o["name"] == ORG_NAME and o.get("is_active", True)), None
        )

    def _reactivate_sac_users(self) -> None:
        """La soft-delete desactiva usuarios huerfanos; re-activarlos via ORM
        local (solo dev — DATABASE_URL del .env)."""
        if self.api.dry_run:
            return
        try:
            from app.core.database import SessionLocal
            from app.models.user import User
        except ImportError:
            logging.warning("  No se pudo importar app.* para reactivar usuarios")
            return
        with SessionLocal() as db:
            for u in USERS:
                user = db.query(User).filter(User.email == u["email"]).first()
                if user and not user.is_active:
                    user.is_active = True
                    logging.info(f"  Re-activado usuario huerfano: {u['email']}")
            db.commit()

    def _force_known_passwords(self) -> None:
        """DEV-ONLY (ver guard `is_local`): unifica la clave de los 4 usuarios.

        Los que ya existian (replica de prod) conservan un hash cuya clave
        nadie conoce — sin esto, 'usuarios con clave conocida' no se cumple.
        Escribe por ORM contra la BD del .env (desarrollo). El equivalente en
        PRODUCCION es el endpoint de reseteo del superusuario; jamas se toca
        la BD de prod.
        """
        if self.api.dry_run:
            return
        if not self.api.is_local:
            # El ORM apunta a la BD del .env LOCAL: contra un backend remoto
            # escribiria en la BD equivocada. En prod se usa el endpoint
            # POST /system/users/{id}/reset-password (decision #85).
            logging.info(
                "  [REMOTO] Claves NO unificadas — usar el reseteo del panel "
                "Sistema (superusuario) para los usuarios que lo necesiten"
            )
            return
        try:
            from app.core.database import SessionLocal
            from app.core.security import get_password_hash
            from app.models.user import User
        except ImportError:
            logging.warning("  No se pudo importar app.* para unificar claves")
            return
        with SessionLocal() as db:
            n = 0
            for u in USERS:
                user = db.query(User).filter(User.email == u["email"]).first()
                if user:
                    user.hashed_password = get_password_hash(self.users_password)
                    n += 1
            db.commit()
        logging.info(f"  Clave unificada para {n} usuarios (dev)")

    def _pre_register_user(self, u: dict) -> None:
        if self.api.dry_run:
            logging.info(f"  [DRY] pre-register {u['email']}")
            return
        r = self.api.session.post(
            f"{self.api.base_url}{API_PREFIX}/auth/register",
            json={"email": u["email"], "password": self.users_password,
                  "full_name": u["full_name"]},
        )
        if r.status_code == 201:
            logging.info(f"  Usuario creado: {u['email']}")
        elif r.status_code == 400 and "already" in r.text.lower():
            logging.info(f"  Usuario {u['email']} ya existia (conserva su password)")
        else:
            raise SystemExit(f"Pre-register {u['email']} [{r.status_code}]: {r.text[:300]}")

    def create_users_and_roles(self) -> None:
        logging.info(f"[2] Usuarios ({len(USERS)}) + rol custom de bascula")
        if self.api.dry_run:
            for u in USERS:
                logging.info(f"  [DRY] {u['email']} -> {u['role']}")
            return

        roles = self.api.get(f"/system/organizations/{self.api.org_id}/roles")
        by_role_name = {r["name"]: r["id"] for r in roles}
        for custom_role in (BASCULA_ROLE, REVISOR_ROLE):
            if custom_role["name"] not in by_role_name:
                created = self.api.post("/roles", custom_role, label=f"rol-{custom_role['name']}")
                by_role_name[custom_role["name"]] = created["id"]
        role_ids = {
            "admin": by_role_name["admin"],
            BASCULA_ROLE["name"]: by_role_name[BASCULA_ROLE["name"]],
            REVISOR_ROLE["name"]: by_role_name[REVISOR_ROLE["name"]],
        }

        sys_users = self.api.get("/system/users")
        by_email = {u["email"]: u for u in sys_users}
        org_id = str(self.api.org_id)

        for u in USERS:
            self._pre_register_user(u)
            if u["email"] not in by_email:
                by_email = {x["email"]: x for x in self.api.get("/system/users")}
            target = by_email[u["email"]]
            ya_miembro = any(
                str(m.get("organization_id")) == org_id
                for m in target.get("memberships", [])
            )
            if ya_miembro:
                logging.info(f"  {u['email']} ya es miembro — sin cambios")
                continue
            self.api.post(
                f"/system/users/{target['id']}/add-to-org",
                {"organization_id": self.api.org_id, "role_id": role_ids[u["role"]]},
                label=f"add-{u['key']}",
            )
            logging.info(f"  {u['email']} -> rol {u['role']}")

    # ---------------- MAESTROS ----------------

    def create_business_units(self) -> None:
        logging.info("[3] Unidades de negocio")
        existing = self.api.existing_by("/business-units", "name")
        for name in BUSINESS_UNITS:
            if name in existing:
                self.business_units[name] = existing[name]["id"]
                continue
            r = self.api.post("/business-units/", {"name": name}, label=name)
            self.business_units[name] = r["id"]

    def create_warehouses(self) -> None:
        """Las bodegas se crean O se actualizan: en prod las 6 ya existen con
        los mismos nombres y solo les faltan los flags de transito/receptora."""
        logging.info("[4] Bodegas (receptoras + molino + transito)")
        existing = self.api.existing_by("/warehouses", "name")
        # 1a pasada: crear/registrar las que no son de transito (los targets
        # tienen que existir antes de apuntarles)
        for name, is_receiving, is_transit, _target, _sede in WAREHOUSES:
            if name in existing:
                self.warehouses[name] = existing[name]["id"]
                continue
            body: dict[str, Any] = {"name": name, "is_receiving": is_receiving}
            r = self.api.post("/warehouses/", body, label=name)
            self.warehouses[name] = r["id"]
        # 2a pasada: alinear flags (PATCH solo si algo difiere)
        for name, is_receiving, is_transit, target, sede in WAREHOUSES:
            current = existing.get(name)
            desired: dict[str, Any] = {
                "is_receiving": is_receiving,
                "is_transit": is_transit,
                "transit_target_warehouse_id": (
                    self.warehouses[target] if is_transit else None
                ),
                "sede_warehouse_id": self.warehouses[sede] if sede else None,
            }
            if current is None:
                # recien creada: le faltan los flags de transito y/o la sede
                if is_transit or sede:
                    self.api.patch(
                        f"/warehouses/{self.warehouses[name]}", desired, label=name
                    )
                continue
            if any(str(current.get(k)) != str(v) for k, v in desired.items()):
                self.api.patch(
                    f"/warehouses/{self.warehouses[name]}", desired, label=name
                )
                logging.info(f"  Bodega '{name}' actualizada (flags transito/receptora)")

    def patch_settings(self) -> None:
        """REPLACE completo del JSONB (D3) — SIEMPRE todas las claves."""
        logging.info("[5] Settings de la org (flags SAC ON + sedes Willard)")
        settings = {
            "kg_ledger_enabled": True,
            "two_step_transfers_enabled": True,
            "internal_maquila_enabled": True,
            "transfer_tolerance_pct": 0.05,
            "intersede_stale_days": 30,
            "aging_buckets": [30, 60, 90],
            "willard_distribution_centers": WILLARD_DISTRIBUTION_CENTERS,
            "willard_sede_drosses": self.warehouses["Juan Mina"],
            "willard_sede_postconsumo_default": self.warehouses["Circunvalar"],
        }
        self.api.patch(
            f"/system/organizations/{self.api.org_id}", {"settings": settings},
            label="settings",
        )

    def create_accounts(self) -> None:
        logging.info("[6] Cuentas de dinero ($0)")
        existing = self.api.existing_by("/money-accounts", "name")
        for acc in ACCOUNTS:
            if acc["name"] in existing:
                continue
            self.api.post("/money-accounts/", acc, label=acc["name"])

    def create_expense_categories(self) -> None:
        logging.info("[7] Categorias de gasto")
        existing = self.api.existing_by("/expense-categories", "name")
        for name, is_direct, pnl_section in EXPENSE_CATEGORIES:
            if name in existing:
                continue
            self.api.post(
                "/expense-categories/",
                {
                    "name": name,
                    "is_direct_expense": is_direct,
                    "pnl_section": pnl_section,
                },
                label=name,
            )

    def create_material_categories(self) -> None:
        logging.info("[8] Categorias de material")
        existing = self.api.existing_by("/material-categories", "name")
        for name in MATERIAL_CATEGORIES:
            if name in existing:
                self.material_categories[name] = existing[name]["id"]
                continue
            r = self.api.post("/material-categories/", {"name": name}, label=name)
            self.material_categories[name] = r["id"]

    def create_materials(self) -> None:
        logging.info(f"[9] Materiales ({len(MATERIALS)}) + perfiles kg + formulas")
        un1 = self.business_units["UN1 Reciclaje Plomo"]
        un2 = self.business_units["UN2 Maquila Willard"]
        existing = self.api.existing_by("/materials", "code")
        # Las formulas son APPEND-ONLY (#35): re-crear una identica generaria
        # una version nueva sin sentido. Se compara contra la vigente.
        current_formulas = {}
        if not self.api.dry_run:
            data = self.api.get("/material-conversion-formulas", {"limit": 500})
            items = data["items"] if isinstance(data, dict) else data
            current_formulas = {str(f["material_id"]): f for f in items}

        n_new = n_profiles = n_formulas = 0
        for code, name, cat, unit, world, compra, ftype, fparam in MATERIALS:
            bu = un2 if code.startswith("MR") else un1
            if code in existing:
                mat_id = existing[code]["id"]
            else:
                r = self.api.post(
                    "/materials/",
                    {"code": code, "name": name, "default_unit": unit,
                     "category_id": self.material_categories[cat],
                     "business_unit_id": bu},
                    label=code,
                )
                mat_id = r["id"]
                n_new += 1
            self.materials[code] = mat_id

            # PUT idempotente por contrato (upsert 1:1)
            self.api.put(
                f"/material-kg-profiles/{mat_id}",
                {"compra_regular": compra, "willard_world": world},
                label=f"perfil-{code}",
            )
            n_profiles += 1

            if ftype == "battery_to_lead":
                params = {"kg_lead_per_unit": fparam}
            elif ftype == "drosses_to_lead":
                params = {"lead_percentage": fparam}
            else:
                continue
            vigente = current_formulas.get(str(mat_id))
            if vigente and vigente.get("formula_type") == ftype and all(
                float(vigente.get("parameters", {}).get(k, -1)) == float(v)
                for k, v in params.items()
            ):
                continue  # ya vigente e identica: no versionar de nuevo
            self.api.post(
                "/material-conversion-formulas",
                {"material_id": mat_id, "formula_type": ftype, "parameters": params},
                label=f"formula-{code}",
            )
            n_formulas += 1

        # Desactivar los materiales que NO estan en el listado vigente (en prod
        # son los 19 codigos viejos: BAT-07, DROSS-MOTO, JAMICHE, SEC...). Es
        # soft delete; si alguno tuviera movimientos el backend lo rechaza y se
        # reporta sin abortar la siembra.
        wanted = {m[0] for m in MATERIALS}
        obsoletos = [
            it for code, it in existing.items()
            if code not in wanted and it.get("is_active", True)
        ]
        n_off = 0
        for it in obsoletos:
            try:
                self.api.delete(f"/materials/{it['id']}")
                n_off += 1
            except SystemExit as e:
                logging.warning(f"  No se pudo desactivar '{it['code']}': {e}")
        if obsoletos:
            logging.info(
                f"  {n_off}/{len(obsoletos)} materiales obsoletos desactivados: "
                + ", ".join(sorted(i["code"] for i in obsoletos))
            )
        logging.info(
            f"  {len(MATERIALS)} materiales ({n_new} nuevos), {n_profiles} perfiles, "
            f"{n_formulas} formulas nuevas"
        )

    def create_third_parties(self) -> None:
        logging.info("[10] Terceros")
        existing = self.api.existing_by("/third-parties", "name")
        if not self.api.dry_run:
            cats = self.api.get("/third-party-categories/flat")
            self.tp_categories = {c["name"]: c["id"] for c in cats["items"]}
        # Los de prueba multi-proveedor SOLO en local (mismo criterio del guard
        # de --reset): produccion no acumula terceros ficticios
        catalog = THIRD_PARTIES + (THIRD_PARTIES_LOCAL if self.api.is_local else [])
        for name, cat_name in catalog:
            if name in existing:
                self.third_parties[name] = existing[name]["id"]
                continue
            body = {"name": name}
            if not self.api.dry_run:
                body["category_ids"] = [self.tp_categories[cat_name]]
            r = self.api.post("/third-parties/", body, label=name)
            self.third_parties[name] = r["id"]

    def create_kg_accounts(self) -> None:
        logging.info("[11] Cuentas kg (Willard x3 + INTERSEDE)")
        existing = self.api.existing_by("/kg-ledger/accounts", "code")
        for code, display, acc_type, wh_name, tp_name in KG_ACCOUNTS:
            if code in existing:
                continue
            body: dict[str, Any] = {
                "code": code, "display_name": display, "account_type": acc_type,
            }
            if wh_name:
                body["warehouse_id"] = self.warehouses[wh_name]
            if tp_name:
                body["third_party_id"] = self.third_parties[tp_name]
            self.api.post("/kg-ledger/accounts", body, label=code)

    def create_tariffs(self) -> None:
        """Append-only (#35): solo se crea si no hay vigente igual."""
        logging.info("[12] Tarifas de servicio")
        vigentes: dict[str, dict] = {}
        if not self.api.dry_run:
            data = self.api.get("/service-tariffs", {"limit": 100})
            items = data["items"] if isinstance(data, dict) else data
            vigentes = {t["tariff_code"]: t for t in items}
        for t in TARIFFS:
            cur = vigentes.get(t["tariff_code"])
            # #93: kg_per_unit entra a la comparacion — la vigente de prod nacio
            # sin el 14 y el seed debe versionar una nueva (append-only #35),
            # no saltarsela por tener el mismo precio
            same_kg = (
                (cur.get("kg_per_unit") is None and t.get("kg_per_unit") is None)
                or (
                    cur.get("kg_per_unit") is not None
                    and t.get("kg_per_unit") is not None
                    and float(cur["kg_per_unit"]) == float(t["kg_per_unit"])
                )
            ) if cur else False
            if cur and float(cur["unit_price_cop"]) == float(t["unit_price_cop"]) \
                    and cur["unit"] == t["unit"] and same_kg:
                continue
            self.api.post("/service-tariffs", t, label=t["tariff_code"])

    def create_retention_configs(self) -> None:
        """El POST responde 409 si la tarifa ya existe (#79) — se tolera."""
        logging.info("[13] Configs de retencion")
        for rc in RETENTION_CONFIGS:
            self.api.post_tolerating(
                "/third-parties/retention-configs", rc, ok_codes=(409,),
                label=f"{rc['retention_type']}-{rc.get('municipality', '')}",
            )

    # ---------------- RUN ----------------

    def run(self, reset: bool) -> None:
        t0 = time.monotonic()
        mode = "DRY-RUN" if self.api.dry_run else "APPLY"
        logging.info("=" * 70)
        logging.info(f"SEED SAC ORG (solo maestros)  |  {mode}")
        logging.info("=" * 70)

        self.create_or_reset_org(reset)
        self.create_users_and_roles()
        self._force_known_passwords()   # dev-only (ver docstring del metodo)
        self.create_business_units()
        self.create_warehouses()
        self.patch_settings()          # necesita IDs de bodegas (sedes Willard)
        self.create_accounts()
        self.create_expense_categories()
        self.create_material_categories()
        self.create_materials()        # perfiles/formulas requieren flag ON (settings ya)
        self.create_third_parties()
        self.create_kg_accounts()      # requiere Willard S.A creado
        self.create_tariffs()
        self.create_retention_configs()

        logging.info("=" * 70)
        logging.info(f"LISTO en {time.monotonic() - t0:.1f}s  ({mode})")
        logging.info(
            f"  Org SAC: {len(WAREHOUSES)} bodegas, {len(BUSINESS_UNITS)} UNs, "
            f"{len(ACCOUNTS)} cuentas, {len(MATERIALS)} materiales, "
            f"{len(self.third_parties)} terceros, {len(KG_ACCOUNTS)} cuentas kg, "
            f"{len(TARIFFS)} tarifas, {len(RETENTION_CONFIGS)} retenciones. "
            f"SIN transacciones."
        )
        if not self.api.dry_run:
            logging.info(
                "  Usuarios: " + ", ".join(f"{u['email']} ({u['role']})" for u in USERS)
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Recrear org SAC (solo maestros) en dev")
    parser.add_argument("--apply", action="store_true", help="Ejecutar de verdad (default dry-run)")
    parser.add_argument(
        "--reset", action="store_true",
        help="SOLO DEV: soft-delete de la org SAC previa y recrearla desde cero",
    )
    parser.add_argument(
        "--api-url", default=BASE_URL,
        help=f"Backend destino (default {BASE_URL}). Produccion: https://api.ecobalance.cc",
    )
    parser.add_argument("--superuser-email", default=os.environ.get("SEED_SU_EMAIL"))
    parser.add_argument("--superuser-password", default=os.environ.get("SEED_SU_PASSWORD"))
    parser.add_argument(
        "--users-password", default="12345678",
        help="Password para usuarios SAC recreados (los existentes conservan la suya)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if not args.superuser_email or not args.superuser_password:
        raise SystemExit(
            "Faltan credenciales: --superuser-email/--superuser-password "
            "o env SEED_SU_EMAIL/SEED_SU_PASSWORD"
        )

    api = APIClient(dry_run=not args.apply, base_url=args.api_url)

    # Guard duro: --reset contra un backend remoto dejaria a los usuarios
    # existentes desactivados como huerfanos (el endpoint que recrea la org NO
    # los reactiva) y el arreglo por ORM solo funciona en local.
    if args.reset and not api.is_local:
        raise SystemExit(
            f"--reset esta prohibido contra {args.api_url}: borraria la org y dejaria "
            "a los usuarios existentes sin acceso. Contra un backend remoto corra "
            "SIN --reset (modo provision idempetente sobre la org existente)."
        )
    if not api.is_local:
        logging.warning(f"*** DESTINO REMOTO: {args.api_url} ***")

    api.login(args.superuser_email, args.superuser_password)
    SacSeeder(api, args.users_password).run(reset=args.reset)


if __name__ == "__main__":
    main()
