# 🧪 Tests - EcoBalance ERP

Documentación completa para ejecutar los tests del sistema multi-tenant.

---

## 📋 Requisitos Previos

- Docker y Docker Compose instalados
- Python 3.11+ con virtualenv activo
- PostgreSQL Test Database ejecutándose (ver abajo)

---

## 🚀 Setup Inicial

### 1. Levantar PostgreSQL Test Database

El proyecto usa una base de datos PostgreSQL separada para tests (puerto 5433) para no interferir con el entorno de desarrollo (puerto 5432).

```bash
# Desde el directorio backend/
cd /path/to/backend

# Levantar PostgreSQL de tests
docker-compose -f docker-compose.test.yml up -d

# Verificar que esté corriendo
docker ps | grep reciclaje-test-db

# Ver logs (opcional)
docker-compose -f docker-compose.test.yml logs -f
```

**Configuración del contenedor:**
- **Image:** postgres:16-alpine
- **Puerto:** 5433 (host) → 5432 (container)
- **Database:** reciclaje_test
- **Usuario:** admin
- **Password:** test_password
- **Network:** reciclaje_test_network

### 2. Instalar Dependencias de Testing

```bash
# Activar virtualenv
source venv/bin/activate

# Instalar dependencias (si no las tienes)
pip install pytest pytest-asyncio pytest-cov httpx
```

---

## 🧪 Ejecutar Tests

### Todos los tests

```bash
cd backend
source venv/bin/activate
pytest
```

### Tests con verbose output

```bash
pytest -v
```

### Tests con output detallado

```bash
pytest -vv --tb=short
```

### Tests específicos por archivo

```bash
# Tests de organizaciones
pytest tests/test_organizations.py -v

# Tests de autenticación con organizaciones
pytest tests/test_auth_with_org.py -v

# Tests de dependencies (context)
pytest tests/test_org_context_dependency.py -v
```

### Test individual

```bash
pytest tests/test_organizations.py::TestCreateOrganization::test_create_organization_success -xvs
```

### Detener en primer fallo

```bash
pytest -x
```

### Tests con marcadores

```bash
# Solo tests unitarios
pytest -m unit

# Excluir tests lentos
pytest -m "not slow"
```

---

## 📊 Coverage Reports

### Coverage en terminal

```bash
pytest --cov=app --cov-report=term-missing
```

### Coverage HTML (recomendado)

```bash
# Generar reporte HTML
pytest --cov=app --cov-report=html

# Abrir en navegador (macOS)
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

### Coverage con filtros

```bash
# Solo coverage de models
pytest --cov=app.models --cov-report=term-missing

# Solo coverage de services
pytest --cov=app.services --cov-report=html
```

---

## 📁 Estructura de Tests

```
backend/tests/
├── conftest.py                      # Fixtures compartidos (usuarios, orgs, tokens)
├── test_organizations.py            # 28 tests CRUD de organizaciones
├── test_auth_with_org.py           # 5 tests registro con organización
├── test_org_context_dependency.py  # 9 tests de dependencies
└── README_TESTS.md                 # Este archivo
```

### Tests por Categoría

**test_organizations.py (28 tests):**
- ✅ Crear organizaciones (auto-slug, slugs únicos)
- ✅ Listar organizaciones del usuario
- ✅ Agregar/remover miembros
- ✅ Validación max_users
- ✅ Prevención de eliminar último admin
- ✅ Actualizar roles
- ✅ Múltiples organizaciones por usuario
- ✅ Salir de organización

**test_auth_with_org.py (5 tests):**
- ✅ Registro con/sin organización
- ✅ Owner recibe rol admin
- ✅ Respuesta incluye detalles de org
- ✅ Validación email duplicado

**test_org_context_dependency.py (9 tests):**
- ✅ Validación UUID en headers
- ✅ Validación de membership
- ✅ Context requerido vs opcional
- ✅ Retorno de roles correctos

---

## 🐛 Debugging Tests

### Ver SQL queries

Edita `tests/conftest.py` y cambia:
```python
test_engine = create_engine(
    TEST_DATABASE_URL,
    echo=True,  # ← Activa SQL logging
)
```

### Ver output de print statements

```bash
pytest -s  # --capture=no
```

### Ver logs completos

```bash
pytest --log-cli-level=DEBUG
```

### Debug con breakpoint

```python
def test_something():
    # ... código
    import pdb; pdb.set_trace()  # Breakpoint
    # ... más código
```

---

## 🔧 Mantenimiento Database Test

### Limpiar y recrear

```bash
# Detener y eliminar contenedor + volumen
docker-compose -f docker-compose.test.yml down -v

# Recrear desde cero
docker-compose -f docker-compose.test.yml up -d

# Esperar a que esté listo
docker-compose -f docker-compose.test.yml logs -f postgres-test
```

### Conectarse a la BD de tests (debugging)

```bash
# Con psql
docker exec -it reciclaje-test-db psql -U admin -d reciclaje_test

# Listar tablas
\dt

# Ver schema de una tabla
\d users

# Salir
\q
```

### Ver datos de tests (después de fallo)

```bash
# Los tests limpian la BD automáticamente después de cada test
# Para ver datos, puedes comentar temporalmente el cleanup en conftest.py:

# @pytest.fixture(scope="function")
# def db_session():
#     ...
#     # Base.metadata.drop_all(bind=test_engine)  # ← Comentar esta línea
```

---

## 📈 Métricas Actuales

**Coverage:** ~69% (objetivo: 80%+)

**Tests:**
- Total: 41 tests
- Pasando: 9-41 (depende de configuración)
- Tiempo: ~20-30 segundos

**Por Módulo:**
- `app/models/`: 93% coverage
- `app/schemas/`: 80-100% coverage
- `app/services/`: 40-65% coverage (pendiente)
- `app/api/`: 30-40% coverage (pendiente)

---

## 🎯 Comandos Útiles Quick Reference

```bash
# Setup completo
docker-compose -f docker-compose.test.yml up -d
source venv/bin/activate
pytest

# Tests rápidos sin coverage
pytest -v --tb=line

# Coverage completo
pytest --cov=app --cov-report=html && open htmlcov/index.html

# Un solo test con detalles
pytest tests/test_organizations.py::TestCreateOrganization::test_create_organization_success -xvs

# Cleanup
docker-compose -f docker-compose.test.yml down -v
```

---

## 🆘 Troubleshooting

### Error: "connection refused"
```bash
# Verificar que PostgreSQL test esté corriendo
docker ps | grep reciclaje-test-db

# Si no está, levantarlo
docker-compose -f docker-compose.test.yml up -d
```

### Error: "database does not exist"
```bash
# Recrear la base de datos
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

### Error: "table already exists"
```bash
# Los tests deben limpiar automáticamente
# Si persiste, eliminar el volumen:
docker-compose -f docker-compose.test.yml down -v
```

### Tests muy lentos
```bash
# Verificar echo=False en conftest.py
# Ejecutar solo tests rápidos:
pytest -m "not slow"
```

### Import errors
```bash
# Asegurar que estás en el directorio correcto
cd backend
source venv/bin/activate
python -c "import app; print('OK')"
```

---

## 📚 Referencias

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

## 🔄 CI/CD Integration (Futuro)

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: admin
          POSTGRES_PASSWORD: test_password
          POSTGRES_DB: reciclaje_test
        ports:
          - 5433:5432
    
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v3
```

---

**Última actualización:** 1 de febrero de 2026  
**Versión:** 1.0.0  
**Autor:** Eduardo Chain
