#!/usr/bin/env python
"""
seed_demo_org.py — Crea una organizacion demo con 4 meses de historial operativo
para servir como sandbox comercial.

Organizacion: "Recicladora del Pacifico Demo S.A.S."
Periodo: 2026-02-01 hasta 2026-05-27 (~4 meses)
Usuarios:
  - gerente@demo.ecobalance.com / 12345678   (Administrador)
  - bascula@demo.ecobalance.com / 12345678   (Bascula)

Uso (default dry-run):
    ./venv/bin/python scripts/seed_demo_org.py --superuser-email <admin@x> --superuser-password <pwd>
    ./venv/bin/python scripts/seed_demo_org.py --apply --superuser-email <admin@x> --superuser-password <pwd>
    ./venv/bin/python scripts/seed_demo_org.py --apply --reset --superuser-email <admin@x> --superuser-password <pwd>

Reglas:
  - Todo via API REST (jamas SQL directo).
  - Idempotente con --reset (soft-delete previa de la org existente).
  - random.seed fijo => regeneracion reproducible.
"""

from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional

import requests

# Agregar backend/ al path para que 'from app.*' funcione
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ============================================================================
# CONFIGURACION GENERAL
# ============================================================================

DEFAULT_BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"

# Mapa target -> base URL. Permite correr el mismo script contra dev/test/prod.
TARGET_URLS = {
    "dev": "http://localhost:8000",
    "test": "http://localhost:8000",  # backend test corre en mismo puerto distinto entorno
    "prod": "http://76.13.118.195:8000",
}

ORG_NAME = "Recicladora del Pacifico Demo S.A.S."
ADMIN_EMAIL = "gerente@demo.ecobalance.com"
ADMIN_FULL_NAME = "Maria Gerente"
ADMIN_PASSWORD = "12345678"

BASCULA_EMAIL = "bascula@demo.ecobalance.com"
BASCULA_FULL_NAME = "Carlos Bascula"
BASCULA_PASSWORD = "12345678"

START_DATE = date(2026, 2, 1)
END_DATE = date(2026, 5, 27)
PROFIT_DISTRIBUTION_DATE = date(2026, 4, 5)
MONTACARGAS_DISPOSAL_DATE = date(2026, 4, 18)

RANDOM_SEED = 42

# ============================================================================
# DATOS HARDCODED (especificacion del demo)
# ============================================================================

BUSINESS_UNITS: list[dict[str, str]] = [
    {"name": "Chatarra Ferrosa", "description": "Linea de chatarra ferrosa"},
    {"name": "No Ferrosos", "description": "Cobre, aluminio, bronce, plomo"},
    {"name": "Fibras", "description": "Carton, papel, plasticos"},
]

WAREHOUSES: list[dict[str, str]] = [
    {"name": "Bodega Principal", "address": "Buenaventura, Valle del Cauca"},
    {"name": "Patio Sur", "address": "Buenaventura, Valle - Sucursal Sur"},
]

ACCOUNTS: list[dict[str, Any]] = [
    {"name": "Caja General", "account_type": "cash", "initial_balance": "25000000"},
    {"name": "Banco Bancolombia", "account_type": "bank",
     "bank_name": "Bancolombia", "account_number": "1234-567890-12",
     "initial_balance": "280000000"},
    {"name": "Banco Davivienda", "account_type": "bank",
     "bank_name": "Davivienda", "account_number": "9876-543210-98",
     "initial_balance": "85000000"},
    {"name": "Nequi", "account_type": "digital",
     "account_number": "300-555-1234", "initial_balance": "3000000"},
    {"name": "Caja Menor", "account_type": "cash", "initial_balance": "5000000"},
]

MATERIAL_CATEGORIES: list[str] = ["Chatarra Ferrosa", "No Ferrosos", "Fibras"]

# Material: (code, name, material_category_idx, business_unit_idx, default_unit,
#            initial_purchase_price, initial_sale_price, initial_stock_kg)
MATERIALS: list[tuple[str, str, int, int, str, int, int, int]] = [
    # Chatarra Ferrosa
    ("CHA-LAM", "Lamina ferrosa", 0, 0, "kg", 800, 950, 12000),
    ("CHA-EST", "Estructural pesado", 0, 0, "kg", 1100, 1300, 8000),
    ("CHA-FUN", "Fundicion", 0, 0, "kg", 950, 1150, 6500),
    ("CHA-HIL", "Hilacha", 0, 0, "kg", 400, 600, 4500),
    # No Ferrosos
    ("NF-COB1", "Cobre limpio #1", 1, 1, "kg", 20000, 22000, 1200),
    ("NF-COB2", "Cobre quemado #2", 1, 1, "kg", 15000, 17000, 800),
    ("NF-ALU", "Aluminio perfil", 1, 1, "kg", 4500, 5200, 3500),
    ("NF-BRO", "Bronce", 1, 1, "kg", 9000, 10500, 600),
    ("NF-PLO", "Plomo", 1, 1, "kg", 2800, 3300, 1500),
    # Fibras
    ("FB-CART", "Carton corrugado", 2, 2, "kg", 350, 480, 15000),
    ("FB-PBLN", "Papel blanco", 2, 2, "kg", 700, 950, 5500),
    ("FB-PER", "Periodico", 2, 2, "kg", 280, 380, 8000),
    ("FB-PET", "PET cristal", 2, 2, "kg", 1100, 1450, 3200),
    ("FB-PEAD", "PEAD soplado", 2, 2, "kg", 900, 1200, 2400),
]

# (name, is_direct, parent_name_or_None, default_bu_idx_or_None, applicable_bu_idxs_or_None)
EXPENSE_CATEGORIES: list[tuple[str, bool, Optional[str], Optional[int], Optional[list[int]]]] = [
    ("Flete", True, None, None, None),
    ("Flete chatarra", True, "Flete", 0, None),
    ("Flete fibras", True, "Flete", 2, None),
    ("Pesaje", True, None, None, None),
    ("Arriendo bodegas", False, None, None, [0, 1, 2]),
    ("Servicios publicos", False, None, None, [0, 1, 2]),
    ("Nomina", False, None, None, None),
    ("Nomina chatarra", False, "Nomina", 0, None),
    ("Nomina no ferrosos", False, "Nomina", 1, None),
    ("Mantenimiento equipos", False, None, None, [0, 1, 2]),
    ("Honorarios contables", False, None, None, [0, 1, 2]),
    ("Depreciacion equipos", False, None, None, [0, 1, 2]),
    ("Combustible y peajes", True, None, None, None),
    ("Papeleria y oficina", False, None, None, [0, 1, 2]),
]

THIRD_PARTY_CATEGORIES: list[tuple[str, str]] = [
    ("Proveedor Mayorista", "material_supplier"),
    ("Proveedor Minorista", "material_supplier"),
    ("Cliente Industrial", "customer"),
    ("Cliente Exportador", "customer"),
    ("Servicios Generales", "service_provider"),
    ("Comisionistas", "service_provider"),
    ("Socios", "investor"),
    ("Empleados", "generic"),
]

