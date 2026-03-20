# EcoBalance ERP — Guía de Operaciones y Mantenimiento

**Versión 1.0 | Marzo 2026 | CONFIDENCIAL**

---

## 1. Información del Servidor

Datos de acceso y configuración del servidor de producción.

| Parámetro | Valor |
|-----------|-------|
| IP del Servidor | 76.13.118.195 |
| Usuario SSH | deploy |
| URL de la Aplicación | http://76.13.118.195 |
| Ruta del Proyecto | /home/deploy/reciclaje-erp |
| Backend | /home/deploy/reciclaje-erp/backend |
| Frontend | /home/deploy/reciclaje-erp/frontend |
| Base de Datos | PostgreSQL 16 (Docker: reciclaje_db) |
| Backups Locales | /var/backups/ecobalance |
| Backups Nube | Backblaze B2: ecobalance-backups |

---

## 2. Proceso de Deploy (Actualización)

Sigue estos pasos cada vez que necesites subir cambios a producción.

### 2.1 Preparar el código (desde tu máquina local)

Una vez que todos los cambios han sido probados en `develop`, mergear a `main`:

```bash
# En tu máquina local
git checkout main
git pull origin main
git merge develop
git push origin main
```

> **Nota:** La rama `main` siempre refleja exactamente lo que está en producción. La rama `develop` es para desarrollo y pruebas.

### 2.2 Conectar al servidor

```bash
ssh deploy@76.13.118.195
```

### 2.3 Actualizar código fuente

```bash
cd /home/deploy/reciclaje-erp
git pull origin main
```

### 2.4 Actualizar Backend (si hay cambios)

```bash
cd /home/deploy/reciclaje-erp/backend
source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
sudo systemctl restart reciclaje-backend
sudo systemctl status reciclaje-backend
```

### 2.5 Actualizar Frontend (si hay cambios)

```bash
cd /home/deploy/reciclaje-erp/frontend
npm install
npm run build
```

### 2.6 Verificar que todo funciona

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost/
```

---

## 3. Sistema de Backups

El sistema realiza backups automáticos cada 6 horas (00:00, 06:00, 12:00, 18:00 UTC).

### 3.1 Ubicación de los Backups

| Ubicación | Ruta / Bucket | Retención |
|-----------|---------------|-----------|
| Local (VPS) | /var/backups/ecobalance/ | 7 días |
| Nube (Backblaze B2) | ecobalance-backups | 30 días |

### 3.2 Ejecutar Backup Manual

```bash
/home/deploy/scripts/backup-database.sh
```

Este comando crea un backup local Y lo sube a Backblaze automáticamente.

### 3.3 Ver Backups Disponibles

```bash
/home/deploy/scripts/restore-database.sh
```

### 3.4 Ver Logs de Backups Automáticos

```bash
tail -50 /var/log/ecobalance-backup.log
```

---

## 4. Restauración Completa (Disaster Recovery)

> ⚠️ **ADVERTENCIA:** Esta operación reemplaza TODOS los datos de TODAS las organizaciones. Usar solo en caso de pérdida total del servidor o corrupción masiva de datos.

### 4.1 Desde Backup Local

```bash
# Ver backups disponibles
/home/deploy/scripts/restore-database.sh

# Restaurar desde backup local
/home/deploy/scripts/restore-database.sh local ecobalance_2026-03-09_20-09-39.sql.gz
```

### 4.2 Desde Backblaze (Nube)

```bash
# Restaurar desde Backblaze (descarga automática)
/home/deploy/scripts/restore-database.sh cloud ecobalance_2026-03-09_20-09-39.sql.gz
```

---

## 5. Restauración Selectiva por Organización

Restaura los datos de UNA sola empresa sin afectar a las demás. Ideal cuando un cliente reporta pérdida de datos.

### 5.1 Listar Organizaciones en un Backup

```bash
/home/deploy/scripts/restore-organization.sh list-orgs ecobalance_2026-03-09_20-09-39.sql.gz
```

Esto muestra todas las empresas contenidas en el backup con su ID.

### 5.2 Restaurar una Organización Específica

```bash
/home/deploy/scripts/restore-organization.sh restore ecobalance_2026-03-09_20-09-39.sql.gz ffb6d0a7-28a3-4191-a71f-43d74f5ae8fe
```

El script te pedirá confirmación escribiendo `SI RESTAURAR`.

### 5.3 ¿Qué hace este proceso?

1. Crea una base de datos temporal con el backup
2. Extrae SOLO los datos de la organización seleccionada
3. Borra los datos actuales de esa organización en producción
4. Inserta los datos del backup
5. Las demás organizaciones NO son afectadas

---

## 6. Comandos Útiles

### 6.1 Estado de Servicios

```bash
# Ver estado del backend
sudo systemctl status reciclaje-backend

# Ver estado de nginx
sudo systemctl status nginx

# Ver estado de PostgreSQL
docker ps
```

### 6.2 Reiniciar Servicios

```bash
# Reiniciar backend
sudo systemctl restart reciclaje-backend

# Reiniciar nginx
sudo systemctl reload nginx

# Reiniciar PostgreSQL
docker restart reciclaje_db
```

### 6.3 Ver Logs

```bash
# Logs del backend (últimas 100 líneas)
sudo journalctl -u reciclaje-backend -n 100

# Logs del backend en tiempo real
sudo journalctl -u reciclaje-backend -f

