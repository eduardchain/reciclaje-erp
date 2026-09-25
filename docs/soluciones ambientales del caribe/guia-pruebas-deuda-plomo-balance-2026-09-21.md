# Guía de pruebas — la deuda en plomo con Willard dentro del balance

Cubre CC-014, lo que Johana describió el 18 de septiembre: *"yo siempre la coloco pues negativo en el balance, en pesos. le doy un valor de acuerdo al precio del mercado en ese momento y la tengo como un valor negativo, o sea, restando dentro de mi inventario"*.

Todo pasa en dos pantallas: **Configuración, Precio del Plomo** y **Reportes, Balance**. No hay transacciones nuevas que registrar.

⚠️ **Los kilos de las tablas están medidos contra la base de desarrollo. Los valores en pesos son la multiplicación, derivada del código y cubierta por los 24 tests, pero no verificados contra la pantalla.** No pude autenticarme contra el backend desde mi lado, así que si algún número sale distinto, eso es justamente lo que esta revisión sirve para encontrar. No lo tomes como verificado.

## Cómo abrirlo

El puerto 8000 lo tiene tu otro proyecto, así que el backend de este trabajo quedó en el 8001:

```
cd frontend && VITE_API_URL=http://localhost:8001 npm run dev
```

Entrás como SAC. Si tocás algo del backend hay que reiniciar el 8001, porque corre sin recarga automática.

## Las tres reglas, que es todo lo que hace

**1. Qué kilos se valoran.** Solo la deuda con Willard: las dos cuentas de baterías y la de drosses. La deuda de planta con Circunvalar, que es `intersede`, **no se valora** y es a propósito: el balance no tiene vista por sede, así que valorarla hoy construiría un número que no aparece en ninguna pantalla. Esa quedó como pregunta abierta para Johana.

```
Kilos valorables = saldo willard_baterias + saldo willard_drosses, a la fecha de corte
                   (intersede, horno y crisol quedan afuera)
```

**2. Qué precio se usa.** El de mayor fecha de vigencia que no pase de la fecha de corte. No el último cargado: el vigente **a esa fecha**.

```
Precio vigente = el de mayor effective_date entre los que tienen effective_date <= corte
```

**3. Cuánto vale y con qué signo.** El signo del libro se respeta, no se le pone valor absoluto:

```
Valor en el balance = - (kilos valorables x precio vigente)
```

Saldo positivo en el libro significa que SAC le debe plomo a Willard, así que entra **restando** dentro del activo. Si algún día Willard le debiera plomo a SAC, la línea sale positiva sola, sin tocar código.

**Dónde entra.** En el Balance General es una línea propia dentro del activo. En el Balance Detallado es un **ítem dentro de la sección de inventario**, no una sección aparte, que es literal lo que Johana describe. El inventario sigue al costo promedio y la deuda va a precio de mercado: son dos líneas separadas, nunca una cifra neteada con dos criterios.

**Qué no se mueve.** La valoración **no pasa por resultados**. Ni la utilidad acumulada, ni la utilidad distribuida, ni los pasivos. El patrimonio la absorbe entera porque es el residual del balance. Esto lo vas a poder comprobar en el paso 4.

## Punto de partida

Lo que ya está cargado en desarrollo:

| Qué | Valor | De dónde salió |
|---|---|---|
| Precio del plomo | 2.400 por kg, vigente desde el 31 de agosto | Lo cargó la prueba de la migración, nota "smoke CC-014" |
| Baterías Circunvalar | 300 kg fechados el 20 de agosto | Lo sembré para esta revisión, ver la nota del final |
| Baterías Circunvalar | 1.000 kg fechados el 17 de septiembre | Saldo inicial de la org |
| Drosses | 1.000 kg fechados el 17 de septiembre | Saldo inicial de la org |
| Intersede | 1.000 kg fechados el 17 de septiembre | **No se valora** |

Kilos valorables acumulados: 300 hasta el 20 de agosto, 2.300 desde el 17 de septiembre.

## Paso 1. Corte al 19 de agosto: la deuda todavía no existe

Reportes, Balance General. Poner fecha de corte **19 de agosto de 2026**.

| Qué mirar | Esperado | Por qué |
|---|---|---|
| Línea de deuda en plomo | **No aparece** | 0 kg valorables a esa fecha. Sin kilos y sin valor, la línea se omite |
| Balance Detallado, sección inventario | Sin el ítem WILLARD | Mismo criterio |

## Paso 2. Corte al 25 de agosto: hay kilos y no hay precio

Cambiar la fecha de corte a **25 de agosto de 2026**.

| Qué mirar | Esperado | Por qué |
|---|---|---|
| Línea de deuda en plomo | Aparece, **sin valorar** | 300 kg valorables y ningún precio vigente: el primero rige desde el 31 |
| Valor en pesos | Dice literalmente **"Sin valorar"**, no un número | Un cero diría que la deuda no vale nada, o peor, que el precio es de cero pesos. Por eso el campo va vacío y la pantalla lo nombra |
| Kilos | Se ven igual, **300 kg**, debajo | Los kilos no dependen del precio: la deuda existe aunque no esté valorada |
| Balance Detallado | El ítem **está ahí también**, con los 300 kg dentro del nombre | Es el documento que exporta Johana. Un aviso que no está ahí no existe para ella |
| Exportar el Detallado a Excel | El ítem aparece en el archivo | Mismo motivo |

