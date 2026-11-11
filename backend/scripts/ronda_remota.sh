#!/usr/bin/env bash
# Ronda de carga SIN --reset ni --ensayo: el procedimiento contra un servidor
# remoto (produccion). Tambien corre contra localhost, para ensayarlo igual.
#
# Uso:
#   SEED_SU_EMAIL=... SEED_SU_PASSWORD=... scripts/ronda_remota.sh <api-url> <libro.xlsx> <corte> <informe.md> [args del cargador]
#
# Los argumentos de mas van al cargador en las TRES corridas (saldos, resto y
# conciliar). Ej.: --muestra, que marca los activos de ejemplo; tiene que ir en
# las tres porque el nombre del activo es la llave de la conciliacion.
#
# Orden (plan-sac-carga-inicial-ronda1.md, G1, y carga de muestra del 10-nov):
#   0. solo lectura: que existan los usuarios del seeder (si falta uno, el paso 2
#      se detendria con la vieja ya archivada) y que las dos fases del cargador
#      simulen sin errores. Si algo falla aca, no se toca nada.
#   1. archiva la org «SAC» activa (la renombra; sus usuarios conservan el acceso)
#   2. crea la «SAC» nueva, vacia, con usuarios y roles
#   3. saldos -> 4. provision del seeder -> 5. resto -> 6. conciliacion
# Se detiene en la primera falla. La org archivada queda ACTIVA: se da de baja
# despues de revisar, con archivar_org_sac.py --modo baja.
#
# Si falla a mitad:
#   - en el paso 2 sin que la «SAC» nueva llegue a existir (no hay ninguna
#     «SAC» activa): archivar_org_sac.py --modo restaurar --org-id <la archivada>
#     --apply, y volver a correr desde el principio;
#   - en el paso 2 con la nueva ya creada, o del 3 en adelante: la «SAC» nueva
#     queda a medio cargar. Se archiva tambien (--modo archivar --apply) y se
#     vuelve a correr; al final se dan de baja las dos.
set -euo pipefail

if [ $# -lt 4 ]; then
  echo "Uso: $0 <api-url> <libro.xlsx> <corte YYYY-MM-DD> <informe.md> [args del cargador]" >&2
  exit 2
fi
API="$1"; LIBRO="$2"; CORTE="$3"; INFORME="$4"
shift 4
cd "$(dirname "$0")/.."
PY=./venv/bin/python
CARGA=(scripts/load_sac_opening.py --file "$LIBRO" --corte "$CORTE" --api-url "$API" "$@")

echo "== 0/6 usuarios del seeder y simulacion de las dos fases (no escribe)"
"$PY" scripts/seed_sac_org.py --verificar-usuarios --api-url "$API"
"$PY" "${CARGA[@]}" --fase saldos
"$PY" "${CARGA[@]}" --fase resto

echo "== 1/6 archivar la org SAC activa"
"$PY" scripts/archivar_org_sac.py --modo archivar --apply --api-url "$API"

echo "== 2/6 org vacia"
"$PY" scripts/seed_sac_org.py --apply --org-vacia --api-url "$API"

echo "== 3/6 saldos"
"$PY" "${CARGA[@]}" --fase saldos --apply

echo "== 4/6 provision del seeder"
"$PY" scripts/seed_sac_org.py --apply --api-url "$API"

echo "== 5/6 resto"
"$PY" "${CARGA[@]}" --fase resto --apply

echo "== 6/6 conciliar"
"$PY" "${CARGA[@]}" --conciliar --salida "$INFORME"

echo "Listo. La org archivada sigue activa: darla de baja despues de revisar con"
echo "  scripts/archivar_org_sac.py --modo baja --org-id <id> --apply --api-url $API"
