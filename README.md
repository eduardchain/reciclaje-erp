# 🔄 ReciclaTrac - Sistema ERP para Empresas de Reciclaje

## 📋 Descripción

Sistema integral de gestión para empresas de reciclaje de metales y materiales. Maneja compras, ventas, inventario, tesorería y reportes financieros con una plataforma moderna y escalable.

**Cliente:** Reciclajes de la Costa

---

## 🛠 Stack Tecnológico

| Componente | Tecnologías |
|-----------|-------------|
| **Backend** | FastAPI • Python 3.11+ • PostgreSQL • SQLAlchemy |
| **Frontend** | React 18 • TypeScript • Vite • Tailwind CSS • shadcn/ui |
| **Deployment** | Docker • Nginx • VPS Hostinger |

---

## ✨ Características Principales

- ✅ **Gestión de Compras** - Proceso de 2 pasos: báscula → liquidación
- ✅ **Gestión de Ventas** - Ventas directas y doble partida
- ✅ **Control de Inventario** - Costo promedio móvil
- ✅ **Múltiples Bodegas** - Gestión de almacenes
- ✅ **Tesorería** - Cuentas, gastos y provisiones
- ✅ **Reportes Financieros** - P&L, Balance, Flujo de caja
- ✅ **Análisis por Unidad de Negocio** - Segmentación de operaciones
- ✅ **Sistema Multi-Tenant** - Soporte para múltiples empresas
- ✅ **Control de Acceso** - 5 roles de usuario con permisos granulares

---

## 📁 Estructura del Proyecto

```
reciclaje-erp/
├── backend/                    # API FastAPI
│   ├── app/
│   │   ├── api/               # Rutas y endpoints
│   │   ├── core/              # Configuración y settings
│   │   ├── models/            # Modelos de BD
│   │   ├── schemas/           # Validación (Pydantic)
│   │   ├── services/          # Lógica de negocio
│   │   └── utils/             # Funciones auxiliares
│   ├── alembic/               # Migraciones de BD
│   ├── tests/                 # Suite de pruebas
│   └── README.md
├── frontend/                   # React App
│   ├── src/
│   │   ├── components/        # Componentes reutilizables
│   │   ├── pages/             # Páginas
│   │   ├── hooks/             # Custom hooks
│   │   ├── services/          # Servicios API
│   │   ├── types/             # TypeScript types
│   │   └── utils/             # Funciones auxiliares
│   ├── public/                # Archivos estáticos
│   └── README.md
├── docs/                       # Documentación
├── deployment/                 # Configuración Docker
└── README.md
```

---

## 🚀 Instalación Local

### ✔️ Requisitos Previos

- Python 3.11+
- Node.js 18+
- PostgreSQL 13+
- Git

### Backend

```bash
# Navegar al directorio backend
cd backend

# Crear y activar entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env

# Ejecutar migraciones (Alembic)
alembic upgrade head

# Iniciar servidor de desarrollo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API disponible en:** http://localhost:8000  
**Documentación interactiva:** http://localhost:8000/docs

### Frontend

```bash
# Navegar al directorio frontend
cd frontend

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

**Aplicación disponible en:** http://localhost:5173

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────┐
│                 Frontend (React)                     │
│              Components • Pages • Hooks              │
└──────────────────┬──────────────────────────────────┘
                   │
                   ├─ HTTP/REST API
                   │
┌──────────────────▼──────────────────────────────────┐
│              Backend (FastAPI)                       │
│  Routes • Services • Models • Validation             │
└──────────────────┬──────────────────────────────────┘
                   │
                   ├─ SQL ORM
                   │
┌──────────────────▼──────────────────────────────────┐
│           Database (PostgreSQL)                      │
│     Tables • Migrations • Data Persistence          │
└──────────────────────────────────────────────────────┘
```

---

## 📝 Roles y Permisos

El sistema incluye 5 roles predefinidos con permisos granulares:

1. **Administrador** - Acceso total al sistema
2. **Gerente** - Gestión operativa y reportes
3. **Operario** - Entrada de datos (compras/ventas)
4. **Contador** - Tesorería y reportes financieros
5. **Visualizador** - Solo lectura

---

## 🔄 Workflow Principal

### Proceso de Compra
1. Báscula - Registro de peso y entrada de material
2. Liquidación - Cálculo y pago a proveedor

### Proceso de Venta
- Ventas directas a clientes
- Ventas con doble partida contable

### Gestión de Inventario
- Actualización automática por compras/ventas
- Cálculo de costo promedio móvil
- Múltiples almacenes/bodegas

---

## 🧪 Testing

```bash
# Backend - Ejecutar pruebas
cd backend
pytest

# Backend - Con cobertura
pytest --cov=app tests/

# Frontend - Ejecutar pruebas
cd frontend
npm run test
```

---

## 📊 Estado del Proyecto

🚧 **En desarrollo activo**  
📅 **Fecha de inicio:** Febrero 2026  
⏳ **Versión:** 0.1.0 (Alfa)

---

## 👨‍💻 Desarrollador

**Eduardo Chain**

---

## 📄 Licencia

**Propiedad privada** - Código propiedad de Eduardo Chain  
Todos los derechos reservados © 2026

---

## 📞 Contacto

Para consultas relacionadas con el proyecto, contactar a:  
📧 **Eduardo Chain**

---

## 🤝 Contribuciones

Este es un proyecto privado. Las contribuciones solo son aceptadas de desarrolladores autorizados.

---

*Última actualización: 31 de enero de 2026*