**Este es el paso que más importa.** Yo lo había omitido, dejando el aviso solo en el Balance General, y QA lo volvió condición para aprobar. El argumento que me tumbó: un balance que esconde una deuda es peor que uno que la muestra sin valorar.

Anotá acá lo que muestre la pantalla, porque lo vas a comparar en el paso 4:

- Total activos: ______
- Utilidad acumulada: ______
- Patrimonio: ______

## Paso 3. Corte de hoy: la deuda valorada

Cambiar la fecha de corte a **hoy**.

| Qué mirar | Esperado | Cuenta |
|---|---|---|
| Kilos | 2.300 kg | 300 del 20 de agosto, más 1.000 de baterías y 1.000 de drosses del 17 de septiembre |
| Precio y fecha | 2.400, del 31 de agosto | Es el único vigente a hoy |
| Valor | **−5.520.000** | 2.300 x 2.400, restando |
| En el nombre del ítem del Detallado | "precio de mercado del 31/08/2026" | Para que el número sea auditable sin salir de la hoja |
| Intersede | **No suma** | Los 1.000 kg de intersede quedan afuera a propósito |

Comprobación de que intersede no entra: si entrara, el número sería 3.300 x 2.400 = 7.920.000. Tiene que decir 5.520.000.

## Paso 4. Cargar un precio con fecha vieja: la consecuencia que aprobaste

Este paso existe para que veas en pantalla lo que decidiste el domingo con el costo a la vista: **cargar un precio con fecha anterior cambia cortes históricos que ya se imprimieron**.

Configuración, Precio del Plomo. Cargar un precio de **2.000 con fecha de vigencia 20 de agosto de 2026**. La pantalla acepta fechas viejas y solo bloquea las futuras, que es exactamente la decisión que tomaste. Uso un número distinto de 2.400 a propósito, para que se vea que el balance elige el precio por fecha y no simplemente el último cargado.

Volver al Balance y repetir los cortes:

| Corte | Antes del paso 4 | Después del paso 4 | Por qué |
|---|---|---|---|
| 19 de agosto | Sin línea | Sin línea | Sigue sin haber kilos |
| **25 de agosto** | Sin valorar | **−600.000** | 300 x 2.000. El corte cambió: esto es lo que aprobaste |
| Hoy | −5.520.000 | −5.520.000 | Sigue rigiendo el de 2.400 del 31 de agosto, que es posterior |

Y la comprobación de que no pasa por resultados. Volvé al corte del **25 de agosto** y compará con lo que anotaste en el paso 2:

| Qué mirar | Esperado | Por qué |
|---|---|---|
| Utilidad acumulada | **Idéntica** | La valoración no toca el estado de resultados |
| Utilidad distribuida | **Idéntica** | |
| Total pasivos | **Idéntico** | |
| Patrimonio | Baja exactamente **600.000** | Es el residual: absorbe la valoración entera |
| Total activos | Baja exactamente **600.000** | La deuda entra restando dentro del activo |

Si la utilidad acumulada se movió, hay un problema y la revisión lo encontró.

## Paso 5. Que ninguna otra empresa vea nada

Cambiar de organización a **Costa** desde el selector del encabezado.

| Qué mirar | Esperado | Por qué |
|---|---|---|
| Balance General y Detallado | **Sin ninguna línea de deuda en plomo** | La función está detrás de la bandera de SAC |
| Configuración | **Sin la pestaña Precio del Plomo** | Misma bandera |

Esto es lo que el golden probó contra las tres empresas reales, pero verlo en pantalla cuesta treinta segundos y es la promesa que más nos importa: que nada de las otras empresas se rompa.

## Detalle que conviene saber

**La pantalla del precio es hoy solo para administradores.** Reutiliza los permisos de tarifas, y ningún rol del sembrado los tiene. Johana es administradora, así que puede. Si algún día hay que delegarla en alguien más, hay que asignarle ese permiso a un rol.

**El histórico de precios no se edita ni se borra.** Cada precio nuevo es una fila más, igual que las tarifas y las listas de precios. Es lo que permite que un corte viejo siga mostrando el precio que se usó.

**Los 300 kg del 20 de agosto son un dato de prueba que sembré yo**, porque sin ellos el paso 2 no se podía ver: los únicos kilos que había estaban fechados después del precio. Cuando termines la revisión se anulan con un comando, no se borran, porque el libro de kilos no admite borrados. Anularlos no toca el balance de ninguna otra empresa.

**El precio de 2.400 del 31 de agosto** también quedó de una prueba, con esa nota escrita. Lo dejamos a propósito: es lo que hace visible el caso valorado.

## Lo que queda abierto con Johana

Dos cosas que este trabajo no cierra y conviene tener presentes:

1. **Hay que decirle en una frase que cargar un precio con fecha anterior cambia balances que ya imprimió.** Enterarse por el número sería la peor forma.
2. **La deuda de planta con Circunvalar no se valora**, y ella no fue preguntada por esa mitad: el 18 de septiembre solo se habló de la deuda con Willard. Quedó como pregunta abierta.
