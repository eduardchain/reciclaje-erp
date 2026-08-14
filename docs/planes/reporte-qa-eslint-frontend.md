# Reporte para QA — ESLint en el frontend (#97)

**Fecha:** 2026-08-14 · **Estado:** implementado, **SIN commitear** (pendiente QA) · **Rama:** develop
**Antecedente:** cierra el último pendiente de infraestructura de #96. El hermano del backend
(`backend/ruff.toml`) ya está commiteado en `e29005a` con GO previo.
**Migraciones:** ninguna. **Backend:** no se toca. **Golden:** no aplica (ver §6).

---

## 1. Qué pasaba

`npm run lint` está en `package.json` desde el día uno y las dependencias están instaladas
(`eslint@8.56`, `@typescript-eslint@6.19`, `eslint-plugin-react-hooks@4.6`,
`eslint-plugin-react-refresh@0.4`). **Lo único que faltaba era `.eslintrc.cjs`.** Sin él, eslint 8
muere con *"no configuration found"*.

Verificado que **nunca existió**:

```
git log --oneline --all -- frontend/.eslintrc.cjs frontend/.eslintrc.js \
                           frontend/.eslintrc.json frontend/eslint.config.js
(sin salida)
```

Es la plantilla de Vite a la que se le instalaron las dependencias y se le copió el script, pero no
el archivo de config.

**La prueba de que alguien lo daba por vivo:** el código tiene **12 `eslint-disable` escritos a
mano en 10 archivos**. Nadie escribe una directiva para un linter que sabe que no corre.

---

## 2. Lo que encontró el primer día

**3 de esos 12 estaban puestos sobre la línea equivocada.** Son `-next-line`, y el `any` que
pretendían tapar está más abajo (dentro del cuerpo de la función o de la interface):

| Sitio | Qué decía la directiva | Realidad |
|---|---|---|
| `hooks/useMoneyMovements.ts:39` | tapa el `any` de `useCreateMovement` | el `any` está 2 líneas después, en `Record<string, (data: any) => Promise<any>>`; los 2 `any` del archivo se reportan igual |
| `pages/config/MoneyAccountsPage.tsx:25` | tapa un `any` | **el archivo no tiene ningún `any`** (`grep` = 0) |
| `pages/treasury/AccountStatementPage.tsx:95` | tapa un `any` | **el archivo no tiene ningún `any`** (`grep` = 0) |

Los tres borrados. Los otros 9 son legítimos y siguen vivos (ver §4, es la razón del diseño).

No hubo hallazgos de `rules-of-hooks`: el bug de #93 ya está arreglado. El gate nace verde.

---

## 3. Que la regla realmente atrapa el bug de #93 — verificado, no supuesto

Planté la forma exacta del bloqueante (a) en un archivo temporal y corrí `npm run lint`:

```tsx
export function Probe({ data }: { data: { n: number }[] | undefined }) {
  if (!data) return <div>cargando…</div>;                       // return condicional
  const total = useMemo(() => data.reduce(...), [data]);        // hook DESPUÉS
```

```
4:17  error  React Hook "useMemo" is called conditionally. React Hooks must be called in the
             exact same order in every component render. Did you accidentally call a React Hook
             after an early return?   react-hooks/rules-of-hooks
✖ 38 problems (1 error, 37 warnings)
exit con el bug = 1
```

Quitando el archivo: `exit = 0`. O sea el gate **falla** con el bug y **pasa** sin él. El mensaje
nombra el modo de falla textualmente.

---

## 4. La decisión que quiero que miren: presupuesto, no `'off'`

En ruff el criterio fue **seleccionar poco y dejar el resto de backlog apagado**. Acá me desvié y
quiero el argumento revisado.

**La deuda medida:** `exhaustive-deps` 22 + `no-explicit-any` 15 = **37**, más
`react-refresh/only-export-components` 9 que no entra (es molestia de HMR, no correctitud).

**Por qué no `'off'`:** apagar esas dos reglas vuelve **inútiles los 12 `eslint-disable`**, y el
script ya trae `--report-unused-disable-directives` — medido:

```
'off'  → ✖ 12 problems (12 errors)      // los 12 disables pasan a "Unused eslint-disable directive"
'warn' → ✖ 40 problems (3 errors, 37 warnings)  // los 3 podridos de §2; los 9 legítimos suprimen bien
'warn' + borrar los 3 → ✖ 37 problems (0 errors, 37 warnings)   ← estado final
```

Con `'off'` habría que **borrar los 12 comentarios** para dejar el gate verde, incluidos los 9 que
documentan una decisión deliberada ("este dep array está incompleto a propósito"). Eso es destruir
señal para satisfacer a una regla apagada, y además ensucia 10 archivos que pertenecen a otros
ciclos.

**Lo elegido:** las dos reglas en `warn` y `--max-warnings 37` en el script. Trinquete: **un
hallazgo nuevo rompe el gate** (38 > 37). El número **solo baja**; está documentado en la cabecera
del config que al arreglar deuda hay que bajarlo o queda cupo libre.

**La debilidad conocida, dicha de frente:** si alguien arregla 5 warnings y no baja el número,
quedan 5 slots para que entre uno nuevo sin romper. Es la debilidad clásica del trinquete. La
alternativa (`'off'`) no tiene ese problema pero paga con los 12 comentarios y con enterrar la
deuda. **Si prefieren `'off'` + borrar los 12, es un cambio de 10 minutos** — díganlo.

---

## 5. El límite del gate, dicho explícito

