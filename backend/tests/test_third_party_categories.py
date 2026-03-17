"""
Tests para endpoints de ThirdPartyCategory (Categorias de Terceros).

Cubre: CRUD completo, jerarquia max 2 niveles, behavior_type obligatorio
en nivel 1, herencia en subcategorias, GET /flat con filtro, soft delete
con validacion de hijos y asignaciones, aislamiento multi-tenant.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment
from app.models.third_party import ThirdParty


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_category_supplier(db_session: Session, test_organization) -> ThirdPartyCategory:
    """Categoria nivel-1: proveedor de material."""
    cat = ThirdPartyCategory(
        name="Proveedor de Material",
        description="Proveedores de materia prima",
        behavior_type="material_supplier",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_category_customer(db_session: Session, test_organization) -> ThirdPartyCategory:
    """Categoria nivel-1: cliente."""
    cat = ThirdPartyCategory(
        name="Cliente",
        behavior_type="customer",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_category_investor(db_session: Session, test_organization) -> ThirdPartyCategory:
    """Categoria nivel-1: inversionista."""
    cat = ThirdPartyCategory(
        name="Inversionista",
        behavior_type="investor",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreateThirdPartyCategory:
    """Tests para POST /api/v1/third-party-categories."""

    def test_create_level1_with_behavior_type(self, client: TestClient, org_headers: dict):
        """Crear categoria nivel-1 con behavior_type valido."""
        payload = {
            "name": "Proveedor de Servicios",
            "description": "Proveedores de servicios externos",
            "behavior_type": "service_provider",
        }
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Proveedor de Servicios"
        assert data["behavior_type"] == "service_provider"
        assert data["is_active"] is True
        assert data["parent_id"] is None

    def test_create_level1_without_behavior_type_fails(self, client: TestClient, org_headers: dict):
        """Nivel-1 sin behavior_type debe fallar."""
        payload = {"name": "Sin Tipo"}
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 422
        assert "behavior_type" in response.json()["detail"]

    def test_create_level1_invalid_behavior_type_fails(self, client: TestClient, org_headers: dict):
        """behavior_type invalido debe fallar."""
        payload = {"name": "Invalido", "behavior_type": "no_existe"}
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 422

    def test_create_subcategory_inherits_behavior_type(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Subcategoria hereda behavior_type del padre."""
        payload = {
            "name": "Proveedor Local",
            "parent_id": str(test_category_supplier.id),
        }
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["parent_id"] == str(test_category_supplier.id)
        assert data["behavior_type"] == "material_supplier"

    def test_create_subcategory_ignores_sent_behavior_type(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Subcategoria ignora behavior_type enviado, usa el del padre."""
        payload = {
            "name": "Sub con Tipo",
            "parent_id": str(test_category_supplier.id),
            "behavior_type": "customer",  # Debe ignorarse
        }
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        assert response.json()["behavior_type"] == "material_supplier"

    def test_create_level3_fails(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier,
    ):
        """No se puede crear sub-subcategoria (max 2 niveles)."""
        # Crear subcategoria
        sub = ThirdPartyCategory(
            name="Sub Nivel 2",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        # Intentar crear nivel 3
        payload = {"name": "Sub Sub", "parent_id": str(sub.id)}
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 422
        assert "2 niveles" in response.json()["detail"]

    def test_create_with_invalid_parent_id(self, client: TestClient, org_headers: dict):
        """parent_id inexistente retorna 404."""
        payload = {
            "name": "Huerfana",
            "parent_id": str(uuid4()),
        }
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 404

    def test_create_empty_name_fails(self, client: TestClient, org_headers: dict):
        """Nombre vacio debe fallar."""
        payload = {"name": "", "behavior_type": "customer"}
        response = client.post(
            "/api/v1/third-party-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 422

    def test_create_without_auth(self, client: TestClient):
        """Sin autenticacion retorna 401."""
        payload = {"name": "Test", "behavior_type": "customer"}
        response = client.post("/api/v1/third-party-categories", json=payload)

        assert response.status_code == 401

    def test_create_all_behavior_types(self, client: TestClient, org_headers: dict):
        """Verificar que todos los behavior_type validos funcionan."""
        valid_types = [
            "material_supplier", "service_provider", "customer",
            "investor", "employee", "provision",
        ]
        for bt in valid_types:
            response = client.post(
                "/api/v1/third-party-categories",
                json={"name": f"Cat {bt}", "behavior_type": bt},
                headers=org_headers,
            )
            assert response.status_code == 201, f"Fallo con behavior_type={bt}"
            assert response.json()["behavior_type"] == bt


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------

class TestListThirdPartyCategories:
    """Tests para GET /api/v1/third-party-categories."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna total=0."""
        response = client.get("/api/v1/third-party-categories", headers=org_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 0

    def test_list_with_categories(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """Listar retorna todas las categorias."""
        response = client.get("/api/v1/third-party-categories", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_search_by_name(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """Buscar por nombre."""
        response = client.get(
            "/api/v1/third-party-categories?search=Material", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Proveedor de Material"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """Paginacion con limit=1."""
        response = client.get(
            "/api/v1/third-party-categories?skip=0&limit=1", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1

    def test_list_includes_parent_name(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier,
    ):
        """GET / incluye parent_name en la respuesta."""
        sub = ThirdPartyCategory(
            name="Local",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(sub)
        db_session.commit()

        response = client.get("/api/v1/third-party-categories", headers=org_headers)
        items = response.json()["items"]

        child_item = next(i for i in items if i["name"] == "Local")
        assert child_item["parent_name"] == "Proveedor de Material"

        parent_item = next(i for i in items if i["name"] == "Proveedor de Material")
        assert parent_item["parent_name"] is None


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetThirdPartyCategory:
    """Tests para GET /api/v1/third-party-categories/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Obtener categoria por ID."""
        response = client.get(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Proveedor de Material"
        assert data["behavior_type"] == "material_supplier"

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/third-party-categories/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de actualizacion
# ---------------------------------------------------------------------------

class TestUpdateThirdPartyCategory:
    """Tests para PATCH /api/v1/third-party-categories/{id}."""

    def test_update_name(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Actualizar nombre."""
        response = client.patch(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            json={"name": "Proveedor Material Reciclado"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Proveedor Material Reciclado"
        assert response.json()["behavior_type"] == "material_supplier"

    def test_update_description(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Actualizar descripcion."""
        response = client.patch(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            json={"description": "Nueva descripcion"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Nueva descripcion"

    def test_cannot_be_own_parent(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Categoria no puede ser su propia subcategoria."""
        response = client.patch(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            json={"parent_id": str(test_category_supplier.id)},
            headers=org_headers,
        )

        assert response.status_code == 422
        assert "propia subcategoria" in response.json()["detail"]

    def test_cannot_assign_parent_to_category_with_children(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier, test_category_customer,
    ):
        """Categoria con hijos no puede convertirse en subcategoria."""
        child = ThirdPartyCategory(
            name="Hijo",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(child)
        db_session.commit()

        response = client.patch(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            json={"parent_id": str(test_category_customer.id)},
            headers=org_headers,
        )

        assert response.status_code == 422
        assert "subcategorias" in response.json()["detail"]

    def test_update_change_parent(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier, test_category_customer,
    ):
        """Mover subcategoria a otro padre — hereda behavior_type."""
        sub = ThirdPartyCategory(
            name="Movible",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.patch(
            f"/api/v1/third-party-categories/{sub.id}",
            json={"parent_id": str(test_category_customer.id)},
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == str(test_category_customer.id)
        assert data["behavior_type"] == "customer"

    def test_update_remove_parent(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier,
    ):
        """Quitar parent_id (null) funciona."""
        sub = ThirdPartyCategory(
            name="Temporal",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.patch(
            f"/api/v1/third-party-categories/{sub.id}",
            json={"parent_id": None},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["parent_id"] is None


# ---------------------------------------------------------------------------
# Tests de eliminacion
# ---------------------------------------------------------------------------

class TestDeleteThirdPartyCategory:
    """Tests para DELETE /api/v1/third-party-categories/{id}."""

    def test_soft_delete(
        self, client: TestClient, org_headers: dict, test_category_supplier,
    ):
        """Soft delete marca is_active=False."""
        response = client.delete(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_not_found(self, client: TestClient, org_headers: dict):
        """Eliminar inexistente retorna 404."""
        response = client.delete(
            f"/api/v1/third-party-categories/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404

    def test_delete_blocked_with_active_children(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier,
    ):
        """No se puede eliminar categoria con subcategorias activas."""
        child = ThirdPartyCategory(
            name="Hijo Activo",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
        )
        db_session.add(child)
        db_session.commit()

        response = client.delete(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            headers=org_headers,
        )

        assert response.status_code == 422
        assert "subcategorias activas" in response.json()["detail"]

    def test_delete_blocked_with_assigned_third_parties(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier, test_organization,
    ):
        """No se puede eliminar categoria con terceros asignados."""
        # Crear tercero y asignarlo a la categoria
        tp = ThirdParty(
            name="Proveedor Test",
            organization_id=test_organization.id,
        )
        db_session.add(tp)
        db_session.commit()
        db_session.refresh(tp)

        assignment = ThirdPartyCategoryAssignment(
            third_party_id=tp.id,
            category_id=test_category_supplier.id,
        )
        db_session.add(assignment)
        db_session.commit()

        response = client.delete(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            headers=org_headers,
        )

        assert response.status_code == 422
        assert "terceros asignados" in response.json()["detail"]

    def test_delete_allowed_after_children_deactivated(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_category_supplier,
    ):
        """Se puede eliminar si los hijos ya estan inactivos."""
        child = ThirdPartyCategory(
            name="Hijo Inactivo",
            behavior_type="material_supplier",
            parent_id=test_category_supplier.id,
            organization_id=test_category_supplier.organization_id,
            is_active=False,
        )
        db_session.add(child)
        db_session.commit()

        response = client.delete(
            f"/api/v1/third-party-categories/{test_category_supplier.id}",
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Tests de GET /flat
# ---------------------------------------------------------------------------

class TestThirdPartyCategoryFlat:
    """Tests para GET /api/v1/third-party-categories/flat."""

    def test_flat_display_name_format(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat retorna display_name formateado correctamente."""
        parent = ThirdPartyCategory(
            name="PROVEEDORES",
            behavior_type="material_supplier",
            organization_id=test_organization.id,
        )
        db_session.add(parent)
        db_session.commit()
        db_session.refresh(parent)

        child = ThirdPartyCategory(
            name="Locales",
            behavior_type="material_supplier",
            parent_id=parent.id,
            organization_id=test_organization.id,
        )
        db_session.add(child)
        db_session.commit()

        response = client.get("/api/v1/third-party-categories/flat", headers=org_headers)
        assert response.status_code == 200
        items = response.json()["items"]

        display_names = {i["display_name"] for i in items}
        assert "PROVEEDORES" in display_names
        assert "PROVEEDORES > Locales" in display_names

    def test_flat_filter_by_behavior_type(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """GET /flat con ?behavior_type= filtra correctamente."""
        response = client.get(
            "/api/v1/third-party-categories/flat?behavior_type=material_supplier",
            headers=org_headers,
        )

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["behavior_type"] == "material_supplier"

    def test_flat_without_filter_returns_all(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """GET /flat sin filtro retorna todas las categorias activas."""
        response = client.get("/api/v1/third-party-categories/flat", headers=org_headers)

        assert response.status_code == 200
        items = response.json()["items"]
        assert len(items) == 2

    def test_flat_excludes_inactive(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat no incluye categorias inactivas."""
        active = ThirdPartyCategory(
            name="Activa", behavior_type="customer",
            organization_id=test_organization.id, is_active=True,
        )
        inactive = ThirdPartyCategory(
            name="Inactiva", behavior_type="customer",
            organization_id=test_organization.id, is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        response = client.get("/api/v1/third-party-categories/flat", headers=org_headers)
        items = response.json()["items"]
        names = {i["name"] for i in items}
        assert "Activa" in names
        assert "Inactiva" not in names

    def test_flat_alphabetical_order(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat ordenado alfabeticamente por display_name."""
        for name, bt in [("TRANSPORTE", "service_provider"), ("ARRIENDOS", "service_provider"), ("NOMINA", "employee")]:
            cat = ThirdPartyCategory(
                name=name, behavior_type=bt,
                organization_id=test_organization.id,
            )
            db_session.add(cat)
        db_session.commit()

        response = client.get("/api/v1/third-party-categories/flat", headers=org_headers)
        items = response.json()["items"]
        names = [i["display_name"] for i in items]
        assert names == sorted(names, key=str.lower)

    def test_flat_includes_behavior_type(
        self, client: TestClient, org_headers: dict,
        test_category_supplier, test_category_customer,
    ):
        """GET /flat incluye behavior_type en cada item."""
        response = client.get("/api/v1/third-party-categories/flat", headers=org_headers)
        items = response.json()["items"]

        for item in items:
            assert "behavior_type" in item
            assert item["behavior_type"] in [
                "material_supplier", "service_provider", "customer",
                "investor", "employee", "provision",
            ]


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestThirdPartyCategoryOrganizationIsolation:
    """Verificar aislamiento entre organizaciones."""

    def test_cannot_access_other_org_category(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Categoria de otra organizacion retorna 404."""
        other_cat = ThirdPartyCategory(
            name="Cat Org2",
            behavior_type="customer",
            organization_id=test_organization2.id,
        )
        db_session.add(other_cat)
        db_session.commit()
        db_session.refresh(other_cat)

        response = client.get(
            f"/api/v1/third-party-categories/{other_cat.id}", headers=org_headers
        )

        assert response.status_code == 404

    def test_list_only_shows_own_org(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization, test_organization2,
    ):
        """Listado solo muestra categorias de la organizacion actual."""
        own = ThirdPartyCategory(
            name="Propia", behavior_type="customer",
            organization_id=test_organization.id,
        )
        other = ThirdPartyCategory(
            name="Ajena", behavior_type="customer",
            organization_id=test_organization2.id,
        )
        db_session.add_all([own, other])
        db_session.commit()

        response = client.get("/api/v1/third-party-categories", headers=org_headers)
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Propia"

    def test_cannot_create_with_parent_from_other_org(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """parent_id de otra organizacion retorna 404."""
        other_parent = ThirdPartyCategory(
            name="Padre Org2",
            behavior_type="customer",
            organization_id=test_organization2.id,
        )
        db_session.add(other_parent)
        db_session.commit()
        db_session.refresh(other_parent)

        response = client.post(
            "/api/v1/third-party-categories",
            json={"name": "Sub Cross-Org", "parent_id": str(other_parent.id)},
            headers=org_headers,
        )
        assert response.status_code == 404
