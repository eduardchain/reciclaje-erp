"""
Operaciones CRUD para MoneyAccount (Cuentas de Dinero).

Tipos soportados: cash (efectivo), bank (banco), digital (Nequi, Daviplata, etc.)
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.money_account import MoneyAccount
from app.schemas.money_account import MoneyAccountCreate, MoneyAccountUpdate
from app.services.base import CRUDBase, Select

# Tipos de cuenta validos
VALID_ACCOUNT_TYPES = {"cash", "bank", "digital"}


class CRUDMoneyAccount(CRUDBase[MoneyAccount, MoneyAccountCreate, MoneyAccountUpdate]):
    """Operaciones CRUD para MoneyAccount con validaciones de negocio."""

    def _apply_search_filter(self, query: Select, search: str) -> Select:
        """Buscar por nombre, nombre de banco o numero de cuenta."""
        search_term = f"%{search}%"
        return query.where(
            or_(
                self.model.name.ilike(search_term),
                self.model.bank_name.ilike(search_term),
                self.model.account_number.ilike(search_term),
            )
        )

    def create(
        self,
        db: Session,
        obj_in: MoneyAccountCreate,
        organization_id: UUID,
    ) -> MoneyAccount:
        """
        Crear cuenta de dinero con saldo inicial.

        Validaciones:
        - account_type debe ser 'cash', 'bank' o 'digital'

        El campo initial_balance del schema se mapea a current_balance del modelo.
        """
        # Validar tipo de cuenta
        if obj_in.account_type not in VALID_ACCOUNT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de cuenta invalido: '{obj_in.account_type}'. Debe ser: {', '.join(sorted(VALID_ACCOUNT_TYPES))}",
            )

        # Convertir schema a dict y mapear initial_balance -> current_balance
        obj_data = obj_in.model_dump(exclude={"initial_balance"})
        obj_data["organization_id"] = organization_id
        obj_data["current_balance"] = obj_in.initial_balance

        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)

        return db_obj

    def delete(
        self,
        db: Session,
        id: UUID,
        organization_id: UUID,
    ) -> MoneyAccount:
        """
        Soft delete de cuenta de dinero.

        Validacion: No se puede eliminar una cuenta con saldo != 0.
        """
        db_obj = self.get_or_404(
            db, id, organization_id, detail="Cuenta de dinero no encontrada"
        )

        if db_obj.current_balance != 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se puede eliminar una cuenta con saldo ({db_obj.current_balance}). Debe tener saldo 0.",
            )

        db_obj.is_active = False
        db.commit()
        db.refresh(db_obj)

        return db_obj


# Instancia singleton para uso en endpoints
money_account = CRUDMoneyAccount(MoneyAccount)
