import "@tanstack/react-table";

declare module "@tanstack/react-table" {
  interface ColumnMeta<TData extends unknown, TValue> {
    hideOnMobile?: boolean;
    /** El export a Excel deja el valor como TEXTO exacto. Por defecto, un string
     * que parece numero se convierte a Number (los Decimal llegan como string);
     * un identificador no es un numero: "0012" saldria 12 y uno largo perderia
     * digitos pasado 2^53. */
    exportAsText?: boolean;
  }
}
