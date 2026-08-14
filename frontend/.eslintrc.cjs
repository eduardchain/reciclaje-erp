/**
 * Linter del frontend. Motivo de existir, 2026-08-14 (#96, hermano de
 * `backend/ruff.toml`):
 *
 * `npm run lint` existia en package.json y las dependencias estaban instaladas
 * desde el dia uno — lo unico que faltaba era ESTE archivo, asi que el comando
 * moria con "no configuration found" y nadie corria nada. Un lint roto no es un
 * gate: es un gate que se cree que existe, que es peor. La prueba de que alguien
 * lo daba por vivo: habia 12 `eslint-disable` escritos a mano en 10 archivos, y
 * 3 estaban puestos sobre la linea equivocada — nunca taparon nada, y dos de
 * ellos sobrevivian a codigo que ya no tiene ningun `any`.
 *
 * Lo que costo: los dos bloqueantes de #93 aparecieron recien en las pruebas de
 * usuario, con `tsc` verde, build verde, 1.593 tests verdes y golden verde.
 * Ninguno de esos gates EJECUTA una pantalla. El primero — un `useMemo` despues
 * de un `return` condicional, pantalla en blanco en TODA liquidacion — lo atrapa
 * `react-hooks/rules-of-hooks` de una, con un mensaje que literalmente pregunta
 * "Did you accidentally call a React Hook after an early return?".
 *
 * ⚠️ Honestidad sobre el alcance: el SEGUNDO bloqueante de #93 (FastAPI
 * serializa Decimal como string, el tipo TS decia `number`, y `acc + x`
 * concatenaba texto) NO lo atrapa este linter ni ninguno. El tipo MENTIA, y
 * ninguna herramienta estatica puede saber que el JSON de la red no se parece a
 * su interface.
 *
 * Lo que SI lo cubriria de forma durable — anotado aca porque este es el archivo
 * donde alguien va a leer el verde — es **coercionar en la FRONTERA**, no en el
 * consumidor. La pieza ya existe y esta copiada TRES veces (`num()` en
 * `utils/excelExport.ts`, `pages/inbound/InboundLiquidatePage.tsx` y
 * `pages/inbound/InboundDetailPage.tsx`), que es exactamente el sintoma de la
 * capa que falta: promoverla a los mapeos de `services/*.ts` convierte "el tipo
 * miente" en "el tipo se cumple porque se fuerza al entrar". Ciclo propio.
 * Mientras tanto, abrir la pantalla.
 *
 * Uso:  npm run lint      (desde frontend/)
 *
 * ── Errores (rompen el gate) ────────────────────────────────────────────────
 * La familia de correctitud, que es la que ya mordio. Cero hallazgos hoy.
 *
 * ── Warnings con PRESUPUESTO ────────────────────────────────────────────────
 * `--max-warnings 37` en package.json. Es un trinquete: 37 es la deuda medida
 * el 2026-08-14 y esta AL RAS (no acolchado), asi que el gate esta verde hoy y
 * **el hallazgo 38 lo rompe**. Se eligio presupuesto en vez de apagar las reglas
 * por tres razones: la deuda queda a la vista en cada corrida en vez de
 * enterrada en un comentario; los 9 `eslint-disable` legitimos siguen VIVOS
 * (apagar la regla los volveria directivas inutiles y habria que borrarlos,
 * perdiendo la intencion que documentan); y `--report-unused-disable-directives`
 * — la bandera que encontro los 3 comentarios podridos — es incompatible con
 * apagar la regla, o sea que apagarlas costaba la herramienta que produjo uno de
 * los hallazgos.
 *
 * 🔴 Esto es un TECHO DE DEUDA, **no** un invariante — no confundirlo con
 * `RELOJES_PERMITIDOS` (backend), que es fuerte justamente porque esta VACIO y
 * porque cada entrada exige razon escrita. Un presupuesto de 37 son 37 entradas
 * anonimas. No citar este numero como "guarda".
 *
 * El numero SOLO baja, y **baja de dos maneras, no una**:
 *   (a) arreglando la deuda;
 *   (b) 🟢 DOCUMENTANDO lo deliberado. Varios de los `exhaustive-deps` son
 *       intencionales (efecto de montaje, dependencia omitida a proposito):
 *       para esos la resolucion correcta NO es agregar la dependencia — seria
 *       meter un loop de render — sino un `// eslint-disable-next-line
 *       react-hooks/exhaustive-deps` con la razon al lado. Eso convierte una
 *       entrada anonima del presupuesto en una decision documentada, y se
 *       AUTOLIMPIA: el dia que la dependencia deje de hacer falta, la directiva
 *       se marca sola como inutil (que es lo que no paso con los 3 borrados hoy,
 *       porque no habia linter que lo dijera).
 * Aplicado a fondo queda solo la deuda genuina — los 15 `any` de #69/#86, que si
 * son refactor — y el cupo libre del trinquete deja de importar.
 *
 *   react-hooks/exhaustive-deps        22  ⚠️ NO auto-fixear: agregar una
 *                                          dependencia faltante puede meter un
 *                                          loop de render infinito. Sitio por
 *                                          sitio, y varios son deliberados.
 *   @typescript-eslint/no-explicit-any 15  concentrados en 4 archivos (6 en
 *                                          ObligationsPage, 5 en
 *                                          ObligationDetailPage, 2+2 en hooks).
 *                                          Tipar bien es refactor de #69/#86.
 *
 * Sin prender, disponible: `react-refresh/only-export-components` (9 hallazgos,
 * el plugin ya esta instalado). Es molestia de HMR en desarrollo, no
 * correctitud — por eso no entra al presupuesto.
 */
module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', 'node_modules', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
  plugins: ['@typescript-eslint', 'react-hooks'],
  rules: {
    // 🔴 LA regla de este archivo. Ya viene en error desde
    // `react-hooks/recommended`; se repite explicita porque es documentacion:
    // si alguien toca el `extends`, esta linea sobrevive.
    'react-hooks/rules-of-hooks': 'error',

    // El codigo ya usa el guion bajo para descartar (`const { _key, ...rest }`),
    // que es la convencion: 18 de los 20 hallazgos eran eso. A la regla solo
    // habia que decirselo.
    '@typescript-eslint/no-unused-vars': ['error', {
      argsIgnorePattern: '^_',
      varsIgnorePattern: '^_',
      caughtErrorsIgnorePattern: '^_',
    }],

    // --- Deuda con presupuesto (ver cabecera). Visibles, no apagadas. ---
    'react-hooks/exhaustive-deps': 'warn',
    '@typescript-eslint/no-explicit-any': 'warn',
  },
  overrides: [
    {
      // Las augmentaciones de modulo tienen que CALCAR la firma generica de la
      // libreria para que TypeScript las mezcle con la original. `TData extends
      // unknown` viene copiado de @tanstack/react-table: es redundante alla y
      // aca, pero cambiarlo rompe la augmentacion.
      files: ['*.d.ts'],
      rules: {
        '@typescript-eslint/no-unused-vars': 'off',
        '@typescript-eslint/no-unnecessary-type-constraint': 'off',
      },
    },
  ],
}
