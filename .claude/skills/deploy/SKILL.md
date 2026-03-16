---
name: deploy
description: Deploy EcoBalance ERP al VPS (backend + frontend)
disable-model-invocation: true
allowed-tools: Bash(ssh*), Bash(git*), Read
---

# Deploy EcoBalance al VPS

**Servidor:** deploy@76.13.118.195
**Ruta:** /home/deploy/reciclaje-erp

## Argumentos

- `/deploy` — Deploy rama main (produccion)
- `/deploy develop` — Deploy rama develop (pruebas del cliente)

## Pasos

### 1. Verificar estado local

```bash
git status
git log --oneline -3
```

Confirmar que no hay cambios sin commitear que deberian ir en el deploy. Si hay cambios pendientes, AVISAR al usuario (no commitear automaticamente).

### 2. Determinar rama y commits a deployar

- Si `$ARGUMENTS` es "develop" → rama = develop
- Si no → rama = main. Verificar que main esta actualizado con develop:
  ```bash
  git log main..develop --oneline
  ```
  Si hay commits pendientes, AVISAR al usuario antes de continuar (no mergear automaticamente).

Obtener commits desde el ultimo deploy tag:
```bash
git log $(git describe --tags --match "deploy-*" --abbrev=0 2>/dev/null || echo HEAD~10)..{rama} --oneline
```

Guardar esta lista para el reporte final.

### 3. Backup pre-deploy

SIEMPRE hacer backup de la BD antes de deployar:

```bash
ssh deploy@76.13.118.195 "/home/deploy/scripts/backup-database.sh 2>&1 | tail -5"
```

Si el backup falla, DETENER el deploy y avisar al usuario. Guardar nombre del archivo para el reporte.

### 4. Verificar migraciones pendientes

```bash
ssh deploy@76.13.118.195 "cd /home/deploy/reciclaje-erp/backend && source venv/bin/activate && alembic check 2>&1 || alembic history -r current:head 2>&1"
```

Informar al usuario si hay migraciones pendientes antes de aplicarlas.

### 5. Deploy remoto

```bash
ssh deploy@76.13.118.195 "cd /home/deploy/reciclaje-erp && git fetch origin && git checkout {rama} && git pull origin {rama}"
```

### 6. Backend (si hay cambios en backend/)

```bash
ssh deploy@76.13.118.195 "cd /home/deploy/reciclaje-erp/backend && source venv/bin/activate && pip install -r requirements.txt && alembic upgrade head && sudo systemctl restart reciclaje-backend"
```

### 7. Frontend (si hay cambios en frontend/)

```bash
ssh deploy@76.13.118.195 "cd /home/deploy/reciclaje-erp/frontend && npm install && npm run build"
```

### 8. Verificacion y recoleccion de datos

Health check:
```bash
ssh deploy@76.13.118.195 "curl -s http://localhost:8000/api/v1/health && echo '' && curl -s -o /dev/null -w 'Frontend HTTP: %{http_code}' http://localhost/ && echo ''"
```

Estado del servidor:
```bash
ssh deploy@76.13.118.195 "echo '--- DB size ---' && docker exec reciclaje_db psql -U admin -d reciclaje_db -t -c \"SELECT pg_size_pretty(pg_database_size('reciclaje_db'));\" && echo '--- Disk ---' && df -h / | tail -1 | awk '{print \$3 \" used / \" \$2 \" total (\" \$5 \" used)\"}' && echo '--- Orgs ---' && docker exec reciclaje_db psql -U admin -d reciclaje_db -t -c \"SELECT name FROM organizations WHERE is_active = true;\" && echo '--- Last backup ---' && ls -lt /var/backups/ecobalance/ | head -2 && echo '--- Backend errors (last 20 lines) ---' && sudo journalctl -u reciclaje-backend -n 20 --no-pager -p err 2>/dev/null || echo 'Sin errores recientes'"
```

### 9. Git tag

Crear tag con la fecha del deploy:

```bash
git tag -a deploy-$(date +%Y-%m-%d-%H%M) -m "Deploy {rama}: {descripcion breve de los cambios}"
git push origin deploy-$(date +%Y-%m-%d-%H%M)
```

### 10. Reporte

Informar al usuario con este formato:

```
## Deploy completado

- Rama: {rama}
- Tag: deploy-YYYY-MM-DD-HHMM
- Commits deployados:
  - {hash} {mensaje}
  - {hash} {mensaje}

- Backend: healthy / error
- Frontend: HTTP 200 / error
- Migraciones: {aplicadas con nombre / ninguna}

- Backup pre-deploy: {nombre archivo} ({tamano}, Backblaze OK/error)
- Backups automaticos: {ultimo backup y frecuencia cada 6h}

- BD: {tamano} | Disco: {usado} / {total} ({porcentaje})
- Organizaciones activas: {count} ({nombres})
- Errores recientes backend: {ninguno / resumen}
```

Si algo fallo, usar este formato:

```
## Deploy FALLIDO

- Rama: {rama}
- Backup pre-deploy: {nombre} (respaldo seguro)
- Error: {descripcion del error}
- Backend: {estado actual}
- Accion requerida: {que debe decidir el usuario}
```

### Rollback (si algo falla)

```bash
ssh deploy@76.13.118.195 "cd /home/deploy/reciclaje-erp && git log --oneline -5"
```

Mostrar commits recientes y preguntar al usuario a cual revertir. NO hacer rollback automatico.

Si fue una migracion la que fallo, avisar que se puede restaurar desde el backup pre-deploy:
```bash
ssh deploy@76.13.118.195 "/home/deploy/scripts/restore-database.sh local {backup_file}"
```
