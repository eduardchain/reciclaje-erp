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


# ---------------------------------------------------------------------------
# Subcategorias (parent_id, max 2 niveles)
# ---------------------------------------------------------------------------

class TestExpenseCategorySubcategories:
    """Tests para jerarquia de subcategorias (max 2 niveles)."""

    def test_create_with_parent(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense,
    ):
        """Crear subcategoria con parent_id valido."""
        response = client.post(
            "/api/v1/expense-categories",
            json={"name": "Flete Local", "parent_id": str(test_direct_expense.id)},
            headers=org_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["parent_id"] == str(test_direct_expense.id)
        # Hereda is_direct_expense del padre
        assert data["is_direct_expense"] == test_direct_expense.is_direct_expense

    def test_subcategory_inherits_direct_expense(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense,
    ):
        """Subcategoria hereda is_direct_expense del padre, ignora valor enviado."""
        response = client.post(
            "/api/v1/expense-categories",
            json={
                "name": "Flete Especial",
                "parent_id": str(test_direct_expense.id),
                "is_direct_expense": False,  # Intentar forzar False
            },
            headers=org_headers,
        )
        assert response.status_code == 201
        # Hereda True del padre, ignora el False enviado
        assert response.json()["is_direct_expense"] is True

    def test_create_with_invalid_parent_id(
        self, client: TestClient, org_headers: dict,
    ):
        """parent_id inexistente retorna 404."""
        response = client.post(
            "/api/v1/expense-categories",
            json={"name": "Sub Invalida", "parent_id": str(uuid4())},
            headers=org_headers,
        )
        assert response.status_code == 404

    def test_create_with_parent_from_other_org(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """parent_id de otra organizacion retorna 404."""
        other_parent = ExpenseCategory(
            name="Padre Org2",
            is_direct_expense=False,
            organization_id=test_organization2.id,
        )
        db_session.add(other_parent)
        db_session.commit()
        db_session.refresh(other_parent)

        response = client.post(
            "/api/v1/expense-categories",
            json={"name": "Sub Cross-Org", "parent_id": str(other_parent.id)},
            headers=org_headers,
        )
        assert response.status_code == 404

    def test_max_two_levels(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense,
    ):
        """No se puede crear sub-subcategoria (max 2 niveles)."""
        # Crear subcategoria
        sub = ExpenseCategory(
            name="Flete Interno",
            is_direct_expense=True,
            parent_id=test_direct_expense.id,
            organization_id=test_direct_expense.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        # Intentar crear sub-subcategoria
        response = client.post(
            "/api/v1/expense-categories",
            json={"name": "Sub-Sub", "parent_id": str(sub.id)},
            headers=org_headers,
        )
        assert response.status_code == 422
        assert "2 niveles" in response.json()["detail"]

    def test_cannot_assign_parent_to_category_with_children(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense, test_indirect_expense,
    ):
        """Categoria con hijos no puede convertirse en subcategoria."""
        # Crear hijo de test_direct_expense
        child = ExpenseCategory(
            name="Hijo",
            is_direct_expense=True,
            parent_id=test_direct_expense.id,
            organization_id=test_direct_expense.organization_id,
        )
        db_session.add(child)
        db_session.commit()

        # Intentar asignar parent a test_direct_expense (que ya tiene hijos)
        response = client.patch(
            f"/api/v1/expense-categories/{test_direct_expense.id}",
            json={"parent_id": str(test_indirect_expense.id)},
            headers=org_headers,
        )
        assert response.status_code == 422
        assert "subcategorias" in response.json()["detail"]

    def test_cannot_be_own_parent(
        self, client: TestClient, org_headers: dict,
        test_direct_expense,
    ):
        """Categoria no puede ser su propia subcategoria."""
        response = client.patch(
            f"/api/v1/expense-categories/{test_direct_expense.id}",
            json={"parent_id": str(test_direct_expense.id)},
            headers=org_headers,
        )
        assert response.status_code == 422
        assert "propia subcategoria" in response.json()["detail"]

    def test_update_change_parent(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense, test_indirect_expense,
    ):
        """Editar: cambiar parent_id funciona."""
        # Crear subcategoria de directo
        sub = ExpenseCategory(
            name="Movil",
            is_direct_expense=True,
            parent_id=test_direct_expense.id,
            organization_id=test_direct_expense.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        # Mover a indirecto
        response = client.patch(
            f"/api/v1/expense-categories/{sub.id}",
            json={"parent_id": str(test_indirect_expense.id)},
            headers=org_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["parent_id"] == str(test_indirect_expense.id)
        # Hereda is_direct_expense del nuevo padre
        assert data["is_direct_expense"] == test_indirect_expense.is_direct_expense

    def test_update_remove_parent(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_direct_expense,
    ):
        """Editar: quitar parent_id (null) funciona."""
        sub = ExpenseCategory(
            name="Temporal",
            is_direct_expense=True,
            parent_id=test_direct_expense.id,
            organization_id=test_direct_expense.organization_id,
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.patch(
            f"/api/v1/expense-categories/{sub.id}",
            json={"parent_id": None},
            headers=org_headers,
        )
        assert response.status_code == 200
        assert response.json()["parent_id"] is None


class TestExpenseCategoryFlat:
    """Tests para GET /flat endpoint."""

    def test_flat_display_name_format(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat retorna display_name formateado correctamente."""
        parent = ExpenseCategory(
            name="NOMINA",
            is_direct_expense=False,
            organization_id=test_organization.id,
        )
        db_session.add(parent)
        db_session.commit()
        db_session.refresh(parent)

        child = ExpenseCategory(
            name="Personal Contratado",
            is_direct_expense=False,
            parent_id=parent.id,
            organization_id=test_organization.id,
        )
        db_session.add(child)
        db_session.commit()

        response = client.get("/api/v1/expense-categories/flat", headers=org_headers)
        assert response.status_code == 200
        items = response.json()["items"]

        display_names = {i["display_name"] for i in items}
        assert "NOMINA" in display_names
        assert "NOMINA > Personal Contratado" in display_names

    def test_flat_alphabetical_order(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat ordenado alfabeticamente por display_name."""
        # Crear categorias en desorden
        for name in ["TRANSPORTE", "ARRIENDOS", "NOMINA"]:
            cat = ExpenseCategory(
                name=name, is_direct_expense=False,
                organization_id=test_organization.id,
            )
            db_session.add(cat)
        db_session.commit()

        response = client.get("/api/v1/expense-categories/flat", headers=org_headers)
        items = response.json()["items"]
        names = [i["display_name"] for i in items]
        assert names == sorted(names, key=str.lower)

    def test_flat_excludes_inactive(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET /flat no incluye categorias inactivas."""
        active = ExpenseCategory(
            name="Activa", is_direct_expense=False,
            organization_id=test_organization.id, is_active=True,
        )
        inactive = ExpenseCategory(
            name="Inactiva", is_direct_expense=False,
            organization_id=test_organization.id, is_active=False,
        )
        db_session.add_all([active, inactive])
        db_session.commit()

        response = client.get("/api/v1/expense-categories/flat", headers=org_headers)
        items = response.json()["items"]
        names = {i["name"] for i in items}
        assert "Activa" in names
        assert "Inactiva" not in names

    def test_list_includes_parent_name(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization,
    ):
        """GET / incluye parent_name en la respuesta."""
        parent = ExpenseCategory(
            name="SERVICIOS",
            is_direct_expense=False,
            organization_id=test_organization.id,
        )
        db_session.add(parent)
        db_session.commit()
        db_session.refresh(parent)

        child = ExpenseCategory(
            name="Agua",
            is_direct_expense=False,
            parent_id=parent.id,
            organization_id=test_organization.id,
        )
        db_session.add(child)
        db_session.commit()

        response = client.get("/api/v1/expense-categories", headers=org_headers)
        assert response.status_code == 200
        items = response.json()["items"]

        child_item = next(i for i in items if i["name"] == "Agua")
        assert child_item["parent_name"] == "SERVICIOS"

        parent_item = next(i for i in items if i["name"] == "SERVICIOS")
        assert parent_item["parent_name"] is None