# (name, identification, category_name)
THIRD_PARTIES: list[tuple[str, str, str]] = [
    # Proveedores Mayoristas
    ("Chatarrera La Industria S.A.S.", "900001001-1", "Proveedor Mayorista"),
    ("Metales del Caribe Ltda.", "900001002-2", "Proveedor Mayorista"),
    ("Reciclajes del Pacifico Sur", "900001003-3", "Proveedor Mayorista"),
    ("Comercializadora Ferro Andina", "900001004-4", "Proveedor Mayorista"),
    ("Recuperaciones del Valle", "900001005-5", "Proveedor Mayorista"),
    ("Materiales Recuperados Cali", "900001006-6", "Proveedor Mayorista"),
    ("Acopio Industrial Buenaventura", "900001007-7", "Proveedor Mayorista"),
    ("Metales y Mas S.A.", "900001008-8", "Proveedor Mayorista"),
    # Proveedores Minoristas
    ("Don Pedro Reciclajes", "5123456", "Proveedor Minorista"),
    ("Recolectora Familia Lopez", "5234567", "Proveedor Minorista"),
    ("Patio Don Jose", "5345678", "Proveedor Minorista"),
    ("Casa de Reciclajes Maria", "5456789", "Proveedor Minorista"),
    # Clientes Industriales
    ("Fundicion Pacifico S.A.", "800001001-1", "Cliente Industrial"),
    ("Papelera del Pacifico", "800001002-2", "Cliente Industrial"),
    ("Aceros Industriales del Cauca", "800001003-3", "Cliente Industrial"),
    ("Plasticos Reciclados Andina", "800001004-4", "Cliente Industrial"),
    # Clientes Exportadores
    ("Exportadora Caribe Metal", "830001001-1", "Cliente Exportador"),
    ("Global Recycling Trade S.A.S.", "830001002-2", "Cliente Exportador"),
    # Servicios Generales
    ("Transportadora Fletes del Sur", "900100001-1", "Servicios Generales"),
    ("Empresa de Servicios Publicos", "899200001-1", "Servicios Generales"),
    ("Inmobiliaria del Puerto Ltda.", "900100002-2", "Servicios Generales"),
    ("Contadores Asociados S.A.S.", "900100003-3", "Servicios Generales"),
    # Comisionistas
    ("Pedro Comisionista Compras", "5500001", "Comisionistas"),
    ("Ana Comisionista Senior", "5500002", "Comisionistas"),
    ("Luis Broker Ventas", "5500003", "Comisionistas"),
    # Socios
    ("Ricardo Mejia (Socio 60%)", "5700001", "Socios"),
    ("Sandra Lopez (Socio 40%)", "5700002", "Socios"),
    # Empleados
    ("Juan Operario", "5800001", "Empleados"),
    ("Maria Asistente", "5800002", "Empleados"),
]

# Aporte de capital inicial por socio
CAPITAL_INJECTIONS: list[tuple[str, str]] = [
    ("Ricardo Mejia (Socio 60%)", "90000000"),
    ("Sandra Lopez (Socio 40%)", "60000000"),
]

# ============================================================================
# UTILIDADES
# ============================================================================


def setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def fmt_money(x: Decimal | str | int | float) -> str:
    """Format COP money with thousand separators."""
    d = Decimal(str(x))
    return f"${d:,.0f}"


def iso(d: date) -> str:
    return d.isoformat()


def business_days(start: date, end: date) -> list[date]:
    """Days from start to end inclusive, excluding Sundays."""
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() != 6:  # 6 = sunday
            days.append(cur)
        cur += timedelta(days=1)
    return days


def month_range(year: int, month: int) -> tuple[date, date]:
    """First and last day of a calendar month."""
    first = date(year, month, 1)
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


# ============================================================================
# API CLIENT
# ============================================================================


class APIClient:
    """Thin wrapper for the EcoBalance REST API."""

    def __init__(self, base_url: str, dry_run: bool = True, target: str = "dev"):
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.target = target
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
        url = f"{self.base_url}{API_PREFIX}/auth/login/json"
        r = self.session.post(url, json={"email": email, "password": password})
        if r.status_code != 200:
            raise SystemExit(f"Login failed [{r.status_code}]: {r.text[:300]}")
        self.token = r.json()["access_token"]

    def _fake_id(self) -> str:
        self._dry_id_counter += 1
        return f"00000000-0000-0000-0000-{self._dry_id_counter:012d}"

    def post(self, path: str, body: dict, label: str = "") -> dict:
        if self.dry_run:
            logging.debug(f"[DRY] POST {path}  ({label})")
            fake = {"id": self._fake_id()}
            fake.update({k: v for k, v in body.items() if k != "lines"})
            return fake
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.post(url, json=body, headers=self._headers())
        if r.status_code >= 400:
            raise SystemExit(
                f"POST {path} failed [{r.status_code}]: {r.text[:500]}\nbody={body}"
            )
        return r.json() if r.text else {}

    def get(self, path: str, params: Optional[dict] = None) -> Any:
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.get(url, headers=self._headers(), params=params)
        if r.status_code >= 400:
            raise SystemExit(f"GET {path} failed [{r.status_code}]: {r.text[:300]}")
        return r.json()

    def delete(self, path: str) -> None:
        if self.dry_run:
            logging.debug(f"[DRY] DELETE {path}")
            return
        url = f"{self.base_url}{API_PREFIX}{path}"
        r = self.session.delete(url, headers=self._headers())
        if r.status_code >= 400 and r.status_code != 404:
            raise SystemExit(f"DELETE {path} failed [{r.status_code}]: {r.text[:300]}")


# ============================================================================
# SEEDER PRINCIPAL
# ============================================================================


@dataclass
class SeederStats:
    """Conteo de cada cosa creada para resumen final."""
    org_created: bool = False
    users_created: int = 0
    masters_count: dict[str, int] = field(default_factory=dict)
    purchases: int = 0
    sales: int = 0
    double_entries: int = 0
    money_movements: int = 0
    fixed_assets: int = 0
    transformations: int = 0
    adjustments: int = 0
    transfers: int = 0


