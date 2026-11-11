# Procedimiento: carga de muestra de SAC en producción (10-nov-2026)

**Qué es.** El 10-nov Daniel decidió cargar en la SAC de producción una muestra con el balance del 31-oct, «para ir viendo cómo queda el sistema»: *«esta no será la carga final, pero es mejor ir afinando con datos de carga que ellos vean»*. Los supuestos (exportaciones en bodega propia, pasivos como terceros, activos de ejemplo, drosses en 0, etc.) están en `inventario-preguntas-cliente.md`, en el bloque «Supuestos de la carga de MUESTRA». Ninguna Q cambia de estado por esto.

Base: develop `1e35f80`, igual a producción (`7566bf6`) en `backend/app` y `backend/alembic` (`git diff --stat 7566bf6 HEAD -- backend/app backend/alembic` vacío). **No hace falta deploy.** Los scripts corren en local contra la API de producción y no tocan la base de datos.

**Ritmo.** Las rondas de corrección se hacen en local, donde una carga completa tarda un minuto. A producción solo suben los hitos: esta muestra y la carga final al corte (Q-57). Recargar en producción exige una org nueva porque el saldo inicial de un tercero solo se fija al crearlo; corregirlo en sitio pasaría por un ajuste que cae en el Estado de Resultados.

## 1. Por qué así

El cargador necesita una org «SAC» vacía. El seeder solo la recrea con `--reset`, que está prohibido contra un servidor remoto, y la prohibición tiene una razón real: dar de baja una org (`DELETE /system/organizations/{id}`) **desactiva a todo miembro sin otra membresía, sea superusuario o no**. Además, el backend cuenta como «otra membresía» cualquiera, también la de una org ya dada de baja (`system.py`, `orphaned`).

La salida es no dar de baja nada hasta el final:

1. **Archivar**: la «SAC» actual pasa a llamarse «SAC (archivada AAAA-MM-DD HHMM)». Sigue activa e intacta, y sus usuarios no pierden acceso.
2. Se crea la «SAC» nueva vacía (`seed_sac_org.py --org-vacia`, ahora sin `--reset`), con los 5 usuarios del seeder, y se hace la carga.
3. **Baja** de la archivada, recién después de revisar. El script exige antes que cada miembro de la archivada esté también en la nueva, **sin excepción para superusuarios**. Si falta alguien, se detiene y lo nombra; con `--copiar-miembros` lo agrega con el mismo rol. Después comprueba en la respuesta que la baja haya desactivado a 0.