# Logs de nginx
sudo tail -f /var/log/nginx/ecobalance_access.log
sudo tail -f /var/log/nginx/ecobalance_error.log

# Logs de backups
tail -50 /var/log/ecobalance-backup.log
```

### 6.4 Acceso a Base de Datos

```bash
# Conectar a PostgreSQL
docker exec -it reciclaje_db psql -U admin -d reciclaje_db

# Ver organizaciones
docker exec reciclaje_db psql -U admin -d reciclaje_db -c "SELECT id, name FROM organizations;"
```

---

## 7. Solución de Problemas

### 7.1 La aplicación no carga

**Verificar que el backend está corriendo:**

```bash
sudo systemctl status reciclaje-backend
```

**Si está 'inactive' o 'failed', reiniciar:**

```bash
sudo systemctl restart reciclaje-backend
```

### 7.2 Error 502 Bad Gateway

El backend no está respondiendo. Verificar logs:

```bash
sudo journalctl -u reciclaje-backend -n 50
```

### 7.3 Error de conexión a base de datos

Verificar que PostgreSQL está corriendo:

```bash
docker ps | grep reciclaje_db

# Si no está corriendo:
docker start reciclaje_db
```

### 7.4 El frontend muestra versión antigua

Recompilar el frontend:

```bash
cd /home/deploy/reciclaje-erp/frontend
npm run build
```

Pedir al usuario que limpie la caché del navegador (Ctrl+Shift+R).

---

## 8. Carga Inicial de Datos Maestros

Para cargar datos maestros (materiales, terceros, categorías, etc.) desde un archivo Excel.

### 8.1 Subir el archivo Excel al servidor

```bash
scp docs/CargaInicial_EcoBalance_v2_cliente.xlsx deploy@76.13.118.195:/home/deploy/reciclaje-erp/docs/
```

### 8.2 Conectar al servidor

```bash
ssh deploy@76.13.118.195
```

### 8.3 Obtener el UUID de la organización

```bash
docker exec reciclaje_db psql -U admin -d reciclaje_db -c "SELECT id, name FROM organizations;"
```

### 8.4 Ejecutar validación (dry-run)

```bash
cd /home/deploy/reciclaje-erp/backend
source venv/bin/activate
python scripts/load_initial_data.py \
    --file ../docs/CargaInicial_EcoBalance_v2_cliente.xlsx \
    --email admin@empresa.com \
    --password <password> \
    --org-id <uuid_de_la_organizacion> \
    --dry-run
```

Verificar que el resumen muestre **0 errores** antes de continuar.

### 8.5 Ejecutar carga real

```bash
python scripts/load_initial_data.py \
    --file ../docs/CargaInicial_EcoBalance_v2_cliente.xlsx \
    --email admin@empresa.com \
    --password <password> \
    --org-id <uuid_de_la_organizacion>
```

### 8.6 Limpieza y Recarga (Reset de datos maestros)

Si necesitas borrar todos los datos transaccionales y maestros para recargar desde cero (manteniendo org, usuarios, roles y permisos):

```bash
# 1. Backup primero
/home/deploy/scripts/backup-database.sh

# 2. Limpiar TODO excepto org/users/roles/permisos
docker exec reciclaje_db psql -U admin -d reciclaje_db -c "
TRUNCATE TABLE
  profit_distribution_lines, profit_distributions,
  scheduled_expense_applications, scheduled_expenses,
  asset_depreciations, fixed_assets,
  sale_commissions, purchase_commissions,
  double_entry_lines, double_entries,
  sale_lines, sales, purchase_lines, purchases,
  money_movements, material_cost_histories,
  material_transformation_lines, material_transformations,
  inventory_adjustments, inventory_movements,
  price_lists, user_account_assignments,
  materials, material_categories,
  money_accounts, warehouses, business_units,
  expense_categories,
  third_party_category_assignments, third_parties, third_party_categories
CASCADE;
"

# 3. Verificar que org/users/roles siguen intactos
docker exec reciclaje_db psql -U admin -d reciclaje_db -c "
SELECT 'organizations' as tabla, count(*) FROM organizations
UNION ALL SELECT 'users', count(*) FROM users
UNION ALL SELECT 'roles', count(*) FROM roles;
"

# 4. Re-ejecutar carga inicial
cd /home/deploy/reciclaje-erp/backend
source venv/bin/activate
python scripts/load_initial_data.py \
    --file ../docs/CargaInicial_EcoBalance_v2_cliente.xlsx \
    --email admin@ecobalance.com \
    --password <password> \
    --org-id <uuid>
```

### 8.7 Notas importantes

- El script es **idempotente**: si se ejecuta dos veces, las entidades ya existentes se omiten
- Los roles, permisos y la organización **no se tocan** — solo carga datos maestros
- El orden de las hojas importa: el script procesa en orden de dependencia (UNs → Categorías → Terceros → Materiales → Precios)
- Hacer un **backup antes** de cualquier operación destructiva
- La limpieza usa `TRUNCATE CASCADE` — borra en cascada todas las tablas dependientes

---

## 9. Información de Contacto

Para soporte técnico o emergencias:

| Concepto | Información |
|----------|-------------|
| Desarrollador | Eduardo Chain |
| Proveedor VPS | Hostinger |
| Backups en Nube | Backblaze B2 |

---

*— Fin del Documento —*
