"""
Endpoints de vistas consolidadas de inventario.

Vistas de lectura para consultar stock, movimientos y valorizacion:
- GET /stock: Vista consolidada de stock por material
- GET /stock/{material_id}: Detalle + desglose por bodega
- GET /transit: Materiales con stock en transito
- GET /movements: Historial de movimientos con filtros
- GET /valuation: Valorizacion del inventario
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.deps import get_required_org_context, get_db
from app.models.inventory_movement import InventoryMovement
from app.models.material import Material
from app.models.warehouse import Warehouse

router = APIRouter()


# ---------------------------------------------------------------------------
# Response Schemas (locales a este endpoint)
# ---------------------------------------------------------------------------

class StockItem(BaseModel):
    """Stock consolidado de un material."""
    material_id: UUID
    material_code: str
    material_name: str
    default_unit: str
    current_stock_liquidated: float
    current_stock_transit: float
    current_stock_total: float
    current_average_cost: float
    total_value: float  # stock_liquidated * avg_cost
    is_active: bool

    model_config = {"from_attributes": True}


class StockConsolidatedResponse(BaseModel):
    """Respuesta de vista consolidada de stock."""
    items: list[StockItem]
    total: int
    total_valuation: float  # sum(total_value)


class WarehouseStockDetail(BaseModel):
    """Detalle de stock de un material en una bodega."""
    warehouse_id: UUID
    warehouse_name: str
    stock: float


class MaterialStockDetailResponse(BaseModel):
    """Detalle de stock de un material con desglose por bodega."""
    material_id: UUID
    material_code: str
    material_name: str
    default_unit: str
    current_stock_liquidated: float
    current_stock_transit: float
    current_stock_total: float
    current_average_cost: float
    total_value: float
    warehouses: list[WarehouseStockDetail]


class TransitItem(BaseModel):
    """Material con stock en transito."""
    material_id: UUID
    material_code: str
    material_name: str
    default_unit: str
    current_stock_transit: float
    current_stock_liquidated: float

    model_config = {"from_attributes": True}


class TransitResponse(BaseModel):
    """Respuesta de materiales en transito."""
    items: list[TransitItem]
    total: int


class MovementItem(BaseModel):
    """Movimiento de inventario."""
    id: UUID
    material_id: UUID
    material_code: Optional[str] = None
    material_name: Optional[str] = None
    warehouse_id: UUID
    warehouse_name: Optional[str] = None
    movement_type: str
    quantity: float
    unit_cost: float
    reference_type: Optional[str] = None
    reference_id: Optional[UUID] = None
    date: datetime
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer('quantity', 'unit_cost')
    def serialize_decimal(self, value: Decimal) -> float:
        return float(value)


class PaginatedMovementResponse(BaseModel):
    """Respuesta paginada de movimientos."""
    items: list[MovementItem]
    total: int
    skip: int
    limit: int


class ValuationItem(BaseModel):
    """Valorizacion de un material."""
    material_id: UUID
    material_code: str
    material_name: str
    default_unit: str
    current_stock_liquidated: float
    current_average_cost: float
    total_value: float  # stock_liquidated * avg_cost


class ValuationResponse(BaseModel):
    """Respuesta de valorizacion del inventario."""
    items: list[ValuationItem]
    total_materials: int
    total_valuation: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/stock",
    response_model=StockConsolidatedResponse,
)
def get_stock_consolidated(
    category_id: Optional[UUID] = Query(None, description="Filtrar por categoria"),
    active_only: bool = Query(True, description="Solo materiales activos"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Vista consolidada de stock por material.

    Muestra stock liquidado, en transito, total, costo promedio y valorizacion.
    """
    query = select(Material).where(
        Material.organization_id == org_context["organization_id"]
    )

    if active_only:
        query = query.where(Material.is_active == True)
    if category_id:
        query = query.where(Material.category_id == category_id)

    query = query.order_by(Material.sort_order, Material.name)
    materials = list(db.scalars(query).all())

    items = []
    total_valuation = Decimal("0")

    for m in materials:
        stock_liq = float(m.current_stock_liquidated)
        stock_transit = float(m.current_stock_transit)
        avg_cost = float(m.current_average_cost)
        value = float(m.current_stock_liquidated * m.current_average_cost)
        total_valuation += m.current_stock_liquidated * m.current_average_cost

        items.append(StockItem(
            material_id=m.id,
            material_code=m.code,
            material_name=m.name,
            default_unit=m.default_unit,
            current_stock_liquidated=stock_liq,
            current_stock_transit=stock_transit,
            current_stock_total=stock_liq + stock_transit,
            current_average_cost=avg_cost,
            total_value=value,
            is_active=m.is_active,
        ))

    return StockConsolidatedResponse(
        items=items,
        total=len(items),
        total_valuation=float(total_valuation),
    )


