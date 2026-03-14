"""
Endpoints de reportes y dashboard.

Todos los endpoints son GET (read-only), requieren autenticacion y contexto de organizacion.
"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission, require_any_permission, get_db
from app.schemas.reports import (
    AuditBalancesResponse,
    BalanceSheetResponse,
    CashFlowResponse,
    DashboardResponse,
    MarginAnalysisResponse,
    ProfitAndLossResponse,
    PurchaseReportResponse,
    SalesReportResponse,
    ThirdPartyBalancesResponse,
    TreasuryDashboardResponse,
)
from app.services.reports import report_service

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_dashboard")),
    db: Session = Depends(get_db),
):
    """
    Dashboard principal con metricas clave, top listas y alertas.

    Incluye comparacion vs periodo anterior de igual duracion.
    """
    return report_service.get_dashboard(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/profit-and-loss", response_model=ProfitAndLossResponse)
def get_profit_and_loss(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_pnl")),
    db: Session = Depends(get_db),
):
    """
    Estado de Resultados (P&L) para el periodo indicado.

    Estructura:
    - Sales Revenue (ventas normales)
    - (-) COGS (metodo directo)
    - = Gross Profit Sales
    - (+) Double Entry Profit (Utilidad Pasa Mano)
    - (+) Service Income
    - = Total Gross Profit
    - (-) Operating Expenses
    - (-) Commissions Paid
    - = Net Profit
    """
    return report_service.get_profit_and_loss(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
def get_cash_flow(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_cashflow")),
    db: Session = Depends(get_db),
):
    """
    Flujo de caja para el periodo indicado.

    Combina dos fuentes: liquidacion de compras/ventas y money_movements.
    Opening balance calculado a partir del balance actual de cuentas.
    """
    return report_service.get_cash_flow(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
def get_balance_sheet(
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_balance")),
    db: Session = Depends(get_db),
):
    """
    Balance General (snapshot actual).

    Activos = Efectivo + CxC + Inventario
    Pasivos = CxP + Deuda inversores
    Patrimonio = Activos - Pasivos
    """
    return report_service.get_balance_sheet(
        db=db,
        organization_id=org_context["organization_id"],
    )


@router.get("/purchases", response_model=PurchaseReportResponse)
def get_purchase_report(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    supplier_id: Optional[UUID] = Query(None, description="Filtrar por proveedor"),
    material_id: Optional[UUID] = Query(None, description="Filtrar por material"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_purchases")),
    db: Session = Depends(get_db),
):
    """
    Reporte de compras del periodo con desglose por proveedor, material y tendencia diaria.
    """
    return report_service.get_purchase_report(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
        supplier_id=supplier_id,
        material_id=material_id,
    )


@router.get("/sales", response_model=SalesReportResponse)
def get_sales_report(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    customer_id: Optional[UUID] = Query(None, description="Filtrar por cliente"),
    material_id: Optional[UUID] = Query(None, description="Filtrar por material"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_sales")),
    db: Session = Depends(get_db),
):
    """
    Reporte de ventas del periodo con profit, margenes y desglose por cliente/material.
    """
    return report_service.get_sales_report(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
        customer_id=customer_id,
        material_id=material_id,
    )


@router.get("/margins", response_model=MarginAnalysisResponse)
def get_margin_analysis(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_margins")),
    db: Session = Depends(get_db),
):
    """
    Analisis de margenes por material.

    Combina datos de compras, ventas normales y doble partida por material.
    """
    return report_service.get_margin_analysis(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/third-party-balances", response_model=ThirdPartyBalancesResponse)
def get_third_party_balances(
    type: Optional[str] = Query(
        None,
        description="Filtrar: 'suppliers' o 'customers'",
        regex="^(suppliers|customers)$",
    ),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_third_parties")),
    db: Session = Depends(get_db),
):
    """
    Saldos de terceros: lo que debemos a proveedores y lo que nos deben clientes.
    """
    return report_service.get_third_party_balances(
        db=db,
        organization_id=org_context["organization_id"],
        type_filter=type,
    )


@router.get("/treasury-dashboard", response_model=TreasuryDashboardResponse)
def get_treasury_dashboard(
    org_context: dict = Depends(require_permission("treasury.view")),
    db: Session = Depends(get_db),
):
    """
    Dashboard financiero de tesoreria.

    Incluye: cuentas por tipo, CxC/CxP, provisiones, MTD ingresos/egresos,
    y ultimos 10 movimientos.
    """
    return report_service.get_treasury_dashboard(
        db=db,
        organization_id=org_context["organization_id"],
    )


@router.get("/audit-balances", response_model=AuditBalancesResponse)
def audit_balances(
    org_context: dict = Depends(require_permission("admin.view_audit")),
    db: Session = Depends(get_db),
):
    """
    Auditoria de saldos: recalcula balances desde movimientos y compara
    con los valores almacenados en current_balance.

    Detecta discrepancias causadas por bugs o errores de sincronizacion.
    Solo lectura — no modifica ningun dato.
    """
    return report_service.audit_balances(
        db=db,
        organization_id=org_context["organization_id"],
    )
