"""
Tests para endpoints de ExpenseCategory (Categorias de Gastos).

Cubre: CRUD completo, distincion directo/indirecto, busqueda,
paginacion y aislamiento multi-tenant.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.expense_category import ExpenseCategory


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_direct_expense(db_session: Session, test_organization) -> ExpenseCategory:
    """Crear categoria de gasto directo (afecta costo de material)."""
    cat = ExpenseCategory(
        name="Flete",
        description="Costo de transporte de material",
        is_direct_expense=True,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_indirect_expense(db_session: Session, test_organization) -> ExpenseCategory:
    """Crear categoria de gasto indirecto (administrativo)."""
    cat = ExpenseCategory(
        name="Servicios Publicos",
        description="Agua, luz, gas de la bodega",
        is_direct_expense=False,
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreateExpenseCategory:
    """Tests para POST /api/v1/expense-categories."""

    def test_create_direct_expense(self, client: TestClient, org_headers: dict):
        """Crear gasto directo con todos los campos."""
        payload = {
            "name": "Pesaje",
            "description": "Costo de bascula para pesaje de material",
            "is_direct_expense": True,
        }
        response = client.post(
            "/api/v1/expense-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Pesaje"
        assert data["is_direct_expense"] is True
        assert data["is_active"] is True

    def test_create_indirect_expense(self, client: TestClient, org_headers: dict):
        """Crear gasto indirecto."""
        payload = {
            "name": "Arriendo",
            "description": "Arriendo mensual de bodega",
            "is_direct_expense": False,
        }
        response = client.post(
            "/api/v1/expense-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_direct_expense"] is False

    def test_create_default_is_indirect(self, client: TestClient, org_headers: dict):
        """Sin especificar is_direct_expense, default es False (indirecto)."""
        payload = {"name": "Papeleria"}
        response = client.post(
            "/api/v1/expense-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 201
        assert response.json()["is_direct_expense"] is False

    def test_create_empty_name_fails(self, client: TestClient, org_headers: dict):
        """Nombre vacio debe fallar por validacion."""
        payload = {"name": ""}
        response = client.post(
            "/api/v1/expense-categories", json=payload, headers=org_headers
        )

        assert response.status_code == 422

    def test_create_without_auth(self, client: TestClient):
        """Sin autenticacion debe retornar 401."""
        payload = {"name": "Flete"}
        response = client.post("/api/v1/expense-categories", json=payload)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests de listado
# ---------------------------------------------------------------------------

class TestListExpenseCategories:
    """Tests para GET /api/v1/expense-categories."""

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia retorna total=0."""
        response = client.get("/api/v1/expense-categories", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    def test_list_with_categories(
        self, client: TestClient, org_headers: dict,
        test_direct_expense, test_indirect_expense,
    ):
        """Listar retorna todas las categorias de la organizacion."""
        response = client.get("/api/v1/expense-categories", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    def test_list_search_by_name(
        self, client: TestClient, org_headers: dict,
        test_direct_expense, test_indirect_expense,
    ):
        """Buscar por nombre."""
        response = client.get(
            "/api/v1/expense-categories?search=Flete", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Flete"

    def test_list_pagination(
        self, client: TestClient, org_headers: dict,
        test_direct_expense, test_indirect_expense,
    ):
        """Paginacion con limit=1."""
        response = client.get(
            "/api/v1/expense-categories?skip=0&limit=1", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 1


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetExpenseCategory:
    """Tests para GET /api/v1/expense-categories/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_direct_expense,
    ):
        """Obtener categoria por ID."""
        response = client.get(
            f"/api/v1/expense-categories/{test_direct_expense.id}",
            headers=org_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Flete"
        assert data["is_direct_expense"] is True

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/expense-categories/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de actualizacion
# ---------------------------------------------------------------------------

class TestUpdateExpenseCategory:
    """Tests para PATCH /api/v1/expense-categories/{id}."""

    def test_update_name(
        self, client: TestClient, org_headers: dict, test_direct_expense,
    ):
        """Actualizar nombre (PATCH parcial)."""
        response = client.patch(
            f"/api/v1/expense-categories/{test_direct_expense.id}",
            json={"name": "Flete Terrestre"},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Flete Terrestre"
        # Tipo no cambia
        assert response.json()["is_direct_expense"] is True

    def test_update_type(
        self, client: TestClient, org_headers: dict, test_indirect_expense,
    ):
        """Cambiar de indirecto a directo."""
        response = client.patch(
            f"/api/v1/expense-categories/{test_indirect_expense.id}",
            json={"is_direct_expense": True},
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["is_direct_expense"] is True


# ---------------------------------------------------------------------------
# Tests de eliminacion
# ---------------------------------------------------------------------------

class TestDeleteExpenseCategory:
    """Tests para DELETE /api/v1/expense-categories/{id}."""

    def test_soft_delete(
        self, client: TestClient, org_headers: dict, test_direct_expense,
    ):
        """Soft delete marca is_active=False."""
        response = client.delete(
            f"/api/v1/expense-categories/{test_direct_expense.id}",
            headers=org_headers,
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_delete_not_found(self, client: TestClient, org_headers: dict):
        """Eliminar inexistente retorna 404."""
        response = client.delete(
            f"/api/v1/expense-categories/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestExpenseCategoryOrganizationIsolation:
    """Verificar aislamiento entre organizaciones."""

    def test_cannot_access_other_org_category(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Categoria de otra organizacion retorna 404."""
        other_cat = ExpenseCategory(
            name="Gasto Org2",
            is_direct_expense=False,
            organization_id=test_organization2.id,
        )
        db_session.add(other_cat)
        db_session.commit()
        db_session.refresh(other_cat)

        response = client.get(
            f"/api/v1/expense-categories/{other_cat.id}", headers=org_headers
        )

        assert response.status_code == 404