`react-hooks/rules-of-hooks` cierra **el bloqueante (a)** de #93. **El (b) no lo cierra ni lo puede
cerrar**: FastAPI serializa `Decimal` como string, el tipo TS declaraba `number`, y `acc + x`
concatenaba texto. El tipo **mentía sobre el runtime**, y ninguna herramienta estática puede saber
que el JSON de la red no se parece a su interface.

De las cuatro clases documentadas en la memoria `gates-punto-ciego-frontend`, este linter cierra
**una**. Las otras tres (tipo que miente, formateador que miente, ternario que asumía dos estados)
siguen necesitando abrir la pantalla. La cabecera del config lo dice para que nadie lea el gate
verde como "ya está cubierto".

---

## 6. Riesgo de deploy: ninguno, y por qué

- `npm run build` es `tsc && vite build` — **no invoca lint**. La skill `/deploy` corre build, no
  lint. Un `--max-warnings` mal puesto no puede tumbar un deploy.
- Los únicos archivos de `src/` tocados son las **3 líneas de comentario** borradas. `tsc --noEmit`
  pasa.
- **Golden no aplica**: no se toca backend, ni esquema, ni ninguna respuesta HTTP.

---

## 7. Gates de este cambio

| Gate | Resultado |
|---|---|
| `npm run lint` | ✅ `37 problems (0 errors, 37 warnings)`, **exit 0** |
| `npm run lint` con el bug de #93 plantado | ✅ **exit 1**, señalando `rules-of-hooks` |
| `./node_modules/.bin/tsc --noEmit` | ✅ limpio |
| Backend | sin tocar |

---

## 8. Dónde mirar más duro

1. **La decisión de §4** (presupuesto vs `'off'`). Es la única que tiene dos respuestas defendibles.
2. **El número 37.** ¿Vale la pena, o prefieren que gaste el ciclo bajándolo a 0? Mi lectura: los 22
   de `exhaustive-deps` **no se deben tocar en masa** — agregar una dependencia faltante puede meter
   un loop de render infinito, y varios de esos sitios son deliberados (por eso tienen disable). Es
   un ciclo de limpieza propio con pruebas de pantalla, no un efecto colateral de montar el linter.
3. **Los 3 borrados.** ¿Alguno merecía moverse a la línea correcta en vez de borrarse? Mi criterio:
   dos apuntan a archivos **sin ningún `any`** (no hay línea correcta a la que moverlos), y el
   tercero taparía un `any` que hoy está contado en el presupuesto — moverlo escondería deuda.
4. **El override de `*.d.ts`.** Apaga `no-unused-vars` y `no-unnecessary-type-constraint` en
   `types/tanstack-table.d.ts`, donde `interface ColumnMeta<TData extends unknown, TValue>` es copia
   literal de la firma de la librería (una augmentación de módulo debe calcarla). ¿Preferirían
   `// eslint-disable-next-line` en el sitio en vez de un override por extensión?
5. **`react-refresh` fuera.** 9 hallazgos, plugin instalado. Lo dejé afuera por ser DX y no
   correctitud. Si lo quieren dentro, entra al presupuesto (37 → 46) o se arreglan.

---

## 9. Resolución de QA (2026-08-14) — **GO**, con dos refinaciones incorporadas

QA verificó de primera mano lo cinco puntos (historia de git, conteo al ras, la sonda plantada, los
3 disable sobre la línea equivocada, y que `build` no invoca lint). Dos correcciones al texto, ya
aplicadas al config y a la decisión #97:

**(a) §4 no era una desviación del criterio de ruff, era el mismo criterio con otro mecanismo.**
En los dos casos la regla fue *el gate nace verde, un hallazgo nuevo lo rompe, la deuda queda
escrita donde se lee*. Lo que cambia es que las herramientas no son simétricas:
`--report-unused-disable-directives` **es incompatible con apagar la regla**, y esa bandera es
justamente la que encontró los 3 comentarios podridos — o sea que `'off'` costaba la herramienta
que produjo uno de los hallazgos del paquete.

**(b) El presupuesto es un TECHO DE DEUDA, no un invariante — y no debe heredar la credibilidad de
`RELOJES_PERMITIDOS`.** Esa guarda es fuerte porque está **vacía** y porque exige razón escrita por
entrada; un presupuesto de 37 son 37 entradas anónimas. El config ahora lo dice con esas palabras,
para que nadie lo cite después como "guarda".

**La salida práctica que cierra casi todo el cupo libre del trinquete** (anotada en el config): el
número baja de **dos** maneras, no una. Para un `exhaustive-deps` deliberado la resolución correcta
no es arreglarlo —sería meter un loop de render— sino un `disable-next-line` **con la razón al
lado**: convierte una entrada anónima en una decisión documentada, baja el número en el mismo
commit, y **se autolimpia** (el día que la dependencia deje de hacer falta, la directiva se marca
sola como inútil — que es exactamente lo que no pasó con los 3 borrados hoy, porque no había linter
que lo dijera). Aplicado a fondo queda solo la deuda genuina: los 15 `any` de #69/#86.

**Sobre §5**, QA agrega el remedio durable de la clase que ningún linter cubre: **coercionar en la
frontera**. `num()` ya existe copiado **tres veces** (`utils/excelExport.ts:911`,
`InboundLiquidatePage.tsx:148`, `InboundDetailPage.tsx:52`) — el síntoma exacto de la capa que
falta. Promoverlo a los mapeos de `services/*.ts` convierte *"el tipo miente"* en *"el tipo se
cumple porque se fuerza al entrar"*. Ciclo propio; anotado en la cabecera del config, que es donde
alguien va a leer el verde.

**Pendiente anotado para el próximo que lo toque:** bajar el 37 documentando los `exhaustive-deps`
deliberados, no solo arreglándolos.
