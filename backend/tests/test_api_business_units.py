"""
Tests para endpoints de BusinessUnit (Unidades de Negocio).

Cubre: CRUD completo, busqueda por nombre,
paginacion y aislamiento multi-tenant.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business_unit import BusinessUnit


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_business_unit(db_session: Session, test_organization) -> BusinessUnit:
    """Crear una unidad de negocio de prueba."""
    bu = BusinessUnit(
        name="Fibras",
        description="Linea de negocio de fibras y carton",
        organization_id=test_organization.id,
    )
    db_session.add(bu)
    db_session.commit()
    db_session.refresh(bu)
    return bu


@pytest.fixture
def test_business_unit2(db_session: Session, test_organization) -> BusinessUnit:
    """Crear una segunda unidad de negocio."""
    bu = BusinessUnit(
        name="Chatarra",
        description="Linea de negocio de chatarra metalica",
        organization_id=test_organization.id,
    )
    db_session.add(bu)
    db_session.commit()
    db_session.refresh(bu)
    return bu


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreateBusinessUnit:
    """Tests para POST /api/v1/business-units."""

    def test_create_business_unit(self, client: TestClient, org_headers: dict):
        """Crear unidad de negocio con todos los campos."""
        payload = {
            "name": "Metales No Ferrosos",
            "description": "Aluminio, cobre, bronce, etc.",
        }
        response = client.post(
            "/api/v1/business-units", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Metales No Ferrosos"
        assert data["description"] == "Aluminio, cobre, bronce, etc."
        assert data["is_active"] is True

    def test_create_business_unit_minimal(self, client: TestClient, org_headers: dict):
        """Crear unidad de negocio solo con nombre."""
        payload = {"name": "Plasticos"}
        response = client.post(
            "/api/v1/business-units", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Plasticos"
        assert data["description"] is None

    def test_create_empty_name_fails(self, client: TestClient, org_headers: dict):
        """Nombre vacio debe fallar por validacion."""
        payload = {"name": ""}
        response = client.post(
            "/api/v1/business-units", json=payload, headers=org_headers
        )

        assert response.status_code == 422

    def test_create_without_auth(self, client: TestClient):
        """Sin autenticacion debe retornar 401."""
        payload = {"name": "Fibras"}
        response = client.post("/api/v1/business-units", json=payload)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------

class TestListBusinessUnits:
    """Tests para GET /api/v1/business-units."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna total=0."""
        response = client.get("/api/v1/business-units", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_units(
        self, client: TestClient, org_headers: dict,
        test_business_unit, test_business_unit2,
    ):
        """Listar retorna todas las unidades de la organizacion."""
        response = client.get("/api/v1/business-units", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_search_by_name(
        self, client: TestClient, org_headers: dict,
        test_business_unit, test_business_unit2,
    ):
        """Buscar por nombre."""
        response = client.get(
            "/api/v1/business-units?search=Chatarra", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Chatarra"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_business_unit, test_business_unit2,
    ):
        """Paginacion con limit=1."""
        response = client.get(
            "/api/v1/business-units?skip=0&limit=1", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetBusinessUnit:
    """Tests para GET /api/v1/business-units/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_business_unit,
    ):
        """Obtener unidad de negocio por ID."""
        response = client.get(
            f"/api/v1/business-units/{test_business_unit.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Fibras"

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/business-units/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de actualizacion
# ---------------------------------------------------------------------------

class TestUpdateBusinessUnit:
    """Tests para PATCH /api/v1/business-units/{id}."""

    def test_update_name(
        self, client: TestClient, org_headers: dict, test_business_unit,
    ):
        """Actualizar nombre (PATCH parcial)."""
        response = client.patch(
            f"/api/v1/business-units/{test_business_unit.id}",
            json={"name": "Fibras y Carton"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Fibras y Carton"

    def test_update_description(
        self, client: TestClient, org_headers: dict, test_business_unit,
    ):
        """Actualizar descripcion sin cambiar nombre."""
        response = client.patch(
            f"/api/v1/business-units/{test_business_unit.id}",
            json={"description": "Incluye carton, papel, archivo"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Incluye carton, papel, archivo"
        assert response.json()["name"] == "Fibras"


# ---------------------------------------------------------------------------
# Tests de eliminacion
# ---------------------------------------------------------------------------

class TestDeleteBusinessUnit:
    """Tests para DELETE /api/v1/business-units/{id}."""

    def test_soft_delete(
        self, client: TestClient, org_headers: dict, test_business_unit,
    ):
        """Soft delete marca is_active=False."""
        response = client.delete(
            f"/api/v1/business-units/{test_business_unit.id}", headers=org_headers
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_not_found(self, client: TestClient, org_headers: dict):
        """Eliminar unidad inexistente retorna 404."""
        response = client.delete(
            f"/api/v1/business-units/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestBusinessUnitOrganizationIsolation:
    """Verificar que una organizacion no puede ver unidades de otra."""

    def test_cannot_access_other_org_unit(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Unidad de otra organizacion retorna 404."""
        other_bu = BusinessUnit(
            name="Unidad Org2",
            organization_id=test_organization2.id,
        )
        db_session.add(other_bu)
        db_session.commit()
        db_session.refresh(other_bu)

        response = client.get(
            f"/api/v1/business-units/{other_bu.id}", headers=org_headers
        )

        assert response.status_code == 404
