"""
REST API endpoints for sales management.

Supports 1-step and 2-step sale workflows:
- 1-step: POST with auto_liquidate=True
- 2-step: POST then PATCH /liquidate
"""
import logging
from datetime import date, datetime, time as dt_time, timedelta, timezone as tz
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import cast, or_, String
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.sale import Sale
from app.models.user import User
from app.schemas.sale import (
    PaginatedSaleResponse,
    SaleCreate,
    SaleFullUpdate,
    SaleLiquidateRequest,
    SaleResponse,
    SaleUpdate,
)
from app.services.sale import crud_sale

# Setup logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


# ============================================================================
# Helper Functions
# ============================================================================

def _enrich_sale_response(sale: Sale, db: Session = None, warnings: list[str] | None = None) -> dict:
    """
    Enrich sale object with joined data for response.

    Assumes sale was loaded with proper joinedload options.
    If db is provided, resolves audit user names (created_by, liquidated_by, updated_by).
    """
    data = {
        **sale.__dict__,
        "customer_name": sale.customer.name if sale.customer else None,
        "warehouse_name": sale.warehouse.name if sale.warehouse else None,
        "payment_account_name": sale.payment_account.name if sale.payment_account else None,
        "total_profit": float(sale.calculate_total_profit()),
        "warnings": warnings or getattr(sale, "_warnings", []),
        "created_by_name": None,
        "liquidated_by_name": None,
        "updated_by_name": None,
        "lines": [
            {
                **line.__dict__,
                "material_code": line.material.code if line.material else None,
                "material_name": line.material.name if line.material else None,
                "profit": float(line.calculate_profit()),
                "received_quantity": float(line.received_quantity) if line.received_quantity is not None else None,
                "quantity_difference": float(line.received_quantity - line.quantity) if line.received_quantity is not None else None,
                "amount_difference": float((line.received_quantity - line.quantity) * line.unit_price) if line.received_quantity is not None else None,
            }
            for line in sale.lines
        ],
        "commissions": [
            {
                **comm.__dict__,
                "third_party_name": comm.third_party.name if comm.third_party else None,
            }
            for comm in sale.commissions
        ],
    }

    # Calcular totales de diferencia de bascula
    lines_with_received = [l for l in sale.lines if l.received_quantity is not None]
    if lines_with_received:
        data["total_quantity_difference"] = float(sum(
            l.received_quantity - l.quantity for l in lines_with_received
        ))
        data["total_amount_difference"] = float(sum(
            (l.received_quantity - l.quantity) * l.unit_price for l in lines_with_received
        ))
    else:
        data["total_quantity_difference"] = None
        data["total_amount_difference"] = None

    # Resolver nombres de usuarios de auditoria
    if db:
        user_ids = {uid for uid in [sale.created_by, sale.liquidated_by, getattr(sale, 'updated_by', None)] if uid}
        if user_ids:
            users = {u.id: u.full_name or u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()}
            data["created_by_name"] = users.get(sale.created_by)
            data["liquidated_by_name"] = users.get(sale.liquidated_by)
            data["updated_by_name"] = users.get(getattr(sale, 'updated_by', None))

    return data


# ============================================================================
# Endpoints
# ============================================================================

