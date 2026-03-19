"""
Tests para comisiones de compra.

Valida: calculo de comisiones, prorrateo al costo del inventario,
actualizacion de balances de comisionistas, y reversion en cancelacion.

Las comisiones de compra NO crean MoneyMovement — solo actualizan
ThirdParty.current_balance y ajustan InventoryMovement.unit_cost.
"""
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.models import (
    ThirdParty,
    Material,
    Warehouse,
    MoneyAccount,
    MaterialCategory,
    BusinessUnit,
    MoneyMovement,
)
from app.models.purchase import PurchaseCommission
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_supplier(db_session, test_organization):
    supplier = ThirdParty(
        id=uuid4(),
        name="Proveedor Comisiones",
        identification_number="COM-SUP-001",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    cat = ThirdPartyCategory(name="Proveedores Material", behavior_type="material_supplier", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=supplier.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_commission_recipient(db_session, test_organization):
    recipient = ThirdParty(
        id=uuid4(),
        name="Comisionista Uno",
        identification_number="COM-REC-001",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(recipient)
    db_session.flush()
    cat = ThirdPartyCategory(name="Servicios Comisionista1", behavior_type="service_provider", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=recipient.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(recipient)
    return recipient


@pytest.fixture
def test_commission_recipient2(db_session, test_organization):
    recipient = ThirdParty(
        id=uuid4(),
        name="Comisionista Dos",
        identification_number="COM-REC-002",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(recipient)
    db_session.flush()
    cat = ThirdPartyCategory(name="Servicios Comisionista2", behavior_type="service_provider", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=recipient.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(recipient)
    return recipient


@pytest.fixture
def test_category(db_session, test_organization):
    category = MaterialCategory(
        id=uuid4(),
        name="Metales Test",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_business_unit(db_session, test_organization):
    bu = BusinessUnit(
        id=uuid4(),
        name="Unidad Test",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(bu)
    db_session.commit()
    db_session.refresh(bu)
    return bu


@pytest.fixture
def test_material(db_session, test_organization, test_category, test_business_unit):
    material = Material(
        id=uuid4(),
        code="MAT-COM-001",
        name="Cobre Comisiones",
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        default_unit="kg",
        current_stock=Decimal("0.0000"),
        current_average_cost=Decimal("0.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_material2(db_session, test_organization, test_category, test_business_unit):
    material = Material(
        id=uuid4(),
        code="MAT-COM-002",
        name="Aluminio Comisiones",
        category_id=test_category.id,
        business_unit_id=test_business_unit.id,
        default_unit="kg",
        current_stock=Decimal("0.0000"),
        current_average_cost=Decimal("0.0000"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_warehouse(db_session, test_organization):
    warehouse = Warehouse(
        id=uuid4(),
        name="Bodega Comisiones",
        address="Calle Test 123",
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(warehouse)
    db_session.commit()
    db_session.refresh(warehouse)
    return warehouse


@pytest.fixture
def test_money_account(db_session, test_organization):
    account = MoneyAccount(
        id=uuid4(),
        name="Cuenta Comisiones",
        account_type="cash",
        current_balance=Decimal("100000.00"),
        organization_id=test_organization.id,
        is_active=True,
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


# ============================================================================
# Tests
# ============================================================================

class TestPurchaseCommissions:
    """Tests para comisiones en compras."""

    def test_create_purchase_with_fixed_commission_and_auto_liquidate(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Comision fija $50 con auto_liquidate. Costo prorrateado = $50.50."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "notes": "Compra con comision fija",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Intermediacion",
                    "commission_type": "fixed",
                    "commission_value": 50,
                }
            ],
            "auto_liquidate": True,
        }

        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # Comision calculada correctamente
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 50.0
        assert data["commissions"][0]["commission_type"] == "fixed"
        assert data["commissions"][0]["third_party_name"] == "Comisionista Uno"

        # Saldo proveedor = -5000 (solo materiales, sin comision)
        db_session.refresh(test_supplier)
        assert test_supplier.current_balance == Decimal("-5000.00")

        # Saldo comisionista = -50 (le debemos)
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-50.00")

        # Costo promedio = (5000 + 50) / 100 = 50.50
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("50.50")) < Decimal("0.01")

        # NO debe existir MoneyMovement de tipo commission_accrual
        accrual_count = db_session.query(MoneyMovement).filter(
            MoneyMovement.movement_type == "commission_accrual",
        ).count()
        assert accrual_count == 0

    def test_create_purchase_with_percentage_commission(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Comision 5% sobre total $10,000 = $500."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 200,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision porcentual",
                    "commission_type": "percentage",
                    "commission_value": 5,
                }
            ],
            "auto_liquidate": True,
        }

        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # 5% de 10000 = 500
        assert data["commissions"][0]["commission_amount"] == 500.0

        # Costo promedio = (10000 + 500) / 200 = 52.50
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("52.50")) < Decimal("0.01")

        # Saldo comisionista = -500
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-500.00")

    def test_proration_between_multiple_lines(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_material2,
        test_warehouse,
    ):
        """
        2 lineas: L1=100kg×$80=$8000 (80%), L2=50kg×$40=$2000 (20%).
        Comision fija $100.
        Prorrateo: L1=$80, L2=$20.
        Costo ajustado L1 = 80 + 80/100 = 80.80
        Costo ajustado L2 = 40 + 20/50 = 40.40
        """
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 80,
                    "warehouse_id": str(test_warehouse.id),
                },
                {
                    "material_id": str(test_material2.id),
                    "quantity": 50,
                    "unit_price": 40,
                    "warehouse_id": str(test_warehouse.id),
                },
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Flete",
                    "commission_type": "fixed",
                    "commission_value": 100,
                }
            ],
            "auto_liquidate": True,
        }

        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201

        # Material 1: costo promedio ≈ 80.80
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("80.80")) < Decimal("0.01")

        # Material 2: costo promedio ≈ 40.40
        db_session.refresh(test_material2)
        assert abs(test_material2.current_average_cost - Decimal("40.40")) < Decimal("0.01")

        # Saldo comisionista = -100
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-100.00")

    def test_multiple_commissions_on_single_purchase(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_commission_recipient2,
        test_material,
        test_warehouse,
    ):
        """2 comisiones: $30 fija a recipient1, $20 fija a recipient2. Total=$50."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Intermediacion",
                    "commission_type": "fixed",
                    "commission_value": 30,
                },
                {
                    "third_party_id": str(test_commission_recipient2.id),
                    "concept": "Transporte",
                    "commission_type": "fixed",
                    "commission_value": 20,
                },
            ],
            "auto_liquidate": True,
        }

        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # 2 comisiones en response
        assert len(data["commissions"]) == 2
        total_comm = sum(c["commission_amount"] for c in data["commissions"])
        assert total_comm == 50.0

        # Saldos individuales
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-30.00")

        db_session.refresh(test_commission_recipient2)
        assert test_commission_recipient2.current_balance == Decimal("-20.00")

        # Costo ajustado = (5000 + 50) / 100 = 50.50
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("50.50")) < Decimal("0.01")

    def test_cancel_liquidated_purchase_reverts_commissions(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Cancelar compra liquidada revierte saldo del comisionista a 0."""
        # Crear con auto_liquidate
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Flete",
                    "commission_type": "fixed",
                    "commission_value": 50,
                }
            ],
            "auto_liquidate": True,
        }

        resp = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert resp.status_code == 201
        purchase_id = resp.json()["id"]

        # Verificar estado pre-cancelacion
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-50.00")

        # Cancelar
        resp_cancel = client.patch(
            f"/api/v1/purchases/{purchase_id}/cancel",
            headers=org_headers,
        )
        assert resp_cancel.status_code == 200

        # Saldo comisionista revertido a 0
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # Costo promedio revertido a 0
        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("0.00")

    def test_registered_purchase_commissions_no_balance_effect(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Compra registered con comisiones: guardadas pero sin efecto en balance."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Intermediacion",
                    "commission_type": "fixed",
                    "commission_value": 50,
                }
            ],
            "auto_liquidate": False,
        }

        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # Comisiones guardadas en response
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 50.0
        assert data["status"] == "registered"

        # Saldo comisionista sigue en 0 (no aplicadas)
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # Costo promedio sigue en 0 (no liquidada)
        db_session.refresh(test_material)
        assert test_material.current_average_cost == Decimal("0.00")

    def test_liquidate_registered_purchase_applies_commissions(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Crear registered, luego liquidar con comisiones. Se aplican al liquidar."""
        # Paso 1: Crear sin auto_liquidate
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "auto_liquidate": False,
        }

        resp = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert resp.status_code == 201
        purchase_id = resp.json()["id"]

        # Paso 2: Liquidar con comisiones
        liquidate_payload = {
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Flete en liquidacion",
                    "commission_type": "fixed",
                    "commission_value": 50,
                }
            ],
        }

        resp_liq = client.patch(
            f"/api/v1/purchases/{purchase_id}/liquidate",
            json=liquidate_payload,
            headers=org_headers,
        )
        assert resp_liq.status_code == 200
        data = resp_liq.json()

        assert data["status"] == "liquidated"
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 50.0

        # Saldo comisionista actualizado
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-50.00")

        # Costo prorrateado aplicado: (5000 + 50) / 100 = 50.50
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("50.50")) < Decimal("0.01")

    def test_edit_registered_purchase_replaces_commissions(
        self,
        client,
        org_headers,
        db_session,
        test_supplier,
        test_commission_recipient,
        test_material,
        test_warehouse,
    ):
        """Editar compra registered reemplaza comisiones (no duplica)."""
        # Paso 1: Crear con comision $50
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision original",
                    "commission_type": "fixed",
                    "commission_value": 50,
                }
            ],
            "auto_liquidate": False,
        }

        resp = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert resp.status_code == 201
        purchase_id = resp.json()["id"]

        # Paso 2: Editar con comision $100 (reemplaza)
        edit_payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision actualizada",
                    "commission_type": "fixed",
                    "commission_value": 100,
                }
            ],
        }

        resp_edit = client.patch(
            f"/api/v1/purchases/{purchase_id}",
            json=edit_payload,
            headers=org_headers,
        )
        assert resp_edit.status_code == 200
        data = resp_edit.json()

        # Solo 1 comision (reemplazada, no duplicada)
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 100.0
        assert data["commissions"][0]["concept"] == "Comision actualizada"

        # Saldo sigue en 0 (no liquidada)
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # Verificar en BD que no hay comisiones huerfanas
        comm_count = db_session.query(PurchaseCommission).filter(
            PurchaseCommission.purchase_id == purchase_id,
        ).count()
        assert comm_count == 1


class TestPerKgCommission:
    """Tests para comision tipo per_kg."""

    def test_purchase_per_kg_commission(
        self, client, org_headers, db_session,
        test_supplier, test_commission_recipient, test_material, test_warehouse,
    ):
        """Comision per_kg: $5/kg × 100 kg = $500, prorrateada al costo."""
        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {
                    "material_id": str(test_material.id),
                    "quantity": 100,
                    "unit_price": 50,
                    "warehouse_id": str(test_warehouse.id),
                }
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision por kilo",
                    "commission_type": "per_kg",
                    "commission_value": 5,
                }
            ],
            "auto_liquidate": True,
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # Comision = 100 kg × $5/kg = $500
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_amount"] == 500.0
        assert data["commissions"][0]["commission_type"] == "per_kg"

        # Saldo comisionista = -500
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-500.00")

        # Costo prorrateado = (5000 + 500) / 100 = 55.00
        db_session.refresh(test_material)
        assert abs(test_material.current_average_cost - Decimal("55.00")) < Decimal("0.01")

    def test_purchase_per_kg_multiple_lines(
        self, client, org_headers, db_session,
        test_supplier, test_commission_recipient, test_material, test_warehouse, test_organization,
    ):
        """per_kg con multiples lineas: suma todas las cantidades."""
        # Crear segundo material
        from app.models import MaterialCategory
        cat2 = MaterialCategory(name="Cat2 PKG", organization_id=test_organization.id)
        db_session.add(cat2)
        db_session.flush()
        mat2 = Material(
            name="Hierro PKG", code="PKG-002", category_id=cat2.id,
            organization_id=test_organization.id,
            current_stock=Decimal("0"), current_average_cost=Decimal("0"),
        )
        db_session.add(mat2)
        db_session.commit()
        db_session.refresh(mat2)

        payload = {
            "supplier_id": str(test_supplier.id),
            "date": "2026-03-14T12:00:00",
            "lines": [
                {"material_id": str(test_material.id), "quantity": 300, "unit_price": 50, "warehouse_id": str(test_warehouse.id)},
                {"material_id": str(mat2.id), "quantity": 200, "unit_price": 40, "warehouse_id": str(test_warehouse.id)},
            ],
            "commissions": [
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision PKG",
                    "commission_type": "per_kg",
                    "commission_value": 10,
                }
            ],
            "auto_liquidate": True,
        }
        response = client.post("/api/v1/purchases", json=payload, headers=org_headers)
        assert response.status_code == 201
        data = response.json()

        # total_quantity = 300 + 200 = 500 kg × $10/kg = $5,000
        assert data["commissions"][0]["commission_amount"] == 5000.0
