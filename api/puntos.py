"""
MASSGO - Programa de Puntos y Fidelización
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import db
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/puntos", tags=["Puntos y Fidelización"])

class PuntosResponse(BaseModel):
    puntos_actuales: int
    puntos_canjeables: int
    total_gastado: float
    nivel: str
    siguiente_nivel: str
    progreso: float

def calcular_nivel(total_gastado: float) -> dict:
    if total_gastado >= 500:
        return {"nivel": "Oro 🥇", "siguiente_nivel": "Platino", "progreso": min(1.0, total_gastado / 1000)}
    elif total_gastado >= 200:
        return {"nivel": "Plata 🥈", "siguiente_nivel": "Oro", "progreso": (total_gastado - 200) / 300}
    elif total_gastado >= 50:
        return {"nivel": "Bronce 🥉", "siguiente_nivel": "Plata", "progreso": (total_gastado - 50) / 150}
    else:
        return {"nivel": "Nuevo 🆕", "siguiente_nivel": "Bronce", "progreso": total_gastado / 50}

@router.get("/{usuario_id}")
async def obtener_puntos(usuario_id: int):
    res = db.get_pedidos(500)
    pedidos = res.data if res.data else []
    pedidos_usuario = [p for p in pedidos if p.get("id_usuario") == usuario_id and p.get("estado") == "Entregado"]

    total_gastado = sum(float(p.get("total", 0)) for p in pedidos_usuario)
    puntos = int(total_gastado * 10)
    nivel_info = calcular_nivel(total_gastado)

    return PuntosResponse(
        puntos_actuales=puntos,
        puntos_canjeables=max(0, puntos - int(puntos * 0.2)),
        total_gastado=round(total_gastado, 2),
        nivel=nivel_info["nivel"],
        siguiente_nivel=nivel_info["siguiente_nivel"],
        progreso=round(nivel_info["progreso"], 2)
    )

class CanjeRequest(BaseModel):
    usuario_id: int
    puntos_usar: int

@router.post("/canjear")
async def canjear_puntos(data: CanjeRequest):
    if data.puntos_usar < 100:
        raise HTTPException(400, "Mínimo 100 puntos para canjear")
    descuento = data.puntos_usar / 10
    return {
        "mensaje": f"Canje exitoso: S/ {descuento:.2f} de descuento",
        "puntos_utilizados": data.puntos_usar,
        "descuento_obtenido": round(descuento, 2),
        "codigo": f"MASSGO-{data.usuario_id}-{data.puntos_usar}"
    }
