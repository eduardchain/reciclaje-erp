import { QueryClient } from "@tanstack/react-query";

// Inventario: stock, movimientos, valuacion, transito
const invalidateInventory = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["inventory"] });
  qc.invalidateQueries({ queryKey: ["materials"] });
};

// Financiero: terceros (saldos), reportes, cuentas, categorias terceros
const invalidateFinancial = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["third-parties"] });
  qc.invalidateQueries({ queryKey: ["third-party-categories"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  qc.invalidateQueries({ queryKey: ["money-accounts"] });
};

export const invalidateAfterPurchase = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["purchases"] });
  invalidateInventory(qc);
};

export const invalidateAfterPurchaseLiquidateOrCancel = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["purchases"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
  // Ciclo C: la entrada refleja el display_status de su compra (bandeja +
  // badge sidebar). Key inofensiva en orgs sin flag (cero queries bajo ella).
  qc.invalidateQueries({ queryKey: ["inbound-orders"] });
  invalidateInventory(qc);
  invalidateFinancial(qc);
};

export const invalidateAfterSale = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["sales"] });
  invalidateInventory(qc);
};

export const invalidateAfterSaleLiquidateOrCancel = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["sales"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
  invalidateInventory(qc);
  invalidateFinancial(qc);
};

export const invalidateAfterDoubleEntry = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["double-entries"] });
  qc.invalidateQueries({ queryKey: ["purchases"] });
  qc.invalidateQueries({ queryKey: ["sales"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
  invalidateFinancial(qc);
};

export const invalidateAfterTreasury = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["money-accounts"] });
  qc.invalidateQueries({ queryKey: ["third-parties"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
  qc.invalidateQueries({ queryKey: ["scheduled-expenses"] });
};

export const invalidateAfterInventoryChange = (qc: QueryClient) => {
  invalidateInventory(qc);
  qc.invalidateQueries({ queryKey: ["reports"] });
};

// Obligaciones financieras (plan F): mueven cuentas, terceros y P&L
export const invalidateAfterObligation = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["financial-obligations"] });
  invalidateAfterTreasury(qc);
};

// Recepcion (SAC E2, D17): tipos Willard mueven inventario + cuentas kg;
// tipos purchase/ruta derivan una Purchase registrada (transito)
export const invalidateAfterInboundOrder = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["inbound-orders"] });
  qc.invalidateQueries({ queryKey: ["kg-ledger"] });
  qc.invalidateQueries({ queryKey: ["purchases"] });
  invalidateInventory(qc);
};

// #93: liquidar/desliquidar/anular-liquidada una Entrada = N compras
// liquidadas/revertidas + descuadres (ajustes) + comision (accrual) →
// los MISMOS side-effects de liquidar/cancelar una compra, mas el modulo
// propio y el libro kg (el annul willard tambien pasa por aca).
export const invalidateAfterEntradaLiquidation = (qc: QueryClient) => {
  invalidateAfterPurchaseLiquidateOrCancel(qc);
  qc.invalidateQueries({ queryKey: ["kg-ledger"] });
};

// Movimiento manual kg / anulacion (SAC E2, D17): solo toca el ledger kg
export const invalidateAfterKgMovement = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["kg-ledger"] });
};

// Traslados dos pasos (SAC E3.1, N1): la recepcion emite par de maquila +
// intersede kg + posible ajuste de merma; el despacho solo inventario — un
// solo helper mantiene la regla simple (#27).
export const invalidateAfterTransfer = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["transfers"] });
  qc.invalidateQueries({ queryKey: ["kg-ledger"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  invalidateInventory(qc);
};

// W1 — una Salida a Willard toca casi todo: saca inventario (venta derivada o
// ajuste), descarga cuentas en kg, factura a Willard (saldo del tercero + P&L)
// y reparte el ingreso entre sedes.
export const invalidateAfterWillardDelivery = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["willard-deliveries"] });
  qc.invalidateQueries({ queryKey: ["kg-ledger"] });
  qc.invalidateQueries({ queryKey: ["sales"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["third-parties"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
  invalidateInventory(qc);
};

export const invalidateAfterFixedAsset = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["fixed-assets"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["money-accounts"] });
  qc.invalidateQueries({ queryKey: ["third-parties"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
};