class DemoOrgSeeder:
    """Orquestrador completo: crea org, maestros, terceros, 4 meses de historial."""

    def __init__(self, api: APIClient):
        self.api = api
        self.rng = random.Random(RANDOM_SEED)
        self.stats = SeederStats()

        # Cachés de IDs por nombre/code
        self.business_units: dict[str, str] = {}
        self.warehouses: dict[str, str] = {}
        self.accounts: dict[str, str] = {}
        self.material_categories: dict[str, str] = {}
        self.materials: dict[str, dict] = {}   # code -> {id, business_unit_id, ...}
        self.expense_categories: dict[str, str] = {}
        self.third_party_categories: dict[str, dict] = {}  # name -> {id, behavior_type}
        self.third_parties: dict[str, dict] = {}  # name -> {id, category}
        self.fixed_assets: dict[str, str] = {}

        self.bascula_role_id: Optional[str] = None

    # ------------------------------------------------------------------
    # FASE 0: AUTENTICACION + ORG
    # ------------------------------------------------------------------

    def run(self, reset: bool) -> None:
        t0 = time.monotonic()
        logging.info("=" * 70)
        logging.info(f"SEED DEMO ORG  |  {'DRY-RUN' if self.api.dry_run else 'APPLY'}")
        logging.info(f"Org: {ORG_NAME}")
        logging.info(f"Periodo: {iso(START_DATE)} a {iso(END_DATE)}")
        logging.info("=" * 70)

        self.create_or_reset_org(reset=reset)
        self.create_bascula_user()

        # Maestros
        self.create_business_units()
        self.create_warehouses()
        self.create_accounts()
        self.create_material_categories()
        self.create_expense_categories()
        self.create_third_party_categories()
        self.create_materials()
        self.create_price_list()
        self.create_third_parties()

        # Estado inicial
        self.load_initial_inventory()
        self.create_fixed_assets()
        self.create_capital_injection()
        self.create_initial_scheduled_expense()

        # 4 meses de operacion
        for year, month in [(2026, 2), (2026, 3), (2026, 4), (2026, 5)]:
            self.simulate_month(year, month)

        # Casos especiales
        self.dispose_montacargas()
        self.distribute_profits()

        elapsed = time.monotonic() - t0
        self.print_summary(elapsed)

    # ------------------------------------------------------------------
    # ORG + USUARIOS
    # ------------------------------------------------------------------

    def create_or_reset_org(self, reset: bool) -> None:
        logging.info("[FASE 1] Crear/resetear organizacion demo")
        existing = self._find_existing_org()
        if existing:
            if not reset:
                raise SystemExit(
                    f"La organizacion '{ORG_NAME}' ya existe (id={existing['id']}). "
                    f"Use --reset para borrarla y recrearla."
                )
            logging.info(f"  Soft-deleting org existente {existing['id']}")
            self.api.delete(f"/system/organizations/{existing['id']}")
            # La soft-delete desactiva usuarios huerfanos (is_active=False).
            # Cuando se recrea la org, /auth/register falla si el email ya existe
            # y el endpoint de org reutiliza usuarios inactivos sin re-activarlos.
            # Workaround: re-activar los 2 usuarios demo via ORM directo.
            self._reactivate_demo_users()

        # El endpoint /system/organizations crea un User admin con password "123456"
        # hardcoded si el email no existe. Para que la password sea la que queremos,
        # pre-creamos el usuario via /auth/register y dejamos que el endpoint de org
        # detecte el email existente y lo reutilice.
        self._pre_register_user(ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_FULL_NAME)

        body = {
            "name": ORG_NAME,
            "admin_email": ADMIN_EMAIL,
            "admin_full_name": ADMIN_FULL_NAME,
        }
        r = self.api.post("/system/organizations", body, label="org")
        self.api.org_id = r["id"]
        self.stats.org_created = True
        self.stats.users_created += 1
        logging.info(f"  Org creada id={r['id']} admin={ADMIN_EMAIL}")

    def _reactivate_demo_users(self) -> None:
        """Reactivar via ORM los usuarios demo desactivados por la soft-delete.

        IMPORTANTE: Solo funciona contra la BD local (la que apunta DATABASE_URL
        del .env del backend). Si target=prod y se corre desde una maquina cliente,
        SessionLocal apuntaria a la BD dev local, NO a prod. Por eso se skipea.
        """
        if self.api.dry_run:
            return
        if self.api.target == "prod":
            logging.warning(
                "  [PROD] Skipping reactivate_demo_users — el ORM local no apunta "
                "a la BD de prod. Si hay usuarios huerfanos en prod, reactivarlos "
                "manualmente desde el server o agregar endpoint admin."
            )
            return
        try:
            from app.core.database import SessionLocal
            from app.models.user import User
        except ImportError:
            logging.warning("  No se pudo importar app.* para reactivar usuarios")
            return
        with SessionLocal() as db:
            for email in (ADMIN_EMAIL, BASCULA_EMAIL):
                user = db.query(User).filter(User.email == email).first()
                if user and not user.is_active:
                    user.is_active = True
                    logging.info(f"  Re-activado usuario huerfano: {email}")
            db.commit()

    def _pre_register_user(self, email: str, password: str, full_name: str) -> str:
        """Crea un User via /auth/register o retorna ID si ya existe."""
        if self.api.dry_run:
            logging.info(f"  [DRY] Pre-register user {email}")
            return "00000000-0000-0000-0000-000000000000"
        url = f"{self.api.base_url}{API_PREFIX}/auth/register"
        body = {"email": email, "password": password, "full_name": full_name}
        r = self.api.session.post(url, json=body)
        if r.status_code == 201:
            return r.json()["user"]["id"]
        # Si ya existe, retornamos None - el endpoint de org lo encontrara por email
        if r.status_code == 400 and "already" in r.text.lower():
            logging.info(f"  Usuario {email} ya existia, sera reutilizado")
            return ""
        raise SystemExit(f"Pre-register failed [{r.status_code}]: {r.text[:300]}")

    def _find_existing_org(self) -> Optional[dict]:
        if self.api.dry_run:
            return None
        orgs = self.api.get("/system/organizations")
        for o in orgs:
            if o["name"] == ORG_NAME and o.get("is_active", True):
                return o
        return None

    def create_bascula_user(self) -> None:
        logging.info("[FASE 2] Crear usuario bascula y asignarlo a la org")
        if self.api.dry_run:
            logging.info("  [DRY] Crear usuario bascula via /auth/register")
            logging.info(f"  [DRY] Asignar a org con rol 'bascula'")
            self.stats.users_created += 1
            return

        # 1) Crear usuario (o detectar existente)
        bascula_user_id = self._pre_register_user(BASCULA_EMAIL, BASCULA_PASSWORD, BASCULA_FULL_NAME)
        if not bascula_user_id:
            # Si ya existia, buscarlo por email
            users = self.api.get("/system/users")
            user = next((u for u in users if u["email"] == BASCULA_EMAIL), None)
            if not user:
                raise SystemExit(f"Usuario {BASCULA_EMAIL} no encontrado")
            bascula_user_id = user["id"]

        # 2) Buscar role_id de "bascula" en la org
        roles = self.api.get(f"/system/organizations/{self.api.org_id}/roles")
        bascula_role = next((r for r in roles if r["name"] == "bascula"), None)
        if not bascula_role:
            raise SystemExit("No se encontro el rol 'bascula' en la organizacion")
        self.bascula_role_id = bascula_role["id"]

        # 3) Asignar usuario a org con rol
        self.api.post(
            f"/system/users/{bascula_user_id}/add-to-org",
            {"organization_id": self.api.org_id, "role_id": self.bascula_role_id},
            label="add-bascula-to-org",
        )
        self.stats.users_created += 1
        logging.info(f"  Usuario bascula creado y asignado: {BASCULA_EMAIL}")

    # ------------------------------------------------------------------
    # MAESTROS
    # ------------------------------------------------------------------

    def create_business_units(self) -> None:
        logging.info("[FASE 3] Unidades de Negocio")
        for bu in BUSINESS_UNITS:
            r = self.api.post("/business-units/", bu, label=bu["name"])
            self.business_units[bu["name"]] = r["id"]
        self.stats.masters_count["business_units"] = len(BUSINESS_UNITS)
        logging.info(f"  {len(BUSINESS_UNITS)} UN creadas")

    def create_warehouses(self) -> None:
        logging.info("[FASE 4] Bodegas")
        for wh in WAREHOUSES:
            r = self.api.post("/warehouses/", wh, label=wh["name"])
            self.warehouses[wh["name"]] = r["id"]
        self.stats.masters_count["warehouses"] = len(WAREHOUSES)
        logging.info(f"  {len(WAREHOUSES)} bodegas creadas")

    def create_accounts(self) -> None:
        logging.info("[FASE 5] Cuentas de dinero")
        for acc in ACCOUNTS:
            r = self.api.post("/money-accounts/", acc, label=acc["name"])
            self.accounts[acc["name"]] = r["id"]
        self.stats.masters_count["accounts"] = len(ACCOUNTS)
        logging.info(f"  {len(ACCOUNTS)} cuentas creadas")

    def create_material_categories(self) -> None:
        logging.info("[FASE 6] Categorias de materiales")
        for name in MATERIAL_CATEGORIES:
            r = self.api.post("/material-categories/", {"name": name}, label=name)
            self.material_categories[name] = r["id"]
        self.stats.masters_count["material_categories"] = len(MATERIAL_CATEGORIES)
        logging.info(f"  {len(MATERIAL_CATEGORIES)} categorias de material creadas")

    def create_expense_categories(self) -> None:
        logging.info("[FASE 7] Categorias de gasto (con jerarquia padre-hijo)")
        # Primero los padres, despues los hijos
        for name, is_direct, parent, default_bu, applicable in EXPENSE_CATEGORIES:
            if parent is not None:
                continue
            body: dict[str, Any] = {"name": name, "is_direct_expense": is_direct}
            if default_bu is not None:
                body["default_business_unit_id"] = self.business_units[BUSINESS_UNITS[default_bu]["name"]]
            elif applicable:
                body["default_applicable_business_unit_ids"] = [
                    self.business_units[BUSINESS_UNITS[i]["name"]] for i in applicable
                ]
            r = self.api.post("/expense-categories/", body, label=name)
            self.expense_categories[name] = r["id"]
        # Ahora hijos
        for name, is_direct, parent, default_bu, applicable in EXPENSE_CATEGORIES:
            if parent is None:
                continue
            body = {
                "name": name,
                "is_direct_expense": is_direct,
                "parent_id": self.expense_categories[parent],
            }
            if default_bu is not None:
                body["default_business_unit_id"] = self.business_units[BUSINESS_UNITS[default_bu]["name"]]
            elif applicable:
                body["default_applicable_business_unit_ids"] = [
                    self.business_units[BUSINESS_UNITS[i]["name"]] for i in applicable
                ]
            r = self.api.post("/expense-categories/", body, label=name)
            self.expense_categories[name] = r["id"]
        self.stats.masters_count["expense_categories"] = len(EXPENSE_CATEGORIES)
        logging.info(f"  {len(EXPENSE_CATEGORIES)} categorias de gasto creadas")

    def create_third_party_categories(self) -> None:
        logging.info("[FASE 8] Categorias de terceros")
        for name, behavior in THIRD_PARTY_CATEGORIES:
            body = {"name": name, "behavior_type": behavior}
            r = self.api.post("/third-party-categories/", body, label=name)
            self.third_party_categories[name] = {"id": r["id"], "behavior_type": behavior}
        self.stats.masters_count["third_party_categories"] = len(THIRD_PARTY_CATEGORIES)
        logging.info(f"  {len(THIRD_PARTY_CATEGORIES)} categorias de terceros creadas")

    def create_materials(self) -> None:
        logging.info("[FASE 9] Materiales")
        for code, name, cat_idx, bu_idx, unit, _pp, _sp, _stock in MATERIALS:
            body = {
                "code": code,
                "name": name,
                "category_id": self.material_categories[MATERIAL_CATEGORIES[cat_idx]],
                "business_unit_id": self.business_units[BUSINESS_UNITS[bu_idx]["name"]],
                "default_unit": unit,
            }
            r = self.api.post("/materials/", body, label=code)
            self.materials[code] = {
                "id": r["id"],
                "business_unit_id": body["business_unit_id"],
                "name": name,
            }
        self.stats.masters_count["materials"] = len(MATERIALS)
        logging.info(f"  {len(MATERIALS)} materiales creados")

    def create_price_list(self) -> None:
        logging.info("[FASE 10] Lista de precios inicial")
        for code, _name, _cat, _bu, _unit, pp, sp, _stock in MATERIALS:
            body = {
                "material_id": self.materials[code]["id"],
                "purchase_price": str(pp),
                "sale_price": str(sp),
                "notes": "Precios iniciales al inicio de operacion",
            }
            self.api.post("/price-lists/", body, label=f"price-{code}")
        self.stats.masters_count["price_list_entries"] = len(MATERIALS)
        logging.info(f"  {len(MATERIALS)} entradas de precio creadas")

    def create_third_parties(self) -> None:
        logging.info("[FASE 11] Terceros")
        for name, ident, category in THIRD_PARTIES:
            body = {
                "name": name,
                "identification_number": ident,
                "category_ids": [self.third_party_categories[category]["id"]],
            }
            r = self.api.post("/third-parties/", body, label=name)
            self.third_parties[name] = {
                "id": r["id"],
                "category": category,
                "behavior_type": self.third_party_categories[category]["behavior_type"],
            }
        self.stats.masters_count["third_parties"] = len(THIRD_PARTIES)
        logging.info(f"  {len(THIRD_PARTIES)} terceros creados")

    # ------------------------------------------------------------------
    # ESTADO INICIAL
    # ------------------------------------------------------------------

    def load_initial_inventory(self) -> None:
        logging.info("[FASE 12] Inventario inicial via ajustes de carga")
        bodega_principal = self.warehouses["Bodega Principal"]
        for code, _name, _cat, _bu, _unit, pp, _sp, stock_kg in MATERIALS:
            if stock_kg <= 0:
                continue
            body = {
                "material_id": self.materials[code]["id"],
                "warehouse_id": bodega_principal,
                "quantity": str(stock_kg),
                "unit_cost": str(pp),
                "date": iso(START_DATE),
                "reason": "Carga inicial migracion Recicladora Demo",
                "notes": "Saldo inicial al 1 de febrero 2026",
            }
            self.api.post("/inventory/adjustments/increase", body, label=f"inv-init-{code}")
            self.stats.adjustments += 1
        logging.info(f"  Inventario inicial cargado para {len(MATERIALS)} materiales")

    def create_fixed_assets(self) -> None:
        logging.info("[FASE 13] Activos fijos")
        depr_cat = self.expense_categories["Depreciacion equipos"]
        # Lista de specs concretos (uso indices a las cuentas y supplier names)
        assets = [
            {
                "name": "Bascula camionera #1", "asset_code": "BSC-001",
                "purchase_date": iso(date(2026, 2, 1)), "purchase_value": "18000000",
                "salvage_value": "1500000", "depreciation_rate": "1.667",
                "depreciation_start_date": iso(date(2026, 2, 1)),
                "expense_category_id": depr_cat,
                "source_account_id": self.accounts["Banco Bancolombia"],
                "notes": "Bascula camionera bodega principal",
            },
            {
                "name": "Bascula peatonal #2", "asset_code": "BSC-002",
                "purchase_date": iso(date(2026, 2, 15)), "purchase_value": "5500000",
                "salvage_value": "500000", "depreciation_rate": "2.083",
                "depreciation_start_date": iso(date(2026, 3, 1)),
                "expense_category_id": depr_cat,
                "supplier_id": self.third_parties["Comercializadora Ferro Andina"]["id"],
                "notes": "Comprada a credito al proveedor",
            },
            {
                "name": "Camion Volvo FH 2018", "asset_code": "VEH-001",
                "purchase_date": iso(date(2024, 8, 1)), "purchase_value": "180000000",
                "salvage_value": "30000000", "depreciation_rate": "1.389",
                "depreciation_start_date": iso(date(2024, 8, 1)),
                "expense_category_id": depr_cat,
                "accumulated_depreciation": "45000000",
                "historical_load": True,
                "notes": "Carga historica - camion ya depreciado del sistema anterior",
            },
            {
                "name": "Montacargas Toyota", "asset_code": "VEH-002",
                "purchase_date": iso(date(2026, 3, 5)), "purchase_value": "32000000",
                "salvage_value": "5000000", "depreciation_rate": "1.389",
                "depreciation_start_date": iso(date(2026, 3, 5)),
                "expense_category_id": depr_cat,
                "source_account_id": self.accounts["Banco Davivienda"],
                "notes": "Montacargas para patio sur",
            },
            {
                "name": "Computador oficina", "asset_code": "OFC-001",
                "purchase_date": iso(date(2026, 2, 5)), "purchase_value": "3200000",
                "salvage_value": "200000", "depreciation_rate": "2.778",
                "depreciation_start_date": iso(date(2026, 2, 5)),
                "expense_category_id": depr_cat,
                "source_account_id": self.accounts["Caja General"],
                "notes": "PC administracion",
            },
        ]
        for asset in assets:
            r = self.api.post("/fixed-assets/", asset, label=asset["name"])
            self.fixed_assets[asset["asset_code"]] = r["id"]
            self.stats.fixed_assets += 1
        logging.info(f"  {len(assets)} activos fijos creados")

    def create_capital_injection(self) -> None:
        logging.info("[FASE 14] Aporte inicial de socios")
        for socio_name, amount in CAPITAL_INJECTIONS:
            body = {
                "investor_id": self.third_parties[socio_name]["id"],
                "amount": amount,
                "account_id": self.accounts["Banco Bancolombia"],
                "date": iso(START_DATE),
                "description": f"Aporte inicial de capital - {socio_name}",
            }
            self.api.post("/money-movements/capital-injection", body, label=f"capital-{socio_name}")
            self.stats.money_movements += 1
        logging.info(f"  Aportes de capital: {sum(int(a) for _, a in CAPITAL_INJECTIONS):,} COP")

    def create_initial_scheduled_expense(self) -> None:
        logging.info("[FASE 15] Gasto diferido (seguro anual)")
        body = {
            "name": "Seguro anual de bodegas y activos",
            "total_amount": "12000000",
            "total_months": 12,
            "source_account_id": self.accounts["Banco Bancolombia"],
            "expense_category_id": self.expense_categories["Servicios publicos"],
            "start_date": iso(date(2026, 2, 1)),
            "apply_day": 5,
            "description": "Poliza anual cubre bodegas, vehiculos y activos",
            "default_applicable_business_unit_ids": [
                self.business_units[bu["name"]] for bu in BUSINESS_UNITS
            ],
        }
        # default_applicable_business_unit_ids no esta en el schema base, usar business_unit_id solo
        body.pop("default_applicable_business_unit_ids", None)
        body["applicable_business_unit_ids"] = [
            self.business_units[bu["name"]] for bu in BUSINESS_UNITS
        ]
        self.api.post("/scheduled-expenses/", body, label="scheduled-seguro")
        logging.info("  Seguro anual: 12.000.000 en 12 cuotas mensuales")

    # ------------------------------------------------------------------
    # OPERACION MES A MES
    # ------------------------------------------------------------------

    def simulate_month(self, year: int, month: int) -> None:
        first, last = month_range(year, month)
        if last > END_DATE:
            last = END_DATE
        logging.info(f"[FASE 16] Operacion {first.strftime('%B %Y')} ({iso(first)} a {iso(last)})")

        days = business_days(first, last)
        self._generate_purchases(days)
        self._generate_sales(days)
        self._generate_double_entries(first, last)
        self._generate_operating_expenses(days)
        self._generate_supplier_payments(days)
        self._generate_customer_collections(days)
        self._apply_monthly_provisions(first)
        self._apply_monthly_payroll_accrual(first)
        self._apply_monthly_transfers(first)

        # Cosas mensuales especiales del primer mes
        if month == 2:
            self._create_advance_examples()
        elif month == 3:
            self._create_transformation()
        elif month == 4:
            self._create_warehouse_transfer()
            self._create_adjustment_examples()

    # --- helpers de poblacion ---

    def _suppliers_pool(self) -> list[str]:
        return [n for n, _, cat in THIRD_PARTIES if cat in ("Proveedor Mayorista", "Proveedor Minorista")]

    def _customers_pool(self) -> list[str]:
        return [n for n, _, cat in THIRD_PARTIES if cat in ("Cliente Industrial", "Cliente Exportador")]

    def _generate_purchases(self, days: list[date]) -> None:
        # Compras moderadas: ~25-28/mes
        for d in days:
            base = 1
            if d.weekday() in (0, 1):
                base = 2
            count = self.rng.choices([0, base, base + 1], weights=[25, 65, 10])[0]
            for _ in range(count):
                self._create_purchase(d)

    def _safe_post(self, path: str, body: dict, label: str) -> Optional[dict]:
        """POST con try/except - logs warning y retorna None si falla."""
        try:
            return self.api.post(path, body, label=label)
        except SystemExit as e:
            logging.warning(f"  [SKIP] {label}: {str(e)[:200]}")
            return None

    def _create_purchase(self, d: date) -> None:
        is_mayorista = self.rng.random() < 0.7
        cat = "Proveedor Mayorista" if is_mayorista else "Proveedor Minorista"
        suppliers = [n for n, _, c in THIRD_PARTIES if c == cat]
        supplier_name = self.rng.choice(suppliers)
        supplier_id = self.third_parties[supplier_name]["id"]

        n_lines = self.rng.choice([1, 1, 2, 2, 3])
        lines = []
        chosen_materials = self.rng.sample(list(self.materials.values()), n_lines)
        for m in chosen_materials:
            qty, unit_price = self._random_quantity_price(m, mode="buy")
            lines.append({
                "material_id": m["id"],
                "quantity": str(qty),
                "unit_price": str(unit_price),
                "warehouse_id": self.warehouses["Bodega Principal"],
            })

        auto_liquidate = self.rng.random() < 0.35
        immediate_payment = auto_liquidate and self.rng.random() < 0.5

        body: dict[str, Any] = {
            "supplier_id": supplier_id,
            "date": iso(d),
            "notes": f"Compra registrada el {iso(d)}",
            "lines": lines,
            "auto_liquidate": auto_liquidate,
        }
        if immediate_payment:
            body["immediate_payment"] = True
            # Pago inmediato solo desde el banco grande para evitar quiebres de caja
            body["payment_account_id"] = self.accounts["Banco Bancolombia"]

        # 10% probabilidad de comision
        if self.rng.random() < 0.10:
            commissioner = self.rng.choice([
                "Pedro Comisionista Compras", "Ana Comisionista Senior"
            ])
            body["commissions"] = [{
                "third_party_id": self.third_parties[commissioner]["id"],
                "concept": "Comision compra",
                "commission_type": "percentage",
                "commission_value": "1.5",
            }]

        if self._safe_post("/purchases/", body, label=f"purchase-{iso(d)}"):
            self.stats.purchases += 1

    def _generate_sales(self, days: list[date]) -> None:
        # Febrero (rampa de arranque): 7-9 ventas. Marzo en adelante: 11-14 ventas
        first_day = days[0]
        if first_day.month == 2:
            n_sales = self.rng.randint(7, 9)
        else:
            n_sales = self.rng.randint(11, 14)
        # Distribuir en cualquier dia del mes (no solo fin de quincena)
        candidates = days
        sale_days = self.rng.sample(candidates, min(n_sales, len(candidates)))
        for d in sale_days:
            self._create_sale(d)

    def _create_sale(self, d: date) -> None:
        is_exportador = self.rng.random() < 0.25
        cat = "Cliente Exportador" if is_exportador else "Cliente Industrial"
        customers = [n for n, _, c in THIRD_PARTIES if c == cat]
        customer_name = self.rng.choice(customers)
        customer_id = self.third_parties[customer_name]["id"]

        n_lines = self.rng.choice([1, 2, 2, 3])
        chosen_materials = self.rng.sample(list(self.materials.values()), n_lines)
        lines = []
        for m in chosen_materials:
            qty, unit_price = self._random_quantity_price(m, mode="sell")
            lines.append({
                "material_id": m["id"],
                "quantity": str(qty),
                "unit_price": str(unit_price),
            })

        auto_liquidate = self.rng.random() < 0.85
        immediate_collection = auto_liquidate and self.rng.random() < 0.55

        body: dict[str, Any] = {
            "customer_id": customer_id,
            "warehouse_id": self.warehouses["Bodega Principal"],
            "date": iso(d),
            "notes": f"Venta del {iso(d)}",
            "lines": lines,
            "auto_liquidate": auto_liquidate,
        }
        if immediate_collection:
            body["immediate_collection"] = True
            body["collection_account_id"] = self.accounts["Banco Bancolombia"]

        # 8% probabilidad de comision a vendedor
        if self.rng.random() < 0.08:
            body["commissions"] = [{
                "third_party_id": self.third_parties["Luis Broker Ventas"]["id"],
                "concept": "Comision venta",
                "commission_type": "percentage",
                "commission_value": "2.0",
            }]

        if self._safe_post("/sales/", body, label=f"sale-{iso(d)}"):
            self.stats.sales += 1

    def _generate_double_entries(self, first: date, last: date) -> None:
        # 2 DPs por mes
        for _ in range(2):
            d = first + timedelta(days=self.rng.randint(0, (last - first).days))
            if d.weekday() == 6:
                d += timedelta(days=1)
            self._create_double_entry(d)

    def _create_double_entry(self, d: date) -> None:
        suppliers = [n for n, _, c in THIRD_PARTIES if c == "Proveedor Mayorista"]
        customers = [n for n, _, c in THIRD_PARTIES if c == "Cliente Industrial"]
        supplier_name = self.rng.choice(suppliers)
        customer_name = self.rng.choice(customers)
        m = self.rng.choice(list(self.materials.values()))
        qty, purchase_price = self._random_quantity_price(m, mode="buy")
        _, sale_price = self._random_quantity_price(m, mode="sell")
        # Margen de doble partida: 8-15% sobre compra
        sale_price = int(purchase_price * (1 + self.rng.uniform(0.08, 0.15)))

        body = {
            "supplier_id": self.third_parties[supplier_name]["id"],
            "customer_id": self.third_parties[customer_name]["id"],
            "date": iso(d),
            "lines": [{
                "material_id": m["id"],
                "quantity": str(qty),
                "purchase_unit_price": str(purchase_price),
                "sale_unit_price": str(sale_price),
            }],
            "notes": f"Doble partida {iso(d)}",
            "auto_liquidate": self.rng.random() < 0.5,
        }
        if self._safe_post("/double-entries/", body, label=f"dp-{iso(d)}"):
            self.stats.double_entries += 1

    def _generate_operating_expenses(self, days: list[date]) -> None:
        # ~15-20 gastos por mes (mas moderado para no consumir tanta utilidad)
        n = self.rng.randint(15, 20)
        chosen = self.rng.sample(days, min(n, len(days)))
        for d in chosen:
            self._create_operating_expense(d)

    def _create_operating_expense(self, d: date) -> None:
        choices = [
            ("Combustible y peajes", "Caja General", 50000, 250000),
            ("Papeleria y oficina", "Caja Menor", 20000, 120000),
            ("Pesaje", "Caja General", 30000, 150000),
            ("Mantenimiento equipos", "Banco Bancolombia", 200000, 800000),
            ("Honorarios contables", "Banco Bancolombia", 300000, 800000),
        ]
        cat_name, account_name, min_v, max_v = self.rng.choice(choices)
        amount = self.rng.randint(min_v, max_v)
        body = {
            "amount": str(amount),
            "expense_category_id": self.expense_categories[cat_name],
            "account_id": self.accounts[account_name],
            "description": f"{cat_name} - {iso(d)}",
            "date": iso(d),
        }
        if self._safe_post("/money-movements/expense", body, label=f"exp-{cat_name}"):
            self.stats.money_movements += 1

    def _generate_supplier_payments(self, days: list[date]) -> None:
        # ~8 pagos a proveedores por mes
        n = self.rng.randint(6, 10)
        chosen = self.rng.sample(days, min(n, len(days)))
        suppliers = [n for n, _, c in THIRD_PARTIES if c in ("Proveedor Mayorista", "Proveedor Minorista")]
        for d in chosen:
            supplier_name = self.rng.choice(suppliers)
            amount = self.rng.randint(500000, 5000000)
            body = {
                "supplier_id": self.third_parties[supplier_name]["id"],
                "amount": str(amount),
                "account_id": self.accounts["Banco Bancolombia"],
                "date": iso(d),
                "description": f"Abono a {supplier_name}",
            }
            if self._safe_post("/money-movements/supplier-payment", body, label="pago-proveedor"):
                self.stats.money_movements += 1

    def _generate_customer_collections(self, days: list[date]) -> None:
        # ~5 cobros a clientes por mes
        n = self.rng.randint(4, 7)
        chosen = self.rng.sample(days, min(n, len(days)))
        customers = [n for n, _, c in THIRD_PARTIES if c in ("Cliente Industrial", "Cliente Exportador")]
        for d in chosen:
            customer_name = self.rng.choice(customers)
            amount = self.rng.randint(2000000, 15000000)
            body = {
                "customer_id": self.third_parties[customer_name]["id"],
                "amount": str(amount),
                "account_id": self.accounts["Banco Bancolombia"],
                "date": iso(d),
                "description": f"Cobro a {customer_name}",
            }
            if self._safe_post("/money-movements/customer-collection", body, label="cobro-cliente"):
                self.stats.money_movements += 1

    def _apply_monthly_provisions(self, first_of_month: date) -> None:
        """Arriendo mensual fijo."""
        body = {
            "amount": "3800000",
            "expense_category_id": self.expense_categories["Arriendo bodegas"],
            "account_id": self.accounts["Banco Bancolombia"],
            "third_party_id": self.third_parties["Inmobiliaria del Puerto Ltda."]["id"],
            "description": f"Arriendo bodega {first_of_month.strftime('%B %Y')}",
            "date": iso(first_of_month.replace(day=2)),
        }
        if self._safe_post("/money-movements/expense", body, label="arriendo"):
            self.stats.money_movements += 1

    def _apply_monthly_payroll_accrual(self, first_of_month: date) -> None:
        """Nomina causada como pasivo, pagada despues."""
        if first_of_month.month > 4:
            return
        accrual_date = first_of_month.replace(day=28) if first_of_month.day == 1 else first_of_month
        accrual_amount = "4200000"
        accrual_body = {
            "amount": accrual_amount,
            "third_party_id": self.third_parties["Empresa de Servicios Publicos"]["id"],
            "expense_category_id": self.expense_categories["Servicios publicos"],
            "description": f"Servicios publicos causados {first_of_month.strftime('%B')}",
            "date": iso(accrual_date),
        }
        if self._safe_post("/money-movements/expense-accrual", accrual_body, label="accrual-serv-pub"):
            self.stats.money_movements += 1
        pay_date = accrual_date + timedelta(days=10)
        if pay_date <= END_DATE:
            pay_body = {
                "supplier_id": self.third_parties["Empresa de Servicios Publicos"]["id"],
                "amount": accrual_amount,
                "account_id": self.accounts["Banco Bancolombia"],
                "date": iso(pay_date),
                "description": "Pago servicios publicos",
            }
            if self._safe_post("/money-movements/supplier-payment", pay_body, label="pago-servicios"):
                self.stats.money_movements += 1

    def _apply_monthly_transfers(self, first_of_month: date) -> None:
        # 2 transferencias por mes Bancolombia -> Caja General para reponer caja chica
        for offset, amount in ((2, "12000000"), (15, "8000000")):
            d = first_of_month + timedelta(days=offset)
            if d > END_DATE:
                continue
            body = {
                "amount": amount,
                "source_account_id": self.accounts["Banco Bancolombia"],
                "destination_account_id": self.accounts["Caja General"],
                "date": iso(d),
                "description": "Traspaso a caja para gastos operativos",
            }
            if self._safe_post("/money-movements/transfer", body, label="transfer"):
                self.stats.money_movements += 1
        # 1 transferencia Caja General -> Caja Menor para reponer caja chica
        d = first_of_month + timedelta(days=5)
        if d <= END_DATE:
            body = {
                "amount": "1500000",
                "source_account_id": self.accounts["Caja General"],
                "destination_account_id": self.accounts["Caja Menor"],
                "date": iso(d),
                "description": "Reposicion caja menor",
            }
            if self._safe_post("/money-movements/transfer", body, label="transfer-caja-menor"):
                self.stats.money_movements += 1

    # ------------------------------------------------------------------
    # CASOS ESPECIALES
    # ------------------------------------------------------------------

    def _create_advance_examples(self) -> None:
        """Anticipo a proveedor y anticipo de cliente."""
        body_anticipo_prov = {
            "supplier_id": self.third_parties["Chatarrera La Industria S.A.S."]["id"],
            "amount": "3000000",
            "account_id": self.accounts["Banco Bancolombia"],
            "date": iso(date(2026, 2, 10)),
            "description": "Anticipo para asegurar volumen de compra",
        }
        if self._safe_post("/money-movements/advance-payment", body_anticipo_prov, label="anticipo-prov"):
            self.stats.money_movements += 1

        body_anticipo_cli = {
            "customer_id": self.third_parties["Exportadora Caribe Metal"]["id"],
            "amount": "8000000",
            "account_id": self.accounts["Banco Bancolombia"],
            "date": iso(date(2026, 2, 20)),
            "description": "Anticipo cliente para reservar lote de cobre",
        }
        if self._safe_post("/money-movements/advance-collection", body_anticipo_cli, label="anticipo-cli"):
            self.stats.money_movements += 1

    def _create_transformation(self) -> None:
        """Transformacion de chatarra (un material en multiples)."""
        # Esta es solo un ejemplo simplificado. Falla si no hay inventario.
        source = self.materials["CHA-EST"]  # Estructural pesado como fuente
        dest1 = self.materials["CHA-LAM"]   # Lamina
        dest2 = self.materials["CHA-FUN"]   # Fundicion
        body = {
            "source_material_id": source["id"],
            "source_warehouse_id": self.warehouses["Bodega Principal"],
            "source_quantity": "2000",
            "waste_quantity": "100",
            "cost_distribution": "average_cost",
            "lines": [
                {
                    "destination_material_id": dest1["id"],
                    "destination_warehouse_id": self.warehouses["Bodega Principal"],
                    "quantity": "1200",
                },
                {
                    "destination_material_id": dest2["id"],
                    "destination_warehouse_id": self.warehouses["Bodega Principal"],
                    "quantity": "700",
                },
            ],
            "date": iso(date(2026, 3, 15)),
            "reason": "Desarme de estructural en lamina y fundicion",
        }
        try:
            self.api.post("/inventory/transformations", body, label="transform-mar")
            self.stats.transformations += 1
        except SystemExit as e:
            logging.warning(f"  Transformacion fallo (puede ser stock insuficiente): {e}")

    def _create_warehouse_transfer(self) -> None:
        """Traslado entre bodegas en abril."""
        body = {
            "material_id": self.materials["FB-CART"]["id"],
            "source_warehouse_id": self.warehouses["Bodega Principal"],
            "destination_warehouse_id": self.warehouses["Patio Sur"],
            "quantity": "3000",
            "date": iso(date(2026, 4, 10)),
            "reason": "Traslado de carton corrugado a patio sur",
        }
        try:
            self.api.post("/inventory/adjustments/warehouse-transfer", body, label="transfer-bodegas")
            self.stats.transfers += 1
        except SystemExit as e:
            logging.warning(f"  Traslado fallo: {e}")

    def _create_adjustment_examples(self) -> None:
        """Ajustes de aumento, disminucion y conteo."""
        # Aumento - encontramos material no contabilizado
        body_aumento = {
            "material_id": self.materials["NF-ALU"]["id"],
            "warehouse_id": self.warehouses["Bodega Principal"],
            "quantity": "250",
            "unit_cost": "4600",
            "date": iso(date(2026, 4, 12)),
            "reason": "Encontrados en revision fisica bodega",
        }
        try:
            self.api.post("/inventory/adjustments/increase", body_aumento, label="adj-aum")
            self.stats.adjustments += 1
        except SystemExit as e:
            logging.warning(f"  Ajuste aumento fallo: {e}")

        # Disminucion - perdida por humedad
        body_dism = {
            "material_id": self.materials["FB-PER"]["id"],
            "warehouse_id": self.warehouses["Bodega Principal"],
            "quantity": "150",
            "date": iso(date(2026, 4, 20)),
            "reason": "Perdida por humedad lote periodico",
        }
        try:
            self.api.post("/inventory/adjustments/decrease", body_dism, label="adj-dis")
            self.stats.adjustments += 1
        except SystemExit as e:
            logging.warning(f"  Ajuste disminucion fallo: {e}")

    def _random_quantity_price(self, material: dict, mode: str) -> tuple[int, int]:
        """Genera cantidad (kg) y precio realista para el material."""
        code = next(c for c, _, _, _, _, _, _, _ in MATERIALS if self.materials[c]["id"] == material["id"])
        spec = next(m for m in MATERIALS if m[0] == code)
        _, _, _, _, _, base_pp, base_sp, _ = spec
        # Rango cantidad por familia (ventas con volumenes mayores)
        if code.startswith("CHA"):
            qty_min, qty_max = (300, 2200) if mode == "sell" else (200, 1800)
        elif code.startswith("NF"):
            qty_min, qty_max = (80, 700) if mode == "sell" else (30, 500)
        else:  # Fibras
            qty_min, qty_max = (800, 5500) if mode == "sell" else (500, 3500)
        qty = self.rng.randint(qty_min, qty_max)
        if mode == "buy":
            # Compras: precio ligeramente por debajo del listado (negociacion a favor)
            variation = self.rng.uniform(-0.06, 0.02)
        else:
            # Ventas: precio arriba del listado (margen comercial)
            variation = self.rng.uniform(0.00, 0.10)
        base = base_pp if mode == "buy" else base_sp
        price = int(base * (1 + variation))
        return qty, price

    # ------------------------------------------------------------------
    # ACTIVOS Y CIERRES
    # ------------------------------------------------------------------

    def dispose_montacargas(self) -> None:
        # Disponemos el computador en lugar del montacargas: el computador es chico
        # ($3.2M) y su depreciacion acelerada no distorsiona el P&L mensual.
        logging.info("[FASE 17] Disposicion del computador de oficina (abril)")
        asset_id = self.fixed_assets.get("OFC-001")
        if not asset_id:
            logging.warning("  No se encontro computador (OFC-001)")
            return
        body = {
            "disposal_date": iso(MONTACARGAS_DISPOSAL_DATE),
            "reason": "Equipo obsoleto - reemplazado",
        }
        try:
            self.api.post(f"/fixed-assets/{asset_id}/dispose", body, label="dispose-computador")
        except SystemExit as e:
            logging.warning(f"  Disposicion fallo: {e}")

    def distribute_profits(self) -> None:
        logging.info("[FASE 18] Reparticion de utilidades Q1 (5 abril)")
        # 80% de utilidad estimada -> repartir 60/40 entre socios
        # Para no calcular utilidad real, usamos un monto fijo realista
        total = 25000000  # 25M de utilidades Q1
        body = {
            "date": iso(PROFIT_DISTRIBUTION_DATE),
            "lines": [
                {
                    "third_party_id": self.third_parties["Ricardo Mejia (Socio 60%)"]["id"],
                    "amount": str(int(total * 0.6)),
                },
                {
                    "third_party_id": self.third_parties["Sandra Lopez (Socio 40%)"]["id"],
                    "amount": str(int(total * 0.4)),
                },
            ],
            "notes": "Reparticion de utilidades cierre Q1 2026",
        }
        try:
            self.api.post("/profit-distributions/", body, label="profit-dist-q1")
            self.stats.money_movements += 2
            logging.info(f"  Repartidos {fmt_money(total)} (60/40 entre socios)")
        except SystemExit as e:
            logging.warning(f"  Reparticion fallo: {e}")

    # ------------------------------------------------------------------
    # RESUMEN
    # ------------------------------------------------------------------

    def print_summary(self, elapsed: float) -> None:
        logging.info("=" * 70)
        logging.info(f"RESUMEN  |  {'DRY-RUN (no se escribio nada)' if self.api.dry_run else 'APPLY OK'}")
        logging.info("=" * 70)
        logging.info(f"  Tiempo: {elapsed:.1f}s")
        logging.info(f"  Org creada: {self.stats.org_created}")
        logging.info(f"  Usuarios creados: {self.stats.users_created}")
        logging.info(f"  Maestros:")
        for k, v in self.stats.masters_count.items():
            logging.info(f"    {k}: {v}")
        logging.info(f"  Operaciones:")
        logging.info(f"    Compras: {self.stats.purchases}")
        logging.info(f"    Ventas: {self.stats.sales}")
        logging.info(f"    Doble Partida: {self.stats.double_entries}")
        logging.info(f"    Movimientos tesoreria: {self.stats.money_movements}")
        logging.info(f"    Activos fijos: {self.stats.fixed_assets}")
        logging.info(f"    Transformaciones: {self.stats.transformations}")
        logging.info(f"    Ajustes inventario: {self.stats.adjustments}")
        logging.info(f"    Traslados: {self.stats.transfers}")
        logging.info("")
        logging.info("  Credenciales del demo:")
        logging.info(f"    gerente@demo.ecobalance.com / {ADMIN_PASSWORD}  (admin)")
        logging.info(f"    bascula@demo.ecobalance.com / {BASCULA_PASSWORD}  (bascula)")
        logging.info("=" * 70)


