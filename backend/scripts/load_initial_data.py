"""
Carga inicial de datos maestros desde archivo Excel.

Lee un archivo Excel con 8 hojas (en orden de dependencia) y carga los datos
via API REST autenticada. Permite re-ejecucion segura (omite duplicados).

Hojas del Excel (en orden):
  1. Categorias       → Categorías de materiales
  2. UnidadesNegocio  → Unidades de negocio
  3. Bodegas          → Bodegas / almacenes
  4. Cuentas          → Cuentas monetarias
  5. Gastos           → Categorías de gastos
  6. Terceros         → Proveedores, clientes, inversionistas, provisiones
  7. Materiales       → Materiales (requiere Categorias + UnidadesNegocio)
  8. Precios          → Lista de precios (requiere Materiales)

Uso:
    cd backend
    python scripts/load_initial_data.py \\
        --file datos_cliente.xlsx \\
        --email admin@empresa.com \\
        --password secreto \\
        --org-id 550e8400-e29b-41d4-a716-446655440000

    # Solo validar sin crear:
    python scripts/load_initial_data.py --file datos.xlsx --dry-run \\
        --email admin@test.com --password test --org-id <uuid>
"""
import argparse
import sys
from decimal import Decimal, InvalidOperation

import requests

try:
    from openpyxl import load_workbook
except ImportError:
    print("ERROR: openpyxl no esta instalado. Ejecuta: pip install openpyxl")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ACCOUNT_TYPE_MAP = {
    "efectivo": "cash",
    "banco": "bank",
    "digital": "digital",
}


def parse_bool(value) -> bool:
    """Convierte SI/NO/True/1 a bool."""
    if value is None:
        return False
    return str(value).strip().upper() in ("SI", "SÍ", "YES", "1", "TRUE")


def parse_decimal(value, default=0) -> float:
    """Convierte valor a float, manejando None y strings."""
    if value is None:
        return default
    try:
        return float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return default


