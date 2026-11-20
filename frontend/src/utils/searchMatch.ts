/**
 * Búsqueda de los selectores (`EntitySelect`): el nombre tiene que CONTENER
 * cada palabra escrita, sin importar mayúsculas ni tildes.
 *
 * Reemplaza al filtro por defecto de cmdk, que es difuso: le basta que las
 * letras aparezcan en orden en cualquier parte, así que «abra» traía 25
 * proveedores (FABIAN TAVERA, AUTO BOLIVAR…) en vez de solo ABRAHAM CABARCAS.
 *
 * Devuelve el puntaje que cmdk usa para ordenar (0 = no se muestra):
 * 1 si el nombre empieza con lo escrito, 0,75 si alguna palabra del nombre
 * empieza con la primera palabra escrita, 0,5 si solo la contiene, y 0,25
 * como respaldo cuando coincide al ignorar espacios, guiones y puntuación
 * («greenloop» ↔ «Bio Green Loop- Maquila», «green loop» ↔ BIOGREENLOOP,
 * «plolin» ↔ PLO-LIN). El respaldo sigue exigiendo letras SEGUIDAS: «abra»
 * no encuentra «fabiantavera».
 */
export function normalizeForSearch(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

function compact(s: string): string {
  return s.replace(/[^a-z0-9]/g, "");
}

export function entitySearchScore(value: string, search: string): number {
  const q = normalizeForSearch(search);
  if (!q) return 1;
  const v = normalizeForSearch(value);
  const words = q.split(" ");
  if (words.every((w) => v.includes(w))) {
    if (v.startsWith(q)) return 1;
    if (v.split(" ").some((part) => part.startsWith(words[0]))) return 0.75;
    return 0.5;
  }
  const cq = compact(q);
  if (cq && compact(v).includes(cq)) return 0.25;
  return 0;
}