@router.post(
    "",
    response_model=SaleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new sale",
    description="""
    Crear venta con workflow de 1 o 2 pasos.

    **1-step (auto_liquidate=True):** Crea y liquida en un paso (status='liquidated').
    **2-step (default):** Crea con status='registered', luego PATCH /liquidate.

    **Efectos en CREATE:**
    - Genera sale_number secuencial
    - Resta stock del material (current_stock, current_stock_liquidated)
    - Captura unit_cost para calculo de utilidad
    - Crea movimientos de inventario (auditoria)
    - Crea comisiones (sin pagar)
    - NO afecta saldo del cliente (se aplica en liquidacion)
    """,
)
async def create_sale(
    sale_in: SaleCreate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.create")),
) -> SaleResponse:
    """Create a new sale (1-step or 2-step workflow)."""
    try:
        sale = crud_sale.create(
            db=db,
            obj_in=sale_in,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Capturar warnings antes de reload (atributo transiente)
        warnings = getattr(sale, "_warnings", [])

        db.commit()
        db.refresh(sale)

        # Reload with eager loading to get all relationships
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )

        # Enrich with joined data (incluir warnings)
        response_data = _enrich_sale_response(sale, db=db, warnings=warnings)

        logger.info(
            f"Sale #{sale.sale_number} created by user {org_context['user_id']} "
            f"in org {org_context['organization_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise  # Re-raise HTTP exceptions from service
    
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error creating sale: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate sale number. Please retry.",
        )
    
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error creating sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "",
    response_model=PaginatedSaleResponse,
    summary="List sales",
    description="""
    List all sales for the organization with pagination and filters.
    
    **Filters:**
    - `status`: Filter by sale status (registered, paid, cancelled)
    - `customer_id`: Filter by customer
    - `warehouse_id`: Filter by warehouse
    - `date_from`: Filter sales on or after this date
    - `date_to`: Filter sales on or before this date
    - `search`: Search in sale number, customer name, notes, vehicle_plate, invoice_number
    
    **Pagination:**
    - `skip`: Number of records to skip (default: 0)
    - `limit`: Maximum records to return (default: 100, max: 1000)
    
    Results are ordered by date (newest first), then by sale number (descending).
    """,
)
async def list_sales(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[str] = Query(None, description="Filter by status: registered, liquidated, cancelled"),
    customer_id: Optional[UUID] = Query(None, description="Filter by customer UUID"),
    warehouse_id: Optional[UUID] = Query(None, description="Filter by warehouse UUID"),
    date_from: Optional[date] = Query(None, description="Filter sales on or after this date"),
    date_to: Optional[date] = Query(None, description="Filter sales on or before this date"),
    search: Optional[str] = Query(None, description="Search in sale number, customer name, notes, vehicle_plate, invoice_number"),
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> PaginatedSaleResponse:
    """List sales with filters and pagination."""
    try:
        # Exclusive upper bound para cubrir todas las horas del dia en cualquier timezone
        date_from_dt = datetime.combine(date_from, dt_time.min, tzinfo=tz.utc) if date_from else None
        date_to_dt = datetime.combine(date_to + timedelta(days=1), dt_time.min, tzinfo=tz.utc) if date_to else None
        
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status=status,
            customer_id=customer_id,
            warehouse_id=warehouse_id,
            date_from=date_from_dt,
            date_to=date_to_dt,
            search=search,
        )
        
        # Enrich each sale with joined data
        items = [SaleResponse(**_enrich_sale_response(s, db=db)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing sales: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/pending",
    response_model=PaginatedSaleResponse,
    summary="List sales pending liquidation",
    description="""
    List all sales with status='registered' (pending liquidation).
    
    These sales have been created but not yet paid.
    Use PATCH /sales/{id}/liquidate to complete payment.
    """,
)
async def list_pending_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> PaginatedSaleResponse:
    """List sales pending liquidation (status='registered')."""
    try:
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            status="registered",
        )
        
        items = [SaleResponse(**_enrich_sale_response(s, db=db)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing pending sales: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/by-number/{sale_number}",
    response_model=SaleResponse,
    summary="Get sale by number",
    description="Get a single sale by its sequential sale_number.",
)
async def get_sale_by_number(
    sale_number: int,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> SaleResponse:
    """Get sale by sale_number."""
    sale = crud_sale.get_by_number(
        db=db,
        sale_number=sale_number,
        organization_id=org_context["organization_id"],
    )
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sale #{sale_number} not found",
        )
    
    # Load with eager loading
    sale = crud_sale.get(
        db=db,
        sale_id=sale.id,
        organization_id=org_context["organization_id"],
    )
    
    response_data = _enrich_sale_response(sale, db=db)
    return SaleResponse(**response_data)


@router.get(
    "/customer/{customer_id}",
    response_model=PaginatedSaleResponse,
    summary="List sales by customer",
    description="List all sales from a specific customer.",
)
async def list_sales_by_customer(
    customer_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> PaginatedSaleResponse:
    """List sales by customer."""
    try:
        sales, total = crud_sale.get_multi(
            db=db,
            organization_id=org_context["organization_id"],
            skip=skip,
            limit=limit,
            customer_id=customer_id,
        )
        
        items = [SaleResponse(**_enrich_sale_response(s, db=db)) for s in sales]
        
        return PaginatedSaleResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    except Exception as e:
        logger.error(f"Error listing sales by customer: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.get(
    "/check-duplicate",
    summary="Check for duplicate sales",
    description="Cuenta ventas del mismo cliente en la misma fecha (no canceladas).",
)
async def check_duplicate_sale(
    customer_id: UUID = Query(..., description="Customer UUID"),
    date: date = Query(..., description="Sale date"),
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> dict:
    """Verificar si ya existe una venta para el mismo cliente en la misma fecha."""
    count = crud_sale.check_duplicate(
        db=db,
        customer_id=customer_id,
        date=date,
        organization_id=org_context["organization_id"],
    )
    return {"count": count}


@router.get(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Get single sale",
    description="""
    Get a single sale by ID with all details.
    
    Includes:
    - Sale lines with material details and profit calculation
    - Commissions with recipient details
    - Customer, warehouse, and payment account information
    """,
)
async def get_sale(
    sale_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.view")),
) -> SaleResponse:
    """Get sale by ID."""
    sale = crud_sale.get(
        db=db,
        sale_id=sale_id,
        organization_id=org_context["organization_id"],
    )
    
    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venta no encontrada",
        )
    
    response_data = _enrich_sale_response(sale, db=db)
    return SaleResponse(**response_data)


@router.patch(
    "/{sale_id}",
    response_model=SaleResponse,
    summary="Update sale (full edit)",
    description="""
    Edicion completa de una venta registrada: metadata, cliente, bodega, lineas y comisiones.

    **Restricciones:**
    - Solo ventas con status='registered'
    - No aplica a ventas creadas por doble partida (double_entry_id != null)

    **Estrategia Revert & Re-apply:**
    - Si se envian lineas nuevas, se revierten los movimientos de inventario originales
      y se re-aplican con las nuevas cantidades/materiales.
    - Si se envian comisiones nuevas, se reemplazan todas las existentes.
    - Stock negativo PERMITIDO: genera warnings, no bloquea la operacion (RN-INV-03).
    """,
)
async def update_sale(
    sale_id: UUID,
    sale_in: SaleFullUpdate,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.edit")),
) -> SaleResponse:
    """Edicion completa de venta registrada."""
    try:
        sale = crud_sale.update(
            db=db,
            sale_id=sale_id,
            obj_in=sale_in,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )

        # Capturar warnings antes de reload
        warnings = getattr(sale, "_warnings", [])

        db.commit()
        db.refresh(sale)

        # Reload con eager loading
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )

        response_data = _enrich_sale_response(sale, db=db, warnings=warnings)

        logger.info(
            f"Sale #{sale.sale_number} updated by user {org_context['user_id']}"
        )

        return SaleResponse(**response_data)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error updating sale: {e}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Error de integridad al actualizar la venta.",
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error updating sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.patch(
    "/{sale_id}/liquidate",
    response_model=SaleResponse,
    summary="Liquidar venta (paso 2)",
    description="""
    Liquidar venta registrada: confirmar precios y aplicar saldo.

    **Efectos:**
    - Status → 'liquidated'
    - Actualiza saldo cliente (+deuda)
    - Paga comisiones (actualiza saldo recipients)
    - Permite actualizar precios por linea y reemplazar comisiones

    **Requisitos:**
    - Sale must have status='registered'
    - Todos los precios deben ser > 0 (V-VENTA-04)
    """,
)
async def liquidate_sale(
    sale_id: UUID,
    liquidate_in: SaleLiquidateRequest,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.liquidate")),
) -> SaleResponse:
    """Liquidate a sale (2-step workflow)."""
    try:
        sale = crud_sale.liquidate(
            db=db,
            sale_id=sale_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
            line_updates=liquidate_in.lines,
            commissions_data=liquidate_in.commissions,
            immediate_collection=liquidate_in.immediate_collection,
            collection_account_id=liquidate_in.collection_account_id,
        )
        
        db.commit()
        db.refresh(sale)
        
        # Reload with eager loading
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_sale_response(sale, db=db)
        
        logger.info(
            f"Sale #{sale.sale_number} liquidated by user {org_context['user_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error liquidating sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )


@router.patch(
    "/{sale_id}/cancel",
    response_model=SaleResponse,
    summary="Cancelar venta",
    description="""
    Cancelar venta y revertir todos los efectos.

    **Permite cancelar:** registered y liquidated.

    **Efectos (registered):** Revierte stock solamente.
    **Efectos (liquidated):** Revierte stock + saldo cliente + comisiones pagadas.

    **Restricciones:**
    - No se puede cancelar ventas ya canceladas
    - No se puede cancelar ventas de doble partida
    """,
)
async def cancel_sale(
    sale_id: UUID,
    db: Session = Depends(get_db),
    org_context: dict = Depends(require_permission("sales.cancel")),
) -> SaleResponse:
    """Cancel a sale."""
    try:
        sale = crud_sale.cancel(
            db=db,
            sale_id=sale_id,
            organization_id=org_context["organization_id"],
            user_id=org_context["user_id"],
        )
        
        db.commit()
        db.refresh(sale)
        
        # Reload with eager loading
        sale = crud_sale.get(
            db=db,
            sale_id=sale.id,
            organization_id=org_context["organization_id"],
        )
        
        response_data = _enrich_sale_response(sale, db=db)
        
        logger.info(
            f"Sale #{sale.sale_number} cancelled by user {org_context['user_id']}"
        )
        
        return SaleResponse(**response_data)
    
    except HTTPException:
        db.rollback()
        raise
    
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling sale: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error. Please contact support.",
        )
