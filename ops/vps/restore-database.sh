#!/bin/bash
#
# EcoBalance - Script de Restauración de Base de Datos
# 
# Uso:
#   ./restore-database.sh                     # Lista backups disponibles
#   ./restore-database.sh local <archivo>     # Restaura desde backup local
#   ./restore-database.sh cloud <archivo>     # Descarga de Backblaze y restaura
#   ./restore-database.sh uploads             # Restaura los archivos adjuntos
#

set -e

# === CONFIGURACIÓN ===
BACKUP_DIR="/var/backups/ecobalance"
DB_CONTAINER="reciclaje_db"
DB_NAME="reciclaje_db"
DB_USER="admin"

# Archivos adjuntos: viven en disco, no en la base. El pg_dump no los trae.
UPLOADS_DIR="/home/deploy/reciclaje-erp/backend/uploads"

# Backblaze B2 Config
B2_BUCKET="s3://ecobalance-backups"
B2_ENDPOINT="https://s3.us-east-005.backblazeb2.com"
AWS_PROFILE="backblaze"

# === COLORES ===
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}$1${NC}"; }
warn() { echo -e "${YELLOW}$1${NC}"; }
error() { echo -e "${RED}$1${NC}"; }
info() { echo -e "${BLUE}$1${NC}"; }

# === FUNCIONES ===

list_backups() {
    echo ""
    info "========== BACKUPS LOCALES =========="
    if ls $BACKUP_DIR/*.sql.gz 1> /dev/null 2>&1; then
        ls -lh $BACKUP_DIR/*.sql.gz
    else
        warn "No hay backups locales"
    fi
    
    echo ""
    info "========== BACKUPS EN BACKBLAZE =========="
    aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 ls "$B2_BUCKET/"
    
    echo ""
    info "========== CÓMO RESTAURAR =========="
    echo "Desde backup local:"
    echo "  ./restore-database.sh local ecobalance_2026-03-09_20-09-39.sql.gz"
    echo ""
    echo "Desde Backblaze:"
    echo "  ./restore-database.sh cloud ecobalance_2026-03-09_20-09-39.sql.gz"
    echo ""
}

restore_local() {
    local BACKUP_FILE="$BACKUP_DIR/$1"
    
    if [ ! -f "$BACKUP_FILE" ]; then
        error "ERROR: No se encontró el archivo $BACKUP_FILE"
        exit 1
    fi
    
    warn "⚠️  ADVERTENCIA: Esto reemplazará TODOS los datos actuales"
    warn "Archivo a restaurar: $BACKUP_FILE"
    read -p "¿Estás seguro? Escribe 'SI' para continuar: " CONFIRM
    
    if [ "$CONFIRM" != "SI" ]; then
        log "Restauración cancelada"
        exit 0
    fi
    
    log "Restaurando desde $BACKUP_FILE..."
    
    # Descomprimir y restaurar
    gunzip -c "$BACKUP_FILE" | docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME
    
    log "✅ Restauración completada exitosamente"
}

restore_cloud() {
    local BACKUP_NAME="$1"
    local TEMP_FILE="$BACKUP_DIR/temp_restore_$BACKUP_NAME"
    
    warn "⚠️  ADVERTENCIA: Esto reemplazará TODOS los datos actuales"
    warn "Archivo a restaurar: $BACKUP_NAME (desde Backblaze)"
    read -p "¿Estás seguro? Escribe 'SI' para continuar: " CONFIRM
    
    if [ "$CONFIRM" != "SI" ]; then
        log "Restauración cancelada"
        exit 0
    fi
    
    log "Descargando backup desde Backblaze..."
    aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 cp "$B2_BUCKET/$BACKUP_NAME" "$TEMP_FILE"
    
    log "Restaurando base de datos..."
    gunzip -c "$TEMP_FILE" | docker exec -i $DB_CONTAINER psql -U $DB_USER -d $DB_NAME
    
    # Limpiar archivo temporal
    rm -f "$TEMP_FILE"
    
    log "✅ Restauración completada exitosamente"
}

restore_uploads() {
    log "Restaurando archivos adjuntos desde Backblaze..."
    warn "Destino: $UPLOADS_DIR"
    mkdir -p "$UPLOADS_DIR"
    # sync SIN --delete a proposito: un restore de adjuntos es "traer de vuelta
    # lo que falte", no "dejar el disco identico a la nube". Asi no destruye
    # archivos subidos despues del ultimo backup.
    aws --profile $AWS_PROFILE --endpoint-url $B2_ENDPOINT s3 sync "$B2_BUCKET/uploads/" "$UPLOADS_DIR"
    COUNT=$(find "$UPLOADS_DIR" -type f | wc -l | tr -d ' ')
    SIZE=$(du -sh "$UPLOADS_DIR" | awk '{print $1}')
    log "✅ Adjuntos restaurados ($COUNT archivos, $SIZE en disco)"
    warn "Si el backend no los sirve, revisar dueno: chown -R deploy:deploy $UPLOADS_DIR"
}

# === MAIN ===

case "${1:-list}" in
    list)
        list_backups
        ;;
    local)
        if [ -z "$2" ]; then
            error "ERROR: Especifica el archivo a restaurar"
            echo "Uso: ./restore-database.sh local <nombre_archivo.sql.gz>"
            exit 1
        fi
        restore_local "$2"
        ;;
    cloud)
        if [ -z "$2" ]; then
            error "ERROR: Especifica el archivo a restaurar"
            echo "Uso: ./restore-database.sh cloud <nombre_archivo.sql.gz>"
            exit 1
        fi
        restore_cloud "$2"
        ;;
    uploads)
        restore_uploads
        ;;
    *)
        echo "Uso: ./restore-database.sh [list|local|cloud|uploads] [archivo]"
        exit 1
        ;;
esac
