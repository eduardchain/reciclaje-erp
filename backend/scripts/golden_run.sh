#!/bin/bash
# Golden aislado: arranca los dos backends, captura y diffea.
#
# 🔴 POR QUE EXISTE ESTE SCRIPT (CC-013 C1, hallazgo de QA)
#
# El golden de CC-013 se corrio a mano y el lado BEFORE **no era el que decia el
# log**: el uvicorn del worktree murio al arrancar con "address already in use"
# —habia un proceso viejo escuchando en 8001 desde hacia horas— y el health
# check lo contesto ESE proceso. El log afirmaba ":8001 BEFORE develop-HEAD
# <sha>" y eso era falso como procedencia.
#
# ⚠️ La prueba de vida de #110 NO lo ve, y esa es la leccion: comprueba que los
# dos lados DIFIEREN, no que el lado viejo sea el que uno dice. Cualquier
# proceso anterior al ciclo la pasa.
#
# Tres guardas, todas fail-closed:
#   1. los puertos tienen que estar LIBRES antes de lanzar;
#   2. el log del server no puede decir "address already in use";
#   3. el PID que ESCUCHA tiene que ser el que lanzamos.
#
# Uso: scripts/golden_run.sh <commit-base> <directorio-de-salida> [--db-before URL --db-after URL]
#
# 🔴 DOS BASES DE DATOS (plan-redondeo-precio-compras, C1 de QA)
#
# Sin opciones, los dos backends leen la MISMA base del `.env`. Eso sirve cuando
# la migracion es aditiva, pero es VACUO cuando la migracion cambia como se lee
# un valor que ya existe: con la base migrada, el codigo BASE tambien lee la
# columna nueva (psycopg devuelve el Decimal con la escala de la BD, no la del
# modelo), asi que los dos lados salen iguales justo en lo que se esta midiendo.
# Con `--db-before`/`--db-after`, cada uvicorn arranca con su DATABASE_URL: el
# lado BEFORE sobre una copia SIN migrar y el AFTER sobre la migrada.
#
# Guarda 4 (solo con dos bases): el esquema de las dos URLs tiene que DIFERIR.
# Se consulta la URL QUE USA CADA PROCESO, se imprimen las columnas distintas y,
# si no hay ninguna, aborta: dos bases con el mismo esquema no prueban la
# migracion.
set -euo pipefail

BASE_COMMIT="${1:?falta el commit base (BEFORE)}"
OUT="${2:?falta el directorio de salida}"
shift 2
DB_BEFORE=""
DB_AFTER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --db-before) DB_BEFORE="${2:?falta la URL de --db-before}"; shift 2 ;;
    --db-after)  DB_AFTER="${2:?falta la URL de --db-after}"; shift 2 ;;
    *) echo "🔴 opcion desconocida: $1"; exit 2 ;;
  esac
done
if { [ -n "$DB_BEFORE" ] && [ -z "$DB_AFTER" ]; } || { [ -z "$DB_BEFORE" ] && [ -n "$DB_AFTER" ]; }; then
  echo "🔴 ABORTA: --db-before y --db-after van juntas o ninguna."
  exit 2
fi
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WT="${OUT}/wt-before"
# Puertos por entorno (protocolo del equipo §1): 8001 es la integracion del
# Coordinador, asi que cada sesion pasa los suyos. Sin variables, los de siempre.
P_BEFORE="${GOLDEN_PORT_BEFORE:-8001}"
P_AFTER="${GOLDEN_PORT_AFTER:-8002}"

: "${SEED_SU_EMAIL:?exportar SEED_SU_EMAIL}"
: "${SEED_SU_PASSWORD:?exportar SEED_SU_PASSWORD}"

mkdir -p "$OUT"

# --- Guarda 1: los puertos, LIBRES ---------------------------------------
for p in "$P_BEFORE" "$P_AFTER"; do
  ocupa="$(lsof -t -iTCP:$p -sTCP:LISTEN 2>/dev/null || true)"
  if [ -n "$ocupa" ]; then
    echo "🔴 ABORTA: el puerto $p ya lo escucha el PID $ocupa."
    echo "   Un golden cuyo lado no se sabe de donde viene no prueba nada."
    ps -p "$ocupa" -o pid,lstart,command | tail -1
    exit 1
  fi
done
echo "✓ guarda 1: $P_BEFORE y $P_AFTER libres"

# Se define ANTES del trap para que el camino de ABORTO limpie igual que el de
# exito: un script que aborta dejando dos uvicorn vivos reproduce, en la corrida
# siguiente, el puerto ocupado que este script existe para atrapar.
limpiar() {
  for f in "$OUT/pid_before" "$OUT/pid_after"; do
    [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null || true
  done
  git -C "$REPO" worktree remove --force "$WT" 2>/dev/null || true
}
trap limpiar EXIT

# --- Arranque -------------------------------------------------------------
git -C "$REPO" worktree remove --force "$WT" 2>/dev/null || true
git -C "$REPO" worktree add --detach "$WT" "$BASE_COMMIT" >/dev/null
cp "$REPO/backend/.env" "$WT/backend/.env"
ln -sfn "$REPO/backend/venv" "$WT/backend/venv"
echo "✓ worktree BEFORE en $(git -C "$WT" rev-parse --short HEAD)"

# --- Guarda 4: con dos bases, sus esquemas tienen que DIFERIR --------------
if [ -n "$DB_BEFORE" ]; then
  echo "▶ dos bases: BEFORE y AFTER con DATABASE_URL propio (credenciales ocultas)"
  if ! "$REPO/backend/venv/bin/python" - "$DB_BEFORE" "$DB_AFTER" <<'PY'
import sys
import psycopg2

def esquema(url):
    with psycopg2.connect(url) as c, c.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name, data_type, numeric_precision, numeric_scale "
            "FROM information_schema.columns WHERE table_schema = 'public'"
        )
        return {(t, col): (dt, p, sc) for t, col, dt, p, sc in cur.fetchall()}

