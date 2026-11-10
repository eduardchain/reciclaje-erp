#!/usr/bin/env bash
# Una ronda de la carga inicial de SAC contra la base LOCAL (plan
# docs/planes/plan-sac-carga-inicial-ronda1.md §2). Corre los cinco pasos en
# orden y se detiene en el primero que falle. Credenciales por
# SEED_SU_EMAIL / SEED_SU_PASSWORD, nunca en la linea de comandos.
#
# Uso: SEED_SU_EMAIL=... SEED_SU_PASSWORD=... scripts/ronda_local.sh <libro.xlsx> <corte YYYY-MM-DD> <informe.md>
#
# El orden es la solucion de G1: `initial_balance` solo existe al CREAR, y el
# seeder es get-or-create por nombre. Primero una org VACIA, despues los saldos
# (crean Willard S.A, Caja Circunvalar... con su saldo), y recien entonces el
# seeder en provision, que los reutiliza por nombre (incluido el titular de las
# cuentas kg).
set -euo pipefail
[ $# -eq 3 ] || { echo "Uso: $0 <libro.xlsx> <corte> <informe.md>" >&2; exit 2; }
LIBRO=$1; CORTE=$2; INFORME=$3
: "${SEED_SU_EMAIL:?Falta SEED_SU_EMAIL}"
: "${SEED_SU_PASSWORD:?Falta SEED_SU_PASSWORD}"
cd "$(dirname "$0")/.."
PY=./venv/bin/python
CARGA=(scripts/load_sac_opening.py --file "$LIBRO" --corte "$CORTE" --ensayo)

paso() { echo; echo "=== $(date -u '+%Y-%m-%d %H:%M:%SZ') paso $*"; }
paso "1/5 org SAC vacía (reset local)"; $PY scripts/seed_sac_org.py --apply --reset --org-vacia
paso "2/5 saldos";                      $PY "${CARGA[@]}" --fase saldos --apply
paso "3/5 seeder en provisión";         $PY scripts/seed_sac_org.py --apply
paso "4/5 resto";                       $PY "${CARGA[@]}" --fase resto --apply
paso "5/5 conciliación";                $PY "${CARGA[@]}" --conciliar --salida "$INFORME"
echo; echo "=== ronda completa: informe en $INFORME"
