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
# Uso: scripts/golden_run.sh <commit-base> <directorio-de-salida>
set -euo pipefail

BASE_COMMIT="${1:?falta el commit base (BEFORE)}"
OUT="${2:?falta el directorio de salida}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WT="${OUT}/wt-before"
P_BEFORE=8001
P_AFTER=8002

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

# ⚠️ El `exec` no es cosmetico: sin el, `$!` es el PID del SUBSHELL y no el de
# uvicorn, asi que el `kill` del final mata un proceso que ya murio y deja los
# backends VIVOS — que es exactamente la causa de C1. La primera version de este
# script reproducia el problema que venia a evitar; lo destapo su propio control
# positivo, no una lectura.
(cd "$WT/backend" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_BEFORE" > "$OUT/b_before.log" 2>&1) &
echo $! > "$OUT/pid_before"
(cd "$REPO/backend" && exec nohup ./venv/bin/uvicorn app.main:app --port "$P_AFTER" > "$OUT/b_after.log" 2>&1) &
echo $! > "$OUT/pid_after"
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
