"""
MASSGO - Backend API
FastAPI + Supabase + IA/ML Integrations
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import logging

from config import settings
from database import db
from api.products import router as products_router
from api.orders import router as orders_router
from api.users import router as users_router
from api.dashboard import router as dashboard_router
from api.categorias import router as categorias_router
from api.comprobantes import router as comprobantes_router
from api.whatsapp import router as whatsapp_router
from api.puntos import router as puntos_router
from api.descuentos import router as descuentos_router
from ai.routes import router as ai_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db.connect()
        logger.info("Base de datos Supabase conectada")
    except Exception as e:
        logger.warning(f"No se pudo conectar a Supabase: {e}")
        logger.warning("La API funcionará sin conexión a base de datos")
    yield


app = FastAPI(
    title="MASSGO API",
    description="Backend administrativo para MASSGO - Supermercado de Barrio",
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "https://massgo.pages.dev",
    "https://massgo-admin.pages.dev",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(orders_router)
app.include_router(users_router)
app.include_router(dashboard_router)
app.include_router(categorias_router)
app.include_router(comprobantes_router)
app.include_router(whatsapp_router)
app.include_router(puntos_router)
app.include_router(descuentos_router)
app.include_router(ai_router)


# ── Config endpoint for frontend ──
@app.get("/api/config")
async def get_public_config():
    return {
        "api_url": f"{'https' if settings.ENVIRONMENT == 'production' else 'http'}://{settings.HOST}:{settings.PORT}/api",
    }

# ── Servir archivos estáticos (frontend) solo si existen ──
BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(BASE, "..")
MASSGO_WEB = os.path.join(PROJECT, "MassGo")
DASHBOARD = os.path.join(PROJECT, "Dashboard")

if os.path.isdir(MASSGO_WEB):
    app.mount("/tienda", StaticFiles(directory=MASSGO_WEB, html=True), name="tienda")
if os.path.isdir(DASHBOARD):
    app.mount("/admin", StaticFiles(directory=DASHBOARD, html=True), name="admin")


@app.get("/")
async def root():
    if os.path.isdir(MASSGO_WEB):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/tienda/")
    return {"status": "healthy", "api": "MassGO backend running", "docs": "/docs"}


@app.get("/health")
async def health():
    return {"status": "healthy", "environment": settings.ENVIRONMENT}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.ENVIRONMENT == "development",
    )
