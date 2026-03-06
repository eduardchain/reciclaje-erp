"""
Script de datos de prueba para EcoBalance ERP.

Crea datos realistas para la empresa "Reciclajes El Progreso" (Colombia).

Uso:
    cd backend
    python scripts/seed_test_data.py            # Crear datos
    python scripts/seed_test_data.py --clear    # Limpiar y recrear
"""
import sys
import os
import argparse
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

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
from app.schemas.purchase import PurchaseCreate, PurchaseLineCreate
from app.schemas.sale import SaleCreate, SaleLineCreate, SaleCommissionCreate
from app.schemas.double_entry import DoubleEntryCreate
from app.schemas.money_movement import (
    SupplierPaymentCreate, CustomerCollectionCreate, ExpenseCreate,
    ServiceIncomeCreate, TransferCreate, CapitalInjectionCreate,
)
from app.schemas.inventory_adjustment import IncreaseCreate, DecreaseCreate, RecountCreate
from app.schemas.material_transformation import MaterialTransformationCreate, TransformationLineCreate
from app.services.purchase import purchase as purchase_service
from app.services.sale import crud_sale as sale_service
from app.services.double_entry import crud_double_entry
from app.services.money_movement import money_movement as money_movement_service
from app.services.inventory_adjustment import inventory_adjustment as adjustment_service
from app.services.material_transformation import material_transformation as transformation_service


# ---------------------------------------------------------------------------
# Utilitario de fechas
# ---------------------------------------------------------------------------

def dias_atras(n: int) -> datetime:
    """Retorna datetime de hace N dias."""
    return datetime.now() - timedelta(days=n)


