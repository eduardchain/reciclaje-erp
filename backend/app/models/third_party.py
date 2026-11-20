from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from decimal import Decimal

from sqlalchemy import String, Boolean, Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.purchase import Purchase
    from app.models.sale import Sale, SaleCommission
    from app.models.third_party_category import ThirdPartyCategoryAssignment


class ThirdParty(Base, TimestampMixin, OrganizationMixin):
    """
    Third party model for suppliers, customers, investors, and provision accounts.
    Multi-purpose entity that can act as supplier, customer, investor, or provision.
    """
    
    __tablename__ = "third_parties"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    identification_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_system_entity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    provision_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )  # e.g., 'tax', 'employee_benefit', 'other'
    
    initial_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )

    current_balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        default=0,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Marca de recolector (SAC, plan recolector-alcance §3 y §10): «este tercero
    # es de ESTE recolector» (Green Loop). NULL en las otras orgs.
    # ⚠️ FK autorreferente SIN `ondelete` = NO ACTION, a proposito (n1 de QA 2):
    # RESTRICT se chequea fila por fila y un DELETE de varias filas podria fallar
    # segun el orden; NO ACTION se chequea al final de la sentencia. Las dos
    # impiden borrar solo al recolector.
    # ⚠️ SIN `relationship` inversa: con la cascada por defecto, la sesion pondria
    # NULL en los marcados antes del DELETE y la base dejaria de proteger (T20).
    collector_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id"),
        nullable=True,
        index=True,
    )

    # Relationships
    purchases: Mapped[list["Purchase"]] = relationship(
        "Purchase",
        foreign_keys="Purchase.supplier_id",
        back_populates="supplier",
    )
    
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        foreign_keys="Sale.customer_id",
        back_populates="customer",
    )
    
    sale_commissions: Mapped[list["SaleCommission"]] = relationship(
        "SaleCommission",
        foreign_keys="SaleCommission.third_party_id",
        back_populates="third_party",
    )

    purchase_commissions: Mapped[list["PurchaseCommission"]] = relationship(
        "PurchaseCommission",
        foreign_keys="PurchaseCommission.third_party_id",
        back_populates="third_party",
    )
    
    category_assignments: Mapped[list["ThirdPartyCategoryAssignment"]] = relationship(
        "ThirdPartyCategoryAssignment",
        cascade="all, delete-orphan",
    )

    double_entries_as_supplier: Mapped[list["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="DoubleEntry.supplier_id",
        back_populates="supplier",
    )
    
    double_entries_as_customer: Mapped[list["DoubleEntry"]] = relationship(
        "DoubleEntry",
        foreign_keys="DoubleEntry.customer_id",
        back_populates="customer",
    )
    
    # Muchos-a-uno hacia el recolector, SOLO para leer su nombre. No hay
    # coleccion inversa (ver la nota de `collector_id`). Carga perezosa: en un
    # listado todos apuntan al mismo recolector, y despues de la primera carga
    # el resto sale del identity map sin SQL.
    collector: Mapped["ThirdParty | None"] = relationship(
        "ThirdParty",
        remote_side=[id],
        foreign_keys=[collector_id],
        viewonly=True,
    )

    @property
    def collector_name(self) -> str | None:
        return self.collector.name if self.collector_id and self.collector else None

    def __repr__(self) -> str:
        return f"<ThirdParty(id={self.id}, name='{self.name}')>"
