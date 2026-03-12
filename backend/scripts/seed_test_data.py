"""
Script de datos de prueba para EcoBalance ERP.

Crea datos maestros para la empresa "Reciclajes El Progreso" (Colombia).
Solo inventario de: terceros, materiales, lista de precios, bodegas, cuentas,
unidades de negocio y categorias de gastos. Sin movimientos ni operaciones.

Uso:
    cd backend
    python scripts/seed_test_data.py            # Crear datos
    python scripts/seed_test_data.py --clear    # Limpiar y recrear
"""
import sys
import os
import argparse
from datetime import date
from decimal import Decimal

# Agregar backend al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.organization import Organization
from app.models.user import User, OrganizationMember
from app.models.material import Material, MaterialCategory
from app.models.third_party import ThirdParty
from app.models.warehouse import Warehouse
from app.models.money_account import MoneyAccount
from app.models.business_unit import BusinessUnit
from app.models.expense_category import ExpenseCategory
from app.models.price_list import PriceList


# ---------------------------------------------------------------------------
# Limpieza de datos
# ---------------------------------------------------------------------------

def clear_data(db, org_slug: str) -> None:
    """Elimina todos los datos de la organizacion de prueba."""
    org = db.query(Organization).filter(Organization.slug == org_slug).first()
    if not org:
        print(f"Organizacion '{org_slug}' no encontrada. Nada que limpiar.")
        return

    print(f"Eliminando datos de '{org.name}'...")
    org_id = org.id

    # Importar modelos con FK dependencies (por si quedaron datos de ejecuciones previas)
    from app.models.inventory_movement import InventoryMovement
    from app.models.inventory_adjustment import InventoryAdjustment
    from app.models.material_transformation import MaterialTransformation, MaterialTransformationLine
    from app.models.money_movement import MoneyMovement
    from app.models.sale import Sale, SaleLine, SaleCommission
    from app.models.purchase import Purchase, PurchaseLine
    from app.models.double_entry import DoubleEntry
    from app.models.scheduled_expense import ScheduledExpense, ScheduledExpenseApplication

    # Eliminar en orden de FK
    # ScheduledExpenseApplications tiene FK a money_movements → eliminar primero
    db.query(ScheduledExpenseApplication).filter(
        ScheduledExpenseApplication.scheduled_expense_id.in_(
            db.query(ScheduledExpense.id).filter(ScheduledExpense.organization_id == org_id)
        )
    ).delete(synchronize_session=False)
    db.query(ScheduledExpense).filter(ScheduledExpense.organization_id == org_id).delete()

    db.query(SaleCommission).filter(
        SaleCommission.sale_id.in_(db.query(Sale.id).filter(Sale.organization_id == org_id))
    ).delete(synchronize_session=False)
    db.query(SaleLine).filter(
        SaleLine.sale_id.in_(db.query(Sale.id).filter(Sale.organization_id == org_id))
    ).delete(synchronize_session=False)
    db.query(PurchaseLine).filter(
        PurchaseLine.purchase_id.in_(db.query(Purchase.id).filter(Purchase.organization_id == org_id))
    ).delete(synchronize_session=False)
    db.query(DoubleEntry).filter(DoubleEntry.organization_id == org_id).delete()
    db.query(Sale).filter(Sale.organization_id == org_id).delete()
    db.query(Purchase).filter(Purchase.organization_id == org_id).delete()
    db.query(MoneyMovement).filter(MoneyMovement.organization_id == org_id).delete()
    db.query(MaterialTransformationLine).filter(
        MaterialTransformationLine.transformation_id.in_(
            db.query(MaterialTransformation.id).filter(MaterialTransformation.organization_id == org_id)
        )
    ).delete(synchronize_session=False)
    db.query(MaterialTransformation).filter(MaterialTransformation.organization_id == org_id).delete()
    db.query(InventoryAdjustment).filter(InventoryAdjustment.organization_id == org_id).delete()
    db.query(InventoryMovement).filter(InventoryMovement.organization_id == org_id).delete()
    db.query(PriceList).filter(PriceList.organization_id == org_id).delete()
    from app.models.material_cost_history import MaterialCostHistory
    db.query(MaterialCostHistory).filter(MaterialCostHistory.organization_id == org_id).delete()
    db.query(Material).filter(Material.organization_id == org_id).delete()
    db.query(MaterialCategory).filter(MaterialCategory.organization_id == org_id).delete()
    db.query(ThirdParty).filter(ThirdParty.organization_id == org_id).delete()
    db.query(MoneyAccount).filter(MoneyAccount.organization_id == org_id).delete()
    db.query(Warehouse).filter(Warehouse.organization_id == org_id).delete()
    db.query(ExpenseCategory).filter(ExpenseCategory.organization_id == org_id).delete()
    db.query(BusinessUnit).filter(BusinessUnit.organization_id == org_id).delete()
    db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id).delete()
    db.query(Organization).filter(Organization.id == org_id).delete()
    db.commit()
    print("Datos eliminados.")


