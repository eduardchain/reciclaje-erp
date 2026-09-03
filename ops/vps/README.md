# Scripts del VPS (copia de referencia)

Estos dos scripts **viven y se ejecutan en el servidor**, en `/home/deploy/scripts/`.
Lo que hay acá es una copia versionada: sirve para leer qué hacen, revisar cambios
en un diff y recuperarlos si el servidor se pierde — **no** se despliegan solos.

Se versionan porque hasta 2026-09-01 el único registro de un cambio era un `.bak`
en el propio servidor: si alguien tocaba el backup, nadie más se enteraba, y es
justo el script del que depende poder deshacer cualquier otro error.

| Script | Qué hace |
|---|---|
| `backup-database.sh` | `pg_dump` + subida a Backblaze, **y** `s3 sync` incremental de `uploads/`. Corre por cron cada 6 h. |
| `restore-database.sh` | `list` / `local` / `cloud` para la base, y `uploads` para los archivos adjuntos. |

## Sobre el respaldo de `uploads/` (2026-09-01)

Un `pg_dump` **no** incluye los archivos en disco: hasta esa fecha, restaurar
devolvía las filas y perdía las evidencias. Dos decisiones que no hay que deshacer:

- **Los adjuntos van al prefijo `uploads/` del bucket, no al raíz.** El paso de
  limpieza borra por antigüedad todo lo que encuentra en el raíz: ahí durarían 30
  días. De paso ese loop se acotó al patrón `ecobalance_*.sql.gz`, porque antes
  habría borrado cualquier objeto viejo que apareciera.
- **`sync` sin `--delete`, en las dos direcciones.** Al respaldar, un adjunto
  borrado desde la aplicación conserva su copia; al restaurar, se trae lo que
  falte sin destruir lo que se subió después del último backup.

## Si se cambian

Editar acá, copiar al servidor con `scp`, y correrlos una vez para verificar
(`bash -n` primero). Los originales previos quedaron como `.bak-20260901`.
