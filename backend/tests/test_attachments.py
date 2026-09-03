"""
Tests de adjuntos multiples (compras, ventas, transformaciones).

Cubre las tres respuestas del cliente con un test propio cada una:
  - se puede adjuntar DESPUES de liquidar
  - cancelar la operacion NO borra sus adjuntos
  - borra quien puede editar (y sube tambien quien crea — GAP-1)
"""
import io
import os
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.security import create_access_token
from app.models import (
    BusinessUnit,
    Material,
    MaterialCategory,
    ThirdParty,
    Warehouse,
)
from app.models.third_party_category import (
    ThirdPartyCategory,
    ThirdPartyCategoryAssignment,
)
from app.utils.dates import business_today_noon

BASE = "/api/v1/attachments"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def cat_supplier(db_session, test_organization):
    cat = ThirdPartyCategory(
        id=uuid4(), name="Proveedor Material",
        behavior_type="material_supplier", organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    return cat


@pytest.fixture
def cat_customer(db_session, test_organization):
    cat = ThirdPartyCategory(
        id=uuid4(), name="Cliente",
        behavior_type="customer", organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    return cat


def _tp(db_session, org, cat, name):
    tp = ThirdParty(
        id=uuid4(), name=name, current_balance=Decimal("0.00"),
        organization_id=org.id, is_active=True,
    )
    db_session.add(tp)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(
        id=uuid4(), third_party_id=tp.id, category_id=cat.id,
    ))
    db_session.commit()
    return tp


@pytest.fixture
def supplier(db_session, test_organization, cat_supplier):
    return _tp(db_session, test_organization, cat_supplier, "Proveedor Adjuntos")


@pytest.fixture
def customer(db_session, test_organization, cat_customer):
    return _tp(db_session, test_organization, cat_customer, "Cliente Adjuntos")


@pytest.fixture
def warehouse(db_session, test_organization):
    w = Warehouse(
        id=uuid4(), name="Bodega Adjuntos",
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(w)
    db_session.commit()
    return w


@pytest.fixture
def material(db_session, test_organization):
    cat = MaterialCategory(
        id=uuid4(), name="Metales Adj",
        organization_id=test_organization.id, is_active=True,
    )
    bu = BusinessUnit(
        id=uuid4(), name="UN Adj",
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add_all([cat, bu])
    db_session.flush()
    m = Material(
        id=uuid4(), code="ADJ-001", name="Cobre Adjuntos",
        category_id=cat.id, business_unit_id=bu.id, default_unit="kg",
        current_stock=Decimal("0.0000"), current_average_cost=Decimal("0.0000"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(m)
    db_session.commit()
    return m


def _new_purchase(client, org_headers, supplier, material, warehouse, auto=False):
    r = client.post("/api/v1/purchases", headers=org_headers, json={
        "supplier_id": str(supplier.id),
        "date": business_today_noon().isoformat(),
        "lines": [{
            "material_id": str(material.id), "quantity": 10.0,
            "unit_price": 1000.0, "warehouse_id": str(warehouse.id),
        }],
        "auto_liquidate": auto,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _new_sale(client, org_headers, customer, material, warehouse):
    r = client.post("/api/v1/sales", headers=org_headers, json={
        "customer_id": str(customer.id),
        "warehouse_id": str(warehouse.id),
        "date": business_today_noon().isoformat(),
        "lines": [{
            "material_id": str(material.id), "quantity": 1.0,
            "unit_price": 2000.0, "warehouse_id": str(warehouse.id),
        }],
        "auto_liquidate": False,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _upload(client, headers, owner_key, owner_id, name="foto.jpg",
            content=b"binario", description=None):
    data = {owner_key: str(owner_id)}
    if description is not None:
        data["description"] = description
    return client.post(
        BASE, headers=headers, data=data,
        files={"file": (name, io.BytesIO(content), "image/jpeg")},
    )


# ============================================================================
# Caso feliz — los tres modulos
# ============================================================================

class TestHappyPath:
    def test_purchase_upload_list_download_delete(
        self, client, org_headers, supplier, material, warehouse
    ):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)

        up = _upload(client, org_headers, "purchase_id", p["id"],
                     name="remision-4471.pdf", description="Remision del camion")
        assert up.status_code == 201, up.text
        att = up.json()
        # D2 — el nombre original se conserva (Tesoreria lo pierde).
        assert att["original_filename"] == "remision-4471.pdf"
        assert att["description"] == "Remision del camion"
        assert att["owner_type"] == "purchase"
        assert att["size_bytes"] == len(b"binario")
        assert att["uploaded_by_name"]

        lst = client.get(BASE, headers=org_headers, params={"purchase_id": p["id"]})
        assert lst.status_code == 200
        assert lst.json()["total"] == 1

        dl = client.get(f"{BASE}/{att['id']}/download", headers=org_headers)
        assert dl.status_code == 200
        assert dl.content == b"binario"

        # N4 — el archivo tiene que irse del disco, no solo la fila: si no, el
        # disco se llena de huerfanos invisibles (que es el recurso que este
        # ciclo dimensiono).
        org_dir = os.path.join(
            settings.UPLOAD_DIR, "attachments",
            org_headers["X-Organization-ID"],
        )
        antes = len(os.listdir(org_dir))

        rm = client.delete(f"{BASE}/{att['id']}", headers=org_headers)
        assert rm.status_code == 204
        assert client.get(
            BASE, headers=org_headers, params={"purchase_id": p["id"]}
        ).json()["total"] == 0
        assert len(os.listdir(org_dir)) == antes - 1, "el archivo quedo huerfano en disco"
        assert client.get(
            f"{BASE}/{att['id']}/download", headers=org_headers
        ).status_code == 404

    def test_editar_la_nota_del_adjunto(
        self, client, org_headers, supplier, material, warehouse
    ):
        """La etiqueta se edita sola (el archivo se reemplaza borrando y subiendo)."""
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        att = _upload(client, org_headers, "purchase_id", p["id"]).json()
        assert att["description"] is None

        r = client.patch(
            f"{BASE}/{att['id']}", headers=org_headers,
            json={"description": "Remision 4471"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["description"] == "Remision 4471"

        # Y se puede limpiar.
        r2 = client.patch(
            f"{BASE}/{att['id']}", headers=org_headers, json={"description": None}
        )
        assert r2.status_code == 200
        assert r2.json()["description"] is None

    def test_sale_attachment(self, client, org_headers, customer, material, warehouse):
        s = _new_sale(client, org_headers, customer, material, warehouse)
        up = _upload(client, org_headers, "sale_id", s["id"])
        assert up.status_code == 201, up.text
        assert up.json()["owner_type"] == "sale"

    def test_transformation_attachment(
        self, client, org_headers, db_session, test_organization, material, warehouse
    ):
        from app.models.material_transformation import MaterialTransformation

        t = MaterialTransformation(
            id=uuid4(), transformation_number=9001,
            source_material_id=material.id, source_quantity=Decimal("1.0000"),
            source_unit_cost=Decimal("0.00"), source_total_value=Decimal("0.00"),
            source_warehouse_id=warehouse.id, date=business_today_noon(),
            waste_quantity=Decimal("0.0000"), waste_value=Decimal("0.00"),
            cost_distribution="average_cost", reason="prueba adjuntos",
            organization_id=test_organization.id,
        )
        db_session.add(t)
        db_session.commit()

        up = _upload(client, org_headers, "transformation_id", t.id)
        assert up.status_code == 201, up.text
        assert up.json()["owner_type"] == "transformation"


# ============================================================================
# Validaciones
# ============================================================================

class TestValidations:
    def test_extension_invalida(self, client, org_headers, supplier, material, warehouse):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        r = _upload(client, org_headers, "purchase_id", p["id"], name="virus.exe")
        assert r.status_code == 400
        assert "no permitido" in r.json()["detail"].lower()

    def test_heic_del_iphone_se_acepta(
        self, client, org_headers, supplier, material, warehouse
    ):
        # N2 — el iPhone fotografia en HEIC por defecto y es el equipo del patio.
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        r = _upload(client, org_headers, "purchase_id", p["id"], name="IMG_0042.HEIC")
        assert r.status_code == 201, r.text

    def test_archivo_muy_grande(self, client, org_headers, supplier, material, warehouse):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        big = b"x" * (settings.MAX_UPLOAD_SIZE + 1)
        r = _upload(client, org_headers, "purchase_id", p["id"], content=big)
        assert r.status_code == 400
        assert "maximo" in r.json()["detail"].lower()

    def test_tope_de_diez(self, client, org_headers, supplier, material, warehouse):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        for i in range(10):
            assert _upload(
                client, org_headers, "purchase_id", p["id"], name=f"f{i}.jpg"
            ).status_code == 201
        r = _upload(client, org_headers, "purchase_id", p["id"], name="f11.jpg")
        assert r.status_code == 400
        assert "10" in r.json()["detail"]

    def test_sin_dueno(self, client, org_headers):
        r = client.post(
            BASE, headers=org_headers, data={},
            files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert r.status_code == 422

    def test_dos_duenos(self, client, org_headers, supplier, customer,
                        material, warehouse):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        s = _new_sale(client, org_headers, customer, material, warehouse)
        r = client.post(
            BASE, headers=org_headers,
            data={"purchase_id": str(p["id"]), "sale_id": str(s["id"])},
            files={"file": ("a.jpg", io.BytesIO(b"x"), "image/jpeg")},
        )
        assert r.status_code == 422

    def test_nota_demasiado_larga(self, client, org_headers, supplier, material, warehouse):
        """La columna es String(200): sin tope en el Form, el INSERT revienta con 500."""
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        r = _upload(client, org_headers, "purchase_id", p["id"], description="x" * 201)
        assert r.status_code == 422

    def test_dueno_inexistente(self, client, org_headers):
        r = _upload(client, org_headers, "purchase_id", uuid4())
        assert r.status_code == 404


# ============================================================================
# Las tres reglas que dio el cliente
# ============================================================================

class TestReglasDelCliente:
    def test_se_adjunta_despues_de_liquidar(
        self, client, org_headers, supplier, material, warehouse
    ):
        p = _new_purchase(client, org_headers, supplier, material, warehouse, auto=True)
        assert p["status"] == "liquidated"
        r = _upload(client, org_headers, "purchase_id", p["id"],
                    name="factura-tardia.pdf")
        assert r.status_code == 201, r.text

    def test_cancelar_no_borra_los_adjuntos(
        self, client, org_headers, supplier, material, warehouse
    ):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        att = _upload(client, org_headers, "purchase_id", p["id"]).json()

        cancel = client.patch(
            f"/api/v1/purchases/{p['id']}/cancel",
            headers=org_headers, params={"reason": "prueba adjuntos"},
        )
        assert cancel.status_code == 200, cancel.text

        # La evidencia sobrevive: siguen listandose Y descargandose.
        lst = client.get(BASE, headers=org_headers, params={"purchase_id": p["id"]})
        assert lst.json()["total"] == 1
        assert client.get(
            f"{BASE}/{att['id']}/download", headers=org_headers
        ).status_code == 200

    def test_gap1_bascula_sube_pero_no_borra(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse
    ):
        """
        GAP-1: el rol que tiene la camara (bascula) tiene .create pero NO .edit.
        Debe poder SUBIR la foto de calidad y NO poder borrarla.
        """
        from app.models.role import Role
        from app.models.user import OrganizationMember, User

        p = _new_purchase(client, org_headers, supplier, material, warehouse)

        pesador = User(
            email="pesador-adj@test.com", hashed_password="x",
            full_name="Pesador Adjuntos", is_active=True,
        )
        db_session.add(pesador)
        db_session.flush()
        role = db_session.query(Role).filter(
            Role.organization_id == test_organization.id,
            Role.name == "bascula",
            Role.is_system_role == True,
        ).first()
        assert role is not None
        db_session.add(OrganizationMember(
            user_id=pesador.id, organization_id=test_organization.id, role_id=role.id,
        ))
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(pesador.id)})}",
            "X-Organization-ID": str(test_organization.id),
        }

        up = _upload(client, headers, "purchase_id", p["id"], name="calidad.jpg")
        assert up.status_code == 201, f"la bascula debe poder subir: {up.text}"

        rm = client.delete(f"{BASE}/{up.json()['id']}", headers=headers)
        assert rm.status_code == 403, "borrar exige .edit (regla del cliente)"

    def test_viewer_lista_pero_no_sube(
        self, client, org_headers, db_session, test_organization,
        supplier, material, warehouse
    ):
        from app.models.role import Role
        from app.models.user import OrganizationMember, User

        p = _new_purchase(client, org_headers, supplier, material, warehouse)

        viewer = User(
            email="viewer-adj@test.com", hashed_password="x",
            full_name="Viewer Adjuntos", is_active=True,
        )
        db_session.add(viewer)
        db_session.flush()
        role = db_session.query(Role).filter(
            Role.organization_id == test_organization.id,
            Role.name == "viewer",
            Role.is_system_role == True,
        ).first()
        db_session.add(OrganizationMember(
            user_id=viewer.id, organization_id=test_organization.id, role_id=role.id,
        ))
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(viewer.id)})}",
            "X-Organization-ID": str(test_organization.id),
        }
        assert client.get(
            BASE, headers=headers, params={"purchase_id": p["id"]}
        ).status_code == 200
        assert _upload(
            client, headers, "purchase_id", p["id"]
        ).status_code == 403


    def test_n1_el_guard_es_por_modulo_no_uno_fijo(
        self, client, org_headers, db_session, test_organization,
        supplier, customer, material, warehouse
    ):
        """
        N1 — el atajo peligroso: poner `require_permission("purchases.view")`
        en el decorador. Los tres modulos quedarian gobernados por el permiso
        de compras y TODOS los demas tests seguirian en verde, porque usan
        admin (que bypassa) o roles que tienen los dos permisos.

        Este usuario tiene ventas y NO compras: si el guard fuera fijo a
        compras, no podria adjuntar a su propia venta.
        """
        from app.models.permission import Permission
        from app.models.role import Role, RolePermission
        from app.models.user import OrganizationMember, User

        s_ = _new_sale(client, org_headers, customer, material, warehouse)
        p_ = _new_purchase(client, org_headers, supplier, material, warehouse)

        rol = Role(
            id=uuid4(), name="solo-ventas", display_name="Solo Ventas",
            organization_id=test_organization.id, is_system_role=False,
        )
        db_session.add(rol)
        db_session.flush()
        codes = ["sales.view", "sales.create"]
        perms = db_session.query(Permission).filter(Permission.code.in_(codes)).all()
        assert len(perms) == len(codes), "faltan permisos en el catalogo de test"
        for perm in perms:
            db_session.add(RolePermission(role_id=rol.id, permission_id=perm.id))

        vendedor = User(
            email="solo-ventas-adj@test.com", hashed_password="x",
            full_name="Solo Ventas", is_active=True,
        )
        db_session.add(vendedor)
        db_session.flush()
        db_session.add(OrganizationMember(
            user_id=vendedor.id, organization_id=test_organization.id, role_id=rol.id,
        ))
        db_session.commit()

        headers = {
            "Authorization": f"Bearer {create_access_token(data={'sub': str(vendedor.id)})}",
            "X-Organization-ID": str(test_organization.id),
        }

        # Sube a SU venta: el guard tiene que mirar el modulo del dueno.
        up = _upload(client, headers, "sale_id", s_["id"], name="remision-venta.pdf")
        assert up.status_code == 201, f"con sales.create debe poder: {up.text}"

        # Y NO puede tocar una compra: el mismo endpoint, otro dueno, otro permiso.
        assert _upload(
            client, headers, "purchase_id", p_["id"]
        ).status_code == 403


# ============================================================================
# Seguridad y multi-tenancy
# ============================================================================

class TestSeguridad:
    def test_path_traversal_no_escapa_del_directorio(
        self, client, org_headers, supplier, material, warehouse, test_organization
    ):
        """D5 — el nombre del usuario nunca toca la ruta en disco."""
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        r = _upload(client, org_headers, "purchase_id", p["id"],
                    name="../../../etc/passwd.jpg")
        assert r.status_code == 201, r.text

        # El nombre original se conserva tal cual (es solo texto)...
        assert r.json()["original_filename"] == "../../../etc/passwd.jpg"
        # ...pero el archivo quedo DENTRO del directorio de la organizacion.
        org_dir = os.path.join(
            settings.UPLOAD_DIR, "attachments", str(test_organization.id)
        )
        stored = os.listdir(org_dir)
        assert any(f.endswith(".jpg") for f in stored)
        assert not os.path.exists("/etc/passwd.jpg")

    def test_otra_org_no_ve_ni_descarga(
        self, client, org_headers, org_headers2, supplier, material, warehouse
    ):
        p = _new_purchase(client, org_headers, supplier, material, warehouse)
        att = _upload(client, org_headers, "purchase_id", p["id"]).json()

        # La compra no es de la org 2 -> ni siquiera puede listar.
        assert client.get(
            BASE, headers=org_headers2, params={"purchase_id": p["id"]}
        ).status_code == 404
        assert client.get(
            f"{BASE}/{att['id']}/download", headers=org_headers2
        ).status_code == 404
        assert client.delete(
            f"{BASE}/{att['id']}", headers=org_headers2
        ).status_code == 404
