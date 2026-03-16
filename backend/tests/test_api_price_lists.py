"""
Tests para endpoints de PriceList (Listas de Precios).

Cubre: creacion, consulta de precio vigente, historial por material,
validacion de material inexistente, y aislamiento multi-tenant.
"""
import time
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.material import Material, MaterialCategory
from app.models.price_list import PriceList


# ---------------------------------------------------------------------------
# Fixtures locales
# ---------------------------------------------------------------------------

@pytest.fixture
def test_category(db_session: Session, test_organization) -> MaterialCategory:
    """Crear categoria de material de prueba."""
    cat = MaterialCategory(
        name="Metales",
        organization_id=test_organization.id,
    )
    db_session.add(cat)
    db_session.commit()
    db_session.refresh(cat)
    return cat


@pytest.fixture
def test_material(db_session: Session, test_organization, test_category) -> Material:
    """Crear material de prueba."""
    mat = Material(
        code="MET-001",
        name="Hierro",
        category_id=test_category.id,
        default_unit="kg",
        organization_id=test_organization.id,
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)
    return mat


@pytest.fixture
def test_material2(db_session: Session, test_organization, test_category) -> Material:
    """Crear segundo material de prueba."""
    mat = Material(
        code="MET-002",
        name="Cobre",
        category_id=test_category.id,
        default_unit="kg",
        organization_id=test_organization.id,
    )
    db_session.add(mat)
    db_session.commit()
    db_session.refresh(mat)
    return mat


@pytest.fixture
def test_price(db_session: Session, test_organization, test_material) -> PriceList:
    """Crear un registro de precio de prueba."""
    price = PriceList(
        material_id=test_material.id,
        purchase_price=Decimal("1500.00"),
        sale_price=Decimal("2000.00"),
        notes="Precio inicial",
        organization_id=test_organization.id,
    )
    db_session.add(price)
    db_session.commit()
    db_session.refresh(price)
    return price


# ---------------------------------------------------------------------------
# Tests de creacion
# ---------------------------------------------------------------------------

