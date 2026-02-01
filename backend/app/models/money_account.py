from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, OrganizationMixin, GUID


class MoneyAccount(Base, TimestampMixin, OrganizationMixin):
    """
    Money account model for treasury management.
    Tracks cash, bank accounts, and digital payment accounts.
    """
    
    __tablename__ = "money_accounts"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    account_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # Options: 'cash', 'bank', 'digital'
    
    account_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    bank_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    def __repr__(self) -> str:
        return f"<MoneyAccount(id={self.id}, name='{self.name}', type='{self.account_type}', balance={self.current_balance})>"
