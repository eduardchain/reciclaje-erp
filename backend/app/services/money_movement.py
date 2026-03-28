"""
Operaciones CRUD para MoneyMovement (Movimientos de Dinero).

Modulo independiente de la liquidacion de compras/ventas.
Cada metodo publico corresponde a un tipo de movimiento:
- pay_supplier: Pago a proveedor
- collect_from_customer: Cobro a cliente
- create_expense: Gasto operativo
- create_service_income: Ingreso por servicio
- create_transfer: Transferencia entre cuentas
- create_capital_injection: Aporte de capital
- create_capital_return: Retiro de capital
- pay_commission: Pago de comision
- pay_asset: Pago de activo fijo
- annul: Anular movimiento con reversion de saldos
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func, text, or_, cast, String
from sqlalchemy.orm import Session, joinedload

from app.models.money_movement import MoneyMovement, VALID_MOVEMENT_TYPES
from app.models.money_account import MoneyAccount
from app.models.third_party import ThirdParty
from app.models.expense_category import ExpenseCategory
from app.models.purchase import Purchase
from app.models.sale import Sale
from app.schemas.money_movement import (
    SupplierPaymentCreate,
    CustomerCollectionCreate,
    ExpenseCreate,
    ServiceIncomeCreate,
    TransferCreate,
    CapitalInjectionCreate,
    CapitalReturnCreate,
    CommissionPaymentCreate,
    ProvisionDepositCreate,
    ProvisionExpenseCreate,
    AdvancePaymentCreate,
    AdvanceCollectionCreate,
    AssetPaymentCreate,
    ExpenseAccrualCreate,
    MoneyMovementResponse,
)


# Tipos de movimiento cuya clasificacion (categoria + UN) es editable
EDITABLE_EXPENSE_TYPES = {
    "expense", "expense_accrual", "provision_expense",
    "deferred_expense", "depreciation_expense",
}


class CRUDMoneyMovement:
    """
    Operaciones para movimientos de dinero en tesoreria.

    Cada movimiento afecta exactamente UNA cuenta.
    Las transferencias crean un par vinculado (transfer_out + transfer_in).
    La anulacion revierte todos los efectos en saldos.
    """

    # ======================================================================
    # Metodos publicos — uno por tipo de operacion
    # ======================================================================

    def pay_supplier(
        self,
        db: Session,
        data: SupplierPaymentCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Pago a proveedor.

        Efectos:
        - account.current_balance -= amount
        - supplier.current_balance += amount (hacia 0, reduce deuda)

        Validaciones:
        - Tercero debe existir y ser is_supplier=True o is_liability=True
        - Cuenta debe tener fondos suficientes
        - Si purchase_id, compra debe pertenecer al proveedor
        """
        # Validaciones
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        supplier = self._validate_third_party(db, data.supplier_id, organization_id, require_behavior=["material_supplier", "service_provider", "liability"])

        if data.purchase_id:
            self._validate_purchase(db, data.purchase_id, organization_id, supplier_id=data.supplier_id)

        # Crear movimiento
        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="payment_to_supplier",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Pago a {supplier.name}",
            third_party_id=data.supplier_id,
            purchase_id=data.purchase_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        # Aplicar efectos
        account.current_balance -= data.amount
        supplier.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def collect_from_customer(
        self,
        db: Session,
        data: CustomerCollectionCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Cobro a cliente.

        Efectos:
        - account.current_balance += amount
        - customer.current_balance -= amount (hacia 0, reduce lo que nos deben)

        Validaciones:
        - Tercero debe existir y ser is_customer=True
        - Si sale_id, venta debe pertenecer al cliente
        """
        account = self._validate_account(db, data.account_id, organization_id)
        customer = self._validate_third_party(db, data.customer_id, organization_id, require_behavior=["customer"])

        if data.sale_id:
            self._validate_sale(db, data.sale_id, organization_id, customer_id=data.customer_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="collection_from_client",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Cobro a {customer.name}",
            third_party_id=data.customer_id,
            sale_id=data.sale_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        # Aplicar efectos
        account.current_balance += data.amount
        customer.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_expense(
        self,
        db: Session,
        data: ExpenseCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Gasto operativo.

        Efectos:
        - account.current_balance -= amount

        Validaciones:
        - Categoria de gasto debe existir
        - Cuenta debe tener fondos suficientes
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        self._validate_expense_category(db, data.expense_category_id, organization_id)

        if data.third_party_id:
            self._validate_third_party(db, data.third_party_id, organization_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="expense",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description,
            expense_category_id=data.expense_category_id,
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
            business_unit_id=data.business_unit_id,
            applicable_business_unit_ids=[str(uid) for uid in data.applicable_business_unit_ids] if data.applicable_business_unit_ids else None,
        )

        # Aplicar efecto
        account.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_service_income(
        self,
        db: Session,
        data: ServiceIncomeCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Ingreso por servicio.

        Efectos:
        - account.current_balance += amount
        """
        account = self._validate_account(db, data.account_id, organization_id)

        if data.third_party_id:
            self._validate_third_party(db, data.third_party_id, organization_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="service_income",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description,
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_transfer(
        self,
        db: Session,
        data: TransferCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Transferencia entre cuentas — crea par de movimientos.

        Efectos:
        - source_account.current_balance -= amount
        - destination_account.current_balance += amount

        Validaciones:
        - Ambas cuentas deben pertenecer a la organizacion
        - Cuentas deben ser diferentes
        - Cuenta origen debe tener fondos suficientes

        Retorna el movimiento transfer_out (el transfer_in se puede consultar via transfer_pair_id).
        """
        if data.source_account_id == data.destination_account_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Las cuentas origen y destino deben ser diferentes",
            )

        source = self._validate_account(db, data.source_account_id, organization_id, require_funds=data.amount)
        destination = self._validate_account(db, data.destination_account_id, organization_id)

        # Crear movimiento de salida (transfer_out)
        movement_out = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="transfer_out",
            amount=data.amount,
            account_id=data.source_account_id,
            date=data.date,
            description=data.description,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        # Crear movimiento de entrada (transfer_in) con numero separado
        movement_in = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="transfer_in",
            amount=data.amount,
            account_id=data.destination_account_id,
            date=data.date,
            description=data.description,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        # Vincular el par
        movement_out.transfer_pair_id = movement_in.id
        movement_in.transfer_pair_id = movement_out.id

        # Aplicar efectos
        source.current_balance -= data.amount
        destination.current_balance += data.amount

        db.commit()
        db.refresh(movement_out)
        return movement_out

    def create_capital_injection(
        self,
        db: Session,
        data: CapitalInjectionCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Aporte de capital.

        Efectos:
        - account.current_balance += amount
        - investor.current_balance -= amount (le debemos mas)
        """
        account = self._validate_account(db, data.account_id, organization_id)
        investor = self._validate_third_party(db, data.investor_id, organization_id, require_behavior=["investor"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="capital_injection",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Aporte de capital de {investor.name}",
            third_party_id=data.investor_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance += data.amount
        investor.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_capital_return(
        self,
        db: Session,
        data: CapitalReturnCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Retiro de capital.

        Efectos:
        - account.current_balance -= amount
        - investor.current_balance += amount (le debemos menos)
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        investor = self._validate_third_party(db, data.investor_id, organization_id, require_behavior=["investor"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="capital_return",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Retiro de capital de {investor.name}",
            third_party_id=data.investor_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount
        investor.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def pay_commission(
        self,
        db: Session,
        data: CommissionPaymentCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Pago de comision.

        Efectos:
        - account.current_balance -= amount
        - third_party.current_balance += amount (hacia 0, reduce deuda)
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        third_party = self._validate_third_party(db, data.third_party_id, organization_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="commission_payment",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Pago comision a {third_party.name}",
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount
        third_party.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def deposit_to_provision(
        self,
        db: Session,
        data: ProvisionDepositCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Deposito a provision.

        Efectos:
        - account.current_balance -= amount
        - provision.current_balance -= amount (negativo = fondos disponibles)
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        provision = self._validate_third_party(db, data.provision_id, organization_id, require_behavior=["provision"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="provision_deposit",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Deposito a provision {provision.name}",
            third_party_id=data.provision_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount
        provision.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_provision_expense(
        self,
        db: Session,
        data: ProvisionExpenseCreate,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Gasto desde provision — NO afecta cuentas de dinero.

        Efectos:
        - provision.current_balance += amount (reduce fondos disponibles)

        Validaciones:
        - Provision no debe estar en sobregiro (balance > 0)
        - Provision debe tener fondos suficientes (abs(balance) >= amount)
        """
        provision = self._validate_third_party(db, data.provision_id, organization_id, require_behavior=["provision"])
        self._validate_expense_category(db, data.expense_category_id, organization_id)

        # Validar fondos de provision
        if provision.current_balance > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Provision '{provision.name}' esta en sobregiro (balance: ${provision.current_balance}). No se pueden registrar mas gastos.",
            )
        available = abs(provision.current_balance)
        if available < data.amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fondos insuficientes en provision '{provision.name}'. Disponible: ${available}, Requerido: ${data.amount}",
            )

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="provision_expense",
            amount=data.amount,
            account_id=None,
            date=data.date,
            description=data.description,
            third_party_id=data.provision_id,
            expense_category_id=data.expense_category_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
            business_unit_id=data.business_unit_id,
            applicable_business_unit_ids=[str(uid) for uid in data.applicable_business_unit_ids] if data.applicable_business_unit_ids else None,
        )

        provision.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Anticipos
    # ======================================================================

    def pay_advance(
        self,
        db: Session,
        data: "AdvancePaymentCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Anticipo a proveedor.

        Efectos:
        - account.current_balance -= amount
        - supplier.current_balance += amount (proveedor nos debe)
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        supplier = self._validate_third_party(db, data.supplier_id, organization_id, require_behavior=["material_supplier", "service_provider", "liability"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="advance_payment",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Anticipo a {supplier.name}",
            third_party_id=data.supplier_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount
        supplier.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def collect_advance(
        self,
        db: Session,
        data: "AdvanceCollectionCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Anticipo de cliente.

        Efectos:
        - account.current_balance += amount
        - customer.current_balance -= amount (nosotros debemos al cliente)
        """
        account = self._validate_account(db, data.account_id, organization_id)
        customer = self._validate_third_party(db, data.customer_id, organization_id, require_behavior=["customer"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="advance_collection",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Anticipo de {customer.name}",
            third_party_id=data.customer_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance += data.amount
        customer.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Pago de activo fijo
    # ======================================================================

    def pay_asset(
        self,
        db: Session,
        data: "AssetPaymentCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Pago de activo fijo.

        Efectos:
        - account.current_balance -= amount
        (tercero es solo referencia informativa, NO afecta su balance)
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)

        if data.third_party_id:
            self._validate_third_party(db, data.third_party_id, organization_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="asset_payment",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description,
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            evidence_url=data.evidence_url,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Gasto causado (pasivo)
    # ======================================================================

    def create_expense_accrual(
        self,
        db: Session,
        data: "ExpenseAccrualCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Gasto causado (pasivo) — NO mueve dinero de ninguna cuenta.

        Efectos:
        - third_party.current_balance -= amount (le debemos mas)
        - Aparece en P&L como gasto operativo

        Validaciones:
        - Tercero debe existir y estar activo (cualquier tipo)
        - Categoria de gasto debe existir
        """
        third_party = self._validate_third_party(db, data.third_party_id, organization_id)
        self._validate_expense_category(db, data.expense_category_id, organization_id)

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="expense_accrual",
            amount=data.amount,
            account_id=None,
            date=data.date,
            description=data.description,
            third_party_id=data.third_party_id,
            expense_category_id=data.expense_category_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
            business_unit_id=data.business_unit_id,
            applicable_business_unit_ids=[str(uid) for uid in data.applicable_business_unit_ids] if data.applicable_business_unit_ids else None,
        )

        # Efecto: tercero nos debe mas (balance negativo = le debemos)
        third_party.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Pago / cobro a tercero generico
    # ======================================================================

    def pay_generic(
        self,
        db: Session,
        data: "GenericPaymentCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Pago a tercero generico — account(-), third_party.balance(+).

        Efectos:
        - account.current_balance -= amount
        - third_party.current_balance += amount
        """
        account = self._validate_account(db, data.account_id, organization_id, require_funds=data.amount)
        tp = self._validate_third_party(db, data.third_party_id, organization_id, require_behavior=["generic"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="payment_to_generic",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Pago a {tp.name}",
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance -= data.amount
        tp.current_balance += data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def collect_from_generic(
        self,
        db: Session,
        data: "GenericCollectionCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Cobro a tercero generico — account(+), third_party.balance(-).

        Efectos:
        - account.current_balance += amount
        - third_party.current_balance -= amount
        """
        account = self._validate_account(db, data.account_id, organization_id)
        tp = self._validate_third_party(db, data.third_party_id, organization_id, require_behavior=["generic"])

        movement = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="collection_from_generic",
            amount=data.amount,
            account_id=data.account_id,
            date=data.date,
            description=data.description or f"Cobro a {tp.name}",
            third_party_id=data.third_party_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        account.current_balance += data.amount
        tp.current_balance -= data.amount

        db.commit()
        db.refresh(movement)
        return movement

    def create_tp_transfer(
        self,
        db: Session,
        data: "ThirdPartyTransferCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """
        Transferencia entre terceros — cruce de cuentas sin mover dinero.

        Un tercero paga directamente a otro. NO toca cuentas bancarias.
        Crea par vinculado: tp_transfer_out + tp_transfer_in.

        Efectos:
        - source.current_balance += amount (se le abona, reduce deuda)
        - destination.current_balance -= amount (se le cobra, aumenta deuda)
        """
        if data.source_third_party_id == data.destination_third_party_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Los terceros origen y destino deben ser diferentes",
            )

        source = self._validate_third_party(db, data.source_third_party_id, organization_id)
        if source.is_system_entity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El tercero '{source.name}' es una entidad del sistema y no puede participar en transferencias",
            )

        destination = self._validate_third_party(db, data.destination_third_party_id, organization_id)
        if destination.is_system_entity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El tercero '{destination.name}' es una entidad del sistema y no puede participar en transferencias",
            )

        # Crear movimiento de salida (source — se le abona)
        movement_out = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="tp_transfer_out",
            amount=data.amount,
            account_id=None,
            date=data.date,
            description=data.description,
            third_party_id=data.source_third_party_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        # Crear movimiento de entrada (destination — se le cobra)
        movement_in = self._create_movement(
            db=db,
            organization_id=organization_id,
            movement_type="tp_transfer_in",
            amount=data.amount,
            account_id=None,
            date=data.date,
            description=data.description,
            third_party_id=data.destination_third_party_id,
            reference_number=data.reference_number,
            notes=data.notes,
            user_id=user_id,
        )

        # Vincular el par
        movement_out.transfer_pair_id = movement_in.id
        movement_in.transfer_pair_id = movement_out.id

        # Aplicar efectos: source paga (balance baja), dest recibe (balance sube)
        source.current_balance -= data.amount
        destination.current_balance += data.amount

        db.commit()
        db.refresh(movement_out)
        return movement_out

    def adjust_tp_credit(
        self,
        db: Session,
        data: "ThirdPartyAdjustmentCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """Ajuste credito: saldo sube (tercero con saldo negativo hacia cero)."""
        tp = self._validate_third_party(db, data.third_party_id, organization_id)
        if tp.current_balance >= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use ajuste debito para terceros con saldo positivo",
            )
        if data.amount > abs(tp.current_balance):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Monto ({data.amount}) excede saldo pendiente ({abs(tp.current_balance)})",
            )

        movement = self._create_movement(
            db=db, organization_id=organization_id,
            movement_type="tp_adjustment_credit", amount=data.amount,
            account_id=None, date=data.date, description=data.description,
            third_party_id=data.third_party_id, notes=data.notes, user_id=user_id,
        )
        movement.adjustment_class = data.adjustment_class

        tp.current_balance += data.amount
        db.commit()
        db.refresh(movement)
        return movement

    def adjust_tp_debit(
        self,
        db: Session,
        data: "ThirdPartyAdjustmentCreate",
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> MoneyMovement:
        """Ajuste debito: saldo baja (tercero con saldo positivo hacia cero)."""
        tp = self._validate_third_party(db, data.third_party_id, organization_id)
        if tp.current_balance <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Use ajuste credito para terceros con saldo negativo",
            )
        if data.amount > tp.current_balance:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Monto ({data.amount}) excede saldo pendiente ({tp.current_balance})",
            )

        movement = self._create_movement(
            db=db, organization_id=organization_id,
            movement_type="tp_adjustment_debit", amount=data.amount,
            account_id=None, date=data.date, description=data.description,
            third_party_id=data.third_party_id, notes=data.notes, user_id=user_id,
        )
        movement.adjustment_class = data.adjustment_class

        tp.current_balance -= data.amount
        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Anulacion
    # ======================================================================

    def annul(
        self,
        db: Session,
        movement_id: UUID,
        reason: str,
        organization_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> tuple[MoneyMovement, list[str]]:
        """
        Anular un movimiento confirmado, revirtiendo todos los efectos.

        Si el movimiento es parte de una transferencia, anula el par tambien.
        NO crea movimiento inverso — solo revierte saldos y cambia status.

        Retorna: (movimiento, warnings)
        """
        warnings: list[str] = []
        movement = self._get_or_404(db, movement_id, organization_id)

        if movement.status == "annulled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El movimiento ya esta anulado",
            )

        # Movimientos generados por Activos Fijos no se anulan desde Tesorería
        ASSET_MOVEMENT_TYPES = {"asset_payment", "depreciation_expense", "asset_purchase"}
        if movement.movement_type in ASSET_MOVEMENT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede anular un movimiento generado por Activos Fijos. "
                "Use la opcion Cancelar Activo desde el modulo de Activos Fijos.",
            )

        now = datetime.now(timezone.utc)

        # Revertir efectos del movimiento
        self._reverse_effects(db, movement)

        # Marcar como anulado
        movement.status = "annulled"
        movement.annulled_reason = reason
        movement.annulled_at = now
        movement.annulled_by = user_id

        # Si es transferencia, anular el par
        if movement.transfer_pair_id:
            pair = db.get(MoneyMovement, movement.transfer_pair_id)
            if pair and pair.status == "confirmed":
                self._reverse_effects(db, pair)
                pair.status = "annulled"
                pair.annulled_reason = reason
                pair.annulled_at = now
                pair.annulled_by = user_id

        # Warning si provision_deposit deja provision en sobregiro
        if movement.movement_type == "provision_deposit" and movement.third_party_id:
            provision = db.get(ThirdParty, movement.third_party_id)
            if provision and provision.current_balance > 0:
                warnings.append(
                    f"La provision '{provision.name}' quedo en sobregiro "
                    f"(balance: ${provision.current_balance}). "
                    f"No se podran registrar gastos hasta depositar fondos."
                )

        db.commit()
        db.refresh(movement)
        return movement, warnings

    # ======================================================================
    # Edicion de clasificacion
    # ======================================================================

    def update_classification(
        self,
        db: Session,
        movement_id: UUID,
        organization_id: UUID,
        expense_category_id: UUID,
        business_unit_id: Optional[UUID] = None,
        applicable_business_unit_ids: Optional[list[str]] = None,
    ) -> MoneyMovement:
        """
        Editar clasificacion (categoria de gasto y unidad de negocio) en movimientos tipo gasto.

        Solo movimientos confirmed de 5 tipos de gasto.
        No modifica montos, cuentas ni terceros — solo campos de clasificacion.
        """
        movement = self._get_or_404(db, movement_id, organization_id)

        if movement.status == "annulled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede editar un movimiento anulado",
            )

        if movement.movement_type not in EDITABLE_EXPENSE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se puede editar la clasificacion de movimientos tipo gasto",
            )

        # Validar que la categoria existe y pertenece a la org
        self._validate_expense_category(db, expense_category_id, organization_id)

        # Aplicar cambios de clasificacion
        movement.expense_category_id = expense_category_id
        movement.business_unit_id = business_unit_id
        movement.applicable_business_unit_ids = applicable_business_unit_ids

        db.commit()
        db.refresh(movement)
        return movement

    # ======================================================================
    # Queries
    # ======================================================================

    def get(
        self,
        db: Session,
        movement_id: UUID,
        organization_id: UUID,
    ) -> Optional[MoneyMovement]:
        """Obtener movimiento por ID con eager loading."""
        stmt = (
            select(MoneyMovement)
            .where(
                MoneyMovement.id == movement_id,
                MoneyMovement.organization_id == organization_id,
            )
            .options(
                joinedload(MoneyMovement.account),
                joinedload(MoneyMovement.third_party),
                joinedload(MoneyMovement.expense_category),
                joinedload(MoneyMovement.business_unit),
            )
        )
        return db.scalar(stmt)

    def get_or_404(
        self,
        db: Session,
        movement_id: UUID,
        organization_id: UUID,
    ) -> MoneyMovement:
        """Obtener movimiento o lanzar 404."""
        movement = self.get(db, movement_id, organization_id)
        if not movement:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movimiento no encontrado",
            )
        return movement

    def get_by_number(
        self,
        db: Session,
        movement_number: int,
        organization_id: UUID,
    ) -> Optional[MoneyMovement]:
        """Obtener movimiento por numero secuencial."""
        stmt = (
            select(MoneyMovement)
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.movement_number == movement_number,
            )
            .options(
                joinedload(MoneyMovement.account),
                joinedload(MoneyMovement.third_party),
                joinedload(MoneyMovement.expense_category),
            )
        )
        return db.scalar(stmt)

    def get_multi(
        self,
        db: Session,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
        movement_type: Optional[str] = None,
        status_filter: Optional[str] = None,
        account_id: Optional[UUID] = None,
        third_party_id: Optional[UUID] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        search: Optional[str] = None,
        allowed_account_ids: Optional[List[UUID]] = None,
    ) -> tuple[List[MoneyMovement], int]:
        """Listar movimientos con filtros y paginacion."""
        query = select(MoneyMovement).where(
            MoneyMovement.organization_id == organization_id
        )

        if allowed_account_ids is not None:
            query = query.where(
                (MoneyMovement.account_id.in_(allowed_account_ids))
                | (MoneyMovement.account_id.is_(None))
            )
        if movement_type:
            query = query.where(MoneyMovement.movement_type == movement_type)
        if status_filter:
            query = query.where(MoneyMovement.status == status_filter)
        if account_id:
            query = query.where(MoneyMovement.account_id == account_id)
        if third_party_id:
            query = query.where(MoneyMovement.third_party_id == third_party_id)
        if date_from:
            query = query.where(MoneyMovement.date >= date_from)
        if date_to:
            query = query.where(MoneyMovement.date < date_to)
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    MoneyMovement.description.ilike(search_term),
                    MoneyMovement.reference_number.ilike(search_term),
                    cast(MoneyMovement.movement_number, String).ilike(search_term),
                )
            )

        # Total count
        count_query = select(func.count()).select_from(query.subquery())
        total = db.scalar(count_query)

        # Aplicar orden y paginacion
        query = (
            query.options(
                joinedload(MoneyMovement.account),
                joinedload(MoneyMovement.third_party),
                joinedload(MoneyMovement.expense_category),
            )
            .order_by(MoneyMovement.date.desc(), MoneyMovement.movement_number.desc())
            .offset(skip)
            .limit(limit)
        )

        movements = list(db.scalars(query).unique().all())
        return movements, total

    def get_by_account(
        self,
        db: Session,
        account_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[MoneyMovement], int]:
        """Movimientos de una cuenta especifica."""
        return self.get_multi(
            db=db,
            organization_id=organization_id,
            account_id=account_id,
            skip=skip,
            limit=limit,
        )

    def get_by_third_party(
        self,
        db: Session,
        third_party_id: UUID,
        organization_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[List[MoneyMovement], int]:
        """Movimientos de un tercero especifico."""
        return self.get_multi(
            db=db,
            organization_id=organization_id,
            third_party_id=third_party_id,
            skip=skip,
            limit=limit,
        )

    def get_summary(
        self,
        db: Session,
        organization_id: UUID,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        allowed_account_ids: Optional[List[UUID]] = None,
    ) -> List[dict]:
        """Resumen de movimientos agrupados por tipo para un periodo."""
        query = (
            select(
                MoneyMovement.movement_type,
                func.count().label("count"),
                func.sum(MoneyMovement.amount).label("total_amount"),
            )
            .where(
                MoneyMovement.organization_id == organization_id,
                MoneyMovement.status == "confirmed",
            )
            .group_by(MoneyMovement.movement_type)
        )
        if allowed_account_ids is not None:
            query = query.where(
                (MoneyMovement.account_id.in_(allowed_account_ids))
                | (MoneyMovement.account_id.is_(None))
            )

        if date_from:
            query = query.where(MoneyMovement.date >= date_from)
        if date_to:
            query = query.where(MoneyMovement.date < date_to)

        rows = db.execute(query).all()
        return [
            {
                "movement_type": row.movement_type,
                "count": row.count,
                "total_amount": float(row.total_amount or 0),
            }
            for row in rows
        ]

    # ======================================================================
    # Helpers internos
    # ======================================================================

    def _generate_movement_number(self, db: Session, organization_id: UUID) -> int:
        """
        Generar numero secuencial por organizacion con advisory lock.

        Usa pg_advisory_xact_lock para prevenir race conditions.
        El lock se libera automaticamente al finalizar la transaccion.
        """
        lock_id = hash(f"{organization_id}-movements") % (2**31)
        db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

        stmt = select(func.max(MoneyMovement.movement_number)).where(
            MoneyMovement.organization_id == organization_id
        )
        max_number = db.scalar(stmt)
        return (max_number or 0) + 1

    def _create_movement(
        self,
        db: Session,
        organization_id: UUID,
        movement_type: str,
        amount: Decimal,
        account_id: Optional[UUID],
        date: datetime,
        description: str,
        user_id: Optional[UUID] = None,
        third_party_id: Optional[UUID] = None,
        expense_category_id: Optional[UUID] = None,
        purchase_id: Optional[UUID] = None,
        sale_id: Optional[UUID] = None,
        reference_number: Optional[str] = None,
        evidence_url: Optional[str] = None,
        notes: Optional[str] = None,
        business_unit_id: Optional[UUID] = None,
        applicable_business_unit_ids: Optional[list] = None,
    ) -> MoneyMovement:
        """Crear registro de movimiento en BD (sin commit, sin aplicar efectos)."""
        number = self._generate_movement_number(db, organization_id)

        movement = MoneyMovement(
            organization_id=organization_id,
            movement_number=number,
            date=date,
            movement_type=movement_type,
            amount=amount,
            account_id=account_id,
            third_party_id=third_party_id,
            expense_category_id=expense_category_id,
            purchase_id=purchase_id,
            sale_id=sale_id,
            description=description,
            reference_number=reference_number,
            notes=notes,
            evidence_url=evidence_url,
            status="confirmed",
            created_by=user_id,
            business_unit_id=business_unit_id,
            applicable_business_unit_ids=applicable_business_unit_ids,
        )
        db.add(movement)
        db.flush()

        return movement

    def _validate_account(
        self,
        db: Session,
        account_id: UUID,
        organization_id: UUID,
        require_funds: Optional[Decimal] = None,
    ) -> MoneyAccount:
        """Validar que la cuenta existe, pertenece a la org, y tiene fondos si se requiere."""
        account = db.get(MoneyAccount, account_id)
        if not account or account.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cuenta de dinero no encontrada",
            )
        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La cuenta esta inactiva",
            )
        if require_funds is not None and account.current_balance < require_funds:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fondos insuficientes. Disponible: ${account.current_balance}, Requerido: ${require_funds}",
            )
        return account

    def _validate_third_party(
        self,
        db: Session,
        third_party_id: UUID,
        organization_id: UUID,
        require_behavior: Optional[list[str]] = None,
    ) -> ThirdParty:
        """Validar que el tercero existe, pertenece a la org, y tiene behavior_type requerido.

        require_behavior: lista de behavior_types aceptados (OR). Ej: ["material_supplier", "service_provider"].
        """
        from app.services.third_party import third_party as tp_service

        tp = db.get(ThirdParty, third_party_id)
        if not tp or tp.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tercero no encontrado",
            )
        if not tp.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El tercero '{tp.name}' esta inactivo",
            )
        behavior_labels = {
            "material_supplier": "proveedor de material",
            "service_provider": "proveedor de servicios",
            "customer": "cliente",
            "investor": "inversor",
            "provision": "provision",
            "generic": "cuenta genérica",
            "liability": "pasivo",
        }
        if require_behavior:
            if not tp_service.has_behavior_type(db, third_party_id, require_behavior):
                labels = [behavior_labels.get(b, b) for b in require_behavior]
                label = " o ".join(labels)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El tercero '{tp.name}' no es {label}",
                )
        return tp

    def _validate_expense_category(
        self,
        db: Session,
        category_id: UUID,
        organization_id: UUID,
    ) -> ExpenseCategory:
        """Validar que la categoria de gasto existe y pertenece a la org."""
        cat = db.get(ExpenseCategory, category_id)
        if not cat or cat.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Categoria de gasto no encontrada",
            )
        return cat

    def _validate_purchase(
        self,
        db: Session,
        purchase_id: UUID,
        organization_id: UUID,
        supplier_id: Optional[UUID] = None,
    ) -> Purchase:
        """Validar que la compra existe y pertenece al proveedor."""
        purchase = db.get(Purchase, purchase_id)
        if not purchase or purchase.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Compra no encontrada",
            )
        if supplier_id and purchase.supplier_id != supplier_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La compra no pertenece al proveedor indicado",
            )
        return purchase

    def _validate_sale(
        self,
        db: Session,
        sale_id: UUID,
        organization_id: UUID,
        customer_id: Optional[UUID] = None,
    ) -> Sale:
        """Validar que la venta existe y pertenece al cliente."""
        sale = db.get(Sale, sale_id)
        if not sale or sale.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Venta no encontrada",
            )
        if customer_id and sale.customer_id != customer_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La venta no pertenece al cliente indicado",
            )
        return sale

    def _reverse_effects(self, db: Session, movement: MoneyMovement) -> None:
        """
        Revertir los efectos de un movimiento en saldos.

        Tabla de reversiones (inverso de la tabla de efectos):
        - payment_to_supplier: account(+), supplier(-)
        - collection_from_client: account(-), customer(+)
        - expense: account(+)
        - service_income: account(-)
        - transfer_out: account(+)
        - transfer_in: account(-)
        - capital_injection: account(-), investor(+)
        - capital_return: account(+), investor(-)
        - commission_payment: account(+), third_party(-)
        - provision_deposit: account(+), provision(+)
        - provision_expense: provision(-) (sin cuenta)
        - advance_payment: account(+), supplier(-)
        - advance_collection: account(-), customer(+)
        - asset_payment: account(+) (tercero es solo referencia)
        - payment_to_generic: account(+), generic(-)
        - collection_from_generic: account(-), generic(+)
        """
        account = db.get(MoneyAccount, movement.account_id) if movement.account_id else None
        third_party = db.get(ThirdParty, movement.third_party_id) if movement.third_party_id else None

        mt = movement.movement_type
        amt = movement.amount

        if mt == "payment_to_supplier":
            account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "collection_from_client":
            account.current_balance -= amt
            if third_party:
                third_party.current_balance += amt

        elif mt == "expense":
            account.current_balance += amt

        elif mt == "service_income":
            account.current_balance -= amt

        elif mt == "transfer_out":
            account.current_balance += amt

        elif mt == "transfer_in":
            account.current_balance -= amt

        elif mt == "capital_injection":
            account.current_balance -= amt
            if third_party:
                third_party.current_balance += amt

        elif mt == "capital_return":
            account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "commission_payment":
            account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "provision_deposit":
            if account:
                account.current_balance += amt
            if third_party:
                third_party.current_balance += amt

        elif mt == "provision_expense":
            # provision_expense no tiene cuenta, solo reversa provision
            if third_party:
                third_party.current_balance -= amt

        elif mt == "advance_payment":
            account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "advance_collection":
            account.current_balance -= amt
            if third_party:
                third_party.current_balance += amt

        elif mt == "asset_payment":
            # Tercero es solo referencia, no se reversa balance
            account.current_balance += amt

        elif mt == "asset_purchase":
            # Compra activo a credito: sin cuenta, solo reversa proveedor
            if third_party:
                third_party.current_balance += amt

        elif mt == "expense_accrual":
            # Sin cuenta, solo reversa tercero
            if third_party:
                third_party.current_balance += amt

        elif mt == "deferred_funding":
            # Reversa: account(+), third_party(-)
            if account:
                account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "deferred_expense":
            # Sin cuenta, solo reversa tercero
            if third_party:
                third_party.current_balance += amt

        elif mt == "commission_accrual":
            # Sin cuenta, solo reversa tercero (causacion hizo -=, reversa +=)
            if third_party:
                third_party.current_balance += amt

        elif mt == "depreciation_expense":
            # Sin cuenta ni tercero, solo anula el status del movimiento
            pass

        elif mt == "profit_distribution":
            # Sin cuenta, solo reversa tercero (reparticion hizo -=, reversa +=)
            if third_party:
                third_party.current_balance += amt

        elif mt == "payment_to_generic":
            account.current_balance += amt
            if third_party:
                third_party.current_balance -= amt

        elif mt == "collection_from_generic":
            account.current_balance -= amt
            if third_party:
                third_party.current_balance += amt

        elif mt == "tp_transfer_out":
            # Reversa: source habia hecho -=, ahora +=
            if third_party:
                third_party.current_balance += amt

        elif mt == "tp_transfer_in":
            # Reversa: dest habia hecho +=, ahora -=
            if third_party:
                third_party.current_balance -= amt

        elif mt == "tp_adjustment_credit":
            # Reversa: habia hecho +=, ahora -=
            if third_party:
                third_party.current_balance -= amt

        elif mt == "tp_adjustment_debit":
            # Reversa: habia hecho -=, ahora +=
            if third_party:
                third_party.current_balance += amt

    def _get_or_404(
        self,
        db: Session,
        movement_id: UUID,
        organization_id: UUID,
    ) -> MoneyMovement:
        """Obtener movimiento sin eager loading (para operaciones de escritura)."""
        movement = db.get(MoneyMovement, movement_id)
        if not movement or movement.organization_id != organization_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movimiento no encontrado",
            )
        return movement


# Instancia singleton para uso en endpoints
money_movement = CRUDMoneyMovement()