# ---------------------------------------------------------------------------
# Creacion de entidades base
# ---------------------------------------------------------------------------

def create_organization(db) -> Organization:
    org = Organization(
        name="Reciclajes El Progreso",
        slug="reciclajes-el-progreso",
        subscription_plan="pro",
        subscription_status="active",
        max_users=20,
    )
    db.add(org)
    db.flush()
    print(f"  Organizacion: {org.name} ({org.id})")
    return org


def create_users(db, org: Organization) -> dict:
    """Crea 5 usuarios con diferentes roles. Retorna dict email->user."""
    usuarios = [
        ("admin@reciclajes.com",    "Nixon Admin",     "admin"),
        ("nixon@reciclajes.com",    "Nixon Gerente",   "manager"),
        ("john@reciclajes.com",     "John Operario",   "user"),
        ("gustavo@reciclajes.com",  "Gustavo Contador","accountant"),
        ("ingrid@reciclajes.com",   "Ingrid Comercial","user"),
    ]
    result = {}
    for email, nombre, rol in usuarios:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            user = existing
        else:
            user = User(
                email=email,
                hashed_password=get_password_hash("Pass1234!"),
                full_name=nombre,
                is_active=True,
            )
            db.add(user)
            db.flush()

        member = OrganizationMember(
            organization_id=org.id,
            user_id=user.id,
            role=rol,
        )
        db.add(member)
        result[email] = user
        print(f"  Usuario: {email} ({rol})")
    return result


def create_business_units(db, org: Organization) -> dict:
    units = [
        ("Chatarra",  "Materiales ferrosos y metales pesados"),
        ("Fibras",    "Papel, carton y plasticos"),
        ("No Ferrosos", "Metales no ferrosos: cobre, aluminio, bronce"),
        ("Electronicos", "Residuos electronicos y motores"),
    ]
    result = {}
    for nombre, desc in units:
        bu = BusinessUnit(organization_id=org.id, name=nombre, description=desc)
        db.add(bu)
        db.flush()
        result[nombre] = bu
        print(f"  Unidad de negocio: {nombre}")
    return result


def create_material_categories(db, org: Organization) -> dict:
    cats = [
        ("Metales Ferrosos",     "Hierro, acero y sus aleaciones"),
        ("Metales No Ferrosos",  "Cobre, aluminio, bronce, plomo, zinc"),
        ("Plasticos",            "PET, HDPE, PVC y otros plasticos"),
        ("Papel y Carton",       "Papel, carton, periodico"),
        ("Electronicos",         "RAEE: motores, cables, tarjetas"),
    ]
    result = {}
    for nombre, desc in cats:
        cat = MaterialCategory(organization_id=org.id, name=nombre, description=desc)
        db.add(cat)
        db.flush()
        result[nombre] = cat
        print(f"  Categoria: {nombre}")
    return result


