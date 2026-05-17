"""
Endpoints de reportes y dashboard.

Todos los endpoints son GET (read-only), requieren autenticacion y contexto de organizacion.
"""
from datetime import date
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission, require_any_permission, get_db
from app.schemas.reports import (
    AuditBalancesResponse,
    BalanceDetailedResponse,
    BalanceSheetResponse,
    CashFlowResponse,
    DashboardResponse,
    ExpenseDetailResponse,
    ExpensesReportResponse,
    MarginAnalysisResponse,
    ProfitAndLossMonthlyResponse,
    ProfitAndLossResponse,
    ProfitabilityByBUResponse,
    PurchaseReportResponse,
    RealCostByMaterialResponse,
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


@router.get("/profit-and-loss/monthly", response_model=ProfitAndLossMonthlyResponse)
def get_profit_and_loss_monthly(
    date_from: date = Query(..., description="Fecha inicio del rango"),
    date_to: date = Query(..., description="Fecha fin del rango"),
    cutoff_day: int = Query(1, ge=1, le=28, description="Dia de inicio del mes contable (1=mes calendario)"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_pnl")),
    db: Session = Depends(get_db),
):
    """
    P&L Mensual: una columna por mes contable derivado de cutoff_day.

    Permite comparar mes a mes dentro de un rango libre y auditar outliers.
    Cap defensivo de 24 meses contables (~168 SQL queries) — rangos mayores
    devuelven 422 para proteger el endpoint.

    `totals` corresponde al rango exacto [date_from, date_to], NO a la suma
    aritmetica de las columnas (los meses contables pueden extenderse mas alla).
    """
    # Cap defensivo antes del loop pesado.
    months = report_service._split_into_accounting_months(date_from, date_to, cutoff_day)
    if len(months) > 24:
        raise HTTPException(
            status_code=422,
            detail=f"Rango demasiado amplio: {len(months)} meses (max 24). Reduzca date_from/date_to.",
        )
    return report_service.get_profit_and_loss_monthly(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
        cutoff_day=cutoff_day,
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
    as_of_date: Optional[date] = Query(None, description="Fecha de corte historica (YYYY-MM-DD). Sin valor = snapshot actual."),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_balance")),
    db: Session = Depends(get_db),
):
    """
    Balance General.

    Sin as_of_date: snapshot actual.
    Con as_of_date: fotografia historica a esa fecha.

    Activos = Efectivo + CxC + Inventario
    Pasivos = CxP + Deuda inversores
    Patrimonio = Activos - Pasivos
    """
    return report_service.get_balance_sheet(
        db=db,
        organization_id=org_context["organization_id"],
        as_of_date=as_of_date,
    )


@router.get("/balance-detailed", response_model=BalanceDetailedResponse)
def get_balance_detailed(
    as_of_date: Optional[date] = Query(None, description="Fecha de corte historica (YYYY-MM-DD). Sin valor = snapshot actual."),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_balance")),
    db: Session = Depends(get_db),
):
    """
    Balance General Detallado (desglose por item individual).

    Sin as_of_date: snapshot actual.
    Con as_of_date: fotografia historica a esa fecha.

    Muestra cada cuenta, tercero, material y activo fijo que compone el balance.
    Activos - Pasivos - Patrimonio = 0.
    """
    return report_service.get_balance_detailed(
        db=db,
        organization_id=org_context["organization_id"],
        as_of_date=as_of_date,
    )


@router.get("/purchases", response_model=PurchaseReportResponse)
def get_purchase_report(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    supplier_id: Optional[UUID] = Query(None, description="Filtrar por proveedor"),
    material_id: Optional[UUID] = Query(None, description="Filtrar por material"),
    dp_filter: Literal["all", "exclude", "only"] = Query(
        "all",
        description="Filtrar Pasa Mano: 'all' incluye todo, 'exclude' omite compras de DPs, 'only' solo compras de DPs",
    ),
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
        dp_filter=dp_filter,
    )


@router.get("/sales", response_model=SalesReportResponse)
def get_sales_report(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    customer_id: Optional[UUID] = Query(None, description="Filtrar por cliente"),
    material_id: Optional[UUID] = Query(None, description="Filtrar por material"),
    dp_filter: Literal["all", "exclude", "only"] = Query(
        "all",
        description="Filtrar Pasa Mano: 'all' incluye todo, 'exclude' omite ventas de DPs, 'only' solo ventas de DPs",
    ),
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
        dp_filter=dp_filter,
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
    org_context: dict = Depends(require_permission("treasury.view_dashboard")),
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


@router.get("/profitability-by-business-unit", response_model=ProfitabilityByBUResponse)
def get_profitability_by_bu(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_pnl")),
    db: Session = Depends(get_db),
):
    """
    Rentabilidad por Unidad de Negocio.

    Calcula ingresos, COGS, gastos (directos/compartidos/generales),
    comisiones y utilidad neta por cada UN activa.
    Gastos compartidos se prorratean por valor de compras liquidadas.
    """
    return report_service.get_profitability_by_business_unit(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/expenses", response_model=ExpensesReportResponse)
def get_expenses_report(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    group_by: Literal["bu", "category", "bu_then_category", "category_then_bu", "none"] = Query(
        "bu_then_category",
        description="Modo de agrupacion del arbol de gastos. 'none' devuelve solo el resumen sin grupos.",
    ),
    business_unit_id: Optional[list[UUID]] = Query(None, description="Filtrar por una o mas UN"),
    expense_category_id: Optional[list[UUID]] = Query(
        None,
        description="Filtrar por categoria(s) (padre expande a hijas)",
    ),
    org_context: dict = Depends(require_any_permission(
        "reports.view", "reports.view_expenses", "reports.view_pnl",
    )),
    db: Session = Depends(get_db),
):
    """
    Reporte de gastos del periodo agrupado por UN y/o Categoria.

    Aplica logica 3-tier (directo / compartido / general) replicando
    Rentabilidad por UN. Filtros se aplican despues del prorrateo
    para preservar proporcionalidad. Categoria padre expande a hijas.
    """
    return report_service.get_expenses_report(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
        business_unit_ids=business_unit_id,
        category_ids=expense_category_id,
    )


@router.get("/expenses/detail", response_model=ExpenseDetailResponse)
def get_expenses_detail(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    business_unit_id: Optional[UUID] = Query(None, description="Filtrar por UN (un valor)"),
    category_id: Optional[UUID] = Query(None, description="Filtrar por categoria (un valor)"),
    business_unit_ids: Optional[list[UUID]] = Query(
        None,
        description="Filtrar por una o mas UN (alterna a business_unit_id, util para 'sin agrupar')",
    ),
    category_ids: Optional[list[UUID]] = Query(
        None,
        description="Filtrar por una o mas categorias (padre expande a hijas)",
    ),
    include_child_categories: bool = Query(
        True,
        description="Si category_id es padre, incluir gastos de categorias hijas",
    ),
    business_unit_unassigned: bool = Query(
        False,
        description="Filtrar al bucket 'Sin Asignar' (gastos sin UN)",
    ),
    category_uncategorized: bool = Query(
        False,
        description="Filtrar al bucket 'Sin Categoría'",
    ),
    org_context: dict = Depends(require_any_permission(
        "reports.view", "reports.view_expenses", "reports.view_pnl",
    )),
    db: Session = Depends(get_db),
):
    """
    Detalle de movimientos que componen un grupo del reporte de gastos.

    Cada item tiene `allocated_amount` (porcion asignada al grupo, == amount
    si directo) y `allocation_type` ('direct' | 'shared' | 'general').
    """
    return report_service.get_expenses_detail(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
        business_unit_id=business_unit_id,
        category_id=category_id,
        business_unit_ids=business_unit_ids,
        category_ids=category_ids,
        include_child_categories=include_child_categories,
        business_unit_unassigned=business_unit_unassigned,
        category_uncategorized=category_uncategorized,
    )


@router.get("/real-cost-by-material", response_model=RealCostByMaterialResponse)
def get_real_cost_by_material(
    date_from: date = Query(..., description="Fecha inicio del periodo"),
    date_to: date = Query(..., description="Fecha fin del periodo"),
    org_context: dict = Depends(require_any_permission("reports.view", "reports.view_pnl")),
    db: Session = Depends(get_db),
):
    """
    Costo real por material = costo promedio + overhead rate.

    Overhead rate = gastos totales de la UN / kg comprados en el periodo.
    """
    return report_service.get_real_cost_by_material(
        db=db,
        organization_id=org_context["organization_id"],
        date_from=date_from,
        date_to=date_to,
    )
