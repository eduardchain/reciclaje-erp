# DOCUMENTO DE REQUERIMIENTOS FUNCIONALES - VERSIÓN FINAL
## Sistema de Gestión para Empresa de Reciclaje - "ReciclaTrac"

**Fecha:** Enero 2026  
**Versión:** 2.0 - FINAL para Implementación  
**Cliente:** Empresa de Reciclaje - Gustavo Díaz  
**Estado:** APROBADO - Listo para Desarrollo

---

## CONTROL DE VERSIONES

| Versión | Fecha | Cambios | Autor |
|---------|-------|---------|-------|
| 1.0 | 16 Ene 2026 | Versión inicial basada en reunión | Eduardo Chain |
| 2.0 | 31 Ene 2026 | Integración de cambios post-revisión cliente | Eduardo Chain |

**Cambios principales v2.0:**
- ✅ Agregadas Unidades de Negocio con análisis de rentabilidad
- ✅ Agregado sistema de Metas y Proyecciones
- ✅ Integrada transformación de materiales (desintegración)
- ✅ Definidas Provisiones como terceros especiales
- ✅ Implementado Inventario en Tránsito
- ✅ Agregadas Múltiples Bodegas
- ✅ Implementadas Listas de Precios predeterminadas
- ✅ Definidos 5 roles específicos con permisos granulares
- ✅ Agregados campos: Placa vehículo, Número factura, Adjuntos
- ✅ Gastos diferidos con programación semi-automática

---

## ÍNDICE

