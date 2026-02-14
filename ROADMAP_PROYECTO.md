# ROADMAP COMPLETO - SISTEMA RECICLAJE
## Plan de Desarrollo Fase por Fase

**Cliente:** Reciclajes de la Costa  
**Desarrollador:** Eduardo Chain  
**Metodología:** Vibe Coding + GitHub Copilot  
**Duración Total:** 7 semanas (110 horas)  
**Fecha Inicio:** Febrero 2026

---

## ÍNDICE DE FASES

- [FASE 0: Setup Infraestructura](#fase-0-setup-infraestructura) - 12 hrs
- [FASE 1: Arquitectura Base](#fase-1-arquitectura-base) - 15 hrs
- [FASE 2: Módulos Core (Compras/Ventas)](#fase-2-módulos-core) - 20 hrs
- [FASE 3: Inventario y Costeo](#fase-3-inventario-y-costeo) - 18 hrs
- [FASE 4: Tesorería Avanzada](#fase-4-tesorería-avanzada) - 15 hrs
- [FASE 5: Módulos Complementarios](#fase-5-módulos-complementarios) - 12 hrs
- [FASE 6: Reportes y BI](#fase-6-reportes-y-bi) - 10 hrs
- [FASE 7: Migración y Go-Live](#fase-7-migración-y-go-live) - 8 hrs

**TOTAL: 110 horas**

---

# FASE 0: SETUP INFRAESTRUCTURA Y CONTROL DE VERSIONES
**Duración:** 14 horas  
**Objetivo:** Git configurado, VPS, base de datos y entorno de desarrollo funcionando

## TAREA 0.0: Configuración Git + GitHub + VS Code
**Duración:** 2 horas  
**Objetivo:** Repositorio GitHub configurado y VS Code conectado para compartir avances con cliente

### Descripción:
Configurar control de versiones desde el inicio:
- Crear repositorio en GitHub (público o privado)
- Configurar Git local en tu máquina
- Conectar VS Code con GitHub
- Crear estructura de carpetas del proyecto
- Configurar .gitignore apropiado
- Hacer primer commit
- Invitar al cliente como colaborador (solo lectura)

### Qué vamos a lograr:
- Repositorio GitHub creado (ejemplo: reciclaje-erp)
- VS Code configurado para push/pull automático
- Cliente puede ver tu código en tiempo real
- Historial completo de cambios
- Protección contra pérdida de código
- Deployment automático desde GitHub (opcional)

### Estructura inicial del proyecto:
```
reciclaje-erp/
├── backend/           # FastAPI
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── .env.example
│   ├── .gitignore
│   ├── requirements.txt
│   └── README.md
├── frontend/          # React + Vite
│   ├── src/
│   ├── public/
│   ├── .env.example
│   ├── .gitignore
│   ├── package.json
│   └── README.md
├── docs/              # Documentación
│   ├── ROADMAP.md
│   ├── REQUERIMIENTOS.md
│   └── API.md
├── deployment/        # Scripts de deploy
│   ├── docker-compose.yml
│   └── nginx.conf
├── .gitignore         # Global
└── README.md          # Principal
```

### Buenas prácticas que configuraremos:
- **Branches:** main (producción) y develop (trabajo)
- **Commits:** Mensajes descriptivos en español
- **Push frecuente:** Al final de cada tarea
- **.gitignore:** No subir .env, node_modules, __pycache__, etc.
- **README.md:** Instrucciones claras de instalación

### Entregables:
- ✅ Repositorio en GitHub creado
- ✅ VS Code conectado (extensión GitHub Pull Requests)
- ✅ Estructura de carpetas inicial
- ✅ .gitignore configurado (Python + Node)
- ✅ README.md con descripción del proyecto
- ✅ Primer commit: "Initial project structure"
- ✅ Cliente invitado como colaborador

### Ventajas para el cliente:
- 📊 Puede ver tu progreso en tiempo real
- 📝 Puede leer el código si quiere
- 📅 Ve historial de cambios con fechas
- 🔄 Puede descargar y probar localmente
- ✅ Transparencia total del desarrollo

---

## TAREA 0.1: Configuración VPS Hostinger
**Duración:** 4 horas  
**Objetivo:** VPS funcionando con acceso SSH y dominio configurado

### Sub-tareas:
1. Contratar VPS Business en Hostinger
2. Configurar acceso SSH con llaves
3. Actualizar sistema operativo (Ubuntu)
4. Configurar firewall básico (UFW)
5. Instalar Docker + Docker Compose
6. Configurar dominio y DNS

### Entregables:
- ✅ VPS accesible vía SSH
- ✅ Docker funcionando
- ✅ Dominio apuntando al VPS

### Prompts para Copilot:
```
Prompt 1: "Configure SSH key authentication for Ubuntu VPS with user 'deploy'"
Prompt 2: "Install Docker and Docker Compose on Ubuntu 22.04 LTS"
Prompt 3: "Configure UFW firewall to allow ports 22, 80, 443 on Ubuntu"
```

---

## TAREA 0.2: Setup PostgreSQL
**Duración:** 2 horas  
**Objetivo:** Base de datos PostgreSQL funcionando en Docker

### Sub-tareas:
1. Crear docker-compose.yml con PostgreSQL 16
2. Configurar volúmenes persistentes
3. Establecer credenciales seguras
4. Crear base de datos inicial
5. Verificar conexión

### Entregables:
- ✅ PostgreSQL corriendo en Docker
- ✅ Base de datos "reciclaje_db" creada
- ✅ Usuario admin con permisos

### Prompts para Copilot:
```
Prompt 1: "Create docker-compose.yml with PostgreSQL 16, persistent volumes, and secure credentials"
Prompt 2: "Create init script to setup reciclaje_db database with user and permissions"
```

---

## TAREA 0.3: Setup Proyecto Backend (FastAPI)
**Duración:** 3 horas  
**Objetivo:** Estructura del proyecto backend lista para desarrollar

### Sub-tareas:
1. Crear estructura de carpetas del proyecto
2. Configurar entorno virtual Python
3. Instalar dependencias (FastAPI, SQLAlchemy, etc)
4. Configurar variables de entorno (.env)
5. Crear archivo main.py básico
6. Probar endpoint /health

### Entregables:
- ✅ Proyecto backend estructurado
- ✅ requirements.txt completo
- ✅ FastAPI corriendo en http://localhost:8000
- ✅ /docs (Swagger) accesible

### Prompts para Copilot:
```
Prompt 1: "Create FastAPI project structure with folders: app/core, app/models, app/schemas, app/api, app/services, app/utils"
Prompt 2: "Create requirements.txt with FastAPI, SQLAlchemy, Alembic, python-jose, passlib, psycopg2-binary, pydantic-settings"
Prompt 3: "Create main.py with FastAPI app, CORS middleware, and health check endpoint"
```

---

## TAREA 0.4: Setup Proyecto Frontend (React)
**Duración:** 3 horas  
**Objetivo:** Proyecto React con Vite y shadcn/ui listo para desarrollar

### Sub-tareas:
1. Crear proyecto Vite con React + TypeScript
2. Instalar y configurar Tailwind CSS
3. Inicializar shadcn/ui
4. Instalar componentes base (button, form, table, dialog)
5. Configurar React Router
6. Crear estructura de carpetas
7. Probar en http://localhost:5173

### Entregables:
- ✅ Proyecto React funcionando
- ✅ shadcn/ui configurado
- ✅ Routing básico
- ✅ Página de login placeholder

### Prompts para Copilot:
```
Prompt 1: "Create Vite React TypeScript project with folder structure: src/components, src/pages, src/hooks, src/services, src/utils, src/types"
Prompt 2: "Configure Tailwind CSS v3 and shadcn/ui in Vite React project"
Prompt 3: "Install shadcn/ui components: button, form, input, table, dialog, select, date-picker, card"
Prompt 4: "Setup React Router v6 with routes for login, dashboard, purchases, sales, inventory"
```

---

# FASE 1: ARQUITECTURA BASE
**Duración:** 15 horas  
**Objetivo:** Sistema de autenticación, multi-tenant y CRUD genérico funcionando

## TAREA 1.1: Modelo de Datos Base
**Duración:** 4 horas  
**Objetivo:** Definir y crear todas las tablas PostgreSQL con SQLAlchemy

### Descripción:
Crear los modelos de SQLAlchemy para las entidades principales del sistema:
- Organizations (multi-tenant)
- Users y autenticación
- Third_parties (proveedores/clientes/provisiones)
- Materials (materiales reciclables)
- Categories (categorías de materiales y gastos)
- Warehouses (bodegas)
- Business_units (unidades de negocio)

### Qué vamos a lograr:
- Archivo base.py con clases base y mixins (TimestampMixin, OrganizationMixin)
- Modelos completos con relaciones
- Script de migración Alembic inicial
- Base de datos con todas las tablas creadas

### Entregables:
- ✅ 15+ modelos de SQLAlchemy funcionando
- ✅ Relaciones (ForeignKey) configuradas
- ✅ Base de datos con estructura completa
- ✅ Migración inicial aplicada

---

## TAREA 1.2: Sistema de Autenticación
**Duración:** 5 horas  
**Objetivo:** Login, registro y manejo de sesiones con JWT

### Descripción:
Implementar sistema completo de autenticación:
- Registro de usuarios
- Login con email/password
- Generación de tokens JWT
- Middleware de autenticación
- Endpoints protegidos
- Gestión de permisos por rol

### Qué vamos a lograr:
- Usuario puede registrarse
- Usuario puede hacer login
- Sistema genera y valida tokens
- Endpoints protegidos requieren autenticación
- Roles básicos funcionando (admin, user)

### Entregables:
- ✅ POST /auth/register funcionando
- ✅ POST /auth/login devuelve token
- ✅ GET /auth/me retorna usuario actual
- ✅ Middleware valida tokens en rutas protegidas
- ✅ Frontend puede hacer login y guardar token

---

## TAREA 1.3: Multi-tenancy (Organizaciones)
**Duración:** 3 horas  
**Objetivo:** Aislar datos por organización automáticamente

### Descripción:
Implementar sistema multi-tenant donde cada empresa tiene sus datos aislados:
- Tabla organizations
- Relación users → organizations
- Middleware que inyecta organization_id
- Filtrado automático en queries
- UI para seleccionar organización

### Qué vamos a lograr:
- Cada usuario pertenece a una organización
- Todas las queries filtran por organization_id automáticamente
- Usuario puede cambiar de organización si tiene múltiples
- Datos completamente aislados entre organizaciones

### Entregables:
- ✅ Middleware organization_context funcionando
- ✅ Dependency get_current_organization
- ✅ Filtrado automático en CRUD operations
- ✅ Selector de organización en frontend

---

## TAREA 1.4: CRUD Genérico y Servicios Base
**Duración:** 3 horas  
**Objetivo:** Crear clases base reutilizables para todos los módulos

### Descripción:
Crear estructura de servicios genéricos que aceleren desarrollo:
- Clase CRUDBase con operaciones comunes
- Servicios específicos que heredan de CRUDBase
- Dependency injection pattern
- Manejo de errores estandarizado

### Qué vamos a lograr:
- Template de CRUD que se reutiliza en todos los módulos
- No repetir código de create/read/update/delete
- Servicios con lógica de negocio separada de rutas
- Ahorro de 50% del código en módulos futuros

### Entregables:
- ✅ CRUDBase genérico funcionando
- ✅ Al menos 2 servicios implementados (materials, third_parties)
- ✅ Endpoints REST completos para materials
- ✅ Validación con Pydantic schemas

---

# FASE 2: MÓDULOS CORE (COMPRAS/VENTAS)
**Duración:** 20 horas  
**Objetivo:** Operaciones principales del negocio funcionando

## TAREA 2.1: Módulo de Terceros
**Duración:** 4 horas  
**Objetivo:** Gestión completa de proveedores, clientes, provisiones

### Descripción:
CRUD completo de terceros con características especiales:
- Tercero puede ser proveedor Y cliente simultáneamente
- Provisiones como terceros especiales (is_provision=true)
- Estado de cuenta histórico
- Saldo actual calculado

### Qué vamos a lograr:
- Crear/editar/listar terceros
- Marcar roles múltiples (supplier, customer, investor, provision)
- Ver saldo actual de cada tercero
- Filtrar por tipo

### Entregables:
- ✅ Backend: CRUD third_parties completo
- ✅ Frontend: Página de gestión de terceros
- ✅ Formulario crear/editar tercero
- ✅ Lista con filtros por tipo
- ✅ Vista de estado de cuenta

---

## TAREA 2.2: Módulo de Materiales y Catálogos
**Duración:** 3 horas  
**Objetivo:** Catálogo de materiales y configuraciones

### Descripción:
Gestión de materiales reciclables y sus categorías:
- CRUD de materiales
- CRUD de categorías
- CRUD de bodegas
- CRUD de unidades de negocio
- Asignación material → unidad de negocio

### Qué vamos a lograr:
- Catálogo completo de materiales (Chatarra, Cobre, Papel, etc.)
- Organizados por categorías
- Asignados a unidades de negocio (Fibras, Metales, etc.)
- Configuración de bodegas (Circunvalar, San Alberto, etc.)

### Entregables:
- ✅ Backend: CRUD materials, categories, warehouses, business_units
- ✅ Frontend: Páginas de administración de catálogos
- ✅ Formularios de creación/edición
- ✅ Validaciones (códigos únicos, nombres requeridos)

---

## TAREA 2.3: Módulo de Compras (Básico)
**Duración:** 6 horas  
**Objetivo:** Registro de compras en 2 pasos (báscula → liquidación)

### Descripción:
Implementar flujo de compras completo:
- **Paso 1 (John):** Crear compra solo con cantidades, sin precios
- **Paso 2 (Nixon):** Liquidar compra asignando precios
- Estado: pending_liquidation → liquidated
- Inventario en tránsito vs liquidado
- Actualización de saldo proveedor

### Qué vamos a lograr:
- John puede registrar material que llega (solo peso)
- Nixon ve lista de "Pendientes de liquidar"
- Nixon asigna precios y confirma
- Sistema actualiza inventario y deuda con proveedor
- Trazabilidad completa (quién creó, quién liquidó)

### Entregables:
- ✅ Backend: POST /purchases (crear sin precios)
- ✅ Backend: PATCH /purchases/{id}/liquidate (asignar precios)
- ✅ Frontend: Formulario "Nueva Compra" (sin precios)
- ✅ Frontend: Lista "Compras Pendientes"
- ✅ Frontend: Modal "Liquidar Compra"
- ✅ Cálculo automático de totales

---

## TAREA 2.4: Módulo de Ventas (Básico)
**Duración:** 5 horas  
**Objetivo:** Registro de ventas directas y en 2 pasos

### Descripción:
Implementar flujo de ventas con dos modalidades:
- **Modalidad A:** Venta en 2 pasos (igual que compras)
- **Modalidad B:** Venta directa con precios (más común)
- Comisiones variables por venta
- Actualización de inventario
- Actualización de saldo cliente

### Qué vamos a lograr:
- Ingrid puede crear ventas con precios directamente
- John puede pesar despacho sin precios
- Manejo de comisiones (0, 1 o múltiples por venta)
- Descuento de inventario automático
- Cliente queda debiendo (o paga de inmediato)

### Entregables:
- ✅ Backend: POST /sales (crear con/sin precios)
- ✅ Backend: PATCH /sales/{id}/liquidate
- ✅ Backend: Comisiones en sale_commissions
- ✅ Frontend: Formulario "Nueva Venta"
- ✅ Frontend: Sección de comisiones
- ✅ Frontend: Lista "Ventas Pendientes"

---

## TAREA 2.5: Operaciones Doble Partida
**Duración:** 2 horas  
**Objetivo:** Compra+Venta simultánea sin pasar por bodega

### Descripción:
Operación "Pasa Mano" donde:
- Se registra compra y venta en una sola pantalla
- Material no pasa por inventario
- Ganancia se calcula inmediatamente
- Ambos documentos quedan vinculados

### Qué vamos a lograr:
- Pantalla especial "Doble Partida"
- Ingresa: Proveedor, Cliente, Material, Cantidad, Precio Compra, Precio Venta
- Sistema crea Purchase + Sale automáticamente
- Muestra ganancia al instante

### Entregables:
- ✅ Backend: POST /double-entry
- ✅ Frontend: Página "Doble Partida"
- ✅ Cálculo de ganancia en tiempo real
- ✅ Vinculación purchase_id ↔ sale_id

---

# FASE 3: INVENTARIO Y COSTEO
**Duración:** 18 horas  
**Objetivo:** Control de stock con costo promedio móvil

## TAREA 3.1: Inventario Básico
**Duración:** 4 horas  
**Objetivo:** Vista de stock actual con múltiples bodegas

### Descripción:
Sistema de inventario que muestra:
- Stock actual por material
- Desglose por bodega
- Stock en tránsito vs liquidado
- Valor total del inventario

### Qué vamos a lograr:
- Vista consolidada de todo el inventario
- Filtrar por bodega, material, categoría
- Ver cuánto hay de cada material
- Identificar material pendiente de liquidar

### Entregables:
- ✅ Backend: GET /inventory/current
- ✅ Backend: GET /inventory/by-warehouse
- ✅ Frontend: Página "Inventario Actual"
- ✅ Tabla con columnas: Material, En Tránsito, Liquidado, Total, Valor
- ✅ Alertas si mucho stock en tránsito

---

## TAREA 3.2: Costo Promedio Móvil
**Duración:** 6 horas  
**Objetivo:** Implementar algoritmo de costeo correcto

### Descripción:
Algoritmo crítico del negocio:
- **Entradas:** Recalculan costo promedio
- **Salidas:** Usan costo promedio pero NO lo modifican
- Solo movimientos liquidados afectan costo
- Si stock = 0, mantener último costo

### Qué vamos a lograr:
- Función calculate_average_cost() correcta
- Se ejecuta automáticamente en cada compra/ajuste
- Campo current_average_cost en materials se actualiza
- Ventas usan este costo para calcular utilidad

### Entregables:
- ✅ Función de cálculo de costo promedio
- ✅ Se ejecuta en: compras, ajustes, transformaciones
- ✅ Tests que validen la lógica
- ✅ Reporte muestra costo promedio actual

---

## TAREA 3.3: Movimientos de Inventario
**Duración:** 3 horas  
**Objetivo:** Historial completo de movimientos

### Descripción:
Tabla inventory_movements con todos los tipos:
- purchase_in (entrada por compra)
- sale_out (salida por venta)
- adjustment_in/out (ajustes manuales)
- transfer_in/out (traslados entre bodegas)
- transformation_in/out (desintegración)

### Qué vamos a lograr:
- Trazabilidad completa de cada kilogramo
- Saber de dónde vino y a dónde fue
- Auditoría de todos los movimientos
- Reporte de movimientos con filtros

### Entregables:
- ✅ Tabla inventory_movements poblándose automáticamente
- ✅ Backend: GET /inventory/movements (con filtros)
- ✅ Frontend: Página "Movimientos de Inventario"
- ✅ Filtros: fecha, material, tipo, bodega

---

## TAREA 3.4: Transformación de Materiales
**Duración:** 3 horas  
**Objetivo:** Desintegrar materiales compuestos

### Descripción:
Funcionalidad para desarmar materiales:
- Ejemplo: Motor 500kg → Cobre 200 + Hierro 180 + Aluminio 100 + Merma 20
- Costos se heredan proporcionalmente
- Validación: Total destinos + merma = origen

### Qué vamos a lograr:
- Operación de transformación
- Sale material origen, entran materiales destino
- Costos se distribuyen correctamente
- Registro de merma/desperdicio

### Entregables:
- ✅ Backend: POST /inventory/transform
- ✅ Frontend: Página "Transformación de Materiales"
- ✅ Validación de cantidades
- ✅ Cálculo automático de costos

---

## TAREA 3.5: Traslados entre Bodegas
**Duración:** 2 horas  
**Objetivo:** Mover material entre ubicaciones

### Descripción:
Funcionalidad para trasladar material:
- De bodega A → bodega B
- Misma cantidad, mismo costo
- Registra quién y cuándo

### Qué vamos a lograr:
- Traslado de material entre bodegas
- Stock se actualiza en ambas
- Trazabilidad del movimiento

### Entregables:
- ✅ Backend: POST /inventory/transfer
- ✅ Frontend: Formulario "Traslado"
- ✅ Validación: bodega origen ≠ destino
- ✅ Verificación de stock disponible

---

# FASE 4: TESORERÍA AVANZADA
**Duración:** 15 horas  
**Objetivo:** Control completo de dinero y gastos

## TAREA 4.1: Cuentas de Dinero y Movimientos Básicos
**Duración:** 4 horas  
**Objetivo:** Gestión de bancos, cajas y movimientos

### Descripción:
Sistema de cuentas de dinero:
- Múltiples cuentas (Caja General, Bancos, Nequi, etc.)
- Tipos de movimientos (pagos, cobros, transferencias, gastos)
- Saldo actualizado en tiempo real

### Qué vamos a lograr:
- CRUD de cuentas de dinero
- Registrar movimientos que afectan saldos
- Dashboard con saldos actuales
- Últimos movimientos

### Entregables:
- ✅ Backend: CRUD money_accounts
- ✅ Backend: POST /money/movements
- ✅ Frontend: Dashboard de tesorería
- ✅ Frontend: Formulario "Registrar Movimiento"
- ✅ Cálculo automático de saldos

---

## TAREA 4.2: Gastos con Categorización
**Duración:** 3 horas  
**Objetivo:** Registro y control de gastos operativos

### Descripción:
Sistema de gastos del negocio:
- Categorías (Capital Humano, Bodega, Fletes, Vehículos, etc.)
- Gastos directos (asignados a unidad de negocio)
- Gastos generales (se prorratean)
- Relación con cuentas de dinero

### Qué vamos a lograr:
- Registrar gastos con categoría
- Marcar si es gasto directo o general
- Ver reporte de gastos por categoría
- Integración con tesorería

### Entregables:
- ✅ Backend: CRUD expense_categories
- ✅ Backend: POST /expenses
- ✅ Frontend: Formulario "Registrar Gasto"
- ✅ Frontend: Reporte "Gastos por Categoría"

---

## TAREA 4.3: Provisiones (Fondos Especiales)
**Duración:** 3 horas  
**Objetivo:** Apartar dinero para gastos futuros

### Descripción:
Sistema de provisiones:
- Crear provisión (es un tercero especial)
- Aportar dinero a provisión
- Gastar desde provisión
- Saldo negativo = fondos disponibles

### Qué vamos a lograr:
- Crear provisiones (Mantenimiento, Dotación, etc.)
- Aportar mensualmente
- Gastar sin afectar caja (ya estaba apartado)
- Ver saldo de cada provisión

### Entregables:
- ✅ Provisiones usando third_parties (is_provision=true)
- ✅ Movimiento tipo "provision_deposit"
- ✅ Movimiento tipo "provision_expense"
- ✅ Frontend: Gestión de provisiones
- ✅ Estado de cuenta de provisión

---

## TAREA 4.4: Gastos Diferidos
**Duración:** 3 horas  
**Objetivo:** Distribuir gastos grandes en varios meses

### Descripción:
Sistema de gastos diferidos:
- Ejemplo: Dotación $3M distribuida en 4 meses
- Cada mes sistema recuerda aplicar $750K
- Usuario confirma o pospone
- Seguimiento de aplicaciones

### Qué vamos a lograr:
- Crear gasto diferido con meses a distribuir
- Dashboard muestra pendientes del mes
- Click "Aplicar Ahora" crea gasto automático
- Historial de aplicaciones

### Entregables:
- ✅ Backend: CRUD deferred_expenses
- ✅ Backend: POST /deferred-expenses/{id}/apply
- ✅ Frontend: Crear gasto diferido
- ✅ Frontend: Dashboard con pendientes
- ✅ Frontend: Botón "Aplicar Ahora"

---

## TAREA 4.5: Importación Bancaria
**Duración:** 2 horas  
**Objetivo:** Subir movimientos desde Excel del banco

### Descripción:
Importador de extractos bancarios:
- Usuario sube Excel del banco
- Sistema detecta formato
- Mapea columnas
- Crea movimientos masivamente

### Qué vamos a lograr:
- Subir archivo Excel
- Preview de movimientos a importar
- Asignar categorías/terceros
- Importar con un click

### Entregables:
- ✅ Backend: POST /money/import-bank-statement
- ✅ Librería openpyxl o pandas para leer Excel
- ✅ Frontend: Página "Importar Movimientos"
- ✅ Preview antes de confirmar

---

# FASE 5: MÓDULOS COMPLEMENTARIOS
**Duración:** 12 horas  
**Objetivo:** Funcionalidades adicionales importantes

## TAREA 5.1: Módulo de Tránsitos
**Duración:** 3 horas  
**Objetivo:** Material en camino sin precios definidos

### Descripción:
Sistema de tránsitos:
- Registrar remisión (proveedor → cliente)
- Material en camino
- Al llegar: cerrar tránsito ingresando cantidades y precios
- Sistema crea compra + venta automáticamente

### Qué vamos a lograr:
- Crear tránsito con datos básicos
- Lista de tránsitos pendientes
- Cerrar tránsito convierte en doble partida
- Ganancia calculada

### Entregables:
- ✅ Backend: CRUD transits
- ✅ Backend: POST /transits/{id}/close
- ✅ Frontend: Crear tránsito
- ✅ Frontend: Lista pendientes
- ✅ Frontend: Modal cerrar tránsito

---

## TAREA 5.2: Unidades de Negocio
**Duración:** 4 horas  
**Objetivo:** Análisis de rentabilidad por línea

### Descripción:
Sistema de unidades de negocio:
- Agrupar materiales (Fibras, Chatarra, Metales No Ferrosos)
- Asignar gastos directos
- Prorratear gastos indirectos
- Calcular utilidad neta por unidad

### Qué vamos a lograr:
- Configurar unidades de negocio
- Asignar materiales a unidades
- Marcar gastos como directos (a qué unidad)
- Reporte de rentabilidad por unidad

### Entregables:
- ✅ Backend: CRUD business_units
- ✅ Backend: GET /business-units/{id}/profitability
- ✅ Frontend: Configuración unidades
- ✅ Frontend: Reporte rentabilidad
- ✅ Cálculo de gastos indirectos prorrateados

---

## TAREA 5.3: Proyecciones y Metas
**Duración:** 3 horas  
**Objetivo:** Seguimiento de cumplimiento de metas

### Descripción:
Sistema de metas mensuales:
- Definir metas de compras (por material)
- Definir metas de ventas (por material)
- Definir presupuesto de gastos (por categoría)
- Dashboard muestra % cumplimiento en tiempo real

### Qué vamos a lograr:
- Crear proyección del mes
- Establecer metas
- Dashboard compara real vs meta
- Alertas si va atrasado

### Entregables:
- ✅ Backend: CRUD projections
- ✅ Backend: GET /projections/{id}/achievement
- ✅ Frontend: Crear proyección
- ✅ Frontend: Dashboard cumplimiento
- ✅ Cálculo de % vs progreso esperado

---

## TAREA 5.4: Lista de Precios
**Duración:** 2 horas  
**Objetivo:** Precios sugeridos para liquidación

### Descripción:
Sistema de lista de precios:
- Precio sugerido de compra por material
- Precio sugerido de venta por material
- Se actualiza diariamente
- Sistema pre-llena al liquidar

### Qué vamos a lograr:
- CRUD de lista de precios
- Al liquidar compra, sistema sugiere precio
- Usuario puede aceptar o modificar
- Historial de cambios de precios

### Entregables:
- ✅ Backend: CRUD price_lists
- ✅ Al liquidar, GET /price-lists/current/{material_id}
- ✅ Frontend: Gestión de lista de precios
- ✅ Precios pre-llenados en liquidación

---

# FASE 6: REPORTES Y BI
**Duración:** 10 horas  
**Objetivo:** Dashboards y reportes financieros

## TAREA 6.1: Dashboard Principal
**Duración:** 3 horas  
**Objetivo:** Vista ejecutiva del negocio

### Descripción:
Dashboard principal con métricas clave:
- Dinero disponible (efectivo + bancos)
- Inventario valorizado
- Utilidad del mes
- Cuentas por cobrar/pagar
- Últimos movimientos
- Alertas importantes

### Qué vamos a lograr:
- Vista HOME con métricas principales
- Gráficas de tendencias
- Alertas visibles (stock bajo, metas atrasadas, etc.)
- Accesos rápidos a módulos

### Entregables:
- ✅ Backend: GET /dashboard/summary
- ✅ Frontend: Página Dashboard
- ✅ Cards con métricas
- ✅ Gráfica de utilidad mensual
- ✅ Lista de alertas

---

## TAREA 6.2: Reportes Financieros
**Duración:** 4 horas  
**Objetivo:** Estado de Resultados, Flujo de Caja, Balance

### Descripción:
Reportes financieros principales:
- Estado de Resultados (P&L)
- Flujo de Caja
- Balance General

### Qué vamos a lograr:
- Reporte con fórmulas correctas
- Filtro por rango de fechas
- Exportar a Excel
- Formato profesional

### Entregables:
- ✅ Backend: GET /reports/income-statement
- ✅ Backend: GET /reports/cash-flow
- ✅ Backend: GET /reports/balance-sheet
- ✅ Frontend: Páginas de reportes
- ✅ Botón "Exportar a Excel"

---

## TAREA 6.3: Reportes Operativos
**Duración:** 3 horas  
**Objetivo:** Compras, Ventas, Inventario, Gastos

### Descripción:
Reportes operativos del día a día:
- Reporte de compras (por período, proveedor, material)
- Reporte de ventas (por período, cliente, material)
- Inventario valorizado
- Gastos por categoría
- Análisis de márgenes por material

### Qué vamos a lograr:
- Filtrar y exportar cada reporte
- Ver totales y promedios
- Gráficas de barras/torta
- Excel descargable

### Entregables:
- ✅ 5+ reportes operativos
- ✅ Filtros avanzados
- ✅ Exportación Excel
- ✅ Gráficas con Recharts

---

# FASE 7: MIGRACIÓN Y GO-LIVE
**Duración:** 8 horas  
**Objetivo:** Puesta en producción con datos reales

## TAREA 7.1: Preparación de Datos
**Duración:** 2 horas  
**Objetivo:** Limpiar y validar Excel del cliente

### Descripción:
Recibir y preparar archivo Excel del cliente con:
- Terceros con saldos
- Inventario actual valorizado
- Cuentas de dinero con saldos
- Provisiones
- Catálogos (materiales, categorías)

### Qué vamos a lograr:
- Excel validado y limpio
- Formato correcto para importación
- Sin duplicados ni inconsistencias

### Entregables:
- ✅ Excel del cliente validado
- ✅ Script de validación
- ✅ Reporte de inconsistencias (si hay)

---

## TAREA 7.2: Scripts de Migración
**Duración:** 3 horas  
**Objetivo:** Importar datos iniciales

### Descripción:
Crear scripts que lean Excel y poblen base de datos:
- Importar organizations
- Importar users
- Importar third_parties con saldos
- Importar materials
- Importar inventory con costos
- Importar money_accounts con saldos

### Qué vamos a lograr:
- Script Python que lee Excel
- Crea registros en base de datos
- Valida integridad referencial
- Maneja errores gracefully

### Entregables:
- ✅ Script migrate_initial_data.py
- ✅ Todos los datos cargados
- ✅ Saldos cuadrados
- ✅ Log de importación

---

## TAREA 7.3: Testing y QA
**Duración:** 2 horas  
**Objetivo:** Validar que todo funciona correctamente

### Descripción:
Pruebas funcionales completas:
- Crear compra → liquidar → verificar inventario
- Crear venta → verificar stock baja → verificar saldo cliente
- Registrar pago → verificar saldo cuenta y tercero
- Aplicar gasto diferido
- Generar reportes

### Qué vamos a lograr:
- Todos los flujos principales funcionando
- No hay errores críticos
- UI responsive funciona
- Datos cuadran

### Entregables:
- ✅ Checklist de pruebas completo
- ✅ Bugs críticos resueltos
- ✅ Sistema estable

---

## TAREA 7.4: Deploy a Producción
**Duración:** 1 hora  
**Objetivo:** Sistema en VPS accesible desde internet

### Descripción:
Deploy final en Hostinger VPS:
- Configurar Nginx como reverse proxy
- SSL con Let's Encrypt
- Variables de entorno de producción
- Backups automáticos configurados
- Dominio apuntando correctamente

### Qué vamos a lograr:
- Sistema accesible desde https://dominio.com
- SSL válido (candado verde)
- Backend y frontend funcionando
- Base de datos con backups

### Entregables:
- ✅ App funcionando en producción
- ✅ HTTPS configurado
- ✅ Backups automáticos
- ✅ Monitoreo básico

---

# RESUMEN DEL ROADMAP

## Por Fases:

| Fase | Duración | Módulos Principales |
|------|----------|---------------------|
| **0: Infraestructura** | 14 hrs | Git/GitHub, VPS, PostgreSQL, Setup proyectos |
| **1: Arquitectura Base** | 15 hrs | Auth, Multi-tenant, CRUD genérico |
| **2: Módulos Core** | 20 hrs | Compras, Ventas, Terceros, Materiales |
| **3: Inventario** | 18 hrs | Stock, Costo Promedio, Transformación |
| **4: Tesorería** | 15 hrs | Cuentas, Gastos, Provisiones, Diferidos |
| **5: Complementarios** | 12 hrs | Tránsitos, Unidades Negocio, Metas |
| **6: Reportes** | 10 hrs | Dashboards, Reportes Financieros |
| **7: Go-Live** | 8 hrs | Migración, Testing, Deploy |
| **TOTAL** | **112 hrs** | **Sistema Completo** |

## Priorización:

### Must Have (Semanas 1-4):
- ✅ Fases 0, 1, 2, 3
- Sin esto el sistema no funciona

### Should Have (Semanas 5-6):
- ✅ Fases 4, 5
- Importante pero puede esperar

### Nice to Have (Semana 7):
- ✅ Fase 6, 7
- Mejora experiencia pero no bloquea operación

---

## Metodología de Trabajo:

Para cada tarea seguiremos este proceso:

1. **Yo (Claude) te explico** qué vamos a hacer
2. **Yo te doy el prompt** para GitHub Copilot
3. **Tú ejecutas** el prompt en Copilot
4. **Tú me compartes** la respuesta de Copilot
5. **Juntos validamos** si está correcto
6. **Iteramos** si hace falta ajustar
7. **Probamos** que funcione
8. **Avanzamos** a la siguiente tarea

---

## Siguiente Paso:

**¿Apruebas este roadmap?**

Si estás de acuerdo, empezamos con **FASE 0 - TAREA 0.1: Configuración VPS Hostinger**.

Si quieres ajustar algo (más detalle, menos tareas, cambiar orden, etc.), dime qué modificar y actualizo el plan.

**¿Qué dices, arrancamos?** 🚀