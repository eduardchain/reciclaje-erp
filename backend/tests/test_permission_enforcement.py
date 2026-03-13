"""Tests para verificar que require_permission() bloquea endpoints correctamente.

Estrategia: test_user es admin en test_organization (org_headers) y
viewer en test_organization2 (org_headers2). Viewer solo tiene permisos
de lectura, asi que cualquier endpoint de escritura debe retornar 403.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.models.organization import Organization


class TestPurchasePermissions:
    """Viewer no puede crear/editar/liquidar/cancelar compras."""

    def test_viewer_can_list_purchases(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/purchases", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_purchase(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/purchases", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestSalePermissions:
    """Viewer no puede crear/editar/liquidar/cancelar ventas."""

    def test_viewer_can_list_sales(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/sales", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_sale(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/sales", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestDoubleEntryPermissions:
    """Viewer no puede crear/editar/liquidar/cancelar doble partida."""

    def test_viewer_can_list_double_entries(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/double-entries", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_double_entry(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/double-entries", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestMaterialPermissions:
    """Viewer no puede crear/editar/eliminar materiales."""

    def test_viewer_can_list_materials(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/materials", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_material(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/materials", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()

    def test_viewer_cannot_delete_material(self, client: TestClient, org_headers2: dict):
        r = client.delete(f"/api/v1/materials/{uuid4()}", headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestThirdPartyPermissions:
    """Viewer no puede crear/editar/eliminar terceros."""

    def test_viewer_can_list_third_parties(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/third-parties", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_third_party(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/third-parties", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestWarehousePermissions:
    """Viewer no puede crear/editar/eliminar bodegas."""

    def test_viewer_can_list_warehouses(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/warehouses", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_warehouse(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/warehouses", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestTreasuryPermissions:
    """Viewer puede ver movimientos pero no crear."""

    def test_viewer_can_list_movements(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/money-movements", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_expense(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/money-movements/expense", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()

    def test_viewer_cannot_create_supplier_payment(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/money-movements/supplier-payment", json={}, headers=org_headers2)
        assert r.status_code == 403


class TestMoneyAccountPermissions:
    """Viewer puede ver cuentas pero no gestionar."""

    def test_viewer_can_list_accounts(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/money-accounts", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_account(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/money-accounts", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestInventoryPermissions:
    """Viewer puede ver inventario pero no ajustar."""

    def test_viewer_can_view_stock(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/inventory/stock", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_adjust_stock(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/inventory/adjustments/increase", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()

    def test_viewer_cannot_transfer(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/inventory/adjustments/warehouse-transfer", json={}, headers=org_headers2)
        assert r.status_code == 403


class TestTransformationPermissions:
    """Viewer puede ver transformaciones pero no crear."""

    def test_viewer_can_list_transformations(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/inventory/transformations", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_transformation(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/inventory/transformations", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestPriceListPermissions:
    """Viewer puede ver precios pero no editar."""

    def test_viewer_can_list_prices(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/price-lists", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_price(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/price-lists", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestReportPermissions:
    """Viewer puede ver reportes."""

    def test_viewer_can_view_balance_sheet(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/reports/balance-sheet", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_view_audit(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/reports/audit-balances", headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestExpenseCategoryPermissions:
    """Viewer no tiene acceso a categorias de gasto (treasury.manage_expenses)."""

    def test_viewer_cannot_list_expense_categories(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/expense-categories", headers=org_headers2)
        assert r.status_code == 403


class TestFixedAssetPermissions:
    """Viewer puede ver activos fijos pero no gestionar."""

    def test_viewer_can_list_fixed_assets(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/fixed-assets/", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_fixed_asset(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/fixed-assets/", json={}, headers=org_headers2)
        assert r.status_code == 403
        assert "permisos insuficientes" in r.json()["detail"].lower()


class TestBusinessUnitPermissions:
    """Viewer puede ver unidades de negocio (materials.view)."""

    def test_viewer_can_list_business_units(self, client: TestClient, org_headers2: dict):
        r = client.get("/api/v1/business-units", headers=org_headers2)
        assert r.status_code == 200

    def test_viewer_cannot_create_business_unit(self, client: TestClient, org_headers2: dict):
        r = client.post("/api/v1/business-units", json={}, headers=org_headers2)
        assert r.status_code == 403


class TestAdminBypassesAll:
    """Admin puede acceder a todos los endpoints protegidos."""

    def test_admin_can_list_purchases(self, client: TestClient, org_headers: dict):
        r = client.get("/api/v1/purchases", headers=org_headers)
        assert r.status_code == 200

    def test_admin_can_list_expense_categories(self, client: TestClient, org_headers: dict):
        r = client.get("/api/v1/expense-categories", headers=org_headers)
        assert r.status_code == 200

    def test_admin_can_view_audit(self, client: TestClient, org_headers: dict):
        r = client.get("/api/v1/reports/audit-balances", headers=org_headers)
        assert r.status_code == 200
