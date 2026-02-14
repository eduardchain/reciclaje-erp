"""
Tests para endpoints de Warehouse (Bodegas).

Cubre: CRUD completo, busqueda por nombre/direccion,
paginacion y aislamiento multi-tenant.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.warehouse import Warehouse


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_warehouse(db_session: Session, test_organization) -> Warehouse:
    """Crear una bodega de prueba."""
    wh = Warehouse(
        name="Bodega Principal",
        description="Bodega central de acopio",
        address="Cra 50 #30-20, Medellin",
        organization_id=test_organization.id,
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


@pytest.fixture
def test_warehouse2(db_session: Session, test_organization) -> Warehouse:
    """Crear una segunda bodega de prueba."""
    wh = Warehouse(
        name="Bodega Norte",
        description="Punto de recepcion norte",
        address="Calle 80 #45-10, Bogota",
        organization_id=test_organization.id,
    )
    db_session.add(wh)
    db_session.commit()
    db_session.refresh(wh)
    return wh


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreateWarehouse:
    """Tests para POST /api/v1/warehouses."""

    def test_create_warehouse(self, client: TestClient, org_headers: dict):
        """Crear bodega con todos los campos."""
        payload = {
            "name": "Bodega Sur",
            "description": "Punto de acopio zona sur",
            "address": "Av 68 #10-50, Cali",
        }
        response = client.post("/api/v1/warehouses", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Bodega Sur"
        assert data["description"] == "Punto de acopio zona sur"
        assert data["address"] == "Av 68 #10-50, Cali"
        assert data["is_active"] is True

    def test_create_warehouse_minimal(self, client: TestClient, org_headers: dict):
        """Crear bodega solo con nombre (campos opcionales omitidos)."""
        payload = {"name": "Bodega Temporal"}
        response = client.post("/api/v1/warehouses", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Bodega Temporal"
        assert data["description"] is None
        assert data["address"] is None

    def test_create_warehouse_empty_name_fails(self, client: TestClient, org_headers: dict):
        """Nombre vacio debe fallar por validacion."""
        payload = {"name": ""}
        response = client.post("/api/v1/warehouses", json=payload, headers=org_headers)

        assert response.status_code == 422

    def test_create_without_auth(self, client: TestClient):
        """Sin autenticacion debe retornar 401."""
        payload = {"name": "Bodega"}
        response = client.post("/api/v1/warehouses", json=payload)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------

class TestListWarehouses:
    """Tests para GET /api/v1/warehouses."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna total=0."""
        response = client.get("/api/v1/warehouses", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_with_warehouses(
        self, client: TestClient, org_headers: dict,
        test_warehouse, test_warehouse2,
    ):
        """Listar retorna todas las bodegas de la organizacion."""
        response = client.get("/api/v1/warehouses", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_search_by_address(
        self, client: TestClient, org_headers: dict,
        test_warehouse, test_warehouse2,
    ):
        """Buscar por direccion debe filtrar correctamente."""
        response = client.get(
            "/api/v1/warehouses?search=Medellin", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Bodega Principal"

    def test_list_search_by_name(
        self, client: TestClient, org_headers: dict,
        test_warehouse, test_warehouse2,
    ):
        """Buscar por nombre."""
        response = client.get(
            "/api/v1/warehouses?search=Norte", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Bodega Norte"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_warehouse, test_warehouse2,
    ):
        """Paginacion con limit=1."""
        response = client.get(
            "/api/v1/warehouses?skip=0&limit=1", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetWarehouse:
    """Tests para GET /api/v1/warehouses/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_warehouse,
    ):
        """Obtener bodega por ID."""
        response = client.get(
            f"/api/v1/warehouses/{test_warehouse.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Bodega Principal"

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/warehouses/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de actualizacion
# ---------------------------------------------------------------------------

class TestUpdateWarehouse:
    """Tests para PATCH /api/v1/warehouses/{id}."""

    def test_update_name(
        self, client: TestClient, org_headers: dict, test_warehouse,
    ):
        """Actualizar nombre (PATCH parcial)."""
        response = client.patch(
            f"/api/v1/warehouses/{test_warehouse.id}",
            json={"name": "Bodega Principal - Renovada"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Bodega Principal - Renovada"

    def test_update_address(
        self, client: TestClient, org_headers: dict, test_warehouse,
    ):
        """Actualizar solo la direccion."""
        response = client.patch(
            f"/api/v1/warehouses/{test_warehouse.id}",
            json={"address": "Nueva direccion #123"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["address"] == "Nueva direccion #123"
        # Nombre no cambia
        assert response.json()["name"] == "Bodega Principal"


# ---------------------------------------------------------------------------
# Tests de eliminacion
# ---------------------------------------------------------------------------

class TestDeleteWarehouse:
    """Tests para DELETE /api/v1/warehouses/{id}."""

    def test_soft_delete(
        self, client: TestClient, org_headers: dict, test_warehouse,
    ):
        """Soft delete marca is_active=False."""
        response = client.delete(
            f"/api/v1/warehouses/{test_warehouse.id}", headers=org_headers
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_not_found(self, client: TestClient, org_headers: dict):
        """Eliminar bodega inexistente retorna 404."""
        response = client.delete(
            f"/api/v1/warehouses/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestWarehouseOrganizationIsolation:
    """Verificar que una organizacion no puede ver bodegas de otra."""

    def test_cannot_access_other_org_warehouse(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Bodega de otra organizacion retorna 404."""
        other_wh = Warehouse(
            name="Bodega Org2",
            organization_id=test_organization2.id,
        )
        db_session.add(other_wh)
        db_session.commit()
        db_session.refresh(other_wh)

        response = client.get(
            f"/api/v1/warehouses/{other_wh.id}", headers=org_headers
        )

        assert response.status_code == 404