# ============================================================================
# MAIN
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Ejecutar de verdad (default: dry-run)")
    parser.add_argument("--reset", action="store_true",
                        help="Si existe la org demo, soft-deletear y recrear (BLOQUEADO en prod)")
    parser.add_argument("--target", choices=["dev", "test", "prod"], default="dev",
                        help="Entorno destino (default dev). Selecciona base URL automaticamente.")
    parser.add_argument("--base-url", default=None,
                        help="Override base URL del backend (usualmente derivado de --target)")
    parser.add_argument("--superuser-email", required=True,
                        help="Email del superuser para autenticar")
    parser.add_argument("--superuser-password", required=True,
                        help="Password del superuser")
    parser.add_argument("--yes-i-mean-prod", action="store_true",
                        help="Confirmacion explicita requerida para --target=prod --apply")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Resolver base URL: --base-url override > --target mapping > default
    base_url = args.base_url or TARGET_URLS.get(args.target, DEFAULT_BASE_URL)

    # Salvaguardas para prod
    if args.target == "prod":
        if args.reset:
            raise SystemExit(
                "ERROR: --reset esta bloqueado para --target=prod. "
                "Una soft-delete en prod requiere coordinacion manual."
            )
        if args.apply and not args.yes_i_mean_prod:
            raise SystemExit(
                "ERROR: --apply contra prod requiere agregar --yes-i-mean-prod "
                "para confirmar explicitamente. Corre primero sin --apply "
                "(dry-run) para verificar el plan."
            )
        logging.warning("=" * 70)
        logging.warning(f"⚠️  TARGET = PROD  |  base_url = {base_url}")
        logging.warning("=" * 70)

    api = APIClient(base_url, dry_run=not args.apply, target=args.target)
    api.login(args.superuser_email, args.superuser_password)

    seeder = DemoOrgSeeder(api)
    try:
        seeder.run(reset=args.reset)
    except SystemExit:
        raise
    except Exception as e:
        logging.exception(f"Error fatal: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