def fecha(n: int) -> date:
    """Retorna date de hace N dias."""
    return date.today() - timedelta(days=n)


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

    # Importar modelos con FK dependencies
    from app.models.inventory_movement import InventoryMovement
    from app.models.inventory_adjustment import InventoryAdjustment
    from app.models.material_transformation import MaterialTransformation, MaterialTransformationLine
    from app.models.money_movement import MoneyMovement
    from app.models.sale import Sale, SaleLine, SaleCommission
    from app.models.purchase import Purchase, PurchaseLine
    from app.models.double_entry import DoubleEntry

    # Eliminar en orden de FK
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
# Creacion de entidades base (sin servicios, directo SQLAlchemy)
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
        # Verificar si ya existe
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
        ("Logistica Express SAS",   "450345678-9", "logistica@express.co", "3173456789", True,  False, False, True),
        ("Agente Lopez Comercial",  "550456789-0", "lopez@agente.co",      "3184567890", False, False, False, True),
        ("Valeria Torres Agente",   "650567890-1", "vtorres@agente.co",    "3195678901", False, False, False, True),
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
        ("Caja Principal",      "cash",    None,         None,             Decimal("30000000")),
        ("Bancolombia Ahorros", "bank",    "Bancolombia", "040-1234567-89", Decimal("100000000")),
        ("Davivienda Corriente","bank",    "Davivienda",  "001-9876543-21", Decimal("50000000")),
        ("Nequi Operaciones",   "digital", None,         "3001234567",     Decimal("5000000")),
        ("Caja Chica",          "cash",    None,         None,             Decimal("3000000")),
    ]
    result = {}
    for nombre, tipo, banco, numero, saldo_inicial in cuentas:
        acc = MoneyAccount(
            organization_id=org.id,
            name=nombre,
            account_type=tipo,
            bank_name=banco,
            account_number=numero,
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
# Operaciones de negocio (usando servicios)
# ---------------------------------------------------------------------------

def create_purchases(db, org, admin_user, mats, warehouses, accounts, suppliers) -> list:
    """Crea 12 compras (todas auto_liquidated)."""
    bodega_principal = warehouses["Bodega Principal"]
    bodega_secundaria = warehouses["Bodega Secundaria"]
    patio = warehouses["Patio de Acopio"]
    caja = accounts["Caja Principal"]
    bancolombia = accounts["Bancolombia Ahorros"]
    davivienda = accounts["Davivienda Corriente"]

    compras_data = [
        # (proveedor, fecha_dias_atras, lineas[(mat, wh, qty, precio)], cuenta_pago)
        (
            "Chatarrero Martinez", 60,
            [("FE001", bodega_principal, 5000, 640), ("FE002", bodega_principal, 2000, 590)],
            caja
        ),
        (
            "Recicladora del Norte", 55,
            [("NF001", bodega_principal, 300, 27500), ("NF002", bodega_principal, 500, 21000)],
            bancolombia
        ),
        (
            "Metales y Materiales SAS", 50,
            [("FE001", patio, 8000, 650), ("FE003", patio, 3000, 490)],
            bancolombia
        ),
        (
            "Ferreterias El Constructor", 45,
            [("NF003", bodega_principal, 800, 4400), ("NF004", bodega_principal, 400, 3700)],
            caja
        ),
        (
            "Chatarrero Rodriguez", 40,
            [("FE004", bodega_principal, 600, 1180), ("NF005", bodega_principal, 200, 17500)],
            davivienda
        ),
        (
            "Chatarrero Martinez", 35,
            [("NF001", bodega_secundaria, 200, 28000), ("NF008", bodega_secundaria, 1500, 3900)],
            bancolombia
        ),
        (
            "Recicladora del Norte", 30,
            [("PL001", patio, 2000, 790), ("PL002", patio, 1500, 580), ("PP002", patio, 3000, 390)],
            caja
        ),
        (
            "Metales y Materiales SAS", 25,
            [("EL001", bodega_principal, 500, 2950), ("EL002", bodega_principal, 300, 7900)],
            bancolombia
        ),
        (
            "Chatarrero Rodriguez", 20,
            [("FE001", patio, 10000, 655), ("FE002", patio, 4000, 595)],
            davivienda
        ),
        (
            "Ferreterias El Constructor", 15,
            [("NF006", bodega_principal, 400, 4900), ("NF007", bodega_principal, 600, 3400)],
            caja
        ),
        (
            "Chatarrero Martinez", 10,
            [("NF002", bodega_principal, 700, 21500), ("NF003", bodega_principal, 600, 4500)],
            bancolombia
        ),
        (
            "Recicladora del Norte", 5,
            [("PP001", patio, 5000, 295), ("PL003", patio, 2000, 195)],
            caja
        ),
    ]

    compras_creadas = []
    for proveedor_nombre, dias, lineas, cuenta_pago in compras_data:
        proveedor = suppliers[proveedor_nombre]
        fecha_compra = dias_atras(dias)

        purchase_lines = [
            PurchaseLineCreate(
                material_id=mats[codigo].id,
                warehouse_id=bodega.id,
                quantity=Decimal(str(qty)),
                unit_price=Decimal(str(precio)),
            )
            for codigo, bodega, qty, precio in lineas
        ]

        create_data = PurchaseCreate(
            supplier_id=proveedor.id,
            date=fecha_compra,
            lines=purchase_lines,
            auto_liquidate=True,
            payment_account_id=cuenta_pago.id,
            notes=f"Compra de prueba - {proveedor_nombre}",
        )

        compra = purchase_service.create(
            db=db,
            obj_in=create_data,
            organization_id=org.id,
            user_id=admin_user.id,
        )
        compras_creadas.append(compra)
        total = sum(qty * precio for _, _, qty, precio in lineas)
        print(f"  Compra #{compra.purchase_number}: {proveedor_nombre} - ${total:,.0f}")

    return compras_creadas


def create_sales(db, org, admin_user, mats, warehouses, accounts, customers, commission_agents) -> list:
    """Crea 8 ventas (todas auto_liquidated, algunas con comisiones)."""
    bodega_principal = warehouses["Bodega Principal"]
    bodega_secundaria = warehouses["Bodega Secundaria"]
    patio = warehouses["Patio de Acopio"]
    bancolombia = accounts["Bancolombia Ahorros"]
    davivienda = accounts["Davivienda Corriente"]

    agente_lopez = commission_agents["Agente Lopez Comercial"]
    agente_valeria = commission_agents["Valeria Torres Agente"]

    ventas_data = [
        # (cliente, bodega, fecha_dias_atras, lineas[(mat, qty, precio)], comisiones, cuenta)
        (
            "Acerías de Colombia SA", bodega_principal, 55,
            [("FE001", 4000, 795), ("FE002", 1500, 745)],
            [],
            bancolombia
        ),
        (
            "Fundiciones Bogota Ltda", bodega_principal, 48,
            [("NF001", 250, 31500), ("NF002", 400, 25500)],
            [(agente_lopez.id, "Comision venta cobre", "percentage", Decimal("2.5"))],
            bancolombia
        ),
        (
            "Metales Exportados SAS", patio, 42,
            [("FE001", 6000, 800), ("FE003", 2000, 645)],
            [],
            davivienda
        ),
        (
            "Industrias del Pacifico", bodega_principal, 35,
            [("NF003", 700, 5700), ("NF004", 350, 4750)],
            [(agente_valeria.id, "Comision venta aluminio", "percentage", Decimal("3.0"))],
            bancolombia
        ),
        (
            "Acerías de Colombia SA", patio, 28,
            [("FE001", 8000, 798), ("FE004", 500, 1480)],
            [],
            davivienda
        ),
        (
            "Plasticos y Fibras SA", patio, 21,
            [("PL001", 1800, 1090), ("PL002", 1200, 880), ("PP002", 2500, 595)],
            [],
            bancolombia
        ),
        (
            "Fundiciones Bogota Ltda", bodega_secundaria, 14,
            [("NF001", 180, 31800), ("NF005", 150, 21500)],
            [(agente_lopez.id, "Comision especial", "fixed", Decimal("250000"))],
            bancolombia
        ),
        (
            "Metales Exportados SAS", bodega_principal, 7,
            [("EL001", 450, 4400), ("EL002", 250, 9800)],
            [(agente_valeria.id, "Comision electronico", "percentage", Decimal("2.0"))],
            davivienda
        ),
    ]

    ventas_creadas = []
    for cliente_nombre, bodega, dias, lineas, comisiones, cuenta in ventas_data:
        cliente = customers[cliente_nombre]
        fecha_venta = dias_atras(dias)

        sale_lines = [
            SaleLineCreate(
                material_id=mats[codigo].id,
                quantity=Decimal(str(qty)),
                unit_price=Decimal(str(precio)),
            )
            for codigo, qty, precio in lineas
        ]

        sale_commissions = [
            SaleCommissionCreate(
                third_party_id=tp_id,
                concept=concepto,
                commission_type=tipo,
                commission_value=valor,
            )
            for tp_id, concepto, tipo, valor in comisiones
        ]

        create_data = SaleCreate(
            customer_id=cliente.id,
            warehouse_id=bodega.id,
            date=fecha_venta,
            lines=sale_lines,
            commissions=sale_commissions,
            auto_liquidate=True,
            payment_account_id=cuenta.id,
            notes=f"Venta de prueba - {cliente_nombre}",
        )

        venta = sale_service.create(
            db=db,
            obj_in=create_data,
            organization_id=org.id,
            user_id=admin_user.id,
        )
        ventas_creadas.append(venta)
        total = sum(qty * precio for _, qty, precio in lineas)
        print(f"  Venta #{venta.sale_number}: {cliente_nombre} - ${total:,.0f} ({'con comision' if comisiones else 'sin comision'})")

    return ventas_creadas


def create_double_entries(db, org, mats, suppliers, customers) -> list:
    """Crea 3 operaciones de doble partida (pasa mano)."""
    chatarrero = suppliers["Chatarrero Martinez"]
    recicladora = suppliers["Recicladora del Norte"]
    metales_mas = suppliers["Metales y Materiales SAS"]
    acerias = customers["Acerías de Colombia SA"]
    fundiciones = customers["Fundiciones Bogota Ltda"]

    des_data = [
        # (material, proveedor, cliente, qty, precio_compra, precio_venta, dias)
        ("NF001", chatarrero, acerias,     500, 27000, 31000, 45),
        ("FE001", recicladora, fundiciones, 10000, 640, 790, 30),
        ("NF002", metales_mas, acerias,    800, 20500, 25000, 10),
    ]

    des_creadas = []
    for mat_codigo, proveedor, cliente, qty, p_compra, p_venta, dias in des_data:
        create_data = DoubleEntryCreate(
            material_id=mats[mat_codigo].id,
            supplier_id=proveedor.id,
            customer_id=cliente.id,
            quantity=Decimal(str(qty)),
            purchase_unit_price=Decimal(str(p_compra)),
            sale_unit_price=Decimal(str(p_venta)),
            date=fecha(dias),
            notes=f"Pasa mano {mats[mat_codigo].name}",
        )

        de = crud_double_entry.create(
            db=db,
            obj_in=create_data,
            organization_id=org.id,
        )
        des_creadas.append(de)
        profit = qty * (p_venta - p_compra)
        print(f"  Doble entrada #{de.double_entry_number}: {mats[mat_codigo].name} {qty}kg - Profit: ${profit:,.0f}")

    return des_creadas


def create_money_movements(db, org, admin_user, accounts, suppliers, customers, investors, expense_cats) -> None:
    """Crea 12 movimientos de tesoreria de distintos tipos."""
    caja = accounts["Caja Principal"]
    bancolombia = accounts["Bancolombia Ahorros"]
    davivienda = accounts["Davivienda Corriente"]
    nequi = accounts["Nequi Operaciones"]
    caja_chica = accounts["Caja Chica"]

    chatarrero = suppliers["Chatarrero Martinez"]
    acerias = customers["Acerías de Colombia SA"]
    fundiciones = customers["Fundiciones Bogota Ltda"]
    carlos = investors["Carlos Perez Inversores"]
    diana = investors["Diana Hernandez Capital"]

    # 1. Aportes de capital (al inicio)
    print("  Movimiento: Aporte capital Carlos Perez")
    money_movement_service.create_capital_injection(
        db=db,
        data=CapitalInjectionCreate(
            investor_id=carlos.id,
            amount=Decimal("20000000"),
            account_id=bancolombia.id,
            date=dias_atras(90),
            description="Aporte inicial de capital - Carlos Perez",
            notes="Capital semilla para operaciones",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Aporte capital Diana Hernandez")
    money_movement_service.create_capital_injection(
        db=db,
        data=CapitalInjectionCreate(
            investor_id=diana.id,
            amount=Decimal("15000000"),
            account_id=davivienda.id,
            date=dias_atras(85),
            description="Aporte inicial de capital - Diana Hernandez",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 2. Gastos operativos
    print("  Movimiento: Gasto arriendo bodega")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("3500000"),
            expense_category_id=expense_cats["Arriendo"].id,
            account_id=bancolombia.id,
            description="Arriendo Bodega Principal - Enero 2026",
            date=dias_atras(60),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Gasto servicios publicos")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("850000"),
            expense_category_id=expense_cats["Servicios"].id,
            account_id=caja_chica.id,
            description="Servicios publicos - Agua y luz enero",
            date=dias_atras(55),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Gasto flete compra")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("450000"),
            expense_category_id=expense_cats["Flete"].id,
            account_id=caja.id,
            description="Flete transporte chatarra desde Rodriguez",
            date=dias_atras(40),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Gasto nomina")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("8500000"),
            expense_category_id=expense_cats["Nomina"].id,
            account_id=bancolombia.id,
            description="Nomina operarios - Febrero 2026",
            date=dias_atras(28),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Gasto arriendo bodega febrero")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("3500000"),
            expense_category_id=expense_cats["Arriendo"].id,
            account_id=bancolombia.id,
            description="Arriendo Bodega Principal - Febrero 2026",
            date=dias_atras(28),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 3. Pago a proveedor (manual, fuera de liquidacion)
    print("  Movimiento: Pago proveedor Chatarrero Martinez")
    money_movement_service.pay_supplier(
        db=db,
        data=SupplierPaymentCreate(
            supplier_id=chatarrero.id,
            amount=Decimal("2000000"),
            account_id=caja.id,
            date=dias_atras(38),
            description="Abono deuda pendiente - Chatarrero Martinez",
            reference_number="REF-2026-001",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 4. Cobro a cliente (manual)
    print("  Movimiento: Cobro cliente Acerias de Colombia")
    money_movement_service.collect_from_customer(
        db=db,
        data=CustomerCollectionCreate(
            customer_id=acerias.id,
            amount=Decimal("5000000"),
            account_id=bancolombia.id,
            date=dias_atras(22),
            description="Abono cuenta por cobrar - Acerias de Colombia",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 5. Ingreso por servicio
    print("  Movimiento: Ingreso por servicio de pesaje")
    money_movement_service.create_service_income(
        db=db,
        data=ServiceIncomeCreate(
            amount=Decimal("350000"),
            account_id=caja.id,
            description="Servicio de pesaje a tercero",
            date=dias_atras(18),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 6. Transferencia entre cuentas
    print("  Movimiento: Transferencia Bancolombia -> Caja")
    money_movement_service.create_transfer(
        db=db,
        data=TransferCreate(
            amount=Decimal("5000000"),
            source_account_id=bancolombia.id,
            destination_account_id=caja.id,
            date=dias_atras(12),
            description="Traslado para pago operaciones en caja",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    print("  Movimiento: Transferencia Davivienda -> Nequi")
    money_movement_service.create_transfer(
        db=db,
        data=TransferCreate(
            amount=Decimal("1000000"),
            source_account_id=davivienda.id,
            destination_account_id=nequi.id,
            date=dias_atras(8),
            description="Recarga Nequi para pagos moviles",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 7. Gasto mantenimiento
    print("  Movimiento: Gasto mantenimiento bascula")
    money_movement_service.create_expense(
        db=db,
        data=ExpenseCreate(
            amount=Decimal("280000"),
            expense_category_id=expense_cats["Mantenimiento"].id,
            account_id=caja_chica.id,
            description="Mantenimiento preventivo bascula",
            date=dias_atras(5),
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )


def create_inventory_adjustments(db, org, admin_user, mats, warehouses) -> None:
    """Crea 4 ajustes de inventario de diferentes tipos."""
    bodega_principal = warehouses["Bodega Principal"]
    patio = warehouses["Patio de Acopio"]

    # 1. Aumento por material encontrado en bodega
    print("  Ajuste: Aumento FE002 por material encontrado")
    adjustment_service.increase(
        db=db,
        data=IncreaseCreate(
            material_id=mats["FE002"].id,
            warehouse_id=bodega_principal.id,
            quantity=Decimal("350"),
            unit_cost=Decimal("610"),
            date=dias_atras(35),
            reason="Material encontrado en revision de bodega",
            notes="Hierro fundido sin registro previo",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 2. Disminucion por merma/perdida
    print("  Ajuste: Disminucion PL001 por merma")
    adjustment_service.decrease(
        db=db,
        data=DecreaseCreate(
            material_id=mats["PL001"].id,
            warehouse_id=patio.id,
            quantity=Decimal("80"),
            date=dias_atras(25),
            reason="Merma por exposicion a la intemperie",
            notes="Plastico deteriorado no apto para venta",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 3. Conteo fisico
    print("  Ajuste: Conteo fisico NF001")
    adjustment_service.recount(
        db=db,
        data=RecountCreate(
            material_id=mats["NF001"].id,
            warehouse_id=bodega_principal.id,
            counted_quantity=mats["NF001"].current_stock_liquidated - Decimal("15"),
            date=dias_atras(15),
            reason="Conteo fisico mensual de inventario",
            notes="Diferencia por toma de muestras para laboratorio",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )

    # 4. Aumento por devolucion de cliente
    print("  Ajuste: Aumento FE001 por devolucion")
    adjustment_service.increase(
        db=db,
        data=IncreaseCreate(
            material_id=mats["FE001"].id,
            warehouse_id=patio.id,
            quantity=Decimal("200"),
            unit_cost=Decimal("650"),
            date=dias_atras(8),
            reason="Devolucion por cliente - material no conforme",
            notes="Acerias de Colombia devolvio chatarra con impurezas",
        ),
        organization_id=org.id,
        user_id=admin_user.id,
    )


def create_transformations(db, org, admin_user, mats, warehouses) -> None:
    """Crea 2 transformaciones de material."""
    bodega_principal = warehouses["Bodega Principal"]
    patio = warehouses["Patio de Acopio"]

    # Transformacion 1: Motor electrico → Cobre + Hierro + Aluminio + Merma
    # Necesitamos tener stock de EL001 en bodega_principal
    stock_motor = mats["EL001"].current_stock_liquidated
    if stock_motor >= Decimal("100"):
        qty_motor = Decimal("100")
        qty_cobre = Decimal("35")    # ~35% cobre
        qty_hierro = Decimal("40")   # ~40% hierro
        qty_aluminio = Decimal("18") # ~18% aluminio
        qty_merma = Decimal("7")     # ~7% merma

        print(f"  Transformacion: Motor Electrico {qty_motor}kg -> Cobre + Hierro + Aluminio + Merma")
        transformation_service.create(
            db=db,
            data=MaterialTransformationCreate(
                source_material_id=mats["EL001"].id,
                source_warehouse_id=bodega_principal.id,
                source_quantity=qty_motor,
                waste_quantity=qty_merma,
                cost_distribution="proportional_weight",
                lines=[
                    TransformationLineCreate(
                        destination_material_id=mats["NF001"].id,
                        destination_warehouse_id=bodega_principal.id,
                        quantity=qty_cobre,
                    ),
                    TransformationLineCreate(
                        destination_material_id=mats["FE001"].id,
                        destination_warehouse_id=bodega_principal.id,
                        quantity=qty_hierro,
                    ),
                    TransformationLineCreate(
                        destination_material_id=mats["NF003"].id,
                        destination_warehouse_id=bodega_principal.id,
                        quantity=qty_aluminio,
                    ),
                ],
                date=dias_atras(20),
                reason="Desintegracion de motores para separacion por material",
                notes="Lote de 100kg de motores industriales",
            ),
            organization_id=org.id,
            user_id=admin_user.id,
        )
    else:
        print(f"  Transformacion 1 omitida: stock insuficiente de EL001 ({stock_motor}kg)")

    # Transformacion 2: Cable electrico → Cobre cable + Plastico PVC
    stock_cable = mats["EL002"].current_stock_liquidated
    if stock_cable >= Decimal("80"):
        qty_cable = Decimal("80")
        qty_cobre_cable = Decimal("50")  # ~62% cobre
        qty_plastico = Decimal("28")     # ~35% plastico PVC
        qty_merma_cable = Decimal("2")   # ~3% merma

        print(f"  Transformacion: Cable Electrico {qty_cable}kg -> Cobre cable + Plastico")
        transformation_service.create(
            db=db,
            data=MaterialTransformationCreate(
                source_material_id=mats["EL002"].id,
                source_warehouse_id=bodega_principal.id,
                source_quantity=qty_cable,
                waste_quantity=qty_merma_cable,
                cost_distribution="proportional_weight",
                lines=[
                    TransformationLineCreate(
                        destination_material_id=mats["NF004"].id,
                        destination_warehouse_id=bodega_principal.id,
                        quantity=qty_cobre_cable,
                    ),
                    TransformationLineCreate(
                        destination_material_id=mats["PL003"].id,
                        destination_warehouse_id=patio.id,
                        quantity=qty_plastico,
                    ),
                ],
                date=dias_atras(10),
                reason="Pelado de cable para recuperacion de cobre",
                notes="Cable de recuperacion de obra civil",
            ),
            organization_id=org.id,
            user_id=admin_user.id,
        )
    else:
        print(f"  Transformacion 2 omitida: stock insuficiente de EL002 ({stock_cable}kg)")


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
        print("  EcoBalance ERP - Script de datos de prueba")
        print("="*60)

        if args.clear:
            print("\n[LIMPIEZA]")
            clear_data(db, "reciclajes-el-progreso")

        # Verificar si ya existe
        existing = db.query(Organization).filter(Organization.slug == "reciclajes-el-progreso").first()
        if existing:
            print(f"\nOrganizacion '{existing.name}' ya existe. Use --clear para recrear.")
            return

        print("\n[1/9] Organizacion y usuarios...")
        org = create_organization(db)
        users = create_users(db, org)
        db.commit()

        print("\n[2/9] Unidades de negocio y categorias...")
        bus = create_business_units(db, org)
        cats = create_material_categories(db, org)
        expense_cats = create_expense_categories(db, org)
        db.commit()

        print("\n[3/9] Materiales...")
        mats = create_materials(db, org, cats, bus)
        db.commit()

        print("\n[4/9] Bodegas y cuentas...")
        warehouses = create_warehouses(db, org)
        accounts = create_money_accounts(db, org)
        db.commit()

        print("\n[5/9] Terceros...")
        tps = create_third_parties(db, org)
        db.commit()

        # Lista de precios
        print("\n[5b] Lista de precios...")
        create_price_lists(db, org, mats)
        db.commit()

        admin_user = users["admin@reciclajes.com"]

        # Separar terceros por rol para facilitar uso
        suppliers = {
            k: v for k, v in tps.items()
            if v.is_supplier
        }
        customers = {
            k: v for k, v in tps.items()
            if v.is_customer
        }
        investors = {
            k: v for k, v in tps.items()
            if v.is_investor
        }
        commission_agents = {
            k: v for k, v in tps.items()
            if v.is_provision
        }

        print("\n[6/9] Compras...")
        create_purchases(db, org, admin_user, mats, warehouses, accounts, suppliers)

        print("\n[7/9] Ventas...")
        create_sales(db, org, admin_user, mats, warehouses, accounts, customers, commission_agents)

        print("\n[8/9] Dobles entradas...")
        create_double_entries(db, org, mats, suppliers, customers)

        print("\n[9a/9] Movimientos de tesoreria...")
        create_money_movements(db, org, admin_user, accounts, suppliers, customers, investors, expense_cats)

        print("\n[9b/9] Ajustes de inventario...")
        create_inventory_adjustments(db, org, admin_user, mats, warehouses)

        print("\n[9c/9] Transformaciones...")
        # Refrescar materiales para tener stock actualizado
        for codigo in list(mats.keys()):
            db.refresh(mats[codigo])
        create_transformations(db, org, admin_user, mats, warehouses)

        print("\n" + "="*60)
        print("  Datos de prueba creados exitosamente!")
        print("="*60)
        print(f"\nOrganizacion: Reciclajes El Progreso")
        print(f"Slug:          reciclajes-el-progreso")
        print(f"\nUsuarios (password: Pass1234!):")
        print(f"  admin@reciclajes.com    - admin")
        print(f"  nixon@reciclajes.com    - manager")
        print(f"  john@reciclajes.com     - operario")
        print(f"  gustavo@reciclajes.com  - contador")
        print(f"  ingrid@reciclajes.com   - comercial")
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
