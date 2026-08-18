from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.inventory_movement import InventoryMovement
    from app.models.sale import Sale


class Warehouse(Base, TimestampMixin, OrganizationMixin):
    """
    Warehouse/Storage location model.
    Used for multi-warehouse inventory management.
    """
    
    __tablename__ = "warehouses"
    
    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    
    # Organization FK is inherited from OrganizationMixin
    
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # SAC Ciclo B addendum (Q-12, feedback Daniel): una bodega recibe material
    # de terceros salvo que se marque como interna (molino/transito). Default
    # True = bodega nueva nace receptora ("¿y si mañana hay otra?" =
    # autoservicio). Solo la Recepcion (SAC) lo consume; prod no cambia.
    is_receiving: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true",
        comment="Recibe material de terceros (false = interna: molino/transito)",
    )

    # SAC E3.1 (E12): bodega virtual de transito intersede — GATE DURO en tabla
    # compartida (golden incluye GET /warehouses x3 orgs). Cuando el flag
    # two_step_transfers_enabled esta ON, operar contra una bodega is_transit
    # fuera del propio 2-pasos da 400 (guard en servicios).
    is_transit: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false",
        comment="Bodega virtual de transito intersede (SAC E3.1)",
    )

    # Mecanismo unico de ruteo (menor-31): la bodega de transito apunta a su
    # bodega fisica destino. E4 lo reusa para CV-TRANSITO sin migracion.
    transit_target_warehouse_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        comment="Bodega fisica destino a la que rutea esta bodega de transito",
    )

    # A que SEDE pertenece esta bodega. NULL = la bodega ES su propia sede.
    #
    # Un traslado emite kg intersede y maquila SOLO si cruza de sede (#84 los
    # emitia por tener formula, sin mirar el recorrido). Con NULL en todas las
    # bodegas —el estado de las 7 orgs— cada una es su propia sede y cualquier
    # traslado entre dos bodegas distintas sigue siendo intersede: comportamiento
    # byte a byte al de hoy. Solo cambia donde alguien agrupe explicitamente.
    #
    # Caso que lo motiva (SAC): Circunvalar-Molino pertenece a la sede
    # Circunvalar. Mover material de la bodega al molino NO puede inventar deuda
    # de plomo ni maquila —"es un solo inventario", Johana— pero Molino -> Juan
    # Mina si cruza de sede y si las genera.
    #
    # Un solo nivel: la bodega apuntada debe ser su propia sede (sin cadenas).
    sede_warehouse_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        comment="Sede a la que pertenece (NULL = es su propia sede)",
    )

    # Relationships
    inventory_movements: Mapped[list["InventoryMovement"]] = relationship(
        "InventoryMovement",
        back_populates="warehouse",
        order_by="InventoryMovement.date.desc()",
    )
    
    sales: Mapped[list["Sale"]] = relationship(
        "Sale",
        foreign_keys="Sale.warehouse_id",
        back_populates="warehouse",
    )
    
    def __repr__(self) -> str:
        return f"<Warehouse(id={self.id}, name='{self.name}', is_active={self.is_active})>"