def clean_str(value) -> str | None:
    """Limpia string, retorna None si vacio."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def read_sheet(wb, sheet_name: str) -> list[dict]:
    """Lee una hoja del Excel y retorna lista de dicts con headers como keys."""
    if sheet_name not in wb.sheetnames:
        return []

    ws = wb[sheet_name]
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []

    headers = [clean_str(h) or f"col_{i}" for i, h in enumerate(rows[0])]
    # Normalizar headers: minusculas, sin asteriscos (marcadores de obligatorio)
    headers = [h.lower().strip().rstrip("*").strip() for h in headers]

    result = []
    for row_idx, row in enumerate(rows[1:], start=2):
        if all(v is None for v in row):
            continue  # Fila completamente vacia
        data = {}
        for col_idx, val in enumerate(row):
            if col_idx < len(headers):
                data[headers[col_idx]] = val
        data["_row"] = row_idx
        result.append(data)
    return result


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class APIClient:
    def __init__(self, base_url: str, org_id: str):
        self.base_url = base_url.rstrip("/")
        self.org_id = org_id
        self.token = None
        self.session = requests.Session()

    def login(self, email: str, password: str) -> bool:
        """Autenticar via JWT."""
        resp = self.session.post(
            f"{self.base_url}/api/v1/auth/login/json",
            json={"email": email, "password": password},
        )
        if resp.status_code == 200:
            self.token = resp.json()["access_token"]
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
                "X-Organization-ID": self.org_id,
            })
            return True
        print(f"  ERROR login: {resp.status_code} - {resp.text}")
        return False

    def post(self, path: str, data: dict) -> tuple[int, dict | str]:
        """POST a la API. Retorna (status_code, response_json o error_text)."""
        resp = self.session.post(f"{self.base_url}{path}", json=data)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text

    def get(self, path: str, params: dict | None = None) -> tuple[int, dict | str]:
        """GET a la API."""
        resp = self.session.get(f"{self.base_url}{path}", params=params)
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, resp.text


# ---------------------------------------------------------------------------
# Loaders por entidad
# ---------------------------------------------------------------------------

class Stats:
    """Contadores de resultado por hoja."""
    def __init__(self):
        self.created = 0
        self.skipped = 0
        self.errors = 0
        self.error_details: list[str] = []

    def report(self, sheet: str) -> str:
        parts = []
        if self.created:
            parts.append(f"{self.created} creados")
        if self.skipped:
            parts.append(f"{self.skipped} omitidos")
        if self.errors:
            parts.append(f"{self.errors} errores")
        return f"  {sheet}: {', '.join(parts) if parts else 'vacio'}"


def load_categorias(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga categorías de materiales. Retorna stats y mapping nombre→id."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {"name": nombre}
        desc = clean_str(row.get("descripcion"))
        if desc:
            payload["description"] = desc

        status, resp = api.post("/api/v1/materials/categories", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
            # Intentar obtener el ID existente
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    # Si hubo omitidos, cargar IDs existentes
    if stats.skipped > 0 and not dry_run:
        _fill_missing_categories(api, rows, mapping)

    return stats, mapping


def _fill_missing_categories(api: APIClient, rows: list[dict], mapping: dict):
    """Carga IDs de categorías que ya existian."""
    status, resp = api.get("/api/v1/materials/categories", {"limit": 500})
    if status == 200:
        existing = {item["name"]: item["id"] for item in resp.get("items", [])}
        for row in rows:
            nombre = clean_str(row.get("nombre"))
            if nombre and nombre not in mapping and nombre in existing:
                mapping[nombre] = existing[nombre]


def load_unidades_negocio(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga unidades de negocio."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {"name": nombre}
        desc = clean_str(row.get("descripcion"))
        if desc:
            payload["description"] = desc

        status, resp = api.post("/api/v1/business-units/", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/business-units/", {"limit": 500})
        if st == 200:
            existing = {item["name"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                nombre = clean_str(row.get("nombre"))
                if nombre and nombre not in mapping and nombre in existing:
                    mapping[nombre] = existing[nombre]

    return stats, mapping


def load_bodegas(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga bodegas."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {"name": nombre}
        desc = clean_str(row.get("descripcion"))
        if desc:
            payload["description"] = desc
        addr = clean_str(row.get("direccion"))
        if addr:
            payload["address"] = addr

        status, resp = api.post("/api/v1/warehouses/", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/warehouses/", {"limit": 500})
        if st == 200:
            existing = {item["name"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                nombre = clean_str(row.get("nombre"))
                if nombre and nombre not in mapping and nombre in existing:
                    mapping[nombre] = existing[nombre]

    return stats, mapping


def load_cuentas(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga cuentas monetarias."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        tipo_raw = clean_str(row.get("tipo"))

        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue
        if not tipo_raw:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): tipo es obligatorio")
            continue

        tipo = ACCOUNT_TYPE_MAP.get(tipo_raw.lower())
        if not tipo:
            stats.errors += 1
            stats.error_details.append(
                f"  Fila {row['_row']} ({nombre}): tipo '{tipo_raw}' invalido. "
                f"Usar: {', '.join(ACCOUNT_TYPE_MAP.keys())}"
            )
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {
            "name": nombre,
            "account_type": tipo,
            "initial_balance": parse_decimal(row.get("saldo_inicial"), 0),
        }
        num = clean_str(row.get("numero_cuenta"))
        if num:
            payload["account_number"] = num
        banco = clean_str(row.get("banco"))
        if banco:
            payload["bank_name"] = banco

        status, resp = api.post("/api/v1/money-accounts/", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/money-accounts/", {"limit": 500})
        if st == 200:
            existing = {item["name"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                nombre = clean_str(row.get("nombre"))
                if nombre and nombre not in mapping and nombre in existing:
                    mapping[nombre] = existing[nombre]

    return stats, mapping


def load_gastos(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga categorías de gastos."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {
            "name": nombre,
            "is_direct_expense": parse_bool(row.get("es_directo")),
        }
        desc = clean_str(row.get("descripcion"))
        if desc:
            payload["description"] = desc

        status, resp = api.post("/api/v1/expense-categories/", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/expense-categories/", {"limit": 500})
        if st == 200:
            existing = {item["name"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                nombre = clean_str(row.get("nombre"))
                if nombre and nombre not in mapping and nombre in existing:
                    mapping[nombre] = existing[nombre]

    return stats, mapping


def load_terceros(api: APIClient, rows: list[dict], dry_run: bool) -> tuple[Stats, dict]:
    """Carga terceros (proveedores, clientes, etc.)."""
    stats = Stats()
    mapping = {}

    for row in rows:
        nombre = clean_str(row.get("nombre"))
        if not nombre:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: nombre es obligatorio")
            continue

        # Al menos un rol debe estar marcado
        es_proveedor = parse_bool(row.get("es_proveedor"))
        es_cliente = parse_bool(row.get("es_cliente"))
        es_inversionista = parse_bool(row.get("es_inversionista"))
        es_provision = parse_bool(row.get("es_provision"))

        if not any([es_proveedor, es_cliente, es_inversionista, es_provision]):
            stats.errors += 1
            stats.error_details.append(
                f"  Fila {row['_row']} ({nombre}): debe tener al menos un rol "
                "(es_proveedor, es_cliente, es_inversionista, es_provision)"
            )
            continue

        if dry_run:
            stats.created += 1
            mapping[nombre] = f"dry-run-{nombre}"
            continue

        payload = {
            "name": nombre,
            "is_supplier": es_proveedor,
            "is_customer": es_cliente,
            "is_investor": es_inversionista,
            "is_provision": es_provision,
            "initial_balance": parse_decimal(row.get("saldo_inicial"), 0),
        }

        ident = clean_str(row.get("identificacion"))
        if ident:
            payload["identification_number"] = ident
        email = clean_str(row.get("email"))
        if email:
            payload["email"] = email
        tel = clean_str(row.get("telefono"))
        if tel:
            payload["phone"] = str(tel)
        addr = clean_str(row.get("direccion"))
        if addr:
            payload["address"] = addr

        status, resp = api.post("/api/v1/third-parties/", payload)
        if status in (200, 201):
            mapping[nombre] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and "ya existe" in str(resp).lower()):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({nombre}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/third-parties/", {"limit": 1000})
        if st == 200:
            existing = {item["name"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                nombre = clean_str(row.get("nombre"))
                if nombre and nombre not in mapping and nombre in existing:
                    mapping[nombre] = existing[nombre]

    return stats, mapping


def load_materiales(
    api: APIClient,
    rows: list[dict],
    cat_map: dict,
    un_map: dict,
    dry_run: bool,
) -> tuple[Stats, dict]:
    """Carga materiales. Requiere mappings de categorías y unidades de negocio."""
    stats = Stats()
    mapping = {}  # codigo → id

    for row in rows:
        codigo = clean_str(row.get("codigo"))
        nombre = clean_str(row.get("nombre"))
        categoria = clean_str(row.get("categoria"))
        unidad_negocio = clean_str(row.get("unidad_negocio"))

        errors = []
        if not codigo:
            errors.append("codigo es obligatorio")
        if not nombre:
            errors.append("nombre es obligatorio")
        if not categoria:
            errors.append("categoria es obligatorio")
        elif categoria not in cat_map:
            errors.append(f"categoria '{categoria}' no encontrada en hoja Categorias")
        if not unidad_negocio:
            errors.append("unidad_negocio es obligatorio")
        elif unidad_negocio not in un_map:
            errors.append(f"unidad_negocio '{unidad_negocio}' no encontrada en hoja UnidadesNegocio")

        if errors:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({codigo or '?'}): {'; '.join(errors)}")
            continue

        if dry_run:
            stats.created += 1
            mapping[codigo] = f"dry-run-{codigo}"
            continue

        payload = {
            "code": codigo,
            "name": nombre,
            "category_id": cat_map[categoria],
            "business_unit_id": un_map[unidad_negocio],
            "default_unit": clean_str(row.get("unidad")) or "kg",
        }
        desc = clean_str(row.get("descripcion"))
        if desc:
            payload["description"] = desc

        status, resp = api.post("/api/v1/materials/", payload)
        if status in (200, 201):
            mapping[codigo] = resp["id"]
            stats.created += 1
        elif status == 409 or (status == 400 and ("ya existe" in str(resp).lower() or "duplicate" in str(resp).lower())):
            stats.skipped += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({codigo}): {status} - {resp}")

    if stats.skipped > 0 and not dry_run:
        st, resp = api.get("/api/v1/materials/", {"limit": 1000})
        if st == 200:
            existing = {item["code"]: item["id"] for item in resp.get("items", [])}
            for row in rows:
                codigo = clean_str(row.get("codigo"))
                if codigo and codigo not in mapping and codigo in existing:
                    mapping[codigo] = existing[codigo]

    return stats, mapping


def load_precios(
    api: APIClient,
    rows: list[dict],
    mat_map: dict,
    dry_run: bool,
) -> tuple[Stats, dict]:
    """Carga lista de precios. Requiere mapping de materiales (codigo→id)."""
    stats = Stats()

    for row in rows:
        codigo = clean_str(row.get("material_codigo"))
        if not codigo:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']}: material_codigo es obligatorio")
            continue

        if codigo not in mat_map:
            stats.errors += 1
            stats.error_details.append(
                f"  Fila {row['_row']} ({codigo}): material no encontrado en hoja Materiales"
            )
            continue

        if dry_run:
            stats.created += 1
            continue

        payload = {
            "material_id": mat_map[codigo],
            "purchase_price": parse_decimal(row.get("precio_compra"), 0),
            "sale_price": parse_decimal(row.get("precio_venta"), 0),
        }
        notas = clean_str(row.get("notas"))
        if notas:
            payload["notes"] = notas

        status, resp = api.post("/api/v1/price-lists/", payload)
        if status in (200, 201):
            stats.created += 1
        else:
            stats.errors += 1
            stats.error_details.append(f"  Fila {row['_row']} ({codigo}): {status} - {resp}")

    return stats, {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Carga inicial de datos maestros desde Excel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplo:
    python scripts/load_initial_data.py \\
        --file datos_cliente.xlsx \\
        --email admin@empresa.com \\
        --password secreto \\
        --org-id 550e8400-e29b-41d4-a716-446655440000
        """,
    )
    parser.add_argument("--file", required=True, help="Ruta al archivo Excel")
    parser.add_argument("--api-url", default="http://localhost:8000", help="URL base de la API")
    parser.add_argument("--email", required=True, help="Email del usuario administrador")
    parser.add_argument("--password", required=True, help="Contraseña del usuario")
    parser.add_argument("--org-id", required=True, help="UUID de la organización")
    parser.add_argument("--dry-run", action="store_true", help="Solo validar, no crear datos")
    args = parser.parse_args()

    # Cargar Excel
    print(f"\n{'=' * 60}")
    print(f"  CARGA INICIAL DE DATOS MAESTROS")
    print(f"  {'(MODO DRY-RUN - solo validación)' if args.dry_run else ''}")
    print(f"{'=' * 60}")
    print(f"\nArchivo: {args.file}")
    print(f"API:     {args.api_url}")
    print(f"Org:     {args.org_id}\n")

    try:
        wb = load_workbook(args.file, read_only=True, data_only=True)
    except FileNotFoundError:
        print(f"ERROR: Archivo '{args.file}' no encontrado")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: No se pudo leer el archivo Excel: {e}")
        sys.exit(1)

    print(f"Hojas encontradas: {', '.join(wb.sheetnames)}\n")

    # Login
    api = APIClient(args.api_url, args.org_id)
    if not args.dry_run:
        print("Autenticando...")
        if not api.login(args.email, args.password):
            print("ERROR: No se pudo autenticar. Verificar credenciales.")
            sys.exit(1)
        print("  OK\n")
    else:
        print("(Dry-run: saltando autenticación)\n")

    # Cargar en orden de dependencia
    all_stats = {}
    all_errors = []

    # 1. Categorías
    print("[1/8] Categorias...")
    rows = read_sheet(wb, "Categorias")
    stats, cat_map = load_categorias(api, rows, args.dry_run)
    all_stats["Categorias"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Categorias"))

    # 2. Unidades de Negocio
    print("[2/8] UnidadesNegocio...")
    rows = read_sheet(wb, "UnidadesNegocio")
    stats, un_map = load_unidades_negocio(api, rows, args.dry_run)
    all_stats["UnidadesNegocio"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("UnidadesNegocio"))

    # 3. Bodegas
    print("[3/8] Bodegas...")
    rows = read_sheet(wb, "Bodegas")
    stats, _ = load_bodegas(api, rows, args.dry_run)
    all_stats["Bodegas"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Bodegas"))

    # 4. Cuentas
    print("[4/8] Cuentas...")
    rows = read_sheet(wb, "Cuentas")
    stats, _ = load_cuentas(api, rows, args.dry_run)
    all_stats["Cuentas"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Cuentas"))

    # 5. Gastos
    print("[5/8] Gastos...")
    rows = read_sheet(wb, "Gastos")
    stats, _ = load_gastos(api, rows, args.dry_run)
    all_stats["Gastos"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Gastos"))

    # 6. Terceros
    print("[6/8] Terceros...")
    rows = read_sheet(wb, "Terceros")
    stats, _ = load_terceros(api, rows, args.dry_run)
    all_stats["Terceros"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Terceros"))

    # 7. Materiales (depende de Categorias + UnidadesNegocio)
    print("[7/8] Materiales...")
    rows = read_sheet(wb, "Materiales")
    stats, mat_map = load_materiales(api, rows, cat_map, un_map, args.dry_run)
    all_stats["Materiales"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Materiales"))

    # 8. Precios (depende de Materiales)
    print("[8/8] Precios...")
    rows = read_sheet(wb, "Precios")
    stats, _ = load_precios(api, rows, mat_map, args.dry_run)
    all_stats["Precios"] = stats
    all_errors.extend(stats.error_details)
    print(stats.report("Precios"))

    wb.close()

    # Resumen
    total_created = sum(s.created for s in all_stats.values())
    total_skipped = sum(s.skipped for s in all_stats.values())
    total_errors = sum(s.errors for s in all_stats.values())

    print(f"\n{'=' * 60}")
    print(f"  RESUMEN")
    print(f"{'=' * 60}")
    print(f"  Creados:  {total_created}")
    print(f"  Omitidos: {total_skipped} (ya existian)")
    print(f"  Errores:  {total_errors}")

    if all_errors:
        print(f"\n  DETALLE DE ERRORES:")
        for err in all_errors:
            print(f"    {err}")

    print()

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
