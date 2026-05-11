"""
Genera el template Excel para migrate_metarecycling.py.

8 hojas con cabeceras + 1-2 filas de ejemplo. Las filas de ejemplo van con
fondo amarillo claro para que el cliente / la AI de Lovable las borre.

Uso (desde backend/):
    ./venv/bin/python scripts/generate_migration_template.py

Output: ../data/migration_metarecycling_template.xlsx
"""
import sys
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
except ImportError:
    print("ERROR: openpyxl no esta instalado.")
    sys.exit(1)


HEADER_FILL = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
HEADER_FONT = Font(color="FFFFFF", bold=True)
EXAMPLE_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
NOTES_FILL = PatternFill(start_color="E7E6E6", end_color="E7E6E6", fill_type="solid")


SHEETS = [
    # (sheet_name, headers, example_rows, notes)
    (
        "CategoriaMateriales",
        ["nombre", "descripcion"],
        [
            ["CHATARRA", "Hierro / chatarra ferrosa"],
            ["ALUMINIO", "Aluminio en todas sus formas"],
        ],
        "Una fila por categoria. nombre es obligatorio.",
    ),
    (
        "CategoriaGastos",
        ["nombre", "padre", "es_directo"],
        [
            ["Operativos", "", "SI"],
            ["Flete", "Operativos", ""],
            ["Administrativos", "", "NO"],
            ["Salarios", "Administrativos", ""],
            ["Depreciacion Activos Fijos", "", "NO"],
        ],
        "padre vacio = categoria raiz. es_directo (SI/NO) solo en raiz; las hijas heredan. Max 2 niveles.",
    ),
    (
        "CategoriaTerceros",
        ["nombre", "tipo_comportamiento", "padre"],
        [
            ["Proveedor Local", "proveedor_material", ""],
        ],
        "OPCIONAL: las 7 default ya vienen con la org. Solo agregar extras aqui. "
        "tipo_comportamiento: proveedor_material | proveedor_servicios | cliente | inversionista | generico | provision | pasivo.",
    ),
    (
        "MapeoUN",
        ["categoria_material", "unidad_negocio_default", "notas"],
        [
            ["CHATARRA", "Chatarra", "Toda chatarra ferrosa va a UN Chatarra"],
            ["ALUMINIO", "Metales", "Aluminio salvo Perfil/Clausen (override por material)"],
        ],
        "Asigna una UN default a cada categoria de material. Los materiales que necesiten "
        "otra UN se especifican explicitamente en la hoja Materiales (columna unidad_negocio).",
    ),
    (
        "Materiales",
        ["codigo", "nombre", "categoria", "unidad_negocio", "unidad", "descripcion"],
        [
            ["CHA-001", "Chatarra Pesada", "CHATARRA", "", "kg", ""],
            ["ALU-001", "Aluminio Perfil", "ALUMINIO", "Perfil", "kg", "Override de la categoria"],
        ],
        "unidad_negocio vacio = usa default de MapeoUN. Llenar solo para override explicito. "
        "unidad: por defecto 'kg'.",
    ),
    (
        "Terceros",
        [
            "nombre",
            "identificacion",
            "email",
            "telefono",
            "direccion",
            "categorias",
            "saldo_inicial",
        ],
        [
            ["Proveedor Ejemplo SAS", "900123456", "info@ejemplo.com", "3001234567", "Cra 1 #2-3", "Proveedor Material", -150000],
            ["Cliente Ejemplo Ltda", "800987654", "", "3009876543", "", "Cliente", 450000],
            ["Eduardo Chain", "", "", "", "", "Inversionista", -262534500],
            ["Credito Bancolombia", "", "", "", "", "Pasivo", -84384600],
        ],
        "categorias: CSV de nombres (ej: 'Proveedor Material,Cliente' para alguien que es ambos). "
        "saldo_inicial: positivo = nos debe, negativo = le debemos. Categorias internas: Pasivo y Provision son aceptadas.",
    ),
    (
        "Cuentas",
        ["nombre", "tipo", "saldo_inicial", "numero_cuenta", "banco"],
        [
            ["Caja Principal", "cash", 1500000, "", ""],
            ["Bancolombia Corriente", "bank", 8000000, "12345678", "Bancolombia"],
            ["Nequi Salomon", "digital", 250000, "", ""],
        ],
        "tipo: cash | bank | digital. saldo_inicial: balance a fecha de corte. "
        "NO incluir 'Utilidades [Socio]' (se funden en initial_balance del inversionista). "
        "NO incluir 'Credito Bancolombia' (se carga como Tercero tipo Pasivo).",
    ),
    (
        "Inventario",
        ["material_codigo", "bodega", "cantidad", "costo_unitario", "fecha"],
        [
            ["CHA-001", "Principal", 1200.5, 1850, ""],
            ["ALU-001", "Principal", 350, 7200, ""],
        ],
        "Solo materiales con stock > 0. bodega: por defecto 'Principal'. "
        "costo_unitario: costo promedio actual de Lovable (genera MaterialCostHistory). "
        "fecha vacia = hoy.",
    ),
    (
        "ActivosFijos",
        [
            "nombre",
            "codigo_activo",
            "fecha_compra",
            "valor_compra",
            "valor_residual",
            "vida_util_meses",
            "fecha_inicio_depreciacion",
            "depreciacion_acumulada",
            "categoria_gasto",
            "proveedor",
            "cuenta_pago",
            "unidad_negocio",
            "notas",
        ],
        [
            ["Camion FORD CARGO", "VEH-001", "2023-01-15", 85000000, 0, 60, "2023-02-01", 32000000, "Depreciacion Activos Fijos", "", "", "", "Pagado integro en Lovable"],
            ["Maquina Caiman", "MAQ-001", "2024-08-10", 120000000, 0, 120, "2024-09-01", 9000000, "Depreciacion Activos Fijos", "Proveedor Ejemplo SAS", "", "Metales", "Saldo pendiente con proveedor (proveedor debe existir en hoja Terceros)"],
        ],
        "vida_util_meses: vehiculos 60, maquinaria 120, herramientas 36. "
        "Si proveedor y cuenta_pago vacios → historical_load (no genera MoneyMovement, no mueve balances). "
        "Si proveedor: crea asset_purchase (mueve balance proveedor, debe existir en hoja Terceros). "
        "Si cuenta_pago: crea asset_payment (mueve cuenta). "
        "categoria_gasto debe existir en hoja CategoriaGastos.",
    ),
]


