#!/bin/bash
#
# EcoBalance - Script de Backup de Base de Datos
# Incluye: backup local + subida a Backblaze B2
#

set -e  # Salir si hay error

# === CONFIGURACIÓN ===
BACKUP_DIR="/var/backups/ecobalance"
DB_CONTAINER="reciclaje_db"
DB_NAME="reciclaje_db"
DB_USER="admin"
DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/ecobalance_$DATE.sql.gz"
RETENTION_DAYS_LOCAL=7
RETENTION_DAYS_CLOUD=30

# Archivos adjuntos (evidencias de tesoreria, fotos de calidad, remisiones).
# Viven en disco, NO en la base: un pg_dump no los incluye.
UPLOADS_DIR="/home/deploy/reciclaje-erp/backend/uploads"

# Backblaze B2 Config
B2_BUCKET="s3://ecobalance-backups"
B2_ENDPOINT="https://s3.us-east-005.backblazeb2.com"
AWS_PROFILE="backblaze"

# === COLORES ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }
warn() { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }
error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"; }

log "Iniciando backup de EcoBalance..."

# Verificar contenedor
if ! docker ps | grep -q $DB_CONTAINER; then
    error "ERROR: El contenedor $DB_CONTAINER no está corriendo"
    exit 1
fi

# === PASO 1: Crear backup local ===
log "Creando backup local..."
docker exec $DB_CONTAINER pg_dump -U $DB_USER $DB_NAME | gzip > "$BACKUP_FILE"

if [ -s "$BACKUP_FILE" ]; then
    SIZE=$(ls -lh "$BACKUP_FILE" | awk '{print $5}')
    log "✅ Backup local creado: $BACKUP_FILE ($SIZE)"
else
    error "ERROR: El backup está vacío"
    exit 1
fi

# === PASO 2: Subir a Backblaze B2 ===
log "Subiendo backup a Backblaze B2..."
if aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 cp "$BACKUP_FILE" "$B2_BUCKET/"; then
    log "✅ Backup subido a Backblaze B2"
else
    error "ERROR: No se pudo subir a Backblaze B2"
    # No salimos, el backup local existe
fi

# === PASO 3: Respaldar archivos adjuntos (uploads/) ===
# El pg_dump NO incluye los archivos en disco: sin este paso, un restore
# devuelve la base completa y las evidencias perdidas (la fila queda, el
# archivo no). `sync` es incremental — solo sube lo nuevo — y va SIN --delete
# a proposito: un adjunto borrado desde la UI conserva su copia en la nube.
# Destino en el prefijo uploads/ para que la limpieza por antiguedad del
# PASO 5, que solo mira el raiz, no los alcance nunca.
log "Sincronizando archivos adjuntos..."
if [ -d "$UPLOADS_DIR" ]; then
    if aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 sync "$UPLOADS_DIR" "$B2_BUCKET/uploads/" --only-show-errors; then
        UP_COUNT=$(find "$UPLOADS_DIR" -type f | wc -l | tr -d ' ')
        UP_SIZE=$(du -sh "$UPLOADS_DIR" | awk '{print $1}')
        log "✅ Adjuntos sincronizados ($UP_COUNT archivos, $UP_SIZE)"
    else
        error "ERROR: No se pudieron sincronizar los adjuntos (el backup de la base SI quedo)"
    fi
else
    warn "No existe $UPLOADS_DIR — nada que sincronizar"
fi

# === PASO 4: Limpiar backups locales antiguos ===
warn "Limpiando backups locales mayores a $RETENTION_DAYS_LOCAL días..."
find $BACKUP_DIR -name "ecobalance_*.sql.gz" -mtime +$RETENTION_DAYS_LOCAL -delete

# === PASO 5: Limpiar backups remotos antiguos ===
warn "Limpiando backups en Backblaze mayores a $RETENTION_DAYS_CLOUD días..."
CUTOFF_DATE=$(date -d "-$RETENTION_DAYS_CLOUD days" +%Y-%m-%d)
aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 ls "$B2_BUCKET/" | while read -r line; do
    FILE_DATE=$(echo "$line" | awk '{print $1}')
    FILE_NAME=$(echo "$line" | awk '{print $4}')
    # El patron es la guarda: sin el, este loop borraria por antiguedad
    # CUALQUIER objeto del raiz del bucket. Los adjuntos viven bajo uploads/
    # (que aca aparece como "PRE uploads/" y no matchea), pero la regla se
    # escribe explicita en vez de descansar en como awk parsea esa linea.
    if [[ "$FILE_NAME" == ecobalance_*.sql.gz ]] && [[ "$FILE_DATE" < "$CUTOFF_DATE" ]] && [[ -n "$FILE_NAME" ]]; then
        warn "Eliminando backup antiguo: $FILE_NAME"
        aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 rm "$B2_BUCKET/$FILE_NAME"
    fi
done

# === RESUMEN ===
log "========== RESUMEN =========="
log "Backups locales:"
ls -lh $BACKUP_DIR/*.sql.gz 2>/dev/null | tail -5
log ""
log "Backups en Backblaze:"
aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 ls "$B2_BUCKET/" | tail -5
log ""
log "Adjuntos en Backblaze:"
aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 ls "$B2_BUCKET/uploads/" --recursive --summarize 2>/dev/null | tail -3
log "============================="
log "✅ Backup completado exitosamente"