### PARTE I: VISIÓN GENERAL
1. [Introducción](#1-introducción)
2. [Objetivos del Sistema](#2-objetivos-del-sistema)
3. [Alcance del Proyecto](#3-alcance-del-proyecto)
4. [Usuarios del Sistema](#4-usuarios-del-sistema)

### PARTE II: MODELO DE DATOS
5. [Entidades Principales](#5-entidades-principales)
6. [Catálogos y Configuración](#6-catálogos-y-configuración)
7. [Relaciones entre Entidades](#7-relaciones-entre-entidades)

### PARTE III: MÓDULOS FUNCIONALES
8. [Módulo de Compras](#8-módulo-de-compras)
9. [Módulo de Ventas](#9-módulo-de-ventas)
10. [Módulo de Inventario](#10-módulo-de-inventario)
11. [Módulo de Tesorería](#11-módulo-de-tesorería)
12. [Módulo de Tránsitos](#12-módulo-de-tránsitos)
13. [Módulo de Unidades de Negocio](#13-módulo-de-unidades-de-negocio)
14. [Módulo de Proyecciones y Metas](#14-módulo-de-proyecciones-y-metas)
15. [Módulo de Terceros](#15-módulo-de-terceros)
16. [Módulo de Materiales](#16-módulo-de-materiales)
17. [Módulo de Administración](#17-módulo-de-administración)

### PARTE IV: REPORTES Y ANÁLISIS
18. [Reportes Financieros](#18-reportes-financieros)
19. [Reportes Operativos](#19-reportes-operativos)
20. [Dashboards y Métricas](#20-dashboards-y-métricas)

### PARTE V: REGLAS DE NEGOCIO
21. [Reglas de Inventario](#21-reglas-de-inventario)
22. [Reglas Financieras](#22-reglas-financieras)
23. [Fórmulas y Cálculos](#23-fórmulas-y-cálculos)

### PARTE VI: SEGURIDAD Y AUDITORÍA
24. [Roles y Permisos](#24-roles-y-permisos)
25. [Auditoría y Trazabilidad](#25-auditoría-y-trazabilidad)

### PARTE VII: IMPLEMENTACIÓN
26. [Plan de Migración](#26-plan-de-migración)
27. [Anexos](#27-anexos)

---

# PARTE I: VISIÓN GENERAL

## 1. INTRODUCCIÓN

### 1.1 Propósito del Documento

Este documento define los requerimientos funcionales COMPLETOS para el desarrollo del sistema de gestión "ReciclaTrac", especializado para empresas del sector de reciclaje de metales y materiales.

**Audiencia:**
- Equipo de desarrollo
- Cliente (Gustavo Díaz y equipo)
- Usuarios finales (para capacitación)
- Soporte técnico futuro

**Uso del documento:**
- ✅ Base para desarrollo (documento de referencia principal)
- ✅ Validación de funcionalidades
- ✅ Casos de prueba
- ✅ Manual de usuario (base)
- ✅ Especificación técnica

### 1.2 Contexto del Negocio

**Industria:** Reciclaje de metales y materiales
**Operación principal:**
1. Compra de material reciclable a proveedores (locales y por fuera)
2. Almacenamiento y/o procesamiento básico
3. Venta a clientes industriales

**Características específicas:**
- Alto volumen de transacciones diarias (20-50 compras/ventas por día)
- Precios variables (fluctúan con dólar/mercado)
- Operaciones mixtas (contado y crédito)
- Material en múltiples ubicaciones físicas
- Operaciones directas proveedor→cliente sin pasar por bodega
- Manejo intensivo de efectivo (compras en ventanilla)

---

## 2. OBJETIVOS DEL SISTEMA

### 2.1 Objetivos Primarios

**OP-01: Gestión del Ciclo Completo del Negocio**
- Registro de todas las transacciones comerciales
- Control de inventario en tiempo real
- Gestión de flujo de caja
- Estados financieros automáticos

**OP-02: Análisis de Rentabilidad por Unidad de Negocio** ⭐ NUEVO
- Segmentación por líneas de negocio (Fibras, Chatarra, Metales No Ferrosos)
- Asignación de gastos directos e indirectos
- Cálculo de utilidad neta por unidad
- Identificación de líneas rentables vs no rentables

**OP-03: Seguimiento de Cumplimiento de Metas** ⭐ NUEVO
- Definición de metas mensuales de compras, ventas y gastos
- Monitoreo en tiempo real de % cumplimiento
- Alertas de desviaciones

**OP-04: Trazabilidad Completa**
- Desde compra hasta venta
- Material en tránsito
- Transformaciones (desintegración)
- Auditoría de cambios

### 2.2 Objetivos Secundarios

**OS-01: Eficiencia Operativa**
- Reducir tiempo de liquidación (precios predeterminados)
- Minimizar errores de captura
- Automatizar cálculos complejos

**OS-02: Control Financiero**
- Visibilidad de inventario real (liquidado + tránsito)
- Manejo de provisiones y fondos
- Gastos diferidos automatizados

**OS-03: Toma de Decisiones**
- Reportes en tiempo real
- Métricas clave visibles
- Identificación de cuellos de botella

---

## 3. ALCANCE DEL PROYECTO

### 3.1 Lo que SÍ Incluye ✅

#### Gestión Comercial
- ✅ Registro de compras con liquidación diferida
- ✅ Registro de ventas (directas y despachos)
- ✅ Operaciones de doble partida (pasa mano)
- ✅ Gestión de tránsitos (material en camino)
- ✅ Comisiones y descuentos variables por transacción

#### Control de Inventario
- ✅ Costeo por promedio ponderado móvil
- ✅ Inventario en múltiples bodegas
- ✅ Inventario en tránsito (pendiente de liquidar)
- ✅ Transformación de materiales (desintegración)
- ✅ Ajustes de inventario con auditoría
- ✅ Traslados entre bodegas
- ✅ Unidades de medida variables (kg, unidades, litros)

#### Tesorería
- ✅ Múltiples cuentas de dinero (bancos, cajas)
- ✅ 10+ tipos de movimientos financieros
- ✅ Gastos con categorización
- ✅ Gastos provisionados (causados no pagados)
- ✅ Gastos diferidos programables
- ✅ Provisiones para mantenimiento/dotación
- ✅ Estados de cuenta por tercero
- ✅ Conciliación bancaria
- ✅ Importación masiva de movimientos bancarios ⭐ NUEVO

#### Análisis y Reportes
- ✅ Balance general consolidado
- ✅ Estado de resultados
- ✅ Flujo de caja
- ✅ Análisis de rentabilidad por unidad de negocio ⭐ NUEVO
- ✅ Seguimiento de metas y proyecciones ⭐ NUEVO
- ✅ Arqueo diario
- ✅ Gastos por categoría
- ✅ Exportación a Excel de todos los reportes

#### Administración
- ✅ 5 roles específicos con permisos granulares
- ✅ Auditoría completa (quién hizo qué y cuándo)
- ✅ Listas de precios predeterminadas ⭐ NUEVO
- ✅ Configuración de cortes mensuales
- ✅ Gestión de bodegas ⭐ NUEVO
- ✅ Gestión de unidades de negocio ⭐ NUEVO
- ✅ Adjuntar imágenes como evidencia ⭐ NUEVO

### 3.2 Lo que NO Incluye ❌

**Integraciones Externas:**
- ❌ Facturación electrónica DIAN
- ❌ Integración con software contable de terceros
- ❌ Pasarela de pagos en línea
- ❌ API pública para terceros

**Módulos no requeridos:**
- ❌ Punto de venta (POS) físico con lector código barras
- ❌ Nómina completa (cálculo prestaciones, desprendibles)
- ❌ Contabilidad de doble partida formal
- ❌ Control de producción/manufactura complejo
- ❌ Logística de ruteo de vehículos
- ❌ CRM con seguimiento de leads
- ❌ Gestión de RRHH (vacaciones, evaluaciones)

**Razón de exclusión:** El negocio no requiere estas funcionalidades o las maneja externamente.

---

## 4. USUARIOS DEL SISTEMA

### 4.1 Perfiles de Usuario

| Rol | Usuario | Cantidad | Función Principal |
|-----|---------|----------|-------------------|
| Báscula | John | 1 | Registro de cantidades (sin precios) |
| Auxiliar Tesorería | Nixon | 1 | Liquidación + Caja Menor |
| Planillador | Ingrid | 1 | Ventas + Tránsitos |
| Administrador | Gustavo | 1 | Gestión completa |
| Administrador Lector | Gabriel | 1 | Solo consulta |

**Total:** 5 usuarios

### 4.2 Descripción Detallada de Roles

Ver sección [24. Roles y Permisos](#24-roles-y-permisos) para especificación completa.

---

# PARTE II: MODELO DE DATOS

## 5. ENTIDADES PRINCIPALES

### 5.1 TERCEROS (third_parties)

Un tercero es cualquier persona o empresa externa con la que se tiene relación comercial.

**Características:**
- ✅ Puede tener múltiples roles simultáneos
- ✅ Incluye provisiones (fondos especiales) ⭐ NUEVO
- ✅ Tiene estado de cuenta histórico
- ✅ Saldo actual positivo/negativo

**Estructura de datos:**
```typescript
interface ThirdParty {
  id: string;
  organization_id: string;
  
  // Información básica
  name: string;                    // Nombre o razón social
  identification_number?: string;  // NIT/Cédula
  email?: string;
  phone?: string;
  address?: string;
  
  // Roles (puede tener varios)
  is_supplier: boolean;      // ¿Es proveedor?
  is_customer: boolean;      // ¿Es cliente?
  is_investor: boolean;      // ¿Es inversionista/socio?
  is_provision: boolean;     // ⭐ NUEVO: ¿Es provisión?
  
  // Específico para provisiones
  provision_type?: string;   // 'mantenimiento', 'dotacion', etc.
  
  // Categorización adicional
  category?: string;  // 'proyecto', 'otra_facturacion', 'obligacion_financiera'
  
  // Control financiero
  current_balance: number;   // Positivo = nos debe, Negativo = le debemos
  
  // Control
  is_active: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Ejemplos de terceros:**

```typescript
// Proveedor simple
{
  name: "Reciclajes del Norte S.A.S.",
  is_supplier: true,
  is_customer: false,
  is_investor: false,
  is_provision: false,
  current_balance: -2500000  // Le debemos
}

// Cliente que también compra (proveedor + cliente)
{
  name: "Metales Industriales Ltda",
  is_supplier: true,
  is_customer: true,
  is_investor: false,
  is_provision: false,
  current_balance: 1500000  // Nos debe más de lo que le debemos
}

// Provisión de mantenimiento ⭐ NUEVO
{
  name: "Provisión Mantenimiento Maquinaria",
  is_supplier: false,
  is_customer: false,
  is_investor: false,
  is_provision: true,
  provision_type: "mantenimiento",
  current_balance: -40000000  // Tenemos $40M provisionados
}
```

**Reglas de negocio:**
- RN-TP-01: Al menos uno de los flags (is_supplier, is_customer, is_investor, is_provision) debe ser `true`
- RN-TP-02: El `identification_number` debe ser único por organización (si se provee)
- RN-TP-03: Las provisiones solo pueden tener `is_provision = true` (no pueden ser supplier/customer/investor)
- RN-TP-04: El saldo se actualiza automáticamente con cada transacción

---

### 5.2 MATERIALES (materials)

Tipos de material reciclable que se compra/vende.

**Estructura de datos:**
```typescript
interface Material {
  id: string;
  organization_id: string;
  
  // Identificación
  code: string;              // Código único (ej: "CU-01", "HIERRO-A")
  name: string;              // Nombre (ej: "Cobre Limpio")
  description?: string;
  
  // Clasificación
  category_id: string;       // FK a material_categories
  business_unit_id: string;  // ⭐ NUEVO: FK a business_units
  
  // Unidades
  default_unit: string;      // ⭐ ACTUALIZADO: 'kg', 'unidad', 'litro', 'ton'
  
  // Control de inventario (campos calculados, actualizados por triggers)
  current_stock_liquidated: number;    // ⭐ NUEVO: Stock con precio
  current_stock_transit: number;       // ⭐ NUEVO: Stock sin precio
  current_stock_total: number;         // Total físico
  current_average_cost: number;        // Costo promedio actual
  total_inventory_value: number;       // Valor total del inventario
  
  // Desglose por bodega (JSONB)
  stock_by_warehouse: {
    [warehouse_id: string]: {
      liquidated: number;
      transit: number;
      total: number;
    }
  };
  
  // Orden personalizado ⭐ NUEVO
  sort_order: number;        // Para ordenar en UI (menor = más prioritario)
  
  // Control
  is_active: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Campos especiales:**

**business_unit_id:** ⭐ NUEVO
- Cada material pertenece a UNA unidad de negocio
- Permite análisis de rentabilidad por línea
- Ejemplos: "Fibras", "Chatarra", "Metales No Ferrosos"

**default_unit:** ⭐ ACTUALIZADO
- Define la unidad de medida del material
- Afecta cómo se muestra en pantalla
- Valores permitidos: 'kg', 'unidad', 'litro', 'ton'

**sort_order:** ⭐ NUEVO
- Orden personalizado para UI
- Materiales más usados tienen sort_order menor
- Ejemplo: Hierro=1, Cobre=2, Aluminio=3, ... Otros=999

**Ejemplos:**

```typescript
// Material normal (por peso)
{
  code: "CU-01",
  name: "Cobre Limpio",
  business_unit_id: "metales_no_ferrosos",
  default_unit: "kg",
  current_stock_liquidated: 1500,
  current_stock_transit: 500,
  current_stock_total: 2000,
  current_average_cost: 8500,
  sort_order: 2
}

// Material por unidades ⭐ NUEVO
{
  code: "BAT-01",
  name: "Baterías Usadas",
  business_unit_id: "otros",
  default_unit: "unidad",
  current_stock_total: 250,
  sort_order: 15
}

// Material compuesto (para desintegrar)
{
  code: "COMP-01",
  name: "Material Compuesto",
  business_unit_id: "metales_no_ferrosos",
  default_unit: "kg",
  description: "Material mixto para desintegración",
  sort_order: 999  // Al final
}
```

**Reglas de negocio:**
- RN-MAT-01: El `code` debe ser único por organización
- RN-MAT-02: Un material solo puede pertenecer a UNA business_unit
- RN-MAT-03: Los campos `current_stock_*` son calculados, no se editan manualmente
- RN-MAT-04: Solo se puede eliminar si NO tiene movimientos de inventario
- RN-MAT-05: Al desactivar, no aparece en selectores pero mantiene historial

---

### 5.3 UNIDADES DE NEGOCIO (business_units) ⭐ NUEVO

Agrupación de materiales que representa una línea de negocio.

**Concepto:**
No es un material individual, sino una familia de materiales que se analiza como unidad.

**Estructura de datos:**
```typescript
interface BusinessUnit {
  id: string;
  organization_id: string;
  
  // Identificación
  code: string;              // Código corto (ej: "FIBRAS", "CHATARRA")
  name: string;              // Nombre (ej: "Fibras")
  description?: string;      // Descripción
  
  // Visualización
  color?: string;            // Color para gráficos
  icon?: string;             // Icono representativo
  
  // Control
  is_active: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Ejemplos:**
```typescript
{
  code: "FIBRAS",
  name: "Fibras",
  description: "Papel, Cartón, Pliega",
  color: "#3B82F6",
  materials: ["Papel Blanco", "Cartón", "Pliega", "Archivo"]
}

{
  code: "CHATARRA",
  name: "Chatarra",
  description: "Metales Ferrosos",
  color: "#EF4444",
  materials: ["Hierro", "Acero", "Hierro Fundido"]
}

{
  code: "NO_FERROSOS",
  name: "Metales No Ferrosos",
  description: "Cobre, Aluminio, Bronce",
  color: "#F59E0B",
  materials: ["Cobre Limpio", "Cobre Sucio", "Aluminio", "Bronce"]
}
```

**Relación con materiales:**
- Un material pertenece a una sola unidad de negocio (campo `business_unit_id` en materials)
- Una unidad de negocio agrupa múltiples materiales
- Los reportes de rentabilidad se hacen por unidad de negocio

---

### 5.4 BODEGAS (warehouses) ⭐ NUEVO

Ubicaciones físicas donde se almacena el inventario.

**Estructura de datos:**
```typescript
interface Warehouse {
  id: string;
  organization_id: string;
  
  // Identificación
  code: string;              // Código corto (ej: "BOD-01", "CIRCUNVAL")
  name: string;              // Nombre (ej: "Bodega Principal")
  address?: string;
  
  // Tipo
  type?: string;             // 'principal', 'secundaria', 'transito'
  
  // Control
  is_active: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Ejemplos:**
```typescript
{
  code: "CIRCUNVAL",
  name: "Bodega Circunvalar",
  address: "Calle 123 #45-67",
  type: "principal",
  is_active: true
}

{
  code: "SAN_ALBERTO",
  name: "Bodega San Alberto",
  type: "secundaria",
  is_active: true
}

{
  code: "VIGAS",
  name: "Bodega de Vigas",
  type: "secundaria",
  is_active: true
}
```

**Reglas de negocio:**
- RN-BOD-01: Debe existir al menos UNA bodega activa
- RN-BOD-02: No se puede eliminar bodega con inventario
- RN-BOD-03: Cada transacción (compra/venta) debe especificar bodega

---

### 5.5 CUENTAS DE DINERO (money_accounts)

Cuentas donde se maneja el efectivo y recursos financieros.

**Estructura de datos:**
```typescript
interface MoneyAccount {
  id: string;
  organization_id: string;
  
  // Identificación
  name: string;              // Nombre (ej: "Banco Bancolombia", "Caja General")
  account_number?: string;   // Número de cuenta (para bancos)
  
  // Tipo
  type: 'cash' | 'bank' | 'digital';
  
  // Saldo
  current_balance: number;   // Actualizado automáticamente
  
  // Control
  is_active: boolean;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Tipos de cuenta:**

1. **cash (Efectivo):**
   - Caja General (Gustavo)
   - Caja Menor (Nixon)
   
2. **bank (Bancos):**
   - Cuenta Bancolombia
   - Cuenta Davivienda
   - Cuenta Banco de Bogotá
   
3. **digital (Billeteras):**
   - Nequi
   - Daviplata

**Ejemplos:**
```typescript
// Caja General
{
  name: "Caja General",
  type: "cash",
  current_balance: 5000000,
  is_active: true
}

// Caja Menor (manejada por Nixon)
{
  name: "Caja Menor",
  type: "cash",
  current_balance: 2000000,
  is_active: true
}

// Cuenta bancaria
{
  name: "Banco Bancolombia Ahorros",
  account_number: "12345678",
  type: "bank",
  current_balance: 50000000,
  is_active: true
}
```

**Reglas de negocio:**
- RN-CTA-01: El saldo se actualiza automáticamente con cada movimiento
- RN-CTA-02: No se puede eliminar cuenta con movimientos
- RN-CTA-03: El sistema permite saldos negativos (sobregiro)

---

## 6. CATÁLOGOS Y CONFIGURACIÓN

### 6.1 CATEGORÍAS DE MATERIALES (material_categories)

Agrupación de materiales similares.

```typescript
interface MaterialCategory {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Ejemplos:**
- Cobre
- Aluminio
- Hierro
- Papel
- Cartón
- Plásticos
- Baterías

---

### 6.2 CATEGORÍAS DE GASTOS (expense_categories)

Clasificación de gastos operativos.

```typescript
interface ExpenseCategory {
  id: string;
  organization_id: string;
  name: string;
  description?: string;
  
  // Para análisis de unidad de negocio ⭐ NUEVO
  is_direct_expense: boolean;  // ¿Puede ser gasto directo de unidad?
  
  created_at: timestamp;
  updated_at: timestamp;
}
```

**Ejemplos según cliente:**

**Capital Humano:**
- Nómina
- Seguridad Social
- Dotación

**Obligaciones Financieras:**
- Préstamos
- 2x1000
- Intereses

**Bodega:**
- Arriendo
- Servicios Públicos
- Vigilancia

**Fletes y Básculas:**
- Fletes Externos
- Pesaje
- Transporte

**Vehículos:**
- Combustible
- Mantenimiento
- Seguros

**Consumibles:**
- Alambre (directo a Fibras)
- Insumos de Patio
- Insumos de Oficina

---

### 6.3 LISTAS DE PRECIOS (price_lists) ⭐ NUEVO

Precios predeterminados para agilizar liquidación.

```typescript
interface PriceList {
  id: string;
  organization_id: string;
  material_id: string;
  
  // Precios actuales
  purchase_price?: number;   // Precio de compra sugerido
  sale_price?: number;       // Precio de venta sugerido
  
  // Control
  last_updated_at: timestamp;
  last_updated_by: string;   // user_id
  
  created_at: timestamp;
}
```

**Funcionalidad:**
- Se actualiza diariamente (precios fluctúan con dólar)
- Ingrid y Nixon mantienen la lista
- Al liquidar, el sistema pre-llena estos precios
- Usuario puede modificar manualmente si hay excepción

**Ejemplo de uso:**
```typescript
// Tabla de precios hoy
{
  material: "Cobre Limpio",
  purchase_price: 8000,
  sale_price: 10000,
  last_updated_at: "2026-01-31 08:00:00",
  last_updated_by: "ingrid_id"
}

// Al liquidar compra:
// Sistema automáticamente sugiere $8,000/kg
// Nixon puede cambiar a $8,200 si negoció mejor precio
```

---

## 7. RELACIONES ENTRE ENTIDADES

### 7.1 Diagrama de Relaciones Principales

```
ORGANIZACIONES
│
├─ TERCEROS (third_parties)
│  ├─ Proveedores
│  ├─ Clientes
│  ├─ Inversionistas
│  └─ Provisiones ⭐
│
├─ MATERIALES (materials)
│  ├─ Categoría (material_categories)
│  └─ Unidad de Negocio (business_units) ⭐
│
├─ BODEGAS (warehouses) ⭐
│
├─ CUENTAS DE DINERO (money_accounts)
│
├─ COMPRAS (purchases)
│  ├─ Líneas (purchase_lines)
│  └─ Movimientos Inventario
│
├─ VENTAS (sales)
│  ├─ Líneas (sale_lines)
│  └─ Movimientos Inventario
│
├─ TRÁNSITOS (transits)
│
├─ MOVIMIENTOS DINERO (money_movements)
│
├─ GASTOS DIFERIDOS (deferred_expenses) ⭐
│
└─ PROYECCIONES (projections) ⭐
   └─ Metas por Material
```

---

# PARTE III: MÓDULOS FUNCIONALES

## 8. MÓDULO DE COMPRAS

### 8.1 Descripción General

Permite registrar todas las compras de material a proveedores, con flujo de dos pasos: creación (solo cantidades) y liquidación (con precios).

### 8.2 Sub-módulos

1. **Nueva Compra** - Crear compra sin precios
2. **Compras Pendientes de Liquidar** ⭐ NUEVO
3. **Liquidar Compras** ⭐ NUEVO
4. **Historial de Compras** - Lista completa

### 8.3 Estructura de Datos

```typescript
interface Purchase {
  id: string;
  organization_id: string;
  purchase_number: number;           // Autoincremental
  
  // Datos básicos
  supplier_id: string;               // FK a third_parties
  warehouse_id: string;              // ⭐ NUEVO: Bodega destino
  date: date;
  
  // Transporte ⭐ NUEVO
  vehicle_plate?: string;            // Placa del vehículo
  
  // Estado ⭐ NUEVO
  status: 'pending_liquidation' | 'liquidated' | 'cancelled';
  
  // Montos
  total_amount: number;              // Calculado
  
  // Liquidación ⭐ NUEVO
  liquidated_at?: timestamp;
  liquidated_by?: string;            // user_id
  
  // Notas
  notes?: string;
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
  
  // Relaciones
  purchase_lines: PurchaseLine[];
}

interface PurchaseLine {
  id: string;
  purchase_id: string;
  material_id: string;
  
  quantity: number;
  unit_price?: number;               // ⭐ Puede ser null si pendiente
  total_price: number;               // Calculado
  
  created_at: timestamp;
}
```

### 8.4 Flujo de Trabajo Detallado

#### PASO 1: BÁSCULA CREA COMPRA (John)

**Pantalla:** Nueva Compra

**Campos visibles:**
```
┌──────────────────────────────────────────────┐
│         REGISTRAR NUEVA COMPRA               │
├──────────────────────────────────────────────┤
│                                              │
│ Fecha: [DD/MM/YYYY] 📅                       │
│                                              │
│ Proveedor: [Buscar/Seleccionar ▼]           │
│                                              │
│ Bodega Destino: [Seleccionar ▼] ⭐          │
│                                              │
│ Placa Vehículo: [ABC-123] ⭐                 │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES                        │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material     │ Cantidad │ Unidad      │  │
│ │ ──────────────────────────────────────│  │
│ │ Chatarra ▼   │ 2000     │ kg          │  │
│ │ Hierro ▼     │ 500      │ kg          │  │
│ │                                        │  │
│ │ [+ Agregar Material]                   │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Notas:                                       │
│ [________________________________]           │
│                                              │
│        [Cancelar]  [Guardar Compra]         │
│                                              │
└──────────────────────────────────────────────┘

⚠️ NOTA: No se ingresan precios en este paso
```

**Acciones al guardar:**
1. Crea registro en `purchases` con `status = 'pending_liquidation'`
2. Crea registros en `purchase_lines` con `unit_price = null`
3. Crea `inventory_movements` con:
   - `status = 'pending_liquidation'`
   - `quantity = cantidad comprada`
   - `unit_cost = null`
   - Actualiza `current_stock_transit` del material
4. Muestra mensaje: "Compra #XXXX creada. Pendiente de liquidar."

---

#### PASO 2: AUXILIAR LIQUIDA COMPRA (Nixon)

**Pantalla:** Compras Pendientes de Liquidar

**Vista lista:**
```
┌────────────────────────────────────────────────────────────────┐
│         COMPRAS PENDIENTES DE LIQUIDAR                         │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Filtros: [Proveedor ▼] [Fecha ▼] [Buscar...]                 │
│                                                                │
│ #     │ Fecha      │ Proveedor       │ Kg Total │ Acciones   │
│ ───────────────────────────────────────────────────────────── │
│ 0145  │ 31/01/2026 │ Reciclajes XYZ  │ 2,500 kg │ [Liquidar] │
│ 0146  │ 31/01/2026 │ Proveedor ABC   │ 1,000 kg │ [Liquidar] │
│ 0147  │ 30/01/2026 │ Metales SA      │   800 kg │ [Liquidar] │
│                                                                │
│                           Página 1 de 3 →                      │
└────────────────────────────────────────────────────────────────┘
```

**Al hacer click en [Liquidar]:**

```
┌──────────────────────────────────────────────┐
│      LIQUIDAR COMPRA #0145                   │
├──────────────────────────────────────────────┤
│                                              │
│ Proveedor: Reciclajes XYZ                    │
│ Fecha: 31/01/2026                            │
│ Bodega: Circunvalar                          │
│ Placa: ABC-123                               │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES A LIQUIDAR             │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material │ Cant │ Precio/kg │ Total   │  │
│ │ ─────────────────────────────────────│  │
│ │ Chatarra │ 2000 │ [1,200] ⭐│ 2,400 M │  │
│ │ Hierro   │  500 │ [  800]   │   400 K │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ TOTAL COMPRA: $2,800,000                     │
│                                              │
│        [Cancelar]  [Confirmar Liquidación]  │
│                                              │
└──────────────────────────────────────────────┘

⭐ Los precios se pre-llenan de la lista de precios
   pero se pueden editar manualmente
```

**Acciones al confirmar:**
1. Actualiza `purchases`:
   - `status = 'liquidated'`
   - `total_amount = suma(líneas)`
   - `liquidated_at = now()`
   - `liquidated_by = nixon_id`
2. Actualiza `purchase_lines` con precios
3. Actualiza `inventory_movements`:
   - `status = 'liquidated'`
   - `unit_cost = precio ingresado`
   - Mueve cantidad de `stock_transit` a `stock_liquidated`
   - Recalcula costo promedio del material
4. Actualiza saldo proveedor: `-total_amount` (le debemos)
5. Muestra mensaje: "Compra liquidada. Material agregado al inventario."

---

### 8.5 Validaciones

**Al crear (John):**
- V-COMP-01: Proveedor es obligatorio
- V-COMP-02: Al menos un material con cantidad > 0
- V-COMP-03: Bodega es obligatoria
- V-COMP-04: Fecha no puede ser futura

**Al liquidar (Nixon):**
- V-LIQ-01: Todos los precios deben ser > 0
- V-LIQ-02: No se puede liquidar una compra ya liquidada
- V-LIQ-03: No se puede liquidar una compra cancelada

### 8.6 Reglas de Negocio

**RN-COMP-01: Numeración automática**
- El `purchase_number` es autoincremental por organización
- Formato: entero secuencial (1, 2, 3, ...)
- No se reutilizan números de compras canceladas

**RN-COMP-02: Detección de duplicados**
- Al crear, el sistema verifica:
  - Mismo proveedor
  - Misma fecha
  - Monto similar (±5%)
- Si coincide, muestra advertencia (pero permite crear)

**RN-COMP-03: Cancelación**
- Solo se puede cancelar si `status != 'cancelled'`
- Al cancelar:
  - Cambia `status = 'cancelled'`
  - Si estaba liquidada, crea movimientos de reversión
  - Restaura saldo de proveedor
  - Revierte inventario

**RN-COMP-04: Inventario en tránsito** ⭐ NUEVO
- Compras pendientes afectan `stock_transit`
- No afectan `stock_liquidated` hasta liquidar
- No afectan valorización de inventario

---

## 9. MÓDULO DE VENTAS

### 9.1 Descripción General

Gestiona todas las ventas a clientes, incluyendo operaciones directas y de doble partida (pasa mano).

### 9.2 Sub-módulos

1. **Nueva Venta** - Venta normal desde inventario
2. **Doble Partida** - Compra+Venta simultánea
3. **Ventas Pendientes de Liquidar** ⭐ NUEVO
4. **Liquidar Ventas** ⭐ NUEVO
5. **Historial de Ventas**

### 9.3 Estructura de Datos

```typescript
interface Sale {
  id: string;
  organization_id: string;
  sale_number: number;               // Autoincremental
  
  // Datos básicos
  customer_id: string;               // FK a third_parties
  warehouse_id: string;              // ⭐ NUEVO: Bodega origen
  date: date;
  
  // Transporte y facturación ⭐ NUEVO
  vehicle_plate?: string;
  invoice_number?: string;           // Número de factura externa
  
  // Estado ⭐ NUEVO
  status: 'pending_liquidation' | 'liquidated' | 'collected' | 'cancelled';
  
  // Montos
  subtotal_amount: number;           // Suma de líneas
  commission_amount: number;         // Suma de comisiones
  total_amount: number;              // subtotal - commissions
  
  // Utilidad
  cost_of_goods_sold: number;        // Costo de inventario
  gross_profit: number;              // total - costo
  
  // Liquidación ⭐ NUEVO
  liquidated_at?: timestamp;
  liquidated_by?: string;
  
  // Cobro
  collected_at?: timestamp;
  collected_by?: string;
  
  // Notas
  notes?: string;
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
  
  // Relaciones
  sale_lines: SaleLine[];
  commissions: SaleCommission[];
}

interface SaleLine {
  id: string;
  sale_id: string;
  material_id: string;
  
  quantity: number;
  unit_price?: number;               // ⭐ Puede ser null si pendiente
  total_price: number;
  
  // Costo (se calcula al liquidar)
  unit_cost?: number;                // Costo promedio al momento de venta
  total_cost?: number;
  line_profit?: number;              // total_price - total_cost
  
  created_at: timestamp;
}

interface SaleCommission {
  id: string;
  sale_id: string;
  
  concept: string;                   // Descripción de la comisión
  amount: number;
  account_id?: string;               // ⭐ A qué tercero/cuenta va
  
  created_at: timestamp;
}
```

### 9.4 Flujo Venta Normal

#### PASO 1A: BÁSCULA CREA VENTA (John) - Venta de mostrador

```
┌──────────────────────────────────────────────┐
│         REGISTRAR NUEVA VENTA                │
├──────────────────────────────────────────────┤
│                                              │
│ Fecha: [DD/MM/YYYY] 📅                       │
│                                              │
│ Cliente: [Buscar/Seleccionar ▼]             │
│                                              │
│ Bodega Origen: [Seleccionar ▼] ⭐           │
│                                              │
│ Placa Vehículo: [ABC-123] ⭐                 │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES                        │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material     │ Cantidad │ Stock       │  │
│ │ ──────────────────────────────────────│  │
│ │ Cobre ▼      │ 1500     │ 3,200 kg ✅ │  │
│ │ Hierro ▼     │  500     │ 2,800 kg ✅ │  │
│ │                                        │  │
│ │ [+ Agregar Material]                   │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Notas:                                       │
│ [________________________________]           │
│                                              │
│        [Cancelar]  [Guardar Venta]          │
│                                              │
└──────────────────────────────────────────────┘

⚠️ El sistema muestra stock disponible
⚠️ PERMITE vender sin stock (muestra advertencia)
⚠️ No se ingresan precios en este paso
```

#### PASO 1B: INGRID CREA VENTA CON PRECIOS - Despacho

```
┌──────────────────────────────────────────────┐
│      REGISTRAR VENTA Y DESPACHO              │
├──────────────────────────────────────────────┤
│                                              │
│ Cliente: [Seleccionar ▼]                     │
│ Fecha: [DD/MM/YYYY]                          │
│ Bodega: [Circunvalar ▼]                      │
│ Placa: [XYZ-789]                             │
│ Nº Factura: [F-00456] ⭐                     │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES                        │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material │ Cant │ Precio/kg │ Total   │  │
│ │ ─────────────────────────────────────│  │
│ │ Hierro ▼ │ 3000 │ [1,800] ⭐│ 5,400 K │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │   COMISIONES Y DESCUENTOS              │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Concepto          │ Monto │ Va a      │  │
│ │ ──────────────────────────────────────│  │
│ │ Comisión fac.     │ 67,500│ Cta Com ▼│  │
│ │ Intermediario     │ 50,000│ Juan P. ▼│  │
│ │                                        │  │
│ │ [+ Agregar]                            │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Subtotal: $5,400,000                         │
│ - Comisiones: $117,500                       │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ TOTAL: $5,282,500                            │
│                                              │
│        [Cancelar]  [Guardar y Despachar]    │
│                                              │
└──────────────────────────────────────────────┘

✅ Ingrid SÍ pone precios
✅ Se crea con status = 'liquidated'
✅ Se puede imprimir remisión inmediatamente
```

#### PASO 2: LIQUIDACIÓN (Nixon o Ingrid)

Para ventas creadas por John (sin precios):

```
┌──────────────────────────────────────────────┐
│      LIQUIDAR VENTA #0289                    │
├──────────────────────────────────────────────┤
│                                              │
│ Cliente: ABC S.A.S.                          │
│ Fecha: 31/01/2026                            │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES                        │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material │ Cant │ Precio/kg │ Total   │  │
│ │ ─────────────────────────────────────│  │
│ │ Cobre    │ 1500 │ [10,000]⭐│ 15,000 K│  │
│ │ Hierro   │  500 │ [ 1,800]  │    900 K│  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │   COMISIONES (Opcional)                │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ [+ Agregar Comisión]                   │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Subtotal: $15,900,000                        │
│ - Comisiones: $0                             │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ TOTAL: $15,900,000                           │
│                                              │
│ 💰 Ganancia Bruta: $3,150,000 (20.1%)       │
│                                              │
│        [Cancelar]  [Confirmar Liquidación]  │
│                                              │
└──────────────────────────────────────────────┘

⭐ Sistema pre-llena precios de lista
💰 Calcula ganancia bruta automáticamente
```

**Cálculo de ganancia bruta:**
```typescript
// Para cada línea:
const avgCost = getMovingAverageCost(material_id, sale_date);
const lineCost = quantity * avgCost;
const lineRevenue = quantity * unit_price;
const lineProfit = lineRevenue - lineCost;

// Total:
const grossProfit = sum(lineProfit for all lines);
const grossMargin = (grossProfit / total_amount) * 100;
```

**Acciones al liquidar:**
1. Actualiza `sales`:
   - `status = 'liquidated'`
   - Calcula totales y ganancia
2. Actualiza `sale_lines` con precios y costos
3. Crea `inventory_movements` (salida):
   - `quantity` negativo
   - `unit_cost = costo promedio actual`
4. Actualiza saldo cliente: `+total_amount` (nos debe)
5. Si hay comisiones, actualiza saldos de cuentas/terceros

---

### 9.5 Doble Partida (Pasa Mano)

**Concepto:**
Operación donde el material va directo del proveedor al cliente sin pasar por bodega.

**Cuándo se usa:**
- Material no entra físicamente a nuestras bodegas
- Se conocen precio de compra y precio de venta
- Ejemplo: Proveedor despacha directo a cliente a nombre nuestro

**Pantalla:**

```
┌──────────────────────────────────────────────┐
│         REGISTRAR DOBLE PARTIDA              │
├──────────────────────────────────────────────┤
│                                              │
│ Fecha: [DD/MM/YYYY] 📅                       │
│                                              │
│ COMPRA:                                      │
│ Proveedor: [Seleccionar ▼]                   │
│                                              │
│ VENTA:                                       │
│ Cliente: [Seleccionar ▼]                     │
│                                              │
│ Placa: [ABC-123]                             │
│ Nº Factura: [F-00789]                        │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │      MATERIALES                        │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material│Cant│P.Compra│P.Venta│Ganancia│ │
│ │ ──────────────────────────────────────│  │
│ │ Alum. ▼ │2000│ 5,000 │ 6,500│3,000,000│ │
│ │         │    │        │      │         │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │   COMISIONES                           │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Intermediario │ 50,000 │ Carlos M. ▼  │  │
│ │                                        │  │
│ │ [+ Agregar]                            │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Total Compra: $10,000,000                    │
│ Total Venta:  $13,000,000                    │
│ - Comisiones: $50,000                        │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│ 💰 GANANCIA NETA: $2,950,000                │
│                                              │
│        [Cancelar]  [Registrar Operación]    │
│                                              │
└──────────────────────────────────────────────┘
```

**Acciones al guardar:**

1. **Crea COMPRA:**
   - Proveedor seleccionado
   - Status = 'liquidated' (ya tiene precio)
   - Fecha = fecha ingresada
   - Crea purchase_lines

2. **Crea VENTA:**
   - Cliente seleccionado
   - Status = 'liquidated'
   - Fecha = misma (1 segundo después para orden)
   - Crea sale_lines
   - Crea commissions si hay

3. **Movimientos de inventario:**
   - Entrada por compra (+)
   - Salida por venta (-) inmediatamente
   - El costo de venta = precio de esa compra específica
   - Actualiza costo promedio

4. **Saldos:**
   - Proveedor: -monto_compra
   - Cliente: +monto_venta
   - Comisiones: según configurado

5. **Vinculación:**
   - Se marcan internamente como operación doble partida
   - Link entre compra y venta para trazabilidad

---

### 9.6 Validaciones

**V-VENTA-01:** Cliente es obligatorio
**V-VENTA-02:** Al menos un material con cantidad > 0
**V-VENTA-03:** Bodega es obligatoria
**V-VENTA-04:** Al liquidar, precios deben ser > 0
**V-VENTA-05:** Stock disponible se verifica pero NO se bloquea (se permite vender sin stock)
**V-VENTA-06:** En doble partida, precio venta debe ser ≥ precio compra

---

### 9.7 Reglas de Negocio

**RN-VENTA-01: Verificación de stock**
- El sistema muestra stock disponible
- Si `cantidad > stock`, muestra advertencia
- PERMITE la venta (común vender antes de comprar)
- Genera inventario negativo

**RN-VENTA-02: Costo de venta**
- Usa el costo promedio móvil AL MOMENTO de la venta
- Se calcula automáticamente
- No se puede editar manualmente

**RN-VENTA-03: Comisiones variables** ⭐
- NO hay porcentaje fijo
- Cada venta puede tener 0, 1 o múltiples comisiones
- Cada comisión especifica monto y destino
- Si comisión = $0, simplemente no se agrega

**RN-VENTA-04: Doble partida**
- Genera exactamente 1 compra + 1 venta
- Compra y venta quedan vinculadas
- Ganancia = Precio Venta - Precio Compra - Comisiones
- El material entra y sale del inventario inmediatamente

---

## 10. MÓDULO DE INVENTARIO

### 10.1 Descripción General

Controla el stock de materiales con valorización automática por costo promedio ponderado móvil.

### 10.2 Sub-módulos

1. **Stock Actual** - Vista consolidada de inventario
2. **Stock por Bodega** ⭐ NUEVO
3. **Inventario en Tránsito** ⭐ NUEVO
4. **Movimientos** - Historial completo
5. **Ajustes** - Correcciones manuales
6. **Traslados entre Materiales** ⭐ NUEVO (Transformación)
7. **Traslados entre Bodegas** ⭐ NUEVO
8. **Valorización** - Valor del inventario

### 10.3 Stock Actual

**Vista consolidada:**

```
┌────────────────────────────────────────────────────────────────┐
│         INVENTARIO - STOCK ACTUAL                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Filtros: [Bodega: Todas ▼] [Categoría ▼] [Buscar...]         │
│                                                                │
│ 📦 Total Inventario Liquidado: $150,000,000                   │
│ ⏳ Total en Tránsito: 2,500 kg (Pend. liquidar) ⭐            │
│ 💰 Valor Total Real: $150,000,000                             │
│                                                                │
│ Código │Material    │Liquidado│Tránsito│TOTAL │Costo│Valor   │
│ ─────────────────────────────────────────────────────────────│
│ CU-01  │Cobre Limpio│ 1,500 kg│  500 kg│2,000 │8,500│12,750 K│
│ HI-01  │Hierro      │ 2,800 kg│    0 kg│2,800 │1,200│ 3,360 K│
│ AL-01  │Aluminio    │ 1,200 kg│  800 kg│2,000 │4,500│ 5,400 K│
│ PAP-01 │Papel Blanco│ 5,000 kg│1,200 kg│6,200 │  600│ 3,000 K│
│                                                                │
│                                   Página 1 de 5 →              │
└────────────────────────────────────────────────────────────────┘

⭐ NUEVO: Separación de stock liquidado vs tránsito
```

**Al hacer click en un material:**

```
┌──────────────────────────────────────────────┐
│      DETALLE: COBRE LIMPIO (CU-01)           │
├──────────────────────────────────────────────┤
│                                              │
│ INVENTARIO GENERAL:                          │
│ • Liquidado:     1,500 kg  $12,750,000       │
│ • En Tránsito:     500 kg  (pendiente) ⭐    │
│ • TOTAL REAL:    2,000 kg  $12,750,000       │
│                                              │
│ Costo Promedio: $8,500/kg                    │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  DESGLOSE POR BODEGA ⭐                │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Bodega      │ Liquidado │ Tránsito    │  │
│ │ ──────────────────────────────────────│  │
│ │ Circunvalar │ 1,200 kg  │  300 kg     │  │
│ │ San Alberto │   300 kg  │  200 kg     │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ⚠️  500 kg pendientes de liquidar           │
│                                              │
│        [Ver Movimientos] [Ajustar Stock]    │
│                                              │
└──────────────────────────────────────────────┘
```

---

### 10.4 Inventario en Tránsito ⭐ NUEVO

**Vista específica:**

```
┌────────────────────────────────────────────────────────────────┐
│         INVENTARIO EN TRÁNSITO                                 │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Compras/Ventas creadas pero NO liquidadas                     │
│                                                                │
│ COMPRAS PENDIENTES:                                            │
│                                                                │
│ # Compra│Fecha      │Proveedor    │Material     │Cantidad     │
│ ─────────────────────────────────────────────────────────────│
│ 0145    │31/01/2026 │Reciclajes   │Chatarra     │ 2,000 kg   │
│ 0146    │31/01/2026 │Metales ABC  │Cobre        │   500 kg   │
│                                                                │
│ TOTAL COMPRAS EN TRÁNSITO: 2,500 kg                           │
│                                                                │
│ VENTAS PENDIENTES:                                             │
│                                                                │
│ # Venta │Fecha      │Cliente      │Material     │Cantidad     │
│ ─────────────────────────────────────────────────────────────│
│ 0289    │30/01/2026 │Industrial X │Hierro       │ 1,500 kg   │
│                                                                │
│ ⚠️ ALERTAS:                                                   │
│ • Chatarra: >30% en tránsito (cuello de botella)              │
│ • Cobre: Normal                                                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Alertas automáticas:**
- Si `stock_transit > stock_liquidated * 0.3` → Alerta de cuello de botella
- Indica que hay mucho material sin liquidar (dinero represado)

---

### 10.5 Transformación de Materiales ⭐ NUEVO

**Concepto:**
Desintegración de elementos compuestos en materiales individuales.

**Caso de uso:**
```
ENTRADA:
Motor Eléctrico: 500 kg a $1,000/kg

DESINTEGRACIÓN:
→ Cobre:    200 kg
→ Hierro:   180 kg
→ Aluminio: 100 kg
→ Merma:     20 kg (desperdicio)
```

**Pantalla:**

```
┌──────────────────────────────────────────────┐
│      TRASLADO ENTRE MATERIALES               │
│      (Transformación/Desintegración)         │
├──────────────────────────────────────────────┤
│                                              │
│ Fecha: [DD/MM/YYYY] 📅                       │
│                                              │
│ ORIGEN:                                      │
│ Material: [Material Compuesto ▼]             │
│ Cantidad a trasladar: [500] kg               │
│ Stock actual: 800 kg                         │
│ Costo unitario: $1,000/kg                    │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  DESTINOS                              │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material │ Cant │ Costo/kg │ Total    │  │
│ │ ──────────────────────────────────────│  │
│ │ Cobre ▼  │  200 │ [1,000]⭐│ 200,000  │  │
│ │ Hierro ▼ │  180 │ [1,000]  │ 180,000  │  │
│ │ Aluminio▼│  100 │ [1,000]  │ 100,000  │  │
│ │                                        │  │
│ │ [+ Agregar Destino]                    │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Merma/Desperdicio: [20] kg ($20,000)         │
│                                              │
│ ✅ Balance: 200+180+100+20 = 500 kg ✓       │
│                                              │
│ Razón del traslado:                          │
│ [Desintegración de motores eléctricos]       │
│                                              │
│        [Cancelar]  [Confirmar Traslado]     │
│                                              │
└──────────────────────────────────────────────┘

⭐ Costos se pre-llenan con costo promedio del origen
   pero se pueden editar manualmente
```

**Validaciones:**
- V-TRANS-01: Cantidad total destinos + merma = cantidad origen
- V-TRANS-02: Stock origen suficiente
- V-TRANS-03: Al menos un destino
- V-TRANS-04: Razón es obligatoria

**Acciones al confirmar:**
1. Crea movimiento salida de material origen
2. Crea movimientos entrada para cada destino
3. Registra merma como ajuste negativo
4. Recalcula costos promedio de materiales destino
5. Registra en auditoría

---

### 10.6 Movimientos de Inventario

**Vista:**

```
┌────────────────────────────────────────────────────────────────┐
│         MOVIMIENTOS DE INVENTARIO                              │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Filtros: [Material ▼] [Tipo ▼] [Fecha] [Buscar...]           │
│                                                                │
│ Fecha     │Material│Tipo    │Cant │Costo/u│Balance│Prom│Ref  │
│ ─────────────────────────────────────────────────────────────│
│ 31/01 10:30│Cobre  │Compra  │+500 │ 8,000 │2,000  │8,500│C145│
│ 31/01 14:15│Cobre  │Venta   │-300 │ 8,500 │1,700  │8,500│V289│
│ 30/01 16:45│Cobre  │Ajuste  │+100 │ 8,200 │2,000  │8,420│ADJ │
│ 30/01 09:20│Cobre  │Traslado│+200 │ 1,000 │1,900  │7,100│T034│
│                                                                │
│ Estado: [Todas ▼] [Solo Liquidadas ▼] [Solo Pendientes ▼]    │
│                                                                │
│                                   Página 1 de 25 →             │
└────────────────────────────────────────────────────────────────┘
```

**Tipos de movimiento:**
- `purchase`: Compra (entrada, +)
- `sale`: Venta (salida, -)
- `adjustment`: Ajuste manual (+/-)
- `transfer`: Traslado entre materiales
- `warehouse_transfer`: Traslado entre bodegas
- `purchase_reversal`: Reversión de compra cancelada
- `sale_reversal`: Reversión de venta cancelada

**Campos importantes:**
- **Balance:** Stock acumulado después del movimiento
- **Prom:** Costo promedio después del movimiento
- **Ref:** Referencia al documento origen (compra, venta, etc.)

---

### 10.7 Cálculo de Costo Promedio Móvil

Esta es la **lógica más crítica** del sistema.

**Algoritmo:**

```typescript
function calculateMovingAverageCost(movements: Movement[]): CostCalculation {
  // 1. Ordenar cronológicamente
  const sorted = movements.sort((a, b) => {
    const dateCompare = compareDate(a.date, b.date);
    if (dateCompare !== 0) return dateCompare;
    return compareTimestamp(a.created_at, b.created_at);
  });
  
  // 2. Identificar movimientos cancelados
  const reversalMap = buildReversalMap(sorted);
  
  // 3. Procesar cada movimiento
  let currentStock = 0;
  let currentAvgCost = 0;
  let totalValue = 0;
  
  for (const mov of sorted) {
    // Ignorar cancelados y reversiones
    if (isCancelled(mov, reversalMap)) continue;
    if (isReversal(mov)) continue;
    // Solo procesar liquidados
    if (mov.status !== 'liquidated') continue;
    
    const qty = Number(mov.quantity);
    const cost = Number(mov.unit_cost) || 0;
    
    if (isIncoming(mov)) {
      // ENTRADA: Recalcula promedio
      const prevStock = currentStock;
      const prevValue = totalValue;
      
      currentStock += qty;
      totalValue = prevValue + (qty * cost);
      
      if (currentStock > 0) {
        currentAvgCost = totalValue / currentStock;
      }
      
    } else if (isOutgoing(mov)) {
      // SALIDA: Usa costo promedio actual, NO lo cambia
      const exitQty = Math.abs(qty);
      
      totalValue -= exitQty * currentAvgCost;
      currentStock -= exitQty;
      
      if (currentStock <= 0) {
        totalValue = 0;
        // Mantener último costo conocido
      }
    }
  }
  
  return {
    averageCost: currentAvgCost,
    totalQuantity: currentStock,
    totalValue: totalValue
  };
}
```

**Reglas:**

**R-COSTO-01:** Las ENTRADAS recalculan el promedio
```
Tengo: 100 kg a $5,000/kg = $500,000
Compro: 50 kg a $6,000/kg = $300,000
Nuevo promedio: ($500,000 + $300,000) / 150 kg = $5,333.33/kg
```

**R-COSTO-02:** Las SALIDAS usan el promedio actual pero NO lo cambian
```
Tengo: 150 kg a $5,333.33/kg
Vendo: 50 kg
Costo de venta: 50 × $5,333.33 = $266,666.67
Quedan: 100 kg a $5,333.33/kg (costo NO cambia)
```

**R-COSTO-03:** Si stock llega a 0, se mantiene el último costo conocido
```
Tengo: 10 kg a $8,000/kg
Vendo: 10 kg
Stock: 0 kg
Costo promedio: $8,000/kg (se mantiene para próxima compra)
```

**R-COSTO-04:** Movimientos pendientes NO afectan el costo
- Solo movimientos con `status = 'liquidated'` se procesan
- Esto mantiene la valorización correcta

---

### 10.8 Ajustes de Inventario

**Tipos de ajuste:**

1. **Increase (Aumentar):**
   - Agrega stock
   - Requiere: cantidad y costo unitario
   - Recalcula promedio

2. **Decrease (Reducir):**
   - Quita stock
   - Usa costo promedio actual

3. **Recount (Conteo Físico):**
   - Ajusta a cantidad exacta
   - Diferencia usa costo promedio

4. **Transfer (Traslado):**
   - Ver sección 10.5

5. **Zero Out (Llevar a cero):**
   - Elimina todo el stock
   - Requiere razón

**Pantalla:**

```
┌──────────────────────────────────────────────┐
│      AJUSTAR INVENTARIO                      │
├──────────────────────────────────────────────┤
│                                              │
│ Material: [Cobre Limpio ▼]                   │
│ Stock actual: 1,500 kg                       │
│ Costo promedio: $8,500/kg                    │
│                                              │
│ Tipo de ajuste:                              │
│ ( ) Aumentar stock                           │
│ ( ) Reducir stock                            │
│ (•) Conteo físico                            │
│ ( ) Llevar a cero                            │
│                                              │
│ Cantidad contada: [1,480] kg                 │
│ Diferencia: -20 kg                           │
│ Valor ajuste: -$170,000                      │
│                                              │
│ Razón del ajuste:                            │
│ [Conteo físico mensual - merma]              │
│                                              │
│        [Cancelar]  [Confirmar Ajuste]       │
│                                              │
└──────────────────────────────────────────────┘
```

**Todas las acciones quedan registradas en auditoría.**

---

---

## 11. MÓDULO DE TESORERÍA

### 11.1 Descripción General

Control completo del flujo de efectivo: cuentas bancarias, cajas, movimientos de dinero, gastos, provisiones y conciliación.

### 11.2 Sub-módulos

1. **Dashboard Financiero** - Resumen ejecutivo
2. **Movimientos de Dinero** - Registro de transacciones
3. **Gastos** - Gestión y categorización
4. **Gastos Diferidos** ⭐ NUEVO - Programación de gastos en el tiempo
5. **Provisiones** ⭐ NUEVO - Fondos reservados
6. **Cuentas de Dinero** - Gestión de bancos y cajas
7. **Estados de Cuenta** - Por tercero
8. **Importación Bancaria** ⭐ NUEVO - Carga masiva desde Excel
9. **Auditoría de Saldos** - Verificación de coherencia

### 11.3 Dashboard Financiero

**Vista principal:**

```
┌─────────────────────────────────────────────────────────────────┐
│              DASHBOARD DE TESORERÍA                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  💰 RECURSOS DISPONIBLES                                        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Efectivo (Cajas)                                               │
│  • Caja General:           $5,000,000                           │
│  • Caja Menor:             $2,000,000                           │
│  Subtotal Efectivo:        $7,000,000                           │
│                                                                 │
│  Bancos                                                         │
│  • Bancolombia:           $50,000,000                           │
│  • Davivienda:            $30,000,000                           │
│  • Banco de Bogotá:       $20,000,000                           │
│  Subtotal Bancos:        $100,000,000                           │
│                                                                 │
│  TOTAL DISPONIBLE:       $107,000,000 ✅                        │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  📊 CUENTAS POR COBRAR/PAGAR                                    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Por Cobrar (nos deben):      +$85,000,000                      │
│  Por Pagar (debemos):         -$45,000,000                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                      │
│  Balance Neto:                +$40,000,000                      │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  🏦 PROVISIONES ⭐                                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  • Mantenimiento:         -$40,000,000 (fondos)                 │
│  • Dotación:               -$3,000,000 (fondos)                 │
│  • Mejora Locativa:        +$5,000,000 (sobregiro)              │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  📈 ESTE MES (Del 04/01 al 03/02)                               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Ingresos:               $250,000,000                           │
│  Egresos:               -$180,000,000                           │
│  Utilidad Neta:          $70,000,000                            │
│  Margen:                 28.0%                                  │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  📋 ÚLTIMOS MOVIMIENTOS                                         │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  31/01 14:30  Cobro Cliente ABC        +$15,000,000  Bancol.   │
│  31/01 10:15  Pago Proveedor XYZ       -$8,000,000   Daviv.    │
│  31/01 09:00  Gasto Combustible          -$500,000   Caja Gral │
│  30/01 16:45  Transferencia             +$2,000,000  Caja Men. │
│                                                                 │
│  [Ver Todos los Movimientos →]                                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.4 Movimientos de Dinero

**Estructura de datos:**

```typescript
interface MoneyMovement {
  id: string;
  organization_id: string;
  
  // Identificación
  reference_number?: string;     // Número de referencia (cheque, transferencia)
  date: date;
  
  // Cuenta afectada
  account_id: string;            // FK a money_accounts
  
  // Tipo de movimiento
  movement_type: MovementType;   // Ver lista abajo
  
  // Monto
  amount: number;                // Siempre positivo
  
  // Relaciones
  third_party_id?: string;       // FK a third_parties (si aplica)
  expense_category_id?: string;  // FK a expense_categories (si es gasto)
  purchase_id?: string;          // FK a purchases (si es pago a proveedor)
  sale_id?: string;              // FK a sales (si es cobro a cliente)
  transfer_account_id?: string;  // Cuenta destino (si es transferencia)
  
  // Detalles
  description: string;
  notes?: string;
  
  // Evidencia ⭐ NUEVO
  evidence_url?: string;         // URL del comprobante adjunto
  
  // Estado
  status: 'draft' | 'confirmed' | 'annulled';
  annulled_reason?: string;
  annulled_at?: timestamp;
  annulled_by?: string;
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
}

type MovementType =
  | 'payment_to_supplier'      // Pago a proveedor
  | 'collection_from_client'   // Cobro a cliente
  | 'expense'                  // Gasto operativo
  | 'service_income'           // Ingreso por servicio
  | 'transfer_out'             // Transferencia salida
  | 'transfer_in'              // Transferencia entrada
  | 'capital_injection'        // Inyección de capital (socio)
  | 'capital_return'           // Retiro de capital
  | 'advance_payment'          // Anticipo dado
  | 'advance_collection'       // Anticipo recibido
  | 'asset_payment'            // Pago de activo fijo
  | 'provision_deposit'        // ⭐ NUEVO: Aporte a provisión
  | 'provision_expense';       // ⭐ NUEVO: Gasto desde provisión
```

**Pantalla de registro:**

```
┌──────────────────────────────────────────────┐
│      REGISTRAR MOVIMIENTO DE DINERO          │
├──────────────────────────────────────────────┤
│                                              │
│ Fecha: [31/01/2026] 📅                       │
│                                              │
│ Tipo de Movimiento:                          │
│ [Seleccionar tipo ▼]                         │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  OPCIONES (según tipo seleccionado)   │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │  Si es PAGO A PROVEEDOR:               │  │
│ │  • Proveedor: [Seleccionar ▼]          │  │
│ │  • Compra vinculada: [#0145 ▼]         │  │
│ │  • Cuenta: [Banco Bancolombia ▼]       │  │
│ │  • Monto: [8,000,000]                  │  │
│ │                                        │  │
│ │  Si es GASTO:                          │  │
│ │  • Categoría: [Seleccionar ▼]          │  │
│ │  • Cuenta: [Caja General ▼]            │  │
│ │  • Monto: [500,000]                    │  │
│ │                                        │  │
│ │  Si es TRANSFERENCIA:                  │  │
│ │  • De: [Banco Davivienda ▼]            │  │
│ │  • A: [Caja Menor ▼]                   │  │
│ │  • Monto: [2,000,000]                  │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ Nº Referencia: [Opcional - Cheque/Transfer] │
│                                              │
│ Descripción:                                 │
│ [____________________________________]       │
│                                              │
│ Adjuntar Comprobante: ⭐                     │
│ [📎 Seleccionar archivo...]                  │
│                                              │
│        [Cancelar]  [Guardar Movimiento]     │
│                                              │
└──────────────────────────────────────────────┘
```

**Efectos según tipo:**

| Tipo | Cuenta | Tercero | Descripción |
|------|--------|---------|-------------|
| payment_to_supplier | - | + | Pagamos a proveedor, su saldo sube |
| collection_from_client | + | - | Cliente paga, su saldo baja |
| expense | - | - | Gasto sale de cuenta |
| service_income | + | - | Ingreso entra a cuenta |
| transfer_out | - | - | Sale de cuenta origen |
| transfer_in | + | - | Entra a cuenta destino |
| capital_injection | + | - (inv) | Socio aporta, le debemos |
| capital_return | - | + (inv) | Socio retira, le debemos menos |
| provision_deposit ⭐ | - | - (prov) | Fondos a provisión |
| provision_expense ⭐ | cuenta normal | + (prov) | Gasto desde provisión |

### 11.5 Provisiones ⭐ NUEVO

**Concepto:**
Fondos reservados para gastos futuros específicos.

**Implementación técnica:**
- Son terceros especiales con `is_provision = true`
- Tienen estado de cuenta como cualquier tercero
- Saldo negativo = fondos disponibles
- Saldo positivo = sobregiro (gastado de más)

**Pantalla de gestión:**

```
┌─────────────────────────────────────────────────────────────────┐
│              GESTIÓN DE PROVISIONES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [+ Nueva Provisión]                                            │
│                                                                 │
│  Provisión              │ Tipo          │ Saldo     │ Estado   │
│  ───────────────────────────────────────────────────────────── │
│  Mantenimiento Maquinar │ Mantenimiento │ -40,000 K │ ✅ Fondos│
│  Dotación 2026          │ Dotación      │  -3,000 K │ ✅ Fondos│
│  Mejora Locativa Bodega │ Mejoras       │  +5,000 K │ ⚠️ Sobre │
│                                                                 │
│  [Ver Movimientos] [Aportar] [Gastar]                          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Flujo de trabajo:**

**1. Crear provisión:**
```typescript
// Se crea como tercero especial
{
  name: "Provisión Mantenimiento Maquinaria",
  is_provision: true,
  provision_type: "mantenimiento",
  current_balance: 0
}
```

**2. Aportar a provisión:**
```typescript
// Movimiento tipo provision_deposit
{
  movement_type: "provision_deposit",
  account_id: "caja_general_id",  // De dónde sale
  third_party_id: "provision_id",  // A qué provisión va
  amount: 20000000,
  description: "Aporte mensual mantenimiento"
}

// Efectos:
// - Caja General: -20,000,000
// - Saldo provisión: -20,000,000 (tenemos fondos)
```

**3. Gastar desde provisión:**
```typescript
// Movimiento tipo provision_expense
{
  movement_type: "provision_expense",
  account_id: null,  // ⭐ No sale de cuenta de dinero
  third_party_id: "provision_id",
  expense_category_id: "mantenimiento_id",
  amount: 5000000,
  description: "Mantenimiento bomba hidráulica"
}

// Efectos:
// - Saldo provisión: -15,000,000 (usamos fondos)
// - Se registra como gasto del mes
// - NO afecta cuentas de dinero (ya se había apartado)
```

**Vista de estado de cuenta:**

```
┌──────────────────────────────────────────────┐
│  ESTADO DE CUENTA: PROVISIÓN MANTENIMIENTO   │
├──────────────────────────────────────────────┤
│                                              │
│  Fecha     │ Concepto           │ Saldo     │
│  ──────────────────────────────────────────  │
│  01/12/2025│ Saldo inicial      │        0  │
│  05/12/2025│ Aporte mensual     │ -20,000 K │
│  15/12/2025│ Mant. bomba        │ -15,000 K │
│  05/01/2026│ Aporte mensual     │ -35,000 K │
│  20/01/2026│ Mant. eléctrico    │ -30,000 K │
│  05/02/2026│ Aporte mensual     │ -50,000 K │
│                                              │
│  Saldo actual: -$50,000,000 (fondos)         │
│                                              │
└──────────────────────────────────────────────┘
```

### 11.6 Gastos Diferidos ⭐ NUEVO

**Concepto:**
Gastos grandes que se distribuyen en varios meses.

**Estructura de datos:**

```typescript
interface DeferredExpense {
  id: string;
  organization_id: string;
  
  // Información básica
  name: string;                  // "Dotación Diciembre 2025"
  total_amount: number;          // Monto total ($3,000,000)
  
  // Programación
  start_date: date;              // Primer mes a aplicar
  months_to_defer: number;       // Meses a distribuir (4)
  monthly_amount: number;        // Calculado: total / meses
  
  // Seguimiento
  applied_months: number;        // Cuántos meses ya aplicados (0)
  
  // Opciones
  expense_category_id: string;   // Categoría del gasto
  provision_id?: string;         // Si sale de provisión
  
  // Estado
  status: 'active' | 'completed' | 'cancelled';
  
  // Historial de aplicaciones
  applications: DeferredApplication[];
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
}

interface DeferredApplication {
  month: string;                 // "2026-01"
  amount: number;
  expense_id: string;            // FK al gasto creado
  applied_at: timestamp;
  applied_by: string;
}
```

**Pantalla de creación:**

```
┌──────────────────────────────────────────────┐
│      CREAR GASTO DIFERIDO                    │
├──────────────────────────────────────────────┤
│                                              │
│ Nombre:                                      │
│ [Dotación Diciembre 2025______________]      │
│                                              │
│ Monto Total: [$3,000,000]                    │
│                                              │
│ Categoría de Gasto:                          │
│ [Capital Humano - Dotación ▼]                │
│                                              │
│ Distribuir en: [4] meses                     │
│                                              │
│ Primer mes: [Diciembre 2025]                 │
│                                              │
│ 💡 Se aplicará:                              │
│    • Diciembre 2025: $750,000                │
│    • Enero 2026:     $750,000                │
│    • Febrero 2026:   $750,000                │
│    • Marzo 2026:     $750,000                │
│                                              │
│ ¿Sale de provisión?                          │
│ [☐] Sí, de: [Seleccionar provisión ▼]       │
│ [☑] No, es gasto directo                     │
│                                              │
│        [Cancelar]  [Crear Gasto Diferido]   │
│                                              │
└──────────────────────────────────────────────┘
```

**Dashboard de gastos diferidos:**

```
┌─────────────────────────────────────────────────────────────────┐
│              GASTOS DIFERIDOS                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ⏰ PENDIENTES DE APLICAR ESTE MES                              │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Dotación Diciembre 2025                                   │ │
│  │ Mes 2/4 • Aplicar: $750,000                               │ │
│  │                                                           │ │
│  │ [Aplicar Ahora] [Posponer]                                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Mejora Locativa Bodega                                    │ │
│  │ Mes 1/6 • Aplicar: $500,000                               │ │
│  │                                                           │ │
│  │ [Aplicar Ahora] [Posponer]                                │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  📋 ACTIVOS                                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Nombre               │ Total    │ Aplicado │ Pend. │ Próximo  │
│  ────────────────────────────────────────────────────────────  │
│  Dotación Dic 2025    │ 3,000 K  │ 1,500 K  │1,500K │ Feb 2026 │
│  Mejora Locativa      │ 3,000 K  │   500 K  │2,500K │ Feb 2026 │
│                                                                 │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  ✅ COMPLETADOS                                                │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Dotación Nov 2025    │ 4,000 K  │ Completado: Dic 2025         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Al hacer click en [Aplicar Ahora]:**

```typescript
async function applyDeferredExpense(deferredId: string) {
  const deferred = await getDeferredExpense(deferredId);
  
  // 1. Crear gasto automático
  const expense = await createExpense({
    category_id: deferred.expense_category_id,
    amount: deferred.monthly_amount,
    date: today(),
    description: `${deferred.name} - Mes ${deferred.applied_months + 1}/${deferred.months_to_defer}`,
    
    // Si sale de provisión
    from_provision_id: deferred.provision_id,
    
    // Marcar como automático
    is_from_deferred: true,
    deferred_expense_id: deferred.id
  });
  
  // 2. Registrar aplicación
  await updateDeferredExpense(deferredId, {
    applied_months: deferred.applied_months + 1,
    applications: [...deferred.applications, {
      month: getCurrentMonth(),
      amount: deferred.monthly_amount,
      expense_id: expense.id,
      applied_at: now(),
      applied_by: getCurrentUserId()
    }]
  });
  
  // 3. Si completó todos los meses
  if (deferred.applied_months + 1 === deferred.months_to_defer) {
    await updateDeferredExpense(deferredId, {
      status: 'completed'
    });
  }
  
  return expense;
}
```

### 11.7 Importación Bancaria ⭐ NUEVO

**Concepto:**
Importar movimientos desde archivo Excel del banco.

**Flujo:**

```
┌──────────────────────────────────────────────┐
│      IMPORTAR MOVIMIENTOS BANCARIOS          │
├──────────────────────────────────────────────┤
│                                              │
│ Paso 1: Seleccionar archivo                 │
│                                              │
│ Cuenta bancaria:                             │
│ [Banco Bancolombia ▼]                        │
│                                              │
│ Archivo Excel del banco:                     │
│ [📎 Seleccionar archivo...]                  │
│                                              │
│ Formato detectado: ✅ Banco de Bogotá        │
│                                              │
│        [Cancelar]  [Siguiente →]             │
│                                              │
└──────────────────────────────────────────────┘
```

**Paso 2: Preview y mapeo**

```
┌──────────────────────────────────────────────────────────────────┐
│      PREVIEW DE MOVIMIENTOS A IMPORTAR                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Se encontraron 45 movimientos                                   │
│                                                                  │
│  Fecha    │ Descripción        │ Valor      │ Asignar a         │
│  ──────────────────────────────────────────────────────────────  │
│  31/01    │ Transferencia #123 │ +5,000,000 │ [Cliente ▼] [Cat▼]│
│  31/01    │ Pago proveedor     │ -2,000,000 │ [Proveedor ▼]     │
│  30/01    │ Retiro cajero      │   -500,000 │ [Categoría ▼]     │
│  ...                                                             │
│                                                                  │
│  Opciones de importación:                                        │
│  [☑] Crear movimientos nuevos                                   │
│  [☐] Actualizar existentes                                      │
│  [☑] Solicitar confirmación antes de importar                   │
│                                                                  │
│        [← Atrás]  [Confirmar Importación]                       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 12. MÓDULO DE TRÁNSITOS

### 12.1 Descripción General

Control de material en camino que aún no ha llegado ni se han definido precios finales.

### 12.2 Estructura de Datos

```typescript
interface Transit {
  id: string;
  organization_id: string;
  
  // Identificación
  remission_number: string;      // Número de remisión
  
  // Partes involucradas
  supplier_id: string;           // De quién se compra
  customer_id: string;           // A quién se vende
  
  // Material
  material_id: string;
  estimated_quantity?: number;   // Cantidad estimada (opcional)
  
  // Fechas
  transit_date: date;            // Fecha de despacho
  
  // Estado
  status: 'pending' | 'closed';
  
  // Al cerrar (convertir a doble partida)
  actual_quantity?: number;      // Cantidad real al llegar
  purchase_price?: number;       // Precio de compra final
  sale_price?: number;           // Precio de venta final
  purchase_id?: string;          // FK a purchases creada
  sale_id?: string;              // FK a sales creada
  closed_date?: date;
  closed_by?: string;
  
  // Notas
  notes?: string;
  
  // Placa ⭐
  vehicle_plate?: string;
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
}
```

### 12.3 Pantalla de Creación

```
┌──────────────────────────────────────────────┐
│      CREAR TRÁNSITO                          │
├──────────────────────────────────────────────┤
│                                              │
│ Nº Remisión: [R-00345_____]                  │
│                                              │
│ Fecha de Despacho: [31/01/2026] 📅           │
│                                              │
│ COMPRA (De):                                 │
│ Proveedor: [Seleccionar ▼]                   │
│                                              │
│ VENTA (Para):                                │
│ Cliente: [Seleccionar ▼]                     │
│                                              │
│ Material: [Aluminio ▼]                       │
│                                              │
│ Cantidad Estimada: [2,000] kg (Opcional)     │
│                                              │
│ Placa Vehículo: [ABC-123] ⭐                 │
│                                              │
│ Notas:                                       │
│ [Material despachado directo a cliente___]   │
│                                              │
│        [Cancelar]  [Crear Tránsito]         │
│                                              │
└──────────────────────────────────────────────┘
```

**Estado inicial:** `pending`

### 12.4 Vista de Tránsitos Pendientes

```
┌─────────────────────────────────────────────────────────────────┐
│              TRÁNSITOS PENDIENTES                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Remisión│Fecha   │Proveedor  │Cliente    │Material│Cant.Est. │
│  ───────────────────────────────────────────────────────────── │
│  R-00345 │31/01/26│Metales XYZ│Indust. ABC│Aluminio│ 2,000 kg │
│  R-00346 │30/01/26│Prov Local │Cliente SA │Cobre   │   500 kg │
│  R-00347 │29/01/26│Reciclajes │Corp ZXC   │Hierro  │ 3,000 kg │
│                                                                 │
│  [Cerrar] [Ver Detalle] [Eliminar]                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 12.5 Cerrar Tránsito

**Al hacer click en [Cerrar]:**

```
┌──────────────────────────────────────────────┐
│      CERRAR TRÁNSITO #R-00345                │
├──────────────────────────────────────────────┤
│                                              │
│ DATOS ORIGINALES:                            │
│ Proveedor: Metales XYZ                       │
│ Cliente: Industrial ABC                      │
│ Material: Aluminio                           │
│ Estimado: 2,000 kg                           │
│                                              │
│ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                              │
│ DATOS FINALES (Al llegar):                   │
│                                              │
│ Fecha de cierre: [31/01/2026] 📅             │
│                                              │
│ Cantidad Real: [1,850] kg                    │
│                                              │
│ Precio de Compra: [4,800] $/kg               │
│ Total Compra: $8,880,000                     │
│                                              │
│ Precio de Venta: [6,200] $/kg                │
│ Total Venta: $11,470,000                     │
│                                              │
│ 💰 Ganancia: $2,590,000 (22.6%)             │
│                                              │
│ Comisiones (Opcional):                       │
│ [+ Agregar Comisión]                         │
│                                              │
│        [Cancelar]  [Confirmar Cierre]       │
│                                              │
└──────────────────────────────────────────────┘
```

**Al confirmar:**

1. Crea COMPRA:
   - Proveedor del tránsito
   - Material y cantidad real
   - Precio de compra ingresado
   - Status = 'liquidated'

2. Crea VENTA:
   - Cliente del tránsito
   - Material y cantidad real
   - Precio de venta ingresado
   - Status = 'liquidated'

3. Crea movimientos de inventario:
   - Entrada por compra
   - Salida por venta

4. Actualiza tránsito:
   - Status = 'closed'
   - Vincula purchase_id y sale_id
   - Registra closed_date y closed_by

5. Muestra confirmación con enlaces a compra y venta creadas

---

## 13. MÓDULO DE UNIDADES DE NEGOCIO ⭐ NUEVO

### 13.1 Descripción General

Análisis de rentabilidad por línea de negocio, asignando gastos directos e indirectos.

### 13.2 Concepto

Una **Unidad de Negocio** agrupa materiales similares para analizar rentabilidad.

**Ejemplos:**
- **Fibras:** Papel, Cartón, Pliega, Archivo
- **Chatarra:** Hierro, Acero, Hierro Fundido
- **Metales No Ferrosos:** Cobre, Aluminio, Bronce
- **Otros:** Baterías, Plásticos, etc.

### 13.3 Gestión de Unidades

```
┌─────────────────────────────────────────────────────────────────┐
│              UNIDADES DE NEGOCIO                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [+ Nueva Unidad]                                               │
│                                                                 │
│  Código     │ Nombre              │ Materiales │ % Ventas      │
│  ─────────────────────────────────────────────────────────────  │
│  FIBRAS     │ Fibras              │ 4          │ 45%           │
│  CHATARRA   │ Chatarra            │ 3          │ 30%           │
│  NO_FERRO   │ Metales No Ferrosos │ 5          │ 20%           │
│  OTROS      │ Otros               │ 2          │  5%           │
│                                                                 │
│  [Editar] [Ver Análisis] [Configurar Gastos]                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 13.4 Asignación de Gastos

**Tipos de gastos:**

1. **Gastos Directos:** Se asignan a UNA unidad específica
   - Ejemplo: Alambre → solo para Fibras
   - Ejemplo: Nómina operario de chatarra → solo Chatarra

2. **Gastos Generales/Indirectos:** Se prorratean entre todas
   - Ejemplo: Arriendo de bodega
   - Ejemplo: Nómina administrativa
   - Ejemplo: Servicios públicos

**Pantalla de configuración:**

```
┌──────────────────────────────────────────────┐
│      CONFIGURAR CATEGORÍAS DE GASTOS         │
├──────────────────────────────────────────────┤
│                                              │
│  Categoría              │ Tipo     │ Unidad │
│  ──────────────────────────────────────────  │
│  Nómina Operativa       │ Directo  │ [▼]    │
│  Nómina Administrativa  │ General  │ -      │
│  Arriendo               │ General  │ -      │
│  Alambre                │ Directo  │ Fibras │
│  Combustible Patio      │ General  │ -      │
│  Fletes                 │ General  │ -      │
│                                              │
└──────────────────────────────────────────────┘
```

**Al registrar gasto directo:**

```
┌──────────────────────────────────────────────┐
│      REGISTRAR GASTO                         │
├──────────────────────────────────────────────┤
│                                              │
│ Categoría: [Alambre ▼]                       │
│                                              │
│ ⚠️ Esta categoría es gasto DIRECTO          │
│                                              │
│ Asignar a Unidad de Negocio:                 │
│ (•) Fibras  ← (Pre-seleccionada)             │
│ ( ) Chatarra                                 │
│ ( ) Metales No Ferrosos                      │
│                                              │
│ Monto: [$500,000]                            │
│                                              │
└──────────────────────────────────────────────┘
```

### 13.5 Reporte de Rentabilidad

**Pantalla principal:**

```
┌─────────────────────────────────────────────────────────────────┐
│        ANÁLISIS DE RENTABILIDAD POR UNIDAD DE NEGOCIO           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Período: [Del 04/01/2026 al 03/02/2026] 📅                     │
│                                                                 │
│  ══════════════════════════════════════════════════════════════ │
│                                                                 │
│  📦 FIBRAS                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Toneladas vendidas: 500 ton                                    │
│                                                                 │
│  INGRESOS:                                                      │
│  Margen bruto total:       $215,000,000                         │
│  Margen bruto por kg:           $430/kg                         │
│                                                                 │
│  COSTOS:                                                        │
│  Gastos directos:           $50,000,000                         │
│  Costo directo por kg:          $100/kg                         │
│                                                                 │
│  Gastos indirectos:         $90,900,000 ⭐                      │
│  Costo indirecto por kg:    $181.81/kg                          │
│                                                                 │
│  ──────────────────────────────────────────────────────────     │
│                                                                 │
│  💰 UTILIDAD NETA:          $74,100,000                         │
│  Utilidad por kg:               $148.19/kg                      │
│  Margen neto:                   34.5%                           │
│                                                                 │
│  ══════════════════════════════════════════════════════════════ │
│                                                                 │
│  [Ver Detalle] [Comparar Unidades] [Exportar]                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Cálculo de gastos indirectos (Prorrateo):**

```typescript
// Fórmula acordada con Gustavo:

// 1. Calcular total kg vendidos de TODA la empresa
const totalKgAllUnits = sum(kgSold for each business_unit);

// 2. Sumar gastos generales del período
const totalGeneralExpenses = sum(
  expenses where category.type === 'general'
);

// 3. Calcular costo general por kg
const costPerKg = totalGeneralExpenses / totalKgAllUnits;

// 4. Asignar a cada unidad según sus kg
function calculateIndirectCosts(businessUnit) {
  const unitKgSold = getKgSold(businessUnit, period);
  const indirectCosts = unitKgSold * costPerKg;
  const indirectCostPerKg = costPerKg;
  
  return {
    totalIndirectCosts: indirectCosts,
    indirectCostPerKg: indirectCostPerKg
  };
}
```

**Ejemplo numérico:**

```
EMPRESA TOTAL EN EL MES:
• Total kg vendidos: 1,100 ton
• Gastos generales: $200,000,000
• Costo general/kg: $200,000,000 / 1,100,000 kg = $181.81/kg

UNIDAD FIBRAS:
• Kg vendidos: 500 ton = 500,000 kg
• Gastos indirectos: 500,000 kg × $181.81/kg = $90,900,000 ⭐
```

### 13.6 Comparación entre Unidades

```
┌─────────────────────────────────────────────────────────────────┐
│        COMPARACIÓN DE UNIDADES DE NEGOCIO                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Unidad      │ Ton │ Margen│ Utilidad  │ Util/kg│ Margen %    │
│  ─────────────────────────────────────────────────────────────  │
│  Fibras      │ 500 │ 430   │ 74,100 K  │ 148.19 │ 34.5% ✅    │
│  Chatarra    │ 350 │ 320   │ 35,000 K  │ 100.00 │ 31.3% ✅    │
│  No Ferrosos │ 200 │ 650   │ 60,000 K  │ 300.00 │ 46.2% ⭐    │
│  Otros       │  50 │ 200   │ -5,000 K  │-100.00 │ -50.0% ⚠️   │
│                                                                 │
│  📊 Gráfico de torta: Contribución a utilidad                  │
│                                                                 │
│  [Ver Tendencia Mensual] [Exportar]                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 14. MÓDULO DE PROYECCIONES Y METAS ⭐ NUEVO

### 14.1 Descripción General

Sistema para establecer metas mensuales y monitorear cumplimiento en tiempo real.

### 14.2 Tipos de Metas

1. **Metas de Compras** - Por material (medir comerciales/compradores)
2. **Metas de Ventas** - Por material (medir producción)
3. **Presupuesto de Gastos** - Por categoría

### 14.3 Estructura de Datos

```typescript
interface Projection {
  id: string;
  organization_id: string;
  
  // Identificación
  name: string;                  // "Metas Enero 2026"
  month: string;                 // "2026-01"
  
  // Período (según corte configurado)
  start_date: date;              // 04/01/2026
  end_date: date;                // 03/02/2026
  
  // Estado
  status: 'active' | 'closed';
  
  // Metas
  purchase_goals: PurchaseGoal[];
  sale_goals: SaleGoal[];
  expense_budgets: ExpenseBudget[];
  
  // Auditoría
  created_by: string;
  created_at: timestamp;
  updated_at: timestamp;
}

interface PurchaseGoal {
  id: string;
  projection_id: string;
  material_id: string;
  target_quantity: number;       // Toneladas a comprar
}

interface SaleGoal {
  id: string;
  projection_id: string;
  material_id: string;
  target_quantity: number;       // Toneladas a vender
}

interface ExpenseBudget {
  id: string;
  projection_id: string;
  expense_category_id: string;
  budgeted_amount: number;       // Presupuesto
}
```

### 14.4 Creación de Proyección

```
┌──────────────────────────────────────────────┐
│      CREAR PROYECCIÓN MENSUAL                │
├──────────────────────────────────────────────┤
│                                              │
│ Nombre: [Metas Febrero 2026___________]      │
│                                              │
│ Mes: [Febrero 2026 ▼]                        │
│                                              │
│ Período: Del 04/02/2026 al 03/03/2026        │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  METAS DE COMPRAS                      │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material          │ Meta (ton)         │  │
│ │ ──────────────────────────────────────│  │
│ │ Chatarra ▼        │ [300]              │  │
│ │ Cobre ▼           │ [50]               │  │
│ │ Papel ▼           │ [200]              │  │
│ │                                        │  │
│ │ [+ Agregar Material]                   │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  METAS DE VENTAS                       │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Material          │ Meta (ton)         │  │
│ │ ──────────────────────────────────────│  │
│ │ Hierro ▼          │ [250]              │  │
│ │ Aluminio ▼        │ [100]              │  │
│ │                                        │  │
│ │ [+ Agregar Material]                   │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│ ┌────────────────────────────────────────┐  │
│ │  PRESUPUESTO DE GASTOS                 │  │
│ ├────────────────────────────────────────┤  │
│ │                                        │  │
│ │ Categoría         │ Presupuesto        │  │
│ │ ──────────────────────────────────────│  │
│ │ Consumibles ▼     │ [5,000,000]        │  │
│ │ Mantenimiento ▼   │ [20,000,000]       │  │
│ │ Fletes ▼          │ [10,000,000]       │  │
│ │                                        │  │
│ │ [+ Agregar Categoría]                  │  │
│ │                                        │  │
│ └────────────────────────────────────────┘  │
│                                              │
│        [Cancelar]  [Crear Proyección]       │
│                                              │
└──────────────────────────────────────────────┘
```

### 14.5 Dashboard de Cumplimiento

```
┌─────────────────────────────────────────────────────────────────┐
│        CUMPLIMIENTO DE METAS - FEBRERO 2026                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Período: Del 04/02/2026 al 03/03/2026                          │
│  Días transcurridos: 15 / 28                                    │
│  Progreso esperado: 53.6%                                       │
│                                                                 │
│  ══════════════════════════════════════════════════════════════ │
│                                                                 │
│  📦 COMPRAS                                                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Material        │ Meta    │ Ejecutado │ % Cumpl │ Estado      │
│  ───────────────────────────────────────────────────────────   │
│  Chatarra        │ 300 ton │ 187 ton   │ 62.3%   │ ⚠️ Bajo    │
│  Cobre           │  50 ton │  38 ton   │ 76.0%   │ ✅ Bien    │
│  Papel           │ 200 ton │ 150 ton   │ 75.0%   │ ✅ Bien    │
│                                                                 │
│  ⚠️ Chatarra está 8.7% por debajo del progreso esperado        │
│                                                                 │
│  ══════════════════════════════════════════════════════════════ │
│                                                                 │
│  🏭 VENTAS                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Material        │ Meta    │ Ejecutado │ % Cumpl │ Estado      │
│  ───────────────────────────────────────────────────────────   │
│  Hierro          │ 250 ton │ 205 ton   │ 82.0%   │ ⭐ Excelente│
│  Aluminio        │ 100 ton │  65 ton   │ 65.0%   │ ✅ Bien    │
│                                                                 │
│  ══════════════════════════════════════════════════════════════ │
│                                                                 │
│  💰 GASTOS                                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                 │
│  Categoría       │ Presup. │ Ejecutado │ % Uso   │ Estado      │
│  ───────────────────────────────────────────────────────────   │
│  Consumibles     │  5,000 K│  3,200 K  │ 64.0%   │ ✅ OK      │
│  Mantenimiento   │ 20,000 K│ 18,500 K  │ 92.5%   │ ⚠️ Alto    │
│  Fletes          │ 10,000 K│  5,100 K  │ 51.0%   │ ✅ OK      │
│                                                                 │
│  ⚠️ Mantenimiento al 92.5% y quedan 13 días                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Lógica de alertas:**

```typescript
function getAlertStatus(actual: number, target: number, daysElapsed: number, totalDays: number) {
  const percentComplete = (actual / target) * 100;
  const expectedProgress = (daysElapsed / totalDays) * 100;
  const deviation = percentComplete - expectedProgress;
  
  if (deviation >= 10) return '⭐ Excelente';
  if (deviation >= 0) return '✅ Bien';
  if (deviation >= -10) return '⚠️ Atención';
  return '❌ Crítico';
}
```

---

## 15. MÓDULO DE TERCEROS

### 15.1 Funcionalidad

Gestión centralizada de proveedores, clientes, inversionistas y provisiones.

### 15.2 Pantalla Principal

```
┌─────────────────────────────────────────────────────────────────┐
│              GESTIÓN DE TERCEROS                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [+ Nuevo Tercero]  [+ Nueva Provisión] ⭐                      │
│                                                                 │
│  Filtros: [Tipo ▼] [Categoría ▼] [Buscar...]                   │
│                                                                 │
│  Nombre            │ Tipo       │ Saldo      │ Estado │ Acciones│
│  ───────────────────────────────────────────────────────────── │
│  Reciclajes del N. │ Proveedor  │ -2,500,000 │ Activo │ [Ver]  │
│  Industrial ABC    │ Cliente    │ +5,000,000 │ Activo │ [Ver]  │
│  Metales SA        │ Prov+Clie  │   +500,000 │ Activo │ [Ver]  │
│  Juan Pérez        │ Socio      │ -10,000,000│ Activo │ [Ver]  │
│  Prov. Manten. ⭐  │ Provisión  │ -40,000,000│ Activo │ [Ver]  │
│                                                                 │
│                                   Página 1 de 8 →               │
└─────────────────────────────────────────────────────────────────┘
```

### 15.3 Formulario de Tercero

```
┌──────────────────────────────────────────────┐
│      NUEVO/EDITAR TERCERO                    │
├──────────────────────────────────────────────┤
│                                              │
│ Nombre / Razón Social: *                     │
│ [_______________________________]            │
│                                              │
│ NIT / Cédula:                                │
│ [_______________]                            │
│                                              │
│ Email:                                       │
│ [_______________________________]            │
│                                              │
│ Teléfono:                                    │
│ [_______________]                            │
│                                              │
│ Dirección:                                   │
│ [_______________________________]            │
│                                              │
│ Este tercero es: *                           │
│ [☑] Proveedor (le compramos)                 │
│ [☑] Cliente (le vendemos)                    │
│ [☐] Inversionista (aporta capital)           │
│                                              │
│ Categoría adicional:                         │
│ [Seleccionar ▼]                              │
│ - Proyecto                                   │
│ - Otra facturación                           │
│ - Obligación financiera                      │
│ - Normal                                     │
│                                              │
│        [Cancelar]  [Guardar]                 │
│                                              │
└──────────────────────────────────────────────┘
```

### 15.4 Estado de Cuenta

```
┌─────────────────────────────────────────────────────────────────┐
│        ESTADO DE CUENTA: RECICLAJES DEL NORTE S.A.S.            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tipo: Proveedor                                                │
│  Saldo Actual: -$2,500,000 (Le debemos)                         │
│                                                                 │
│  Período: [Del 01/01/2026 al 31/01/2026] 📅                     │
│                                                                 │
│  Fecha    │ Descripción        │ Debe       │ Haber     │ Saldo│
│  ───────────────────────────────────────────────────────────── │
│  01/01/26 │ Saldo inicial      │            │           │  -500K│
│  05/01/26 │ Compra #0095       │  2,000,000 │           │-2,500K│
│  10/01/26 │ Pago efectivo      │            │ 1,000,000 │-1,500K│
│  20/01/26 │ Compra #0102       │  1,500,000 │           │-3,000K│
│  28/01/26 │ Pago transfer.     │            │ 3,000,000 │     0│
│  31/01/26 │ Compra #0125       │  2,500,000 │           │-2,500K│
│                                                                 │
│  Totales:                       │  6,000,000 │ 4,000,000 │       │
│                                                                 │
│  [Exportar a Excel] [Imprimir] [Registrar Pago]                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 16. MÓDULO DE MATERIALES

### 16.1 Funcionalidad

Gestión del catálogo de materiales reciclables.

### 16.2 Pantalla Principal

```
┌─────────────────────────────────────────────────────────────────┐
│              CATÁLOGO DE MATERIALES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [+ Nuevo Material]  [+ Nueva Categoría]  [Ordenar Materiales] │
│                                                                 │
│  Código │ Nombre       │ Cat.    │ Unidad │ U.Neg.│ Estado     │
│  ───────────────────────────────────────────────────────────── │
│  HI-01  │ Hierro       │ Chatarra│ kg     │Chatar.│ Activo [↑↓]│
│  CU-01  │ Cobre Limpio │ Cobre   │ kg     │NoFerro│ Activo [↑↓]│
│  PAP-01 │ Papel Blanco │ Papel   │ kg     │Fibras │ Activo [↑↓]│
│  BAT-01 │ Baterías ⭐  │ Baterías│ unidad │Otros  │ Activo [↑↓]│
│  COMP-01│ Mat.Compuesto│ Varios  │ kg     │NoFerro│ Activo [↑↓]│
│                                                                 │
│  [↑↓] = Reordenar arrastrando                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 16.3 Formulario de Material

```
┌──────────────────────────────────────────────┐
│      NUEVO/EDITAR MATERIAL                   │
├──────────────────────────────────────────────┤
│                                              │
│ Código: * (Único)                            │
│ [CU-02______]                                │
│                                              │
│ Nombre: *                                    │
│ [Cobre Sucio_________________]               │
│                                              │
│ Descripción:                                 │
│ [_______________________________]            │
│                                              │
│ Categoría: *                                 │
│ [Cobre ▼]                                    │
│                                              │
│ Unidad de Negocio: * ⭐                      │
│ [Metales No Ferrosos ▼]                      │
│                                              │
│ Unidad de Medida: * ⭐                       │
│ ( ) Kilogramos (kg)                          │
│ ( ) Unidades                                 │
│ ( ) Toneladas (ton)                          │
│ ( ) Litros                                   │
│                                              │
│ Orden de Prioridad: ⭐                       │
│ [5__] (menor = más prioritario)              │
│                                              │
│        [Cancelar]  [Guardar]                 │
│                                              │
└──────────────────────────────────────────────┘
```

---

## 17. MÓDULO DE ADMINISTRACIÓN

### 17.1 Sub-módulos

1. **Gestión de Usuarios**
2. **Asignación de Roles**
3. **Configuración de Roles Personalizados**
4. **Configuración General**
5. **Herramientas del Sistema**

### 17.2 Gestión de Usuarios

```
┌─────────────────────────────────────────────────────────────────┐
│              USUARIOS DEL SISTEMA                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [+ Invitar Usuario]                                            │
│                                                                 │
│  Usuario    │ Email              │ Roles          │ Estado      │
│  ───────────────────────────────────────────────────────────── │
│  John       │ john@empresa.com   │ Báscula        │ Activo      │
│  Nixon      │ nixon@empresa.com  │ Aux. Tesorería │ Activo      │
│  Ingrid     │ ingrid@empresa.com │ Planillador    │ Activo      │
│  Gustavo    │ gustavo@empresa.com│ Administrador  │ Activo      │
│  Gabriel    │ gabriel@empresa.com│ Admin Lector   │ Activo      │
│                                                                 │
│  [Editar Roles] [Desactivar] [Ver Actividad]                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 17.3 Configuración General

```
┌──────────────────────────────────────────────┐
│      CONFIGURACIÓN GENERAL                   │
├──────────────────────────────────────────────┤
│                                              │
│ ORGANIZACIÓN:                                │
│ Nombre: [Empresa de Reciclaje_______]        │
│ Logo: [📎 Subir logo...]                     │
│                                              │
│ CORTE MENSUAL: ⭐                            │
│ Los meses van del día:                       │
│ [4__] de cada mes al [3__] del siguiente     │
│                                              │
│ TIMEZONE:                                    │
│ [America/Bogota ▼]                           │
│                                              │
│ MONEDA:                                      │
│ [COP - Peso Colombiano ▼]                    │
│                                              │
│ INVENTARIO:                                  │
│ [☑] Permitir stock negativo                  │
│ [☑] Alertar cuando stock < 10% promedio      │
│                                              │
│ BODEGAS POR DEFECTO:                         │
│ Compras: [Circunvalar ▼]                     │
│ Ventas: [Circunvalar ▼]                      │
│                                              │
│        [Cancelar]  [Guardar Cambios]         │
│                                              │
└──────────────────────────────────────────────┘
```

---

# PARTE IV: REPORTES Y ANÁLISIS

## 18. REPORTES FINANCIEROS

### 18.1 Estado de Resultados

**Fórmula:**

```
INGRESOS
  Ventas                           $XXX,XXX,XXX
  Ingresos por servicios           $ XX,XXX,XXX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TOTAL INGRESOS                   $XXX,XXX,XXX

COSTO DE VENTAS
  Inventario Inicial (día antes)   $ XX,XXX,XXX
  (+) Compras del período          $XXX,XXX,XXX
  (-) Inventario Final             $ XX,XXX,XXX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  COSTO DE VENTAS                  $XXX,XXX,XXX

UTILIDAD BRUTA                     $ XX,XXX,XXX
Margen Bruto: XX.X%

GASTOS OPERACIONALES
  Capital Humano                   $ XX,XXX,XXX
  Obligaciones Financieras         $  X,XXX,XXX
  Bodega                           $  X,XXX,XXX
  Fletes y Básculas                $  X,XXX,XXX
  Vehículos                        $  X,XXX,XXX
  Consumibles                      $  X,XXX,XXX
  Otros                            $    XXX,XXX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TOTAL GASTOS                     $ XX,XXX,XXX

UTILIDAD NETA                      $ XX,XXX,XXX
Margen Neto: XX.X%
```

### 18.2 Flujo de Caja

```
ENTRADAS DE EFECTIVO
  Cobros a clientes                $XXX,XXX,XXX
  Ingresos por servicios           $ XX,XXX,XXX
  Inyección de capital             $ XX,XXX,XXX
  Anticipos recibidos              $  X,XXX,XXX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TOTAL ENTRADAS                   $XXX,XXX,XXX

SALIDAS DE EFECTIVO
  Pagos a proveedores              $XXX,XXX,XXX
  Gastos operativos                $ XX,XXX,XXX
  Retiros de capital               $ XX,XXX,XXX
  Anticipos dados                  $  X,XXX,XXX
  Pagos de activos                 $  X,XXX,XXX
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TOTAL SALIDAS                    $XXX,XXX,XXX

FLUJO NETO DEL PERÍODO             $ XX,XXX,XXX

Saldo inicial                      $ XX,XXX,XXX
Saldo final                        $XXX,XXX,XXX
```

### 18.3 Balance General

Ver ejemplo en sección 5.6 del documento original.

---

## 19. REPORTES OPERATIVOS

### 19.1 Compras del Período

```
┌─────────────────────────────────────────────────────────────────┐
│        REPORTE DE COMPRAS                                       │
│        Del 04/01/2026 al 31/01/2026                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Total Compras: $XXX,XXX,XXX                                    │
│  Compras Liquidadas: XXX                                        │
│  Compras Pendientes: XX                                         │
│  Proveedores Únicos: XX                                         │
│                                                                 │
│  #    │Fecha  │Proveedor   │Material│Kg  │Total    │Estado    │
│  ───────────────────────────────────────────────────────────── │
│  0145 │31/01  │Reciclajes  │Chatarra│2000│2,400 K  │Liquidada │
│  0146 │30/01  │Metales ABC │Cobre   │ 500│4,000 K  │Liquidada │
│  0147 │30/01  │Proveedor X │Hierro  │1000│1,200 K  │Pendiente │
│                                                                 │
│  [Exportar a Excel] [Agrupar por Proveedor] [Agrupar por Mat.] │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 19.2 Ventas del Período

Similar a compras.

### 19.3 Análisis de Márgenes por Material

```
┌─────────────────────────────────────────────────────────────────┐
│        ANÁLISIS DE MÁRGENES POR MATERIAL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Material    │Kg Vend│Costo Prom│Precio Prom│Margen│Utilidad  │
│  ───────────────────────────────────────────────────────────── │
│  Cobre Limpio│ 5,000 │  8,500   │  10,500   │ 23.5%│ 10,000 K │
│  Hierro      │25,000 │  1,200   │   1,600   │ 33.3%│ 10,000 K │
│  Aluminio    │ 3,000 │  4,500   │   6,000   │ 33.3%│  4,500 K │
│                                                                 │
│  [Gráfico de barras: Margen % por material]                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 20. DASHBOARDS Y MÉTRICAS

### 20.1 Dashboard Principal (Home)

```
┌─────────────────────────────────────────────────────────────────┐
│              DASHBOARD PRINCIPAL                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  HOY: 31 Enero 2026                                             │
│                                                                 │
│  ┌────────────────┬────────────────┬────────────────┐          │
│  │ 💰 Efectivo    │ 📦 Inventario  │ 📊 Utilidad    │          │
│  │ $107,000,000   │ $150,000,000   │ $70,000,000    │          │
│  │ ↑ +5% vs ayer  │ → Sin cambios  │ ↑ +12% vs mes │          │
│  └────────────────┴────────────────┴────────────────┘          │
│                                                                 │
│  📈 ESTE MES:                                                   │
│  Ingresos:  $250,000,000                                        │
│  Egresos:   $180,000,000                                        │
│  Margen:    28.0%                                               │
│                                                                 │
│  ⚠️ ALERTAS:                                                   │
│  • 5 tránsitos pendientes de cerrar                             │
│  • Chatarra: Meta de compras al 62% (bajo)                      │
│  • Mantenimiento: Presupuesto al 92%                            │
│                                                                 │
│  📋 TAREAS HOY:                                                 │
│  • Liquidar 3 compras pendientes                                │
│  • Aplicar gasto diferido: Dotación                             │
│  • Revisar saldo Prov. Mantenimiento                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

# PARTE V: REGLAS DE NEGOCIO

## 21. REGLAS DE INVENTARIO

**RN-INV-01: Costo Promedio Móvil**
- Las ENTRADAS recalculan el costo promedio
- Las SALIDAS usan el costo promedio actual sin modificarlo
- Si stock = 0, se mantiene último costo conocido

**RN-INV-02: Inventario en Tránsito** ⭐
- Compras/ventas pendientes afectan `stock_transit`
- Solo movimientos liquidados afectan `stock_liquidated`
- Valorización usa solo stock liquidado

**RN-INV-03: Stock Negativo**
- El sistema PERMITE stock negativo
- Se muestra advertencia al usuario
- Común en el negocio (vender antes de comprar)

**RN-INV-04: Transformación de Materiales** ⭐
- Total destinos + merma = cantidad origen
- Los costos se distribuyen proporcionalmente
- Usuario puede ajustar costos manualmente

---

## 22. REGLAS FINANCIERAS

**RN-FIN-01: Provisiones** ⭐
- Son terceros especiales (is_provision = true)
- Saldo negativo = fondos disponibles
- Saldo positivo = sobregiro
- Gastos desde provisión NO afectan cuentas de dinero

**RN-FIN-02: Gastos Diferidos** ⭐
- Se aplican semi-automáticamente
- Usuario debe confirmar cada mes
- Se pueden posponer si necesario
- Al completar, status = 'completed'

**RN-FIN-03: Movimientos Confirmados**
- Solo movimientos `status = 'confirmed'` afectan saldos
- `draft` no afecta
- `annulled` revierte efectos

**RN-FIN-04: Transferencias**
- Crean 2 movimientos: transfer_out + transfer_in
- Monto debe coincidir exacto
- Cuentas origen y destino deben ser diferentes

---

## 23. FÓRMULAS Y CÁLCULOS

### 23.1 Inventario

**Valor de Inventario:**
```
Valor Total = Σ (Stock Liquidado × Costo Promedio) para cada material
```

**Costo de Ventas (Período):**
```
Costo Ventas = Inventario Inicial + Compras - Inventario Final
```

### 23.2 Utilidades

**Utilidad Bruta:**
```
Utilidad Bruta = Ingresos - Costo de Ventas
```

**Utilidad Neta:**
```
Utilidad Neta = Utilidad Bruta - Gastos Operativos
```

**Márgenes:**
```
Margen Bruto % = (Utilidad Bruta / Ingresos) × 100
Margen Neto % = (Utilidad Neta / Ingresos) × 100
```

### 23.3 Unidades de Negocio ⭐

**Gastos Indirectos por Unidad:**
```
Total Gastos Generales = Σ Gastos categoría.type = 'general'
Total Kg Empresa = Σ Kg vendidos todas las unidades
Costo General por Kg = Total Gastos Generales / Total Kg Empresa

Para cada unidad:
  Gastos Indirectos = Kg Vendidos Unidad × Costo General por Kg
```

**Utilidad Neta por Unidad:**
```
Utilidad Neta = Margen Bruto - Gastos Directos - Gastos Indirectos
```

---

# PARTE VI: SEGURIDAD Y AUDITORÍA

## 24. ROLES Y PERMISOS

### 24.1 ROL 1: BÁSCULA (John)

**Permisos:**

✅ **Puede:**
- Crear compras (solo cantidades, sin precios)
- Crear ventas (solo cantidades, sin precios)
- Crear traslados entre materiales
- Consultar inventario (lectura)
- Seleccionar bodega destino/origen
- Ingresar placa de vehículo

❌ **NO puede:**
- Poner precios (ni en compras ni ventas)
- Liquidar transacciones
- Ver tesorería
- Ver reportes financieros
- Modificar catálogos
- Gestionar usuarios

**Pantallas accesibles:**
- Compras → Nueva Compra
- Ventas → Nueva Venta
- Inventario → Stock Actual (solo lectura)
- Inventario → Traslados entre Materiales

---

### 24.2 ROL 2: AUXILIAR DE TESORERÍA (Nixon)

**Permisos:**

✅ **Puede:**
- Liquidar compras (asignar precios)
- Liquidar ventas de contado (asignar precios)
- Actualizar lista de precios
- Registrar movimientos en Caja Menor
- Registrar gastos en Caja Menor
- Registrar pagos a proveedores
- Registrar cobros a clientes
- Ver pendientes de liquidación

❌ **NO puede:**
- Crear/editar terceros
- Crear/editar materiales
- Modificar configuración
- Ver todos los reportes (solo su caja)
- Gestionar usuarios
- Acceder a otras cuentas de dinero

**Pantallas accesibles:**
- Compras → Pendientes de Liquidar
- Compras → Liquidar
- Ventas → Pendientes de Liquidar
- Ventas → Liquidar
- Tesorería → Movimientos (Caja Menor)
- Tesorería → Gastos (Caja Menor)
- Configuración → Lista de Precios

---

### 24.3 ROL 3: PLANILLADOR DE DESPACHOS (Ingrid)

**Permisos:**

✅ **Puede:**
- Crear ventas CON precios (despachos)
- Crear tránsitos (remisiones)
- Crear operaciones de doble partida
- Liquidar ventas
- Actualizar lista de precios
- Ver inventario
- Ingresar número de factura

❌ **NO puede:**
- Liquidar compras
- Ver toda la tesorería
- Ver estados de cuenta completos
- Modificar configuración
- Gestionar usuarios

**Pantallas accesibles:**
- Ventas → Nueva Venta (con precios)
- Ventas → Doble Partida
- Ventas → Liquidar
- Tránsitos → Crear
- Tránsitos → Cerrar
- Inventario → Consulta
- Configuración → Lista de Precios

---

### 24.4 ROL 4: ADMINISTRADOR OPERATIVO (Gustavo)

**Permisos:**

✅ **Puede TODO:**
- Gestión completa de todos los módulos
- Liquidar compras y ventas pendientes
- Registrar movimientos en todas las cuentas
- Ver todos los reportes
- Configurar sistema
- Gestionar usuarios
- Auditar movimientos
- Cerrar períodos
- Aplicar gastos diferidos

**Acceso:** Sin restricciones

---

### 24.5 ROL 5: ADMINISTRADOR LECTOR (Gabriel)

**Permisos:**

✅ **Puede:**
- Ver todos los módulos
- Ver todos los reportes
- Exportar datos
- Consultar estados de cuenta
- Ver dashboard completo

❌ **NO puede:**
- Crear/Modificar/Eliminar nada
- Liquidar transacciones
- Registrar movimientos
- Configurar sistema
- Gestionar usuarios

**Propósito:** Supervisión y análisis sin capacidad de modificación

---

## 25. AUDITORÍA Y TRAZABILIDAD

### 25.1 Registro Automático

**Todos los registros incluyen:**
```typescript
{
  created_by: string;      // user_id quien creó
  created_at: timestamp;   // cuándo se creó
  updated_by?: string;     // user_id quien modificó
  updated_at?: timestamp;  // cuándo se modificó
}
```

### 25.2 Historial de Cambios

Para registros críticos (compras, ventas, movimientos):

```typescript
interface AuditLog {
  id: string;
  table_name: string;
  record_id: string;
  action: 'create' | 'update' | 'delete' | 'annul';
  old_values?: Record<string, any>;
  new_values?: Record<string, any>;
  user_id: string;
  user_name: string;
  timestamp: timestamp;
  ip_address?: string;
}
```

**Ejemplo de vista:**

```
┌─────────────────────────────────────────────────────────────────┐
│        HISTORIAL DE CAMBIOS: COMPRA #0145                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  31/01 10:30  John       Creó compra (solo cantidades)          │
│  31/01 14:45  Nixon      Liquidó con precios                    │
│  31/01 14:46  Nixon      Cambió precio Chatarra: $1,200→$1,250  │
│  31/01 16:20  Gustavo    Cambió precio Chatarra: $1,250→$1,200  │
│                          Razón: "Error de Nixon, precio correcto│
│                          es $1,200"                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 25.3 Reportes de Auditoría

```
┌──────────────────────────────────────────────┐
│      REPORTE DE ACTIVIDAD                    │
├──────────────────────────────────────────────┤
│                                              │
│ Usuario: [Todos ▼]                           │
│ Acción: [Todas ▼]                            │
│ Módulo: [Todos ▼]                            │
│ Fecha: [Del ___ al ___]                      │
│                                              │
│ Fecha/Hora │Usuario│Acción │Módulo │Detalle │
│ ──────────────────────────────────────────── │
│ 31/01 16:20│Gustavo│Update │Compras│C #0145 │
│ 31/01 14:46│Nixon  │Update │Compras│C #0145 │
│ 31/01 14:45│Nixon  │Liquidó│Compras│C #0145 │
│ 31/01 10:30│John   │Create │Compras│C #0145 │
│                                              │
│ [Exportar] [Filtrar] [Ver Detalle]           │
│                                              │
└──────────────────────────────────────────────┘
```

---

# PARTE VII: IMPLEMENTACIÓN

## 26. PLAN DE MIGRACIÓN

### 26.1 Estrategia

**Enfoque:** Convivencia temporal Excel + Sistema

**Duración estimada:** 1 semana

**Fases:**

1. **Preparación (Días 1-2):**
   - Configurar organización
   - Crear usuarios
   - Configurar catálogos (materiales, categorías, bodegas)
   - Crear lista de precios inicial

2. **Carga de Saldos Iniciales (Día 3):**
   - Terceros con saldos
   - Inventario valorizado
   - Cuentas de dinero con saldos
   - Provisiones

3. **Período de Convivencia (Días 4-7):**
   - Registrar nuevas transacciones en ambos sistemas
   - Comparar resultados diarios
   - Ajustar discrepancias
   - Capacitar usuarios

4. **Validación Final (Día 7):**
   - Cuadrar balances
   - Verificar estados de cuenta
   - Confirmar inventario
   - Validar utilidades

5. **Go-Live (Día 8):**
   - Excel pasa a solo consulta
   - Sistema es fuente única de verdad

### 26.2 Datos a Migrar

**Archivo Excel del cliente debe incluir:**

1. **Terceros:**
   - Proveedores con saldos
   - Clientes con saldos
   - Socios/inversionistas con saldos
   - Provisiones con fondos

2. **Inventario:**
   - Material, cantidad, costo promedio
   - Por bodega si aplica

3. **Cuentas de Dinero:**
   - Cada cuenta con saldo actual

4. **Catálogos:**
   - Materiales completos
   - Categorías de gastos
   - Categorías de materiales
   - Unidades de negocio

### 26.3 Formato de Importación

**Hoja "Terceros":**
```
Nombre | Tipo | NIT | Saldo | Categoría
-------|------|-----|-------|----------
Reciclajes XYZ | Proveedor | 123456 | -2500000 | Normal
Cliente ABC | Cliente | 789012 | 5000000 | Normal
```

**Hoja "Inventario":**
```
Código | Material | Categoría | Unidad Neg | Cantidad | Costo Prom | Bodega
-------|----------|-----------|------------|----------|------------|--------
CU-01 | Cobre | Cobre | No Ferrosos | 1500 | 8500 | Circunvalar
```

**Hoja "Cuentas":**
```
Nombre | Tipo | Saldo
-------|------|-------
Caja General | cash | 5000000
Banco Bancolombia | bank | 50000000
```

### 26.4 Validaciones Post-Migración

```
✓ Balance General cuadra con Excel
✓ Inventario valorizado coincide
✓ Estados de cuenta terceros OK
✓ Saldos provisiones OK
✓ Utilidad acumulada coincide
```

---

## 27. ANEXOS

### 27.1 Glosario

| Término | Definición |
|---------|------------|
| **Tercero** | Persona/empresa externa (proveedor, cliente, socio, provisión) |
| **Doble Partida / Pasa Mano** | Compra+venta simultánea sin pasar por bodega |
| **Tránsito** | Material en camino, precios no definidos |
| **Promedio Móvil** | Método de costeo que recalcula con cada entrada |
| **Liquidar** | Asignar precios a transacción creada sin ellos |
| **Provisión** | Fondos reservados para gastos futuros |
| **Gasto Diferido** | Gasto grande distribuido en varios meses |
| **Unidad de Negocio** | Agrupación de materiales por línea |

### 27.2 Casos de Uso Detallados

**CU-001: Compra Normal**
1. John pesa material: 2,000 kg Chatarra
2. Crea compra sin precio
3. Nixon liquida a $1,200/kg
4. Sistema actualiza inventario y saldo proveedor
5. Gustavo paga al proveedor
6. Sistema actualiza saldo cuenta y tercero

**CU-002: Venta con Comisiones**
1. Ingrid despacha 3,000 kg Hierro a $1,800/kg
2. Agrega comisión facturación $67,500
3. Agrega comisión intermediario $50,000
4. Sistema calcula ganancia bruta
5. Cliente paga
6. Sistema distribuye comisiones

**CU-003: Transformación**
1. John registra llegada 500 kg Motor Eléctrico
2. Nixon liquida a $1,000/kg
3. Operarios desintegran
4. John crea traslado:
   - Origen: Motor 500 kg
   - Destino: Cobre 200, Hierro 180, Aluminio 100
   - Merma: 20 kg
5. Sistema recalcula costos promedio

**CU-004: Cierre de Tránsito**
1. Ingrid crea tránsito R-00345
2. Material en camino varios días
3. Material llega con 1,850 kg real
4. Gustavo cierra tránsito ingresando precios
5. Sistema crea compra + venta automáticas

**CU-005: Aplicar Gasto Diferido**
1. Gustavo crea gasto diferido: Dotación $3M en 4 meses
2. Cada mes sistema alerta
3. Nixon aplica $750K del mes
4. Sistema crea gasto automático
5. Después de 4 meses, status = completed

### 27.3 Preguntas Frecuentes

**Q: ¿Puedo vender material que no tengo?**
A: Sí, el sistema permite stock negativo. Muestra advertencia pero permite la venta.

**Q: ¿Cómo afecta el inventario en tránsito los reportes?**
A: El inventario en tránsito NO afecta la valorización. Solo el stock liquidado tiene valor en balance.

**Q: ¿Puedo cambiar un precio después de liquidar?**
A: Sí, con permisos de administrador. Queda registrado en auditoría.

**Q: ¿Qué pasa si cancelo una compra?**
A: El sistema crea movimientos de reversión que anulan el efecto en inventario y saldos.

**Q: ¿Cómo funcionan los gastos desde provisión?**
A: No salen de ninguna cuenta de dinero, solo reducen el fondo de la provisión.

### 27.4 Roadmap Futuro (No incluido en v1.0)

**Posibles mejoras futuras:**
- ❌ Integración DIAN (facturación electrónica)
- ❌ App móvil para báscula
- ❌ Lector de código de barras
- ❌ Integración contabilidad externa
- ❌ Portal de clientes (autoservicio)
- ❌ Predicción de precios con ML
- ❌ Optimización de rutas de vehículos

---

## RESUMEN EJECUTIVO

### Funcionalidades Principales

✅ **8 Módulos Core:**
1. Compras (con liquidación diferida)
2. Ventas (normal + doble partida)
3. Inventario (tránsito + liquidado + transformación)
4. Tesorería (provisiones + diferidos + importación)
5. Tránsitos
6. Unidades de Negocio ⭐
7. Proyecciones y Metas ⭐
8. Administración

✅ **5 Roles Específicos:**
- Báscula (solo cantidades)
- Auxiliar (liquidación + caja menor)
- Planillador (ventas + tránsitos)
- Administrador (acceso total)
- Lector (solo consulta)

✅ **Innovaciones Clave:**
- Separación creación vs liquidación
- Inventario en tránsito visible
- Provisiones como terceros
- Gastos diferidos semi-automáticos
- Análisis por unidad de negocio
- Múltiples bodegas
- Transformación de materiales

### Decisiones Técnicas Confirmadas

| Aspecto | Solución |
|---------|----------|
| Provisiones | third_parties con is_provision=true |
| Inventario Tránsito | Campos en materials + status en movements |
| Gastos Diferidos | Semi-automático con recordatorios |
| Costeo | Promedio ponderado móvil |
| Roles | 5 roles predefinidos + personalizables |

---

## VALIDACIÓN Y APROBACIÓN

**Cambios vs Versión 1.0:**
- ✅ Agregadas 8 nuevas funcionalidades críticas
- ✅ Modificadas 4 funcionalidades existentes
- ✅ Agregados 3 nuevos campos
- ✅ Definidos 5 roles detallados
- ✅ Resueltos 3 puntos técnicos pendientes

**Estado:** APROBADO para Desarrollo

**Firma Cliente:** _____________________  
**Fecha:** _____________________

**Firma Desarrollo:** Eduardo Chain  
**Fecha:** 31 Enero 2026

---

**FIN DEL DOCUMENTO DE REQUERIMIENTOS FUNCIONALES v2.0**

*Total: 120+ páginas | 27 secciones principales | 100+ pantallas especificadas*