def create_expense_categories(db, org: Organization) -> dict:
    cats = [
        ("Flete",            "Transporte y acarreo de materiales",  True),
        ("Pesaje",           "Servicio de bascula y pesaje",         True),
        ("Arriendo",         "Arrendamiento de bodegas y predios",   False),
        ("Servicios",        "Agua, luz, gas, internet",             False),
        ("Nomina",           "Salarios y prestaciones sociales",     False),
        ("Mantenimiento",    "Mantenimiento de equipos y vehiculos", False),
        ("Papeleria",        "Elementos de oficina y papeleria",     False),
    ]
    result = {}
    for nombre, desc, directo in cats:
        cat = ExpenseCategory(
            organization_id=org.id,
            name=nombre,
            description=desc,
            is_direct_expense=directo,
        )
        db.add(cat)
        db.flush()
        result[nombre] = cat
        print(f"  Categoria gasto: {nombre} ({'directo' if directo else 'indirecto'})")
    return result


def create_materials(db, org: Organization, cats: dict, bus: dict) -> dict:
    """Crea ~20 materiales. Retorna dict codigo->material."""
    materiales = [
        # (codigo, nombre, descripcion, categoria, bu, unidad)
        ("FE001", "Chatarra de Acero",      "Acero estructural mixto",         "Metales Ferrosos",    "Chatarra",     "kg"),
        ("FE002", "Hierro Fundido",          "Hierro gris de fundicion",         "Metales Ferrosos",    "Chatarra",     "kg"),
        ("FE003", "Chatarra Liviana",        "Laminas y perfiles delgados",      "Metales Ferrosos",    "Chatarra",     "kg"),
        ("FE004", "Acero Inoxidable",        "Inox 304 y 316",                   "Metales Ferrosos",    "Chatarra",     "kg"),
        ("NF001", "Cobre Limpio #1",         "Cobre sin recubrimiento",           "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF002", "Cobre #2",                "Cobre con soldadura o recubrimiento","Metales No Ferrosos","No Ferrosos",  "kg"),
        ("NF003", "Aluminio Radiador",       "Radiadores de aluminio",           "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF004", "Aluminio Cable",          "Cable de aluminio pelado",          "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF005", "Bronce",                  "Bronce y laton mixto",              "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF006", "Plomo",                   "Plomo de baterias y tuberias",      "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF007", "Zinc",                    "Zinc galvanizado y laminas",        "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("NF008", "Lata de Aluminio",        "Latas de bebidas trituradas",       "Metales No Ferrosos", "No Ferrosos",  "kg"),
        ("PL001", "PET Transparente",        "Botellas PET sin tapa",             "Plasticos",           "Fibras",       "kg"),
        ("PL002", "HDPE Color",              "Recipientes y contenedores HDPE",   "Plasticos",           "Fibras",       "kg"),
        ("PL003", "Plastico Mixto",          "Plastico sin clasificar",           "Plasticos",           "Fibras",       "kg"),
        ("PP001", "Papel Periodico",         "Periodicos y revistas",             "Papel y Carton",      "Fibras",       "kg"),
        ("PP002", "Carton Corrugado",        "Cajas y empaques corrugados",       "Papel y Carton",      "Fibras",       "kg"),
        ("EL001", "Motor Electrico",         "Motores industriales y domesticos", "Electronicos",        "Electronicos", "kg"),
        ("EL002", "Cable Electrico",         "Cable cobre con PVC",               "Electronicos",        "Electronicos", "kg"),
        ("EL003", "Residuo Electronico",     "Tarjetas, monitores, CPU",          "Electronicos",        "Electronicos", "kg"),
    ]
    result = {}
    for codigo, nombre, desc, cat_nombre, bu_nombre, unidad in materiales:
        mat = Material(
            organization_id=org.id,
            code=codigo,
            name=nombre,
            description=desc,
            category_id=cats[cat_nombre].id,
            business_unit_id=bus[bu_nombre].id,
            default_unit=unidad,
            current_stock=Decimal("0"),
            current_stock_liquidated=Decimal("0"),
            current_stock_transit=Decimal("0"),
            current_average_cost=Decimal("0"),
            is_active=True,
        )
        db.add(mat)
        db.flush()
        result[codigo] = mat
        print(f"  Material: {codigo} - {nombre}")
    return result


def create_warehouses(db, org: Organization) -> dict:
    bodegas = [
        ("Bodega Principal",   "Bodega central en Bogota",           "Calle 80 # 45-23, Bogota"),
        ("Bodega Secundaria",  "Sucursal Medellin",                   "Carrera 45 # 12-67, Medellin"),
        ("Patio de Acopio",   "Zona exterior de almacenamiento",     "Calle 80 # 45-23, Bogota"),
    ]
    result = {}
    for nombre, desc, direccion in bodegas:
        w = Warehouse(
            organization_id=org.id,
            name=nombre,
            description=desc,
            address=direccion,
            is_active=True,
        )
        db.add(w)
        db.flush()
        result[nombre] = w
        print(f"  Bodega: {nombre}")
    return result


def create_third_parties(db, org: Organization) -> dict:
    """Crea ~15 terceros con diferentes roles."""
    terceros = [
        # (nombre, nit, email, tel, is_supplier, is_customer, is_investor, is_provision)
        ("Chatarrero Martinez",     "900123456-1", "martinez@chat.co",     "3001234567", True,  False, False, False),
        ("Recicladora del Norte",   "800234567-8", "info@rnorte.co",       "3102345678", True,  False, False, False),
        ("Metales y Materiales SAS","700345678-9", "ventas@metales.co",    "3203456789", True,  True,  False, False),
        ("Ferreterias El Constructor","600456789-0","compras@constructor.co","3104567890",True,  False, False, False),
        ("Chatarrero Rodriguez",    "500567890-1", "rodriguez@gmail.com",  "3205678901", True,  False, False, False),
        ("Acerías de Colombia SA",  "400678901-2", "compras@acerias.co",   "3016789012", False, True,  False, False),
        ("Fundiciones Bogota Ltda", "300789012-3", "fundi@bogota.co",      "3107890123", False, True,  False, False),
        ("Metales Exportados SAS",  "200890123-4", "exporta@metales.co",   "3208901234", False, True,  False, False),
        ("Industrias del Pacifico", "100901234-5", "ipacifico@ind.co",     "3109012345", False, True,  False, False),
        ("Plasticos y Fibras SA",   "150012345-6", "compras@plasticos.co", "3020123456", False, True,  False, False),
        ("Carlos Perez Inversores", "250123456-7", "cperez@inversiones.co","3151234567", False, False, True,  False),
        ("Diana Hernandez Capital", "350234567-8", "diana@capital.co",     "3162345678", False, False, True,  False),
        ("Logistica Express SAS",   "450345678-9", "logistica@express.co", "3173456789", True,  False, False, False),
        ("Reciclajes del Sur SAS",  "550456789-0", "info@rsur.co",         "3184567890", True,  True,  False, False),
        ("Valeria Torres Comercial","650567890-1", "vtorres@comercial.co", "3195678901", False, True,  False, False),
    ]
    result = {}
    for nombre, nit, email, tel, is_sup, is_cust, is_inv, is_prov in terceros:
        tp = ThirdParty(
            organization_id=org.id,
            name=nombre,
            identification_number=nit,
            email=email,
            phone=tel,
            is_supplier=is_sup,
            is_customer=is_cust,
            is_investor=is_inv,
            is_provision=is_prov,
            current_balance=Decimal("0"),
            is_active=True,
        )
        db.add(tp)
        db.flush()
        roles = []
        if is_sup: roles.append("proveedor")
        if is_cust: roles.append("cliente")
        if is_inv: roles.append("inversor")
        if is_prov: roles.append("provision")
        result[nombre] = tp
        print(f"  Tercero: {nombre} ({', '.join(roles)})")
    return result


def create_money_accounts(db, org: Organization) -> dict:
    cuentas = [
        ("Caja Principal",      "cash",    None,         None,             Decimal("0")),
        ("Bancolombia Ahorros", "bank",    "Bancolombia", "040-1234567-89", Decimal("0")),
        ("Davivienda Corriente","bank",    "Davivienda",  "001-9876543-21", Decimal("0")),
        ("Nequi Operaciones",   "digital", None,         "3001234567",     Decimal("0")),
        ("Caja Chica",          "cash",    None,         None,             Decimal("0")),
    ]
    result = {}
    for nombre, tipo, banco, numero, saldo_inicial in cuentas:
        acc = MoneyAccount(
            organization_id=org.id,
            name=nombre,
            account_type=tipo,
            bank_name=banco,
            account_number=numero,
            initial_balance=saldo_inicial,
            current_balance=saldo_inicial,
            is_active=True,
        )
        db.add(acc)
        db.flush()
        result[nombre] = acc
        print(f"  Cuenta: {nombre} ({tipo}) - Saldo inicial: ${saldo_inicial:,.0f}")
    return result


def create_price_lists(db, org: Organization, materiales: dict) -> None:
    """Crea lista de precios inicial para todos los materiales."""
    precios = {
        "FE001": (650, 800),
        "FE002": (600, 750),
        "FE003": (500, 650),
        "FE004": (1200, 1500),
        "NF001": (28000, 32000),
        "NF002": (22000, 26000),
        "NF003": (4500, 5800),
        "NF004": (3800, 4800),
        "NF005": (18000, 22000),
        "NF006": (5000, 6500),
        "NF007": (3500, 4500),
        "NF008": (4000, 5200),
        "PL001": (800, 1100),
        "PL002": (600, 900),
        "PL003": (200, 400),
        "PP001": (300, 500),
        "PP002": (400, 600),
        "EL001": (3000, 4500),
        "EL002": (8000, 10000),
        "EL003": (2000, 3500),
    }
    for codigo, (precio_compra, precio_venta) in precios.items():
        pl = PriceList(
            organization_id=org.id,
            material_id=materiales[codigo].id,
            purchase_price=Decimal(str(precio_compra)),
            sale_price=Decimal(str(precio_venta)),
            notes=f"Precio inicial {date.today().strftime('%Y-%m-%d')}",
        )
        db.add(pl)
    db.flush()
    print(f"  Lista de precios: {len(precios)} materiales")


# ---------------------------------------------------------------------------
# Punto de entrada principal
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed datos de prueba - EcoBalance ERP")
    parser.add_argument("--clear", action="store_true", help="Limpiar datos existentes antes de crear")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("\n" + "="*60)
        print("  EcoBalance ERP - Script de datos maestros")
        print("="*60)

        if args.clear:
            print("\n[LIMPIEZA]")
            clear_data(db, "reciclajes-el-progreso")

        # Verificar si ya existe
        existing = db.query(Organization).filter(Organization.slug == "reciclajes-el-progreso").first()
        if existing:
            print(f"\nOrganizacion '{existing.name}' ya existe. Use --clear para recrear.")
            return

        print("\n[1/6] Organizacion y usuarios...")
        org = create_organization(db)
        users = create_users(db, org)
        db.commit()

        print("\n[2/6] Unidades de negocio y categorias...")
        bus = create_business_units(db, org)
        cats = create_material_categories(db, org)
        expense_cats = create_expense_categories(db, org)
        db.commit()

        print("\n[3/6] Materiales...")
        mats = create_materials(db, org, cats, bus)
        db.commit()

        print("\n[4/6] Bodegas y cuentas...")
        warehouses = create_warehouses(db, org)
        accounts = create_money_accounts(db, org)
        db.commit()

        print("\n[5/6] Terceros...")
        tps = create_third_parties(db, org)
        db.commit()

        print("\n[6/6] Lista de precios...")
        create_price_lists(db, org, mats)
        db.commit()

        print("\n" + "="*60)
        print("  Datos maestros creados exitosamente!")
        print("  (Sin compras, ventas ni movimientos)")
        print("="*60)
        print(f"\nOrganizacion: Reciclajes El Progreso")
        print(f"Slug:          reciclajes-el-progreso")
        print(f"\nUsuarios (password: Pass1234!):")
        print(f"  admin@reciclajes.com    - admin")
        print(f"  nixon@reciclajes.com    - manager")
        print(f"  john@reciclajes.com     - operario")
        print(f"  gustavo@reciclajes.com  - contador")
        print(f"  ingrid@reciclajes.com   - comercial")
        print(f"\nDatos maestros:")
        print(f"  20 materiales con lista de precios")
        print(f"  15 terceros (proveedores, clientes, inversores)")
        print(f"  3 bodegas")
        print(f"  5 cuentas de dinero")
        print(f"  4 unidades de negocio")
        print(f"  7 categorias de gasto")
        print()

    except Exception as e:
        db.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
