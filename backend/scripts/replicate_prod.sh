#!/bin/bash
# Replica la base de datos de produccion a la BD local de desarrollo.
# Uso: ./scripts/replicate_prod.sh
#
# Descarga el backup mas reciente del VPS y lo restaura en la BD local (puerto 5434).
# La BD local se BORRA completamente antes de restaurar.

set -e

VPS="deploy@76.13.118.195"
LOCAL_CONTAINER="reciclaje_dev_db"
LOCAL_DB="reciclaje_db"
LOCAL_USER="admin"
BACKUP_DIR="/tmp/ecobalance-replicate"

echo "=== Replicar Produccion → Desarrollo ==="
echo ""

# 1. Obtener backup mas reciente del VPS
echo "[1/4] Descargando backup mas reciente del VPS..."
mkdir -p "$BACKUP_DIR"
LATEST=$(ssh "$VPS" "ls -t /var/backups/ecobalance/*.sql.gz | head -1")
echo "  Backup: $(basename $LATEST)"
scp "$VPS:$LATEST" "$BACKUP_DIR/latest.sql.gz"

# 2. Verificar que el contenedor local esta corriendo
echo "[2/4] Verificando BD local..."
if ! docker ps --format '{{.Names}}' | grep -q "$LOCAL_CONTAINER"; then
    echo "  ERROR: Contenedor $LOCAL_CONTAINER no esta corriendo."
    echo "  Ejecuta: POSTGRES_PASSWORD=localdev123 docker-compose up -d"
    exit 1
fi

# 3. Restaurar
echo "[3/4] Restaurando en BD local (esto borra todos los datos locales)..."
gunzip -c "$BACKUP_DIR/latest.sql.gz" > "$BACKUP_DIR/latest.sql"

# Drop y recrear la BD
docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d postgres -c "DROP DATABASE IF EXISTS $LOCAL_DB WITH (FORCE);" 2>/dev/null
docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d postgres -c "CREATE DATABASE $LOCAL_DB OWNER $LOCAL_USER;"

# Restaurar el dump
docker cp "$BACKUP_DIR/latest.sql" "$LOCAL_CONTAINER:/tmp/restore.sql"
docker exec "$LOCAL_CONTAINER" psql -U "$LOCAL_USER" -d "$LOCAL_DB" -f /tmp/restore.sql -q 2>/dev/null

# 4. Limpiar
echo "[4/4] Limpiando archivos temporales..."
rm -rf "$BACKUP_DIR"
docker exec "$LOCAL_CONTAINER" rm -f /tmp/restore.sql

echo ""
echo "✅ Replicacion completada. BD local ahora tiene los datos de produccion."
echo "   Conectar: postgresql://admin:localdev123@localhost:5434/reciclaje_db"