Para volver atrás, `--modo restaurar --org-id <archivada>` le devuelve el nombre «SAC» a una org archivada y la deja activa, aunque ya esté dada de baja. La pantalla de Sistema → Organizaciones renombra pero no reactiva. El modo se niega si hay otra «SAC» activa o si la org no se llama «SAC (archivada …»: un id equivocado no puede tocar otra empresa.

Todas las escrituras van con el `X-Organization-ID` de la org que se llama exactamente «SAC». Ningún script toca otra empresa.

## 2. Qué cambió en el código (sin commit, pendiente de QA)

| Archivo | Cambio |
|---|---|
| `scripts/seed_sac_org.py` | `--org-vacia` sin `--reset`: se niega si ya hay una «SAC» activa. `--reset` sigue prohibido contra un remoto. `existing_by` lee el listado completo (`list_all`) y se detiene si no llega exacto al `total`: con `!=`, porque un endpoint que ignorara `skip` pasaría del total con duplicados (**N1 resuelto**, O1). **Contra un remoto no crea usuarios**: si falta uno de los 5, se detiene ANTES de crear la org y lo nombra. Antes lo habría creado con la clave constante de `--users-password`, la familia del reseteo-a-constante (#85). `--verificar-usuarios`: lo mismo en solo lectura, para el paso 0. `settings_de_la_org()` pasa a ser una función de módulo, la misma fuente para el seeder y para `revisar`. Bodega nueva «Exportaciones por liquidar» (no receptora, sede Juan Mina; Q-47). Los tres «PRUEBA - …» que se sembraban también en producción pasan a la lista que solo se siembra en local (decisión de Daniel, 10-nov). |
| `scripts/load_sac_opening.py` | Destino remoto habilitado sin `--ensayo` (**B1**: antes moría en el paso 0). `--muestra`: los activos fijos llevan «(MUESTRA)» en el nombre y la nota «MUESTRA: valores de ejemplo… No es la carga final» (**C4**). Tipo de tercero «Pasivo» (Q-56). Cruce de depreciación (§4). Sale el tope de 500 terceros: existía por N1 y, con `list_all`, frenaría una carga final legítima con un mensaje falso. El informe muestra con centavos lo que se tolera como redondeo (O2). |
| `scripts/archivar_org_sac.py` (nuevo) | Modos `revisar` (solo lectura), `archivar`, `baja` y `restaurar` (§1). Lee las orgs con `include_inactive`, porque sin eso el backend no lista las dadas de baja. En `revisar`, los terceros sembrados se comparan contra lo que el seeder siembra en ESE destino. |
| `scripts/ronda_remota.sh` (nuevo) | Los pasos del §3 en orden, deteniéndose en la primera falla. El paso 0 verifica los usuarios antes de archivar (C1). Los argumentos de más van al cargador en las tres corridas. |
| `tests/test_archivar_org_sac.py` (nuevo), `tests/test_load_sac_opening.py` | 153 tests puros (`--noconftest`, ~1 s). Los fakes se portan como el backend: la baja calcula los desactivados con su regla (con un 0 fijo, el test de B2 no podía caer), y el listado de orgs no devuelve las dadas de baja sin `include_inactive` (con el fake devolviéndolas siempre, el test de `restaurar` pasaba y el script no las hallaba; lo encontró el ensayo 3). |

## 3. Pasos en producción

**Antes de empezar.**
- (a) OK explícito de Daniel para escribir en producción.
- (b) La credencial del superusuario de producción va en un archivo de Daniel fuera del repo, por ejemplo `~/.config/sac-prod.env` con `chmod 600`, `SEED_SU_EMAIL=` y `SEED_SU_PASSWORD=`. Se carga con `set -a; . ~/.config/sac-prod.env; set +a`. Nunca en la línea de comandos, en el chat ni en un log.
- (c) Exportar el Sheet a `.xlsx` justo antes y anotar su sha256: Johana puede haberlo editado.

```bash
cd backend
API=https://api.ecobalance.cc
LIBRO=<ruta>/carga_31oct_muestra.xlsx

# 1. Solo lectura: qué tiene hoy la SAC de prod que la nueva no heredaría
./venv/bin/python scripts/archivar_org_sac.py --modo revisar --api-url $API

# 2. Simula, archiva, crea la org vacía, carga y concilia (se detiene en la primera falla)
scripts/ronda_remota.sh $API "$LIBRO" 2026-10-31 <ruta>/informe_muestra_prod.md --muestra

# 3. Daniel revisa la SAC nueva en la pantalla

# 4. Baja de la archivada (--copiar-miembros solo si el paso 1 lo pidió)
./venv/bin/python scripts/archivar_org_sac.py --modo baja --org-id <id de la archivada> --apply --api-url $API
```

**Paso 1, qué mira.** Lista lo que la nueva NO hereda, con conteos y diferencias:
- **usuarios:** que los 5 del seeder existan en el servidor, y los miembros que el seeder no vuelve a agregar o que tienen un rol que la nueva no tendrá (superusuarios incluidos);
- **documentos:** compras, ventas, doble partidas, entradas, salidas, crisol, tesorería, traslados, ajustes, transformaciones y activos;
- **lo que el seeder nunca siembra:** conductores, vehículos y listas por proveedor;
- **lo creado a mano en los catálogos:** materiales, bodegas, cuentas, terceros, categorías de gasto y de material, unidades de negocio. Se marcan también los terceros y las cuentas con saldo. Los tres «PRUEBA - …» de la SAC actual salen acá: la nueva ya no los trae;
- **tarifas, fórmulas y perfiles:** tarifas vigentes, fórmulas vigentes y perfiles kg (incluida la marca `lead_product`) que difieran del seeder;
- **retenciones y kilos:** tarifas de retención, entidades de retención con saldo, precios del plomo y cuentas kg con saldo;
- **roles y settings:** roles custom y permisos cambiados, y settings de la org contra los del seeder (sedes comparadas por nombre de bodega).

Nada de eso se borra: queda en la archivada. Pero la nueva nace sin ello. **Si aparece algo, decide Daniel antes del paso 2.** Si sale «Usuario del seeder … no existe», el paso 2 se va a detener: hay que crearlo antes desde Sistema → Usuarios, con una clave propia.

**Paso 2, lo esperado.** Lo primero que hace es verificar, en solo lectura, que existan los 5 usuarios: si falta uno se detiene ahí, antes de archivar nada. Al final, `Fallas de conciliación: 0` y `EXIT=0`. `--muestra` tiene que ir: es la marca de los activos de ejemplo, y como el nombre del activo es la llave de la conciliación, va en las tres corridas (el script se encarga). Si el seeder sale con 3 (DECISIÓN PENDIENTE, #109), el script se detiene y decide Daniel; en una org nueva no debería pasar.

**Si falla a mitad.** La archivada sigue activa e intacta en todos los casos. Qué hacer depende de si la «SAC» nueva llegó a existir (Sistema → Organizaciones):
- *No hay ninguna «SAC» activa* (falló en el paso 2 antes de crearla). Volver a correr la ronda moriría en el paso 1 con «hay 0». Se restaura la archivada y se empieza de nuevo:
  ```bash
  ./venv/bin/python scripts/archivar_org_sac.py --modo restaurar --org-id <id de la archivada> --apply --api-url $API
  ```
- *Hay una «SAC» nueva a medio cargar* (falló en el paso 2 después de crearla, o del 3 en adelante). Se archiva también (`--modo archivar --apply`) y se vuelve a correr el paso 2; al final se dan de baja las dos.

Los dos caminos se ejercieron contra el alias (§4).

**Volver a la anterior.**
- *Antes de la baja:* se archiva la nueva y, en Sistema → Organizaciones, se le devuelve el nombre «SAC» a la archivada.
- *Después de la baja:* tampoco hace falta la base, pero sí el script, porque la pantalla renombra y no reactiva. Se archiva la nueva (`--modo archivar --apply`) y después `--modo restaurar --org-id <id de la vieja> --apply`: el PATCH acepta `is_active` (`SystemOrgUpdate`) y encuentra la org aunque esté dada de baja. La baja no borra membresías y desactivó 0 usuarios, así que todos vuelven a entrar.

**Lo que señaló QA para Daniel.**
- (1) Los saldos de Empleados y la nómina por pagar entran como terceros. El Sheet estaba restringido justamente por la nómina. **Decidido por Daniel el 10-nov: se cargan como están.** Medido contra el código:
  - En pantalla los montos los ven solo los admins (Hugo, Johana, Yurani).
  - `bascula_sac` (Erwin) y `revisor_inventario` (David) ven los nombres en Terceros, pero no la columna de saldo (`third_parties.view_balance`) ni el estado de cuenta (`treasury.view_statements`).
  - El listado de terceros sí trae `current_balance` en la respuesta de la API a cualquiera con `third_parties.view`; solo lo esconde la pantalla. Es así en todas las empresas y la carga no lo cambia.
- (2) Entre archivar y la baja, lo que alguien registre en la archivada deja de verse, así que conviene avisarle a Hugo y Johana que no registren en SAC durante ese rato. Después de la baja, cada usuario tiene que volver a elegir «SAC» en el selector.

## 4. Ensayos en local

Artefactos en el scratchpad de la sesión, en `ensayo/` (localhost), `ensayo2/` y `ensayo3/` (alias).

**Ensayo 1, contra `http://localhost:8000` (23:07–23:15Z).**
- **Primer intento: 1 falla real.** Activos fijos cuadraba (diferencia 0) y aun así quedaban **280.000.000 «sin explicar»**. El supuesto 6 reparte la depreciación global dentro de los activos, así que la fila «DEPRECIACIÓN ACUMULADA» (marcada «No») ya está en el sistema, en el mismo rubro, y el cargador la seguía contando como explicación. Se arregló con un cruce, no a mano: con reparto, esa línea queda `en_el_sistema` y tiene que coincidir con lo repartido. Si no coincide, falla. Plantado 3/3.
- **Segundo intento: 0 fallas**, después de archivar la SAC a medio cargar del primer intento, que es el camino de «si falla a mitad».
- **Lo que este ensayo NO podía ver** (B1 de QA): contra `localhost`, todas las ramas `is_local` toman su lado local. El cargador, de hecho, todavía rechazaba el remoto.

**Ensayo 2, contra el alias `http://127.1:8000` (23:36:53–23:37:11Z).** El alias llega al mismo backend pero el código lo ve como remoto (`is_local=False`, impreso en el log), así que cada rama toma su lado de producción:
- **Revisar → archivar → org vacía → saldos → provisión → resto → conciliación:** **0 fallas, EXIT=0**. 473 entidades sin diferencia. Activos fijos `12.586.769.525 | 12.586.769.525 | 0 | 0 | 0`; depreciación 280.000.000 contra 280.000.000. Los 39 activos quedaron con «(MUESTRA)» en el nombre y la nota de ejemplo (medido en la base).
- **Ramas remotas, medidas.** El seeder no registró a nadie: los 5 «ya existe (conserva su password)». Usuarios modificados en la ventana: **ninguno** (el forzado de claves es solo local). Terceros de prueba locales en la SAC nueva: **0**.
- **Control positivo de B2.** El usuario de control se marcó **superusuario** en la base de dev (y se revirtió después), con membresía solo en la SAC que se archivó. `revisar` lo avisó con «(superusuario) … --copiar-miembros». La baja sin `--copiar-miembros` **se negó y lo nombró**, cuando el código anterior lo habría eximido. Con la opción, lo copió y la baja desactivó **0**.
- **Las otras empresas, medido en la base.** En las 50 tablas con `organization_id`, filas no-SAC creadas o modificadas en la ventana: **0**. Control positivo: 377 terceros SAC. Las 6 orgs no-SAC siguen activas y sin cambios, y ningún usuario de otra empresa quedó inactivo.

**Ensayo 3, contra el alias, después del GO condicionado de QA (00:05–00:08Z del 11-nov).**
- **Control negativo de C1.** Con `david@sac.com` oculto en la base de dev (renombrado y devuelto), la ronda se detuvo en el paso 0, lo nombró y no archivó nada (`control_c1_paso0.log`).
- **La ronda con `--muestra`:** 0 fallas, EXIT=0. Ningún listado cortó con el `!=` de `list_all`, que es la medición de que ningún endpoint real devuelve más filas que su `total`. La SAC nueva nació con **0 terceros PRUEBA** (374 terceros). La vieja tiene 3, sembrados con el código anterior, y `revisar` los avisó. 39 de 39 activos con «(MUESTRA)». El informe trae «Con centavos: Inventario -0,72».
- **La reversa encontró un defecto propio.** `restaurar` buscaba la org en `GET /system/organizations`, que sin `include_inactive` no lista las dadas de baja, y respondía «No existe la org». El test pasaba porque el fake sí las listaba. Se arregló el script (pide `include_inactive`) y el fake (se porta como el backend). El log que lo encontró se conserva (`..._r1_ENCONTRO_include_inactive.log`), y antes hay otro inválido porque zsh no separó una variable con varias palabras.
- **Reversa r2, todo por la API** (`reversa_alias3_r2.log`):
  - Restaurar con otra «SAC» activa se niega.
  - Restaurar con el id de otra empresa se niega y la nombra.
  - Archivar la nueva deja el estado de C1, sin ninguna «SAC» activa.
  - Restaurar la vieja dada de baja la reactiva con sus miembros.
  - Se vuelve a dejar la nueva y se da de baja la vieja con 0 desactivados.
  - Repetir la baja se niega con «ya está dada de baja», un mensaje que antes era inalcanzable con el backend real.
- **Las otras empresas:** 0 filas no-SAC en 50 tablas, control positivo 374, 6 orgs no-SAC activas y sin cambios, ningún usuario modificado (`otras_orgs_alias3.txt`).

**Plantado.**
- **r5:** depreciación 3/3 y la primera versión de `revisar` 3/3.
- **r6:** **8/8 en la diagonal**, uno por arreglo: B1, B2 en la baja, B2 en `revisar`, perfil kg, sedes por nombre, C4, usuario faltante antes de crear la org, y no registrar contra un remoto.
- **r7:** **10/10** sobre C1, C2 y O1–O3. **r7b**, repetido sobre el árbol con `include_inactive`: **11/11**, con P11 (sin `include_inactive`) tumbando exactamente los 5 predichos.
- Todas las rondas con matriz y sha256 antes de plantar, respaldo por ruta y restauración verificada por sha256.

**Gates.** 153 tests puros + 15 de la guarda del reloj (con su BD; 5433 libre), ruff limpio y `bash -n`. La suite completa no se corrió porque el ciclo no toca `app/`.

## 5. Lo que sigue pendiente para la carga FINAL

- Entidades de impuestos y retenciones: necesitan un cambio en `app/`, porque la categoría `taxes` no se asigna por API (#112 D4d).
- Activos reales (Q-52).
- Drosses (Hugo).
- Las filas en «Preguntar».
- La fecha de corte (Q-57).
