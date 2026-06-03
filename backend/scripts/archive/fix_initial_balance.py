"""
Script para resetear initial_balance = 0 en datos existentes del dev DB.

Los datos existentes ya tienen todos sus cambios de saldo rastreados como operaciones,
por lo que initial_balance debe ser 0 (el server_default de la migración).
La migración original copió erróneamente current_balance → initial_balance.

Uso:
    cd backend && python scripts/fix_initial_balance.py
"""
import sys
import os

# Agregar backend/ al path para importar app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from app.core.config import settings

def main():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        result_accounts = conn.execute(
            text("UPDATE money_accounts SET initial_balance = 0 WHERE initial_balance != 0")
        )
        result_tp = conn.execute(
            text("UPDATE third_parties SET initial_balance = 0 WHERE initial_balance != 0")
        )
        conn.commit()

    print(f"money_accounts actualizadas: {result_accounts.rowcount}")
    print(f"third_parties actualizadas: {result_tp.rowcount}")
    print("Done. initial_balance = 0 para todos los registros existentes.")

if __name__ == "__main__":
    main()
