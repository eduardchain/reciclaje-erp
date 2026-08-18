"""
Tests para DoubleEntry (Pasa Mano) API — workflow de 2 pasos (registrar → liquidar).

Endpoints:
1. POST /double-entries — Registrar (sin efectos financieros)
2. GET /double-entries — Listar con filtros
3. GET /double-entries/{id} — Obtener por UUID
4. GET /double-entries/by-number/{n} — Obtener por numero
5. GET /double-entries/supplier/{id} — Listar por proveedor
6. GET /double-entries/customer/{id} — Listar por cliente
7. PATCH /double-entries/{id}/liquidate — Liquidar (aplicar efectos)
8. PATCH /double-entries/{id}/cancel — Cancelar
9. PATCH /double-entries/{id} — Editar (solo registered)

Business Rules:
- Create: Purchase + Sale registered, SIN balances, SIN MoneyMovements comision
- Liquidate: actualiza balances, crea commission_accrual MoneyMovements
- Cancel registered: trivial (sin reversal)
- Cancel liquidated: revierte balances + comisiones
- Edit: solo registered, revert-and-reapply
- No stock movements en ningun paso
"""
import pytest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.models import (
    ThirdParty,
    Material,
    Purchase,
    Sale,
    DoubleEntry,
    DoubleEntryLine,
    MaterialCategory,
    BusinessUnit,
)
from app.models.money_movement import MoneyMovement
from app.models.sale import SaleCommission
from app.models.third_party_category import ThirdPartyCategory, ThirdPartyCategoryAssignment


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_supplier(db_session, test_organization):
    supplier = ThirdParty(
        id=uuid4(), name="Metal Supplier Co.", identification_number="SUP-001",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(supplier)
    db_session.flush()
    cat = ThirdPartyCategory(name="Proveedor Material", behavior_type="material_supplier", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=supplier.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(supplier)
    return supplier


@pytest.fixture
def test_customer(db_session, test_organization):
    customer = ThirdParty(
        id=uuid4(), name="Customer Industries", identification_number="CUST-001",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(customer)
    db_session.flush()
    cat = ThirdPartyCategory(name="Cliente", behavior_type="customer", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=customer.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_supplier_customer(db_session, test_organization):
    party = ThirdParty(
        id=uuid4(), name="Dual Role Company", identification_number="DUAL-001",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(party)
    db_session.flush()
    cat_sup = ThirdPartyCategory(name="Proveedor Material Dual", behavior_type="material_supplier", organization_id=test_organization.id)
    db_session.add(cat_sup)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=party.id, category_id=cat_sup.id))
    cat_cust = ThirdPartyCategory(name="Cliente Dual", behavior_type="customer", organization_id=test_organization.id)
    db_session.add(cat_cust)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=party.id, category_id=cat_cust.id))
    db_session.commit()
    db_session.refresh(party)
    return party


@pytest.fixture
def test_commission_recipient(db_session, test_organization):
    recipient = ThirdParty(
        id=uuid4(), name="Commission Agent",
        current_balance=Decimal("0.00"),
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(recipient)
    db_session.flush()
    cat = ThirdPartyCategory(name="Proveedor Servicios Comision", behavior_type="service_provider", organization_id=test_organization.id)
    db_session.add(cat)
    db_session.flush()
    db_session.add(ThirdPartyCategoryAssignment(third_party_id=recipient.id, category_id=cat.id))
    db_session.commit()
    db_session.refresh(recipient)
    return recipient


@pytest.fixture
def test_category(db_session, test_organization):
    category = MaterialCategory(
        id=uuid4(), name="Metals",
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)
    return category


@pytest.fixture
def test_business_unit(db_session, test_organization):
    bu = BusinessUnit(
        id=uuid4(), name="Main Unit",
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(bu)
    db_session.commit()
    db_session.refresh(bu)
    return bu


@pytest.fixture
def test_material(db_session, test_organization, test_category, test_business_unit):
    material = Material(
        id=uuid4(), code="COPPER-01", name="Copper Wire", default_unit="kg",
        current_stock=Decimal("0.00"), current_average_cost=Decimal("7500.00"),
        category_id=test_category.id, business_unit_id=test_business_unit.id,
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


@pytest.fixture
def test_material_2(db_session, test_organization, test_category, test_business_unit):
    material = Material(
        id=uuid4(), code="ALUM-01", name="Aluminum Scrap", default_unit="kg",
        current_stock=Decimal("0.00"), current_average_cost=Decimal("3000.00"),
        category_id=test_category.id, business_unit_id=test_business_unit.id,
        organization_id=test_organization.id, is_active=True,
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)
    return material


def _create_payload(supplier_id, customer_id, material_id, **kwargs):
    """Helper para crear payload de doble partida."""
    return {
        "lines": kwargs.get("lines", [
            {
                "material_id": str(material_id),
                "quantity": kwargs.get("quantity", 1000.0),
                "purchase_unit_price": kwargs.get("purchase_price", 8000.00),
                "sale_unit_price": kwargs.get("sale_price", 10000.00),
            }
        ]),
        "supplier_id": str(supplier_id),
        "customer_id": str(customer_id),
        "date": kwargs.get("date", date.today().isoformat()),
        "invoice_number": kwargs.get("invoice_number"),
        "vehicle_plate": kwargs.get("vehicle_plate"),
        "notes": kwargs.get("notes"),
        "commissions": kwargs.get("commissions", []),
    }


# Fixture para crear DP registrada via API
@pytest.fixture
def registered_de(client, org_headers, test_supplier, test_customer, test_material):
    """Crear DP registrada via API."""
    payload = _create_payload(
        test_supplier.id, test_customer.id, test_material.id,
        invoice_number="INV-001", vehicle_plate="ABC-123", notes="Test DP",
    )
    resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
    assert resp.status_code == 201
    return resp.json()


# Fixture para crear DP liquidada (registrar + liquidar via API)
@pytest.fixture
def liquidated_de(client, org_headers, test_supplier, test_customer, test_material):
    """Crear DP registrada y luego liquidarla."""
    payload = _create_payload(
        test_supplier.id, test_customer.id, test_material.id,
        invoice_number="INV-LIQ", notes="Test liquidated",
    )
    resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
    assert resp.status_code == 201
    de_id = resp.json()["id"]

    liq_resp = client.patch(
        f"/api/v1/double-entries/{de_id}/liquidate",
        json={},
        headers=org_headers,
    )
    assert liq_resp.status_code == 200
    return liq_resp.json()


# ============================================================================
# Test Class
# ============================================================================

class TestDoubleEntryAPI:

    # ========================================================================
    # POST — Registrar (sin efectos financieros)
    # ========================================================================

    def test_create_registers_without_financial_effects(
        self, client, org_headers, test_supplier, test_customer, test_material, db_session,
    ):
        """Create → status=registered, balances sin cambiar, Purchase/Sale registered."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            invoice_number="INV-001", vehicle_plate="XYZ-789", notes="Test DP",
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201

        data = resp.json()
        assert data["status"] == "registered"
        assert data["double_entry_number"] == 1
        assert data["invoice_number"] == "INV-001"
        assert data["supplier_name"] == "Metal Supplier Co."
        assert data["customer_name"] == "Customer Industries"

        # Lineas
        assert len(data["lines"]) == 1
        line = data["lines"][0]
        assert line["material_code"] == "COPPER-01"
        assert line["material_unit"] == "kg"  # unidad de medida del material
        assert float(line["quantity"]) == 1000.0
        assert float(data["total_purchase_cost"]) == 1000 * 8000
        assert float(data["total_sale_amount"]) == 1000 * 10000
        assert float(data["profit"]) == 1000 * 2000

        # Balances NO cambiaron
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")

        # Stock NO cambio
        db_session.refresh(test_material)
        assert test_material.current_stock == Decimal("0.00")

        # Purchase y Sale en registered
        purchase = db_session.get(Purchase, data["purchase_id"])
        assert purchase.status == "registered"
        assert purchase.liquidated_at is None
        assert purchase.double_entry_id is not None

        sale = db_session.get(Sale, data["sale_id"])
        assert sale.status == "registered"
        assert sale.liquidated_at is None
        assert sale.warehouse_id is None

    def test_line_includes_material_unit(
        self, client, org_headers, test_supplier, test_customer, db_session, test_organization,
    ):
        """La response de doble partida expone material_unit por linea (kg, unidad, etc.)."""
        unit_material = Material(
            id=uuid4(), code="AC-UNIT", name="Aire Acondicionado", default_unit="unidad",
            current_stock=Decimal("0.00"), current_average_cost=Decimal("0.00"),
            organization_id=test_organization.id, is_active=True,
        )
        db_session.add(unit_material)
        db_session.commit()

        payload = _create_payload(test_supplier.id, test_customer.id, unit_material.id)
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)

        assert resp.status_code == 201
        assert resp.json()["lines"][0]["material_unit"] == "unidad"

    def test_create_multi_line(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_material_2, db_session,
    ):
        """Create con multiples materiales."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            lines=[
                {"material_id": str(test_material.id), "quantity": 1000, "purchase_unit_price": 8000, "sale_unit_price": 10000},
                {"material_id": str(test_material_2.id), "quantity": 500, "purchase_unit_price": 3000, "sale_unit_price": 4000},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201

        data = resp.json()
        assert len(data["lines"]) == 2
        assert float(data["total_purchase_cost"]) == 1000 * 8000 + 500 * 3000
        assert float(data["total_sale_amount"]) == 1000 * 10000 + 500 * 4000
        assert "Copper Wire" in data["materials_summary"]
        assert "Aluminum Scrap" in data["materials_summary"]

        # Balances NO cambiaron
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")

    def test_create_with_commissions_no_financial_effects(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_commission_recipient, db_session,
    ):
        """Create con comisiones → SaleCommission existe, pero SIN MoneyMovement, SIN balance."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            commissions=[{
                "third_party_id": str(test_commission_recipient.id),
                "concept": "Sales Commission",
                "commission_type": "percentage",
                "commission_value": 2.5,
            }],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201

        data = resp.json()
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["concept"] == "Sales Commission"

        sale_total = Decimal("1000") * Decimal("10000")
        expected_comm = sale_total * Decimal("0.025")
        assert float(data["commissions"][0]["commission_amount"]) == float(expected_comm)

        # Comisionista balance NO cambio
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # No hay MoneyMovements
        mm_count = db_session.query(MoneyMovement).filter(
            MoneyMovement.sale_id == data["sale_id"]
        ).count()
        assert mm_count == 0

    def test_create_same_supplier_customer_fails(
        self, client, org_headers, test_supplier_customer, test_material,
    ):
        """Proveedor == cliente → 422."""
        payload = _create_payload(
            test_supplier_customer.id, test_supplier_customer.id, test_material.id,
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_negative_quantity_fails(
        self, client, org_headers, test_supplier, test_customer, test_material,
    ):
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id, quantity=-100,
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_zero_price_fails(
        self, client, org_headers, test_supplier, test_customer, test_material,
    ):
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id, purchase_price=0,
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_empty_lines_fails(
        self, client, org_headers, test_supplier, test_customer,
    ):
        payload = {
            "lines": [], "supplier_id": str(test_supplier.id),
            "customer_id": str(test_customer.id),
            "date": date.today().isoformat(), "commissions": [],
        }
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_duplicate_material_fails(
        self, client, org_headers, test_supplier, test_customer, test_material,
    ):
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            lines=[
                {"material_id": str(test_material.id), "quantity": 500, "purchase_unit_price": 8000, "sale_unit_price": 10000},
                {"material_id": str(test_material.id), "quantity": 300, "purchase_unit_price": 7500, "sale_unit_price": 9500},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_create_invalid_supplier_fails(
        self, client, org_headers, test_customer, test_material,
    ):
        payload = _create_payload(uuid4(), test_customer.id, test_material.id)
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 404
        assert "proveedor" in resp.json()["detail"].lower()

    # ========================================================================
    # PATCH /{id}/liquidate — Liquidar
    # ========================================================================

    def test_liquidate_applies_financial_effects(
        self, client, org_headers, test_supplier, test_customer,
        test_material, db_session, registered_de,
    ):
        """Liquidar → balances cambian, status=liquidated."""
        de_id = registered_de["id"]

        resp = client.patch(
            f"/api/v1/double-entries/{de_id}/liquidate",
            json={},
            headers=org_headers,
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "liquidated"
        assert data["liquidated_at"] is not None

        # Balances actualizados
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        purchase_total = Decimal("1000") * Decimal("8000")
        sale_total = Decimal("1000") * Decimal("10000")
        assert test_supplier.current_balance == -purchase_total
        assert test_customer.current_balance == sale_total

        # Purchase y Sale en liquidated
        purchase = db_session.get(Purchase, data["purchase_id"])
        assert purchase.status == "liquidated"
        assert purchase.liquidated_at is not None

        sale = db_session.get(Sale, data["sale_id"])
        assert sale.status == "liquidated"
        assert sale.liquidated_at is not None

    def test_liquidate_with_commissions(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_commission_recipient, db_session,
    ):
        """Liquidar con comisiones → MoneyMovements creados, balances actualizados."""
        # Crear con comisiones
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            commissions=[{
                "third_party_id": str(test_commission_recipient.id),
                "concept": "Sales Commission",
                "commission_type": "percentage",
                "commission_value": 2.5,
            }],
        )
        create_resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert create_resp.status_code == 201
        de_id = create_resp.json()["id"]

        # Verificar que comisionista no tiene balance aun
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # Liquidar
        liq_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/liquidate",
            json={},
            headers=org_headers,
        )
        assert liq_resp.status_code == 200

        # Comisionista balance actualizado
        db_session.refresh(test_commission_recipient)
        sale_total = Decimal("1000") * Decimal("10000")
        expected_comm = sale_total * Decimal("0.025")
        assert test_commission_recipient.current_balance == -expected_comm

        # MoneyMovement commission_accrual creado
        mm = db_session.query(MoneyMovement).filter(
            MoneyMovement.sale_id == create_resp.json()["sale_id"],
            MoneyMovement.movement_type == "commission_accrual",
        ).first()
        assert mm is not None
        assert mm.status == "confirmed"

    def test_liquidate_with_price_adjustments(
        self, client, org_headers, test_supplier, test_customer,
        test_material, db_session, registered_de,
    ):
        """Liquidar con ajuste de precios → totales recalculados."""
        de_id = registered_de["id"]
        line_id = registered_de["lines"][0]["id"]

        liq_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/liquidate",
            json={
                "lines": [{
                    "line_id": line_id,
                    "purchase_unit_price": 9000,
                    "sale_unit_price": 11000,
                }],
            },
            headers=org_headers,
        )
        assert liq_resp.status_code == 200

        data = liq_resp.json()
        assert data["status"] == "liquidated"
        assert float(data["total_purchase_cost"]) == 1000 * 9000
        assert float(data["total_sale_amount"]) == 1000 * 11000
        assert float(data["profit"]) == 1000 * 2000

        # Balances con nuevos precios
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == -Decimal("9000000")
        assert test_customer.current_balance == Decimal("11000000")

    def test_liquidate_replaces_commissions(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_commission_recipient, db_session,
    ):
        """Liquidar puede reemplazar comisiones existentes."""
        # Crear sin comisiones
        payload = _create_payload(test_supplier.id, test_customer.id, test_material.id)
        create_resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        de_id = create_resp.json()["id"]

        # Liquidar CON comisiones
        liq_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/liquidate",
            json={
                "commissions": [{
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "New Commission",
                    "commission_type": "fixed",
                    "commission_value": 100000,
                }],
            },
            headers=org_headers,
        )
        assert liq_resp.status_code == 200

        data = liq_resp.json()
        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["concept"] == "New Commission"

        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == -Decimal("100000")

    def test_liquidate_non_registered_fails(
        self, client, org_headers, liquidated_de,
    ):
        """Liquidar DP ya liquidada → 400."""
        resp = client.patch(
            f"/api/v1/double-entries/{liquidated_de['id']}/liquidate",
            json={},
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "registered" in resp.json()["detail"].lower()

    def test_liquidate_not_found(self, client, org_headers):
        resp = client.patch(
            f"/api/v1/double-entries/{uuid4()}/liquidate",
            json={},
            headers=org_headers,
        )
        assert resp.status_code == 404

    # ========================================================================
    # PATCH /{id}/cancel — Cancelar
    # ========================================================================

    def test_cancel_registered_trivial(
        self, client, org_headers, test_supplier, test_customer,
        test_material, db_session, registered_de,
    ):
        """Cancelar DP registrada → trivial, sin reversal de balances."""
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert resp.json()["cancelled_at"] is not None

        # Balances siguen en 0 (nunca cambiaron)
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")

        # Purchase y Sale cancelados
        purchase = db_session.get(Purchase, registered_de["purchase_id"])
        assert purchase.status == "cancelled"
        sale = db_session.get(Sale, registered_de["sale_id"])
        assert sale.status == "cancelled"

    def test_cancel_liquidated_reverts_balances(
        self, client, org_headers, test_supplier, test_customer,
        test_material, db_session, liquidated_de,
    ):
        """Cancelar DP liquidada → revierte balances proveedor/cliente."""
        # Verificar que balances estan cambiados
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance != Decimal("0.00")
        assert test_customer.current_balance != Decimal("0.00")

        resp = client.patch(
            f"/api/v1/double-entries/{liquidated_de['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

        # Balances revertidos
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")

    def test_cancel_liquidated_with_commissions_reverts_all(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_commission_recipient, db_session,
    ):
        """Cancelar DP liquidada con comisiones → revierte balances + anula MoneyMovements."""
        # Crear con comisiones
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            commissions=[{
                "third_party_id": str(test_commission_recipient.id),
                "concept": "Sales Commission",
                "commission_type": "percentage",
                "commission_value": 2.5,
            }],
        )
        create_resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        de_id = create_resp.json()["id"]

        # Liquidar
        client.patch(f"/api/v1/double-entries/{de_id}/liquidate", json={}, headers=org_headers)

        # Verificar comisionista tiene balance
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance != Decimal("0.00")

        # Cancelar
        cancel_resp = client.patch(
            f"/api/v1/double-entries/{de_id}/cancel",
            headers=org_headers,
        )
        assert cancel_resp.status_code == 200

        # Todo revertido
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        db_session.refresh(test_commission_recipient)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")
        assert test_commission_recipient.current_balance == Decimal("0.00")

        # MoneyMovement anulado
        mm = db_session.query(MoneyMovement).filter(
            MoneyMovement.sale_id == create_resp.json()["sale_id"],
            MoneyMovement.movement_type == "commission_accrual",
        ).first()
        assert mm is not None
        assert mm.status == "annulled"

    def test_cancel_already_cancelled_fails(
        self, client, org_headers, registered_de,
    ):
        """Cancelar DP ya cancelada → 400."""
        client.patch(f"/api/v1/double-entries/{registered_de['id']}/cancel", headers=org_headers)
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}/cancel",
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "cancelada" in resp.json()["detail"].lower()

    # ========================================================================
    # PATCH /{id} — Editar (solo registered)
    # ========================================================================

    def test_edit_registered_metadata(
        self, client, org_headers, registered_de,
    ):
        """Editar metadata de DP registrada."""
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}",
            json={
                "notes": "Updated notes",
                "invoice_number": "INV-UPDATED",
                "vehicle_plate": "NEW-PLATE",
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Updated notes"
        assert data["invoice_number"] == "INV-UPDATED"
        assert data["vehicle_plate"] == "NEW-PLATE"
        assert data["status"] == "registered"

    def test_edit_registered_lines(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_material_2, db_session, registered_de,
    ):
        """Editar lineas de DP registrada (reemplaza todas)."""
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}",
            json={
                "lines": [
                    {"material_id": str(test_material.id), "quantity": 500, "purchase_unit_price": 9000, "sale_unit_price": 12000},
                    {"material_id": str(test_material_2.id), "quantity": 200, "purchase_unit_price": 4000, "sale_unit_price": 5000},
                ],
            },
            headers=org_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["lines"]) == 2
        assert float(data["total_purchase_cost"]) == 500 * 9000 + 200 * 4000
        assert float(data["total_sale_amount"]) == 500 * 12000 + 200 * 5000

        # Balances siguen en 0
        db_session.refresh(test_supplier)
        db_session.refresh(test_customer)
        assert test_supplier.current_balance == Decimal("0.00")
        assert test_customer.current_balance == Decimal("0.00")

    def test_edit_registered_change_supplier(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_supplier_customer, db_session, registered_de,
    ):
        """Editar proveedor de DP registrada."""
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}",
            json={"supplier_id": str(test_supplier_customer.id)},
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["supplier_id"] == str(test_supplier_customer.id)

    def test_edit_liquidated_fails(
        self, client, org_headers, liquidated_de,
    ):
        """Editar DP liquidada → 400."""
        resp = client.patch(
            f"/api/v1/double-entries/{liquidated_de['id']}",
            json={"notes": "should fail"},
            headers=org_headers,
        )
        assert resp.status_code == 400
        assert "registered" in resp.json()["detail"].lower()

    def test_edit_cancelled_fails(
        self, client, org_headers, registered_de,
    ):
        """Editar DP cancelada → 400."""
        client.patch(f"/api/v1/double-entries/{registered_de['id']}/cancel", headers=org_headers)
        resp = client.patch(
            f"/api/v1/double-entries/{registered_de['id']}",
            json={"notes": "should fail"},
            headers=org_headers,
        )
        assert resp.status_code == 400

    # ========================================================================
    # GET endpoints
    # ========================================================================

    def test_list_double_entries(self, client, org_headers, registered_de):
        resp = client.get("/api/v1/double-entries", headers=org_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == registered_de["id"]

    def test_list_filter_by_status(self, client, org_headers, registered_de, liquidated_de):
        resp = client.get("/api/v1/double-entries?status=registered", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["status"] == "registered"

        resp = client.get("/api/v1/double-entries?status=liquidated", headers=org_headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["status"] == "liquidated"

    def test_list_filter_by_material(
        self, client, org_headers, registered_de, test_material,
    ):
        resp = client.get(
            f"/api/v1/double-entries?material_id={test_material.id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get(
            f"/api/v1/double-entries?material_id={uuid4()}",
            headers=org_headers,
        )
        assert resp.json()["total"] == 0

    def test_list_search(self, client, org_headers, registered_de):
        resp = client.get("/api/v1/double-entries?search=INV-001", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = client.get("/api/v1/double-entries?search=NONEXISTENT", headers=org_headers)
        assert resp.json()["total"] == 0

    def test_get_by_id(self, client, org_headers, registered_de):
        resp = client.get(f"/api/v1/double-entries/{registered_de['id']}", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == registered_de["id"]
        assert resp.json()["status"] == "registered"

    def test_get_by_id_not_found(self, client, org_headers):
        resp = client.get(f"/api/v1/double-entries/{uuid4()}", headers=org_headers)
        assert resp.status_code == 404

    def test_get_by_number(self, client, org_headers, registered_de):
        num = registered_de["double_entry_number"]
        resp = client.get(f"/api/v1/double-entries/by-number/{num}", headers=org_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == registered_de["id"]

    def test_get_by_number_not_found(self, client, org_headers):
        resp = client.get("/api/v1/double-entries/by-number/999", headers=org_headers)
        assert resp.status_code == 404

    def test_list_by_supplier(
        self, client, org_headers, registered_de, test_supplier,
    ):
        resp = client.get(
            f"/api/v1/double-entries/supplier/{test_supplier.id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_by_customer(
        self, client, org_headers, registered_de, test_customer,
    ):
        resp = client.get(
            f"/api/v1/double-entries/customer/{test_customer.id}",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_list_double_entries_by_liquidated_at(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
        db_session,
    ):
        """date_field=liquidated_at filtra por fecha de liquidacion (paridad con P&L decision #42)."""
        from sqlalchemy import update as sa_update

        # Crear DP con date=2026-02-28
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            date="2026-02-28", invoice_number="INV-FEB",
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201
        de_id = resp.json()["id"]

        # Liquidarla
        liq = client.patch(f"/api/v1/double-entries/{de_id}/liquidate", json={}, headers=org_headers)
        assert liq.status_code == 200

        # Forzar liquidated_at = 2026-03-03 directo en DB
        db_session.execute(
            sa_update(DoubleEntry)
            .where(DoubleEntry.id == de_id)
            .values(liquidated_at=datetime(2026, 3, 3, 12, 0))
        )
        db_session.commit()

        # date_field=date con marzo → NO aparece
        r1 = client.get(
            "/api/v1/double-entries?date_from=2026-03-01&date_to=2026-03-31&date_field=date",
            headers=org_headers,
        )
        assert r1.status_code == 200
        assert r1.json()["total"] == 0

        # date_field=liquidated_at con marzo → SI aparece
        r2 = client.get(
            "/api/v1/double-entries?date_from=2026-03-01&date_to=2026-03-31&date_field=liquidated_at",
            headers=org_headers,
        )
        assert r2.status_code == 200
        assert r2.json()["total"] == 1
        assert r2.json()["items"][0]["id"] == de_id

    def test_list_double_entries_date_field_invalid(self, client, org_headers):
        """date_field invalido → 422."""
        resp = client.get("/api/v1/double-entries?date_field=foo", headers=org_headers)
        assert resp.status_code == 422

    def test_list_sort_by_date_asc(
        self, client, org_headers, registered_de, liquidated_de,
    ):
        """Sort server-side por date asc — primera fila = mas antigua."""
        resp = client.get(
            "/api/v1/double-entries?sort_by=date&sort_dir=asc",
            headers=org_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 2
        dates = [it["date"] for it in items]
        assert dates == sorted(dates)

    def test_list_sort_by_invalid_column_falls_back(
        self, client, org_headers, registered_de,
    ):
        """sort_by invalido => fallback silencioso al default (no 422)."""
        resp = client.get(
            "/api/v1/double-entries?sort_by=__hack__&sort_dir=desc",
            headers=org_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestDoubleEntryPerKgCommission:
    """Comision por kilo en doble partida."""

    def test_dp_per_kg_commission(
        self, client, org_headers, test_supplier, test_customer,
        test_material, test_commission_recipient,
    ):
        """DP 1000 kg con comision $10/kg = $10,000."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=1000.0,
            commissions=[
                {
                    "third_party_id": str(test_commission_recipient.id),
                    "concept": "Comision por kilo DP",
                    "commission_type": "per_kg",
                    "commission_value": 10,
                }
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()

        assert len(data["commissions"]) == 1
        assert data["commissions"][0]["commission_type"] == "per_kg"
        # 1000 kg × $10/kg = $10,000
        assert data["commissions"][0]["commission_amount"] == 10000.0


class TestDoubleEntryKpiSums:
    """KPI sums + active_total deben excluir DPs canceladas (paridad con P&L)."""

    def test_kpi_sums_exclude_cancelled(
        self,
        client,
        org_headers,
        test_supplier,
        test_customer,
        test_material,
    ):
        # Crear 2 DPs
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=100.0, purchase_price=80.0, sale_price=100.0,
        )
        client.post("/api/v1/double-entries", json=payload, headers=org_headers).raise_for_status()
        client.post("/api/v1/double-entries", json=payload, headers=org_headers).raise_for_status()

        r = client.get("/api/v1/double-entries", headers=org_headers)
        body = r.json()
        assert body["total"] == 2
        assert body["active_total"] == 2
        # 2 DPs × 100kg × $80 (purchase) = $16,000; × $100 (sale) = $20,000
        assert body["total_purchase_cost_sum"] == 16000.0
        assert body["total_sale_amount_sum"] == 20000.0
        assert body["total_profit_sum"] == 4000.0  # 20k - 16k

        # Cancelar una
        de_id = body["items"][0]["id"]
        client.patch(
            f"/api/v1/double-entries/{de_id}/cancel",
            json={"reason": "test"},
            headers=org_headers,
        ).raise_for_status()

        r = client.get("/api/v1/double-entries", headers=org_headers)
        body = r.json()
        assert body["total"] == 2, "total para paginacion debe incluir canceladas"
        assert body["active_total"] == 1, "active_total para KPI debe excluir canceladas"
        assert body["total_purchase_cost_sum"] == 8000.0, "sum debe excluir DPs canceladas"
        assert body["total_sale_amount_sum"] == 10000.0
        assert body["total_profit_sum"] == 2000.0


class TestDoubleEntryCharges:
    """Cargos en cruces DP (plan bonos-fletes §11): commission | freight | bonus.

    Las comisiones DP son SaleCommission de la venta interna — la columna
    charge_type de v1 las cubre sin migración nueva. El accrual nace al
    liquidar con label parametrizado ("Flete DP #N", "Bono DP #N") y cae en
    la sección Pasa Mano de Rentabilidad por UN (join double_entry_id, #58).
    """

    def _accruals(self, db_session, dp_id):
        from uuid import UUID
        from sqlalchemy import select
        sale_id = db_session.execute(
            select(Sale.id).where(Sale.double_entry_id == UUID(dp_id))
        ).scalar_one()
        return db_session.execute(
            select(MoneyMovement).where(
                MoneyMovement.sale_id == sale_id,
                MoneyMovement.movement_type == "commission_accrual",
            )
        ).scalars().all()

    def test_dp_freight_and_bonus_records_and_accruals(
        self, client, org_headers, db_session,
        test_supplier, test_customer, test_material, test_commission_recipient,
    ):
        """Flete $2/kg × 100 kg + bono fijo $300: records con charge_type al
        crear; al liquidar, 2 accruals con su label y receptor -$500."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=100.0, purchase_price=80.0, sale_price=100.0,
            commissions=[
                {"third_party_id": str(test_commission_recipient.id), "concept": "Flete cruce",
                 "commission_type": "per_kg", "commission_value": 2.0, "charge_type": "freight"},
                {"third_party_id": str(test_commission_recipient.id), "concept": "Bono cruce",
                 "commission_type": "fixed", "commission_value": 300, "charge_type": "bonus"},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201
        data = resp.json()
        by_type = {c["charge_type"]: c for c in data["commissions"]}
        assert by_type["freight"]["commission_amount"] == 200.0
        assert by_type["bonus"]["commission_amount"] == 300.0

        # Registrada: sin accruals todavia (efectos solo al liquidar)
        assert self._accruals(db_session, data["id"]) == []

        liq = client.patch(
            f"/api/v1/double-entries/{data['id']}/liquidate", json={}, headers=org_headers,
        )
        assert liq.status_code == 200

        accruals = self._accruals(db_session, data["id"])
        assert len(accruals) == 2
        prefixes = sorted(m.description.split(" DP #")[0] for m in accruals)
        assert prefixes == ["Bono", "Flete"]
        assert sum(m.amount for m in accruals) == Decimal("500.00")

        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-500.00")

    def test_dp_charges_lower_pasamano_net(
        self, client, org_headers,
        test_supplier, test_customer, test_material, test_commission_recipient,
    ):
        """Rentabilidad por UN: el cargo DP cae en pasamano.commissions y baja
        la neta (gross $2.000 - bono $300 = $1.700)."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=100.0, purchase_price=80.0, sale_price=100.0,
            commissions=[
                {"third_party_id": str(test_commission_recipient.id), "concept": "Bono cruce",
                 "commission_type": "fixed", "commission_value": 300, "charge_type": "bonus"},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201
        client.patch(
            f"/api/v1/double-entries/{resp.json()['id']}/liquidate", json={}, headers=org_headers,
        ).raise_for_status()

        from datetime import timedelta
        report = client.get(
            "/api/v1/reports/profitability-by-business-unit",
            params={
                "date_from": (date.today() - timedelta(days=1)).isoformat(),
                "date_to": (date.today() + timedelta(days=1)).isoformat(),
            },
            headers=org_headers,
        )
        assert report.status_code == 200
        de = report.json()["double_entry"]
        assert de["gross_profit"] == 2000.0
        assert de["commissions"] == 300.0
        assert de["net_profit"] == pytest.approx(1700.0, abs=0.01)

    def test_cancel_dp_annuls_charge_accruals(
        self, client, org_headers, db_session,
        test_supplier, test_customer, test_material, test_commission_recipient,
    ):
        """Cancelar DP liquidada anula los accruals de cargos y restaura el
        balance del receptor (mismo camino que comisiones, #23)."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=100.0, purchase_price=80.0, sale_price=100.0,
            commissions=[
                {"third_party_id": str(test_commission_recipient.id), "concept": "Flete cruce",
                 "commission_type": "fixed", "commission_value": 250, "charge_type": "freight"},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        dp_id = resp.json()["id"]
        client.patch(
            f"/api/v1/double-entries/{dp_id}/liquidate", json={}, headers=org_headers,
        ).raise_for_status()
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("-250.00")

        cancel = client.patch(
            f"/api/v1/double-entries/{dp_id}/cancel",
            json={"reason": "error de captura"},
            headers=org_headers,
        )
        assert cancel.status_code == 200

        accruals = self._accruals(db_session, dp_id)
        assert len(accruals) == 1
        assert accruals[0].status == "annulled"
        db_session.refresh(test_commission_recipient)
        assert test_commission_recipient.current_balance == Decimal("0.00")

    def test_dp_default_charge_type_commission(
        self, client, org_headers, db_session,
        test_supplier, test_customer, test_material, test_commission_recipient,
    ):
        """Compat: sin charge_type el cargo es comision y el accrual conserva
        el label 'Comisión DP #N' historico."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            quantity=100.0, purchase_price=80.0, sale_price=100.0,
            commissions=[
                {"third_party_id": str(test_commission_recipient.id), "concept": "Comercial",
                 "commission_type": "percentage", "commission_value": 1.0},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 201
        assert resp.json()["commissions"][0]["charge_type"] == "commission"

        client.patch(
            f"/api/v1/double-entries/{resp.json()['id']}/liquidate", json={}, headers=org_headers,
        ).raise_for_status()
        accruals = self._accruals(db_session, resp.json()["id"])
        assert accruals[0].description.startswith("Comisión DP #")

    def test_dp_invalid_charge_type_422(
        self, client, org_headers,
        test_supplier, test_customer, test_material, test_commission_recipient,
    ):
        """charge_type fuera del Literal (commission|freight|bonus) → 422."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            commissions=[
                {"third_party_id": str(test_commission_recipient.id), "concept": "Peaje",
                 "commission_type": "fixed", "commission_value": 100, "charge_type": "toll"},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 422

    def test_dp_charge_recipient_requires_service_provider(
        self, client, org_headers,
        test_supplier, test_customer, test_material,
    ):
        """Regla #32 con copy generalizado: receptor sin service_provider → 400
        'receptor del cargo' (test_supplier solo es material_supplier)."""
        payload = _create_payload(
            test_supplier.id, test_customer.id, test_material.id,
            commissions=[
                {"third_party_id": str(test_supplier.id), "concept": "Flete cruce",
                 "commission_type": "fixed", "commission_value": 100, "charge_type": "freight"},
            ],
        )
        resp = client.post("/api/v1/double-entries", json=payload, headers=org_headers)
        assert resp.status_code == 400
        assert "receptor del cargo" in resp.json()["detail"]
