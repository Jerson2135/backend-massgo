from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models import ComprobanteResumen
from database import db
from typing import List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/comprobantes", tags=["Comprobantes"])


class CrearComprobanteRequest(BaseModel):
    id_pedido: int
    tipo: str = "Boleta"


def _extraer_pago(pago: dict) -> dict:
    if not pago:
        return {}
    metodopago = pago.get("metodopago") or {}
    pedido = pago.get("pedido") or {}
    usuario = pedido.get("usuario") or {}
    return {
        "monto": float(pago.get("monto", 0)),
        "metodo_pago": metodopago.get("nombre") if isinstance(metodopago, dict) else None,
        "id_pedido": pedido.get("id_pedido") or pago.get("id_pedido"),
        "cliente": usuario.get("username") if isinstance(usuario, dict) else None,
        "email": usuario.get("email") if isinstance(usuario, dict) else None,
        "total_pedido": float(pedido["total"]) if pedido.get("total") else None,
    }


def _generar_numero(tipo: str) -> str:
    prefijo = "B001" if tipo == "Boleta" else "F001"
    ultimo = db.get_ultimo_numero_comprobante()
    if ultimo and ultimo.startswith(prefijo + "-"):
        try:
            n = int(ultimo.split("-")[1]) + 1
        except (ValueError, IndexError):
            n = 1
    else:
        n = 1
    return f"{prefijo}-{n:08d}"


def _formatear(c: dict) -> ComprobanteResumen:
    pago_data = _extraer_pago(c.get("pago"))
    return ComprobanteResumen(
        id_comprobante=c["id_comprobante"],
        tipo=c.get("tipo", ""),
        numero=c.get("numero", ""),
        fecha=c.get("fecha"),
        monto=pago_data.get("monto", 0),
        metodo_pago=pago_data.get("metodo_pago"),
        id_pedido=pago_data.get("id_pedido", 0),
        cliente=pago_data.get("cliente"),
        email=pago_data.get("email"),
        total_pedido=pago_data.get("total_pedido"),
    )


@router.get("/", response_model=List[ComprobanteResumen])
async def listar_comprobantes(limite: int = 50, offset: int = 0, id_pedido: Optional[int] = None):
    if id_pedido:
        pagos = db.get_pagos_por_pedido(id_pedido)
        if not pagos.data:
            return []
        id_pago = pagos.data[0]["id_pago"]
        res = db.table("comprobante").select("*, pago!inner(*, metodopago(nombre), pedido!inner(id_pedido, total, id_usuario, usuario(id_usuario, username, email)))").eq("id_pago", id_pago).execute()
        return [_formatear(c) for c in res.data] if res.data else []
    res = db.get_comprobantes(limite=limite, offset=offset)
    return [_formatear(c) for c in res.data] if res.data else []


@router.post("/", response_model=ComprobanteResumen, status_code=201)
async def crear_comprobante(data: CrearComprobanteRequest):
    pagos = db.get_pagos_por_pedido(data.id_pedido)
    if not pagos.data:
        raise HTTPException(400, "El pedido no tiene pagos registrados")
    id_pago = pagos.data[0]["id_pago"]

    existing = db.table("comprobante").select("id_comprobante").eq("id_pago", id_pago).limit(1).execute()
    if existing.data:
        raise HTTPException(409, "El comprobante ya existe para este pago")

    numero = _generar_numero(data.tipo)
    try:
        res = db.crear_comprobante({
            "tipo": data.tipo,
            "numero": numero,
            "id_pago": id_pago,
            "fecha": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error al crear comprobante: {e}")
        raise HTTPException(500, "Error al generar comprobante")

    if not res.data:
        raise HTTPException(500, "Error al crear comprobante")

    c = res.data[0]
    c["pago"] = pagos.data[0]
    return _formatear(c)
