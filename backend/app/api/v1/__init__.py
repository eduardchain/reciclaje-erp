from fastapi import APIRouter

from .endpoints import (
    health, auth, organizations, roles, system,
    materials, material_categories, third_parties, third_party_categories,
    purchases, sales, double_entries,
    money_accounts, warehouses, business_units,
    price_lists, expense_categories,
    money_movements, scheduled_expenses, fixed_assets,
    profit_distributions, financial_obligations,
    inventory_adjustments, material_transformations, inventory_views,
    reports,
    service_tariffs, material_conversion_formulas, fleet,
    kg_ledger, inbound_orders, material_kg_profiles,
    transfers,
)

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(roles.router, prefix="/roles", tags=["roles"])
api_router.include_router(material_categories.router, prefix="/material-categories", tags=["material-categories"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(third_parties.router, prefix="/third-parties", tags=["third-parties"])
api_router.include_router(third_party_categories.router, prefix="/third-party-categories", tags=["third-party-categories"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["purchases"])
api_router.include_router(sales.router, prefix="/sales", tags=["sales"])
api_router.include_router(double_entries.router, prefix="/double-entries", tags=["double-entries"])
api_router.include_router(money_accounts.router, prefix="/money-accounts", tags=["money-accounts"])
api_router.include_router(warehouses.router, prefix="/warehouses", tags=["warehouses"])
api_router.include_router(business_units.router, prefix="/business-units", tags=["business-units"])
api_router.include_router(price_lists.router, prefix="/price-lists", tags=["price-lists"])
api_router.include_router(expense_categories.router, prefix="/expense-categories", tags=["expense-categories"])
api_router.include_router(money_movements.router, prefix="/money-movements", tags=["treasury"])
api_router.include_router(scheduled_expenses.router, prefix="/scheduled-expenses", tags=["treasury"])
api_router.include_router(fixed_assets.router, prefix="/fixed-assets", tags=["treasury"])
api_router.include_router(profit_distributions.router, prefix="/profit-distributions", tags=["treasury"])
api_router.include_router(financial_obligations.router, prefix="/financial-obligations", tags=["treasury"])
api_router.include_router(inventory_adjustments.router, prefix="/inventory/adjustments", tags=["inventory"])
api_router.include_router(material_transformations.router, prefix="/inventory/transformations", tags=["inventory"])
api_router.include_router(inventory_views.router, prefix="/inventory", tags=["inventory"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(system.router, prefix="/system", tags=["system"])
# SAC E1 (plan-sac-e1-configuracion.md §4.3-§4.5)
api_router.include_router(service_tariffs.router, prefix="/service-tariffs", tags=["sac-config"])
api_router.include_router(material_conversion_formulas.router, prefix="/material-conversion-formulas", tags=["sac-config"])
api_router.include_router(material_kg_profiles.router, prefix="/material-kg-profiles", tags=["sac-config"])
api_router.include_router(fleet.drivers_router, prefix="/drivers", tags=["sac-config"])
api_router.include_router(fleet.vehicles_router, prefix="/vehicles", tags=["sac-config"])
# SAC E2 (plan-sac-e2-kgledger-inbound.md §4.1-§4.2)
api_router.include_router(kg_ledger.router, prefix="/kg-ledger", tags=["kg-ledger"])
api_router.include_router(inbound_orders.router, prefix="/inbound-orders", tags=["inbound-orders"])
# SAC E3.1 (plan-sac-e3-1-traslados-maquila.md §2.4) — gated two_step_transfers_enabled
api_router.include_router(transfers.router, prefix="/transfers", tags=["transfers"])