def build_workbook() -> Workbook:
    wb = Workbook()
    # Eliminar sheet default
    default_sheet = wb.active
    wb.remove(default_sheet)

    for sheet_name, headers, example_rows, notes in SHEETS:
        ws = wb.create_sheet(title=sheet_name)
        # Fila 1: notas
        ws.cell(row=1, column=1, value=f"NOTAS: {notes}").fill = NOTES_FILL
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        notes_cell = ws.cell(row=1, column=1)
        notes_cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[1].height = 45
        # Fila 2: cabecera
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=2, column=col_idx, value=header)
            cell.fill = HEADER_FILL
            cell.font = HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        # Filas 3+: ejemplos
        for row_idx, example in enumerate(example_rows, start=3):
            for col_idx, value in enumerate(example, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.fill = EXAMPLE_FILL
        # Ajustar ancho de columnas
        for col_idx, header in enumerate(headers, start=1):
            col_letter = ws.cell(row=2, column=col_idx).column_letter
            ws.column_dimensions[col_letter].width = max(18, len(header) + 4)
        ws.freeze_panes = "A3"
    return wb


def main():
    out_path = Path(__file__).resolve().parent.parent.parent / "data" / "migration_metarecycling_template.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb = build_workbook()
    wb.save(out_path)
    print(f"Template generado: {out_path}")
    print(f"  Hojas: {', '.join(name for name, *_ in SHEETS)}")


if __name__ == "__main__":
    main()
