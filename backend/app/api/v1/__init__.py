from fastapi import APIRouter

from .endpoints import health, auth, organizations, materials, material_categories, third_parties, purchases, sales

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
api_router.include_router(material_categories.router, prefix="/material-categories", tags=["material-categories"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(third_parties.router, prefix="/third-parties", tags=["third-parties"])
api_router.include_router(purchases.router, prefix="/purchases", tags=["purchases"])
api_router.include_router(sales.router, prefix="/sales", tags=["sales"])