antes, despues = esquema(sys.argv[1]), esquema(sys.argv[2])
distintas = sorted(k for k in antes.keys() | despues.keys() if antes.get(k) != despues.get(k))
print(f"  columnas en BEFORE: {len(antes)} · en AFTER: {len(despues)} · distintas: {len(distintas)}")
for t, col in distintas:
    print(f"  {t}.{col}: BEFORE {antes.get((t, col))} -> AFTER {despues.get((t, col))}")
sys.exit(0 if distintas else 1)
PY
  then
    echo "🔴 ABORTA: las dos bases tienen el MISMO esquema. Un golden de dos bases"
    echo "   cuyas bases no difieren no prueba la migracion."
    exit 1
  fi
  echo "✓ guarda 4: los esquemas de las dos bases difieren (detalle arriba)"
fi

# ⚠️ El `exec` no es cosmetico: sin el, `$!` es el PID del SUBSHELL y no el de
# uvicorn, asi que el `kill` del final mata un proceso que ya murio y deja los
# backends VIVOS — que es exactamente la causa de C1. La primera version de este
# script reproducia el problema que venia a evitar; lo destapo su propio control
# positivo, no una lectura.
# Con dos bases, cada proceso recibe su DATABASE_URL por entorno, que le gana
# al `.env` (pydantic-settings). Sin opciones, el arranque es el de siempre.
if [ -n "$DB_BEFORE" ]; then
  (cd "$WT/backend" && export DATABASE_URL="$DB_BEFORE" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_BEFORE" > "$OUT/b_before.log" 2>&1) &
  echo $! > "$OUT/pid_before"
  (cd "$REPO/backend" && export DATABASE_URL="$DB_AFTER" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_AFTER" > "$OUT/b_after.log" 2>&1) &
  echo $! > "$OUT/pid_after"
else
  (cd "$WT/backend" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_BEFORE" > "$OUT/b_before.log" 2>&1) &
  echo $! > "$OUT/pid_before"
  (cd "$REPO/backend" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_AFTER" > "$OUT/b_after.log" 2>&1) &
  echo $! > "$OUT/pid_after"
fi
sleep 6

# --- Guardas 2 y 3: el proceso que responde es EL QUE LANZAMOS -----------
for par in "$P_BEFORE:$OUT/b_before.log:$OUT/pid_before" "$P_AFTER:$OUT/b_after.log:$OUT/pid_after"; do
  IFS=: read -r p log pidfile <<< "$par"
  if grep -qi "address already in use" "$log"; then
    echo "🔴 ABORTA: el server de :$p no pudo abrir el puerto."
    echo "   Lo que responda ahi es OTRO proceso, de procedencia desconocida."
    exit 1
  fi
  lanzado="$(cat "$pidfile")"
  escucha="$(lsof -t -iTCP:$p -sTCP:LISTEN 2>/dev/null || true)"
  # uvicorn puede forkear: se acepta el PID lanzado o un hijo suyo.
  padre="$(ps -o ppid= -p "$escucha" 2>/dev/null | tr -d ' ' || true)"
  if [ "$escucha" != "$lanzado" ] && [ "$padre" != "$lanzado" ]; then
    echo "🔴 ABORTA: en :$p escucha el PID $escucha y yo lance el $lanzado."
    exit 1
  fi
  echo "✓ :$p lo sirve el proceso que lance (pid $escucha)"
done

until curl -sf "http://localhost:$P_BEFORE/api/v1/health" >/dev/null \
   && curl -sf "http://localhost:$P_AFTER/api/v1/health" >/dev/null; do sleep 2; done
echo "✓ los dos responden"

# --- Captura y diff encadenados (#99: una captura fallida no se ignora) ---
#
# ⚠️ `set -e` MATA una cadena `a && b && c` cuando el ultimo falla, asi que sin
# el `set +e` de abajo el script nunca llegaba a `EXIT=$?` **justo en el unico
# caso que importa**: que el golden encuentre diffs. Se iba dejando el worktree
# colgado y sin imprimir el EXIT — la misma clase de C1, el camino de FALLO sin
# probar. Verificado en un script de tres lineas antes de escribir esto.
cd "$REPO/backend"
rm -rf "$OUT/g_before" "$OUT/g_after"
set +e
./venv/bin/python scripts/golden_capture.py --base-url "http://localhost:$P_BEFORE" --out "$OUT/g_before" \
  && ./venv/bin/python scripts/golden_capture.py --base-url "http://localhost:$P_AFTER" --out "$OUT/g_after" \
  && ./venv/bin/python scripts/golden_diff.py "$OUT/g_before" "$OUT/g_after"
EXIT=$?
set -e

# La limpieza la hace el `trap`, que cubre los dos caminos (aborto de guarda y
# final normal). Llamarla tambien aca la correria dos veces.
echo "EXIT=$EXIT"
exit $EXIT
