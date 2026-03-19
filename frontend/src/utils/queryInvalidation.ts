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

export const invalidateAfterFixedAsset = (qc: QueryClient) => {
  qc.invalidateQueries({ queryKey: ["fixed-assets"] });
  qc.invalidateQueries({ queryKey: ["money-movements"] });
  qc.invalidateQueries({ queryKey: ["money-accounts"] });
  qc.invalidateQueries({ queryKey: ["third-parties"] });
  qc.invalidateQueries({ queryKey: ["reports"] });
  qc.invalidateQueries({ queryKey: ["treasury-dashboard"] });
};