@router.get(
    "/stock/{material_id}",
    response_model=MaterialStockDetailResponse,
)
def get_material_stock_detail(
    material_id: UUID,
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Detalle de stock de un material con desglose por bodega.

    El desglose por bodega se calcula on-the-fly desde InventoryMovement.
    """
    from fastapi import HTTPException, status

    material = db.get(Material, material_id)
    if not material or material.organization_id != org_context["organization_id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Material no encontrado",
        )

    # Calcular stock por bodega desde InventoryMovement
    stmt = (
        select(
            InventoryMovement.warehouse_id,
            func.coalesce(func.sum(InventoryMovement.quantity), 0).label("stock"),
        )
        .where(
            InventoryMovement.organization_id == org_context["organization_id"],
            InventoryMovement.material_id == material_id,
        )
        .group_by(InventoryMovement.warehouse_id)
    )
    warehouse_stocks = db.execute(stmt).all()

    # Obtener nombres de bodegas
    warehouse_ids = [ws[0] for ws in warehouse_stocks]
    warehouses_map = {}
    if warehouse_ids:
        wh_query = select(Warehouse).where(Warehouse.id.in_(warehouse_ids))
        for wh in db.scalars(wh_query).all():
            warehouses_map[wh.id] = wh.name

    warehouse_details = []
    for wh_id, stock in warehouse_stocks:
        stock_val = float(stock)
        if stock_val != 0:  # Solo mostrar bodegas con movimiento
            warehouse_details.append(WarehouseStockDetail(
                warehouse_id=wh_id,
                warehouse_name=warehouses_map.get(wh_id, "Unknown"),
                stock=stock_val,
            ))

    stock_liq = float(material.current_stock_liquidated)
    stock_transit = float(material.current_stock_transit)
    avg_cost = float(material.current_average_cost)

    return MaterialStockDetailResponse(
        material_id=material.id,
        material_code=material.code,
        material_name=material.name,
        default_unit=material.default_unit,
        current_stock_liquidated=stock_liq,
        current_stock_transit=stock_transit,
        current_stock_total=stock_liq + stock_transit,
        current_average_cost=avg_cost,
        total_value=float(material.current_stock_liquidated * material.current_average_cost),
        warehouses=warehouse_details,
    )


@router.get(
    "/transit",
    response_model=TransitResponse,
)
def get_transit_stock(
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Materiales con stock en transito (compras no liquidadas).
    """
    query = (
        select(Material)
        .where(
            Material.organization_id == org_context["organization_id"],
            Material.current_stock_transit > 0,
        )
        .order_by(Material.name)
    )
    materials = list(db.scalars(query).all())

    items = [
        TransitItem(
            material_id=m.id,
            material_code=m.code,
            material_name=m.name,
            default_unit=m.default_unit,
            current_stock_transit=float(m.current_stock_transit),
            current_stock_liquidated=float(m.current_stock_liquidated),
        )
        for m in materials
    ]

    return TransitResponse(items=items, total=len(items))


@router.get(
    "/movements",
    response_model=PaginatedMovementResponse,
)
def list_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    material_id: Optional[UUID] = Query(None),
    warehouse_id: Optional[UUID] = Query(None),
    movement_type: Optional[str] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Historial de movimientos de inventario con filtros.

    Muestra todos los movimientos (compras, ventas, ajustes, transferencias, transformaciones).
    """
    query = select(InventoryMovement).where(
        InventoryMovement.organization_id == org_context["organization_id"]
    )

    if material_id:
        query = query.where(InventoryMovement.material_id == material_id)
    if warehouse_id:
        query = query.where(InventoryMovement.warehouse_id == warehouse_id)
    if movement_type:
        query = query.where(InventoryMovement.movement_type == movement_type)
    if date_from:
        query = query.where(InventoryMovement.date >= date_from)
    if date_to:
        query = query.where(InventoryMovement.date <= date_to)

    count_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(count_query)

    query = query.order_by(
        InventoryMovement.date.desc(),
        InventoryMovement.created_at.desc(),
    ).offset(skip).limit(limit)

    movements = list(db.scalars(query).all())

    # Cargar nombres de materiales y bodegas en batch
    material_ids = {m.material_id for m in movements}
    warehouse_ids = {m.warehouse_id for m in movements}

    materials_map = {}
    if material_ids:
        for mat in db.scalars(select(Material).where(Material.id.in_(material_ids))).all():
            materials_map[mat.id] = mat

    warehouses_map = {}
    if warehouse_ids:
        for wh in db.scalars(select(Warehouse).where(Warehouse.id.in_(warehouse_ids))).all():
            warehouses_map[wh.id] = wh

    items = []
    for mov in movements:
        mat = materials_map.get(mov.material_id)
        wh = warehouses_map.get(mov.warehouse_id)
        items.append(MovementItem(
            id=mov.id,
            material_id=mov.material_id,
            material_code=mat.code if mat else None,
            material_name=mat.name if mat else None,
            warehouse_id=mov.warehouse_id,
            warehouse_name=wh.name if wh else None,
            movement_type=mov.movement_type,
            quantity=mov.quantity,
            unit_cost=mov.unit_cost,
            reference_type=mov.reference_type,
            reference_id=mov.reference_id,
            date=mov.date,
            notes=mov.notes,
            created_at=mov.created_at,
        ))

    return PaginatedMovementResponse(
        items=items, total=total, skip=skip, limit=limit,
    )


@router.get(
    "/valuation",
    response_model=ValuationResponse,
)
def get_valuation(
    category_id: Optional[UUID] = Query(None, description="Filtrar por categoria"),
    org_context: dict = Depends(get_required_org_context),
    db: Session = Depends(get_db),
):
    """
    Valorizacion del inventario: stock_liquidated * avg_cost por material.
    """
    query = select(Material).where(
        Material.organization_id == org_context["organization_id"],
        Material.is_active == True,
        Material.current_stock_liquidated > 0,
    )

    if category_id:
        query = query.where(Material.category_id == category_id)

    query = query.order_by(Material.sort_order, Material.name)
    materials = list(db.scalars(query).all())

    items = []
    total_valuation = Decimal("0")

    for m in materials:
        value = m.current_stock_liquidated * m.current_average_cost
        total_valuation += value
        items.append(ValuationItem(
            material_id=m.id,
            material_code=m.code,
            material_name=m.name,
            default_unit=m.default_unit,
            current_stock_liquidated=float(m.current_stock_liquidated),
            current_average_cost=float(m.current_average_cost),
            total_value=float(value),
        ))

    return ValuationResponse(
        items=items,
        total_materials=len(items),
        total_valuation=float(total_valuation),
    )
