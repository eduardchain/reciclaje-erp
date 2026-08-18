"""
Modelos PriceListGroup y PriceListGroupMember — Listas de precios por proveedor.

Hugo (SAC, 12-ago-2026): "cuando yo vaya a liquidarle la compra a ese proveedor,
me llame la lista que le corresponde".

Una lista agrupa precios (filas de `price_lists` con este `price_list_group_id`)
y proveedores (filas de la puente). Los precios de la lista GENERAL de siempre
son los que tienen `price_list_group_id IS NULL` — ese NULL es lo que hace que
las 3 orgs cliente no cambien en un byte.

⚠️ La lista trae TODOS los materiales y el usuario decide a cuales les pone
precio (Hugo, Q-21). Un material en cero es una DECISION deliberada, no un
hueco: por eso no hay respaldo a la lista general (D3).
"""
from uuid import UUID, uuid4
from typing import TYPE_CHECKING

from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, OrganizationMixin, GUID

if TYPE_CHECKING:
    from app.models.third_party import ThirdParty


class PriceListGroup(Base, TimestampMixin, OrganizationMixin):
    """Una lista de precios con nombre propio."""

    __tablename__ = "price_list_groups"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_price_list_groups_org_name"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre de la lista (ej. 'Lista A', 'Grandes proveedores')",
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    members: Mapped[list["PriceListGroupMember"]] = relationship(
        "PriceListGroupMember",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<PriceListGroup(id={self.id}, name={self.name!r})>"


class PriceListGroupMember(Base, TimestampMixin, OrganizationMixin):
    """
    Un proveedor pertenece a una lista.

    🔴 `UNIQUE(third_party_id)` hace cumplir en la BASE la regla de Hugo — "un
    tercero pertenece a una sola lista" — en vez de confiarla a una validacion
    de servicio que alguien pueda esquivar por otro camino.

    Va en tabla puente y no como columna de `third_parties` porque asi la
    membresia es revocable con un DELETE de fila, sin tocar el registro del
    tercero ni su historial de actualizacion.
    """

    __tablename__ = "price_list_group_members"
    __table_args__ = (
        UniqueConstraint("third_party_id", name="uq_price_list_group_members_third_party"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)

    price_list_group_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("price_list_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    third_party_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("third_parties.id", ondelete="CASCADE"),
        nullable=False,
    )

    group: Mapped["PriceListGroup"] = relationship(
        "PriceListGroup",
        back_populates="members",
    )

    third_party: Mapped["ThirdParty"] = relationship(
        "ThirdParty",
        foreign_keys=[third_party_id],
    )

    def __repr__(self) -> str:
        return (
            f"<PriceListGroupMember(group={self.price_list_group_id}, "
            f"third_party={self.third_party_id})>"
        )