class TestCreatePriceList:
    """Tests para POST /api/v1/price-lists."""

    def test_create_price(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Crear registro de precio con todos los campos."""
        payload = {
            "material_id": str(test_material.id),
            "purchase_price": 1200.50,
            "sale_price": 1800.00,
            "notes": "Precio negociado con proveedor principal",
        }
        response = client.post("/api/v1/price-lists", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["material_id"] == str(test_material.id)
        assert data["purchase_price"] == 1200.50
        assert data["sale_price"] == 1800.00
        assert data["notes"] == "Precio negociado con proveedor principal"
        assert data["updated_by"] is not None  # Se asigna automaticamente

    def test_create_price_minimal(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Crear precio solo con material_id (precios default a 0)."""
        payload = {
            "material_id": str(test_material.id),
        }
        response = client.post("/api/v1/price-lists", json=payload, headers=org_headers)

        assert response.status_code == 201
        data = response.json()
        assert data["purchase_price"] == 0.0
        assert data["sale_price"] == 0.0

    def test_create_price_invalid_material(
        self, client: TestClient, org_headers: dict,
    ):
        """Material inexistente debe retornar 404."""
        payload = {
            "material_id": str(uuid4()),
            "purchase_price": 1000.00,
            "sale_price": 1500.00,
        }
        response = client.post("/api/v1/price-lists", json=payload, headers=org_headers)

        assert response.status_code == 404
        assert "Material no encontrado" in response.json()["detail"]

    def test_create_without_auth(self, client: TestClient, test_material):
        """Sin autenticacion debe retornar 401."""
        payload = {"material_id": str(test_material.id)}
        response = client.post("/api/v1/price-lists", json=payload)

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests de precio vigente
# ---------------------------------------------------------------------------

class TestGetCurrentPrice:
    """Tests para GET /api/v1/price-lists/current/{material_id}."""

    def test_get_current_price(
        self, client: TestClient, org_headers: dict, test_price, test_material,
    ):
        """Obtener precio vigente de un material."""
        response = client.get(
            f"/api/v1/price-lists/current/{test_material.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchase_price"] == 1500.0
        assert data["sale_price"] == 2000.0

    def test_current_price_returns_most_recent(
        self, client: TestClient, org_headers: dict, test_material,
        db_session: Session, test_organization,
    ):
        """El precio vigente debe ser el mas reciente por created_at."""
        # Crear precio viejo
        old_price = PriceList(
            material_id=test_material.id,
            purchase_price=Decimal("1000.00"),
            sale_price=Decimal("1500.00"),
            notes="Precio viejo",
            organization_id=test_organization.id,
        )
        db_session.add(old_price)
        db_session.commit()

        # Crear precio nuevo (via API para que tenga timestamp posterior)
        payload = {
            "material_id": str(test_material.id),
            "purchase_price": 2000.00,
            "sale_price": 3000.00,
            "notes": "Precio actualizado",
        }
        client.post("/api/v1/price-lists", json=payload, headers=org_headers)

        # Consultar precio vigente
        response = client.get(
            f"/api/v1/price-lists/current/{test_material.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchase_price"] == 2000.0
        assert data["sale_price"] == 3000.0
        assert data["notes"] == "Precio actualizado"

    def test_current_price_no_records(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Sin precios registrados debe retornar 404."""
        response = client.get(
            f"/api/v1/price-lists/current/{test_material.id}", headers=org_headers
        )

        assert response.status_code == 404
        assert "No hay precios" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Tests de historial por material
# ---------------------------------------------------------------------------

class TestGetPriceHistory:
    """Tests para GET /api/v1/price-lists/material/{material_id}."""

    def test_get_history(
        self, client: TestClient, org_headers: dict, test_price, test_material,
    ):
        """Obtener historial de precios de un material."""
        response = client.get(
            f"/api/v1/price-lists/material/{test_material.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    def test_history_empty(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Sin precios registrados retorna lista vacia."""
        response = client.get(
            f"/api/v1/price-lists/material/{test_material.id}", headers=org_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Tests de listado general
# ---------------------------------------------------------------------------

class TestListPriceLists:
    """Tests para GET /api/v1/price-lists."""

    def test_list_all(
        self, client: TestClient, org_headers: dict, test_price,
    ):
        """Listar todos los registros de precio."""
        response = client.get("/api/v1/price-lists", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    def test_list_empty(self, client: TestClient, org_headers: dict):
        """Lista vacia."""
        response = client.get("/api/v1/price-lists", headers=org_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 0


# ---------------------------------------------------------------------------
# Tests de lectura individual
# ---------------------------------------------------------------------------

class TestGetPriceList:
    """Tests para GET /api/v1/price-lists/{id}."""

    def test_get_by_id(
        self, client: TestClient, org_headers: dict, test_price,
    ):
        """Obtener registro de precio por ID."""
        response = client.get(
            f"/api/v1/price-lists/{test_price.id}", headers=org_headers
        )

        assert response.status_code == 200
        assert response.json()["notes"] == "Precio inicial"

    def test_get_not_found(self, client: TestClient, org_headers: dict):
        """ID inexistente retorna 404."""
        response = client.get(
            f"/api/v1/price-lists/{uuid4()}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de precios vigentes bulk
# ---------------------------------------------------------------------------

class TestGetAllCurrentPrices:
    """Tests para GET /api/v1/price-lists/current."""

    def test_empty_when_no_prices(
        self, client: TestClient, org_headers: dict,
    ):
        """Sin precios registrados retorna lista vacia."""
        response = client.get("/api/v1/price-lists/current", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    def test_returns_latest_per_material(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization, test_material, test_material2,
    ):
        """Retorna solo el precio mas reciente por material."""
        # Precio viejo para material 1
        old = PriceList(
            material_id=test_material.id,
            purchase_price=Decimal("100.00"),
            sale_price=Decimal("200.00"),
            organization_id=test_organization.id,
        )
        db_session.add(old)
        db_session.commit()

        # Precio nuevo para material 1 (via API para timestamp posterior)
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material.id),
            "purchase_price": 500.0,
            "sale_price": 800.0,
        }, headers=org_headers)

        # Precio unico para material 2
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material2.id),
            "purchase_price": 300.0,
            "sale_price": 450.0,
        }, headers=org_headers)

        response = client.get("/api/v1/price-lists/current", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

        price_map = {item["material_id"]: item for item in data["items"]}
        assert price_map[str(test_material.id)]["purchase_price"] == 500.0
        assert price_map[str(test_material.id)]["sale_price"] == 800.0
        assert price_map[str(test_material2.id)]["purchase_price"] == 300.0
        assert price_map[str(test_material2.id)]["sale_price"] == 450.0

    def test_org_isolation(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2, test_material,
    ):
        """No retorna precios de otra organizacion."""
        # Crear precio en org1
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material.id),
            "purchase_price": 1000.0,
            "sale_price": 1500.0,
        }, headers=org_headers)

        # Crear material + precio en org2 directamente en DB
        mat2 = Material(
            code="ORG2-001",
            name="Material Org2",
            default_unit="kg",
            organization_id=test_organization2.id,
        )
        db_session.add(mat2)
        db_session.flush()
        price2 = PriceList(
            material_id=mat2.id,
            purchase_price=Decimal("999.00"),
            sale_price=Decimal("999.00"),
            organization_id=test_organization2.id,
        )
        db_session.add(price2)
        db_session.commit()

        # Solo debe ver precios de org1
        response = client.get("/api/v1/price-lists/current", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["material_id"] == str(test_material.id)


# ---------------------------------------------------------------------------
# Tests de aislamiento multi-tenant
# ---------------------------------------------------------------------------

class TestPriceListOrganizationIsolation:
    """Verificar que una organizacion no puede ver precios de otra."""

    def test_cannot_access_other_org_price(
        self, client: TestClient, org_headers: dict,
        db_session: Session, test_organization2,
    ):
        """Precio de otra organizacion retorna 404."""
        # Crear material y precio en org2
        mat = Material(
            code="X-001",
            name="Material Org2",
            default_unit="kg",
            organization_id=test_organization2.id,
        )
        db_session.add(mat)
        db_session.flush()

        price = PriceList(
            material_id=mat.id,
            purchase_price=Decimal("100.00"),
            sale_price=Decimal("200.00"),
            organization_id=test_organization2.id,
        )
        db_session.add(price)
        db_session.commit()
        db_session.refresh(price)

        # Intentar acceder desde org1
        response = client.get(
            f"/api/v1/price-lists/{price.id}", headers=org_headers
        )

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests de tabla de precios
# ---------------------------------------------------------------------------

class TestPriceTable:
    """Tests para GET /api/v1/price-lists/table."""

    def test_table_returns_all_active_materials(
        self, client: TestClient, org_headers: dict,
        test_material, test_material2,
    ):
        """Tabla incluye todos los materiales activos, incluso sin precio."""
        response = client.get("/api/v1/price-lists/table", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        ids = {item["material_id"] for item in data["items"]}
        assert str(test_material.id) in ids
        assert str(test_material2.id) in ids

    def test_table_with_and_without_prices(
        self, client: TestClient, org_headers: dict,
        test_material, test_material2,
    ):
        """Material con precio muestra valores; sin precio muestra null."""
        # Crear precio solo para material 1
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material.id),
            "purchase_price": 1500.0,
            "sale_price": 2500.0,
        }, headers=org_headers)

        response = client.get("/api/v1/price-lists/table", headers=org_headers)

        assert response.status_code == 200
        data = response.json()
        item_map = {i["material_id"]: i for i in data["items"]}

        mat1 = item_map[str(test_material.id)]
        assert mat1["purchase_price"] == 1500.0
        assert mat1["sale_price"] == 2500.0

        mat2 = item_map[str(test_material2.id)]
        assert mat2["purchase_price"] is None
        assert mat2["sale_price"] is None

    def test_table_shows_latest_price(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Si hay multiples precios, muestra el mas reciente."""
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material.id),
            "purchase_price": 100.0,
            "sale_price": 200.0,
        }, headers=org_headers)
        client.post("/api/v1/price-lists", json={
            "material_id": str(test_material.id),
            "purchase_price": 999.0,
            "sale_price": 1999.0,
        }, headers=org_headers)

        response = client.get("/api/v1/price-lists/table", headers=org_headers)
        data = response.json()
        item_map = {i["material_id"]: i for i in data["items"]}

        mat = item_map[str(test_material.id)]
        assert mat["purchase_price"] == 999.0
        assert mat["sale_price"] == 1999.0

    def test_table_filter_by_category(
        self, client: TestClient, org_headers: dict,
        test_material, test_material2,
    ):
        """Filtro por category_id retorna solo materiales de esa categoria."""
        response = client.get("/api/v1/price-lists/table", headers=org_headers)
        all_count = len(response.json()["items"])

        # Filtrar por categoria del material 1
        if test_material.category_id:
            response = client.get(
                f"/api/v1/price-lists/table?category_id={test_material.category_id}",
                headers=org_headers,
            )
            filtered = response.json()["items"]
            assert len(filtered) <= all_count
            for item in filtered:
                assert item["category_id"] == str(test_material.category_id)

    def test_table_includes_material_info(
        self, client: TestClient, org_headers: dict, test_material,
    ):
        """Cada item incluye codigo y nombre del material."""
        response = client.get("/api/v1/price-lists/table", headers=org_headers)
        data = response.json()
        item_map = {i["material_id"]: i for i in data["items"]}

        mat = item_map[str(test_material.id)]
        assert mat["material_code"] == test_material.code
        assert mat["material_name"] == test_material.name
