"""
MASSGO - Gestión de Códigos de Descuento (Supabase backend)
Tabla: codigo_descuento en Supabase
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import logging

from database import db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/descuentos", tags=["Descuentos"])


# ─── Models ───

class CodigoDescuentoCreate(BaseModel):
    codigo: str
    tipo_descuento: str = "porcentaje"
    valor: float
    monto_minimo: float = 0
    uso_maximo: Optional[int] = None
    activo: bool = True
    descripcion: str = ""
    fecha_expiracion: Optional[str] = None


class CodigoDescuentoUpdate(BaseModel):
    codigo: Optional[str] = None
    tipo_descuento: Optional[str] = None
    valor: Optional[float] = None
    monto_minimo: Optional[float] = None
    uso_maximo: Optional[int] = None
    activo: Optional[bool] = None
    descripcion: Optional[str] = None
    fecha_expiracion: Optional[str] = None


class ValidarDescuentoRequest(BaseModel):
    codigo: str
    subtotal: float


# ─── Helpers ───

def _formatear(d: dict) -> dict:
    return {
        "id": d.get("id_codigo"),
        "codigo": d.get("codigo", ""),
        "tipo": d.get("tipo_descuento", "porcentaje"),
        "valor": float(d.get("valor", 0)),
        "monto_minimo": float(d.get("monto_minimo", 0)),
        "uso_maximo": d.get("uso_maximo"),
        "usos": d.get("usos_actuales", 0),
        "activo": d.get("activo", True),
        "descripcion": d.get("descripcion", ""),
        "fecha_expiracion": d.get("fecha_expiracion"),
    }


# ─── Endpoints ───

@router.get("/")
async def listar_codigos():
    try:
        res = db.table("codigo_descuento").select("*").order("id_codigo").execute()
        return [_formatear(d) for d in (res.data or [])]
    except Exception as e:
        logger.warning(f"Error listing descuentos: {e}")
        return []


@router.post("/", status_code=201)
async def crear_codigo(data: CodigoDescuentoCreate):
    try:
        res = db.table("codigo_descuento").insert({
            "codigo": data.codigo.upper(),
            "tipo_descuento": data.tipo_descuento,
            "valor": data.valor,
            "monto_minimo": data.monto_minimo,
            "uso_maximo": data.uso_maximo,
            "usos_actuales": 0,
            "activo": data.activo,
            "descripcion": data.descripcion,
            "fecha_expiracion": data.fecha_expiracion,
        }).execute()
        if not res.data:
            raise HTTPException(400, "No se pudo crear el código")
        return _formatear(res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error al crear código: {e}")


@router.put("/{codigo_id}")
async def actualizar_codigo(codigo_id: int, data: CodigoDescuentoUpdate):
    payload = {}
    for key, val in data.model_dump(exclude_none=True).items():
        if key == "tipo_descuento":
            payload["tipo_descuento"] = val
        else:
            payload[key] = val
    if not payload:
        raise HTTPException(400, "No hay campos para actualizar")
    try:
        res = db.table("codigo_descuento").update(payload).eq("id_codigo", codigo_id).execute()
        if not res.data:
            raise HTTPException(404, "Código no encontrado")
        return _formatear(res.data[0])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error al actualizar: {e}")


@router.delete("/{codigo_id}")
async def eliminar_codigo(codigo_id: int):
    try:
        res = db.table("codigo_descuento").delete().eq("id_codigo", codigo_id).execute()
        return {"mensaje": "Código eliminado"}
    except Exception as e:
        raise HTTPException(500, f"Error al eliminar: {e}")


@router.post("/validar")
async def validar_descuento(data: ValidarDescuentoRequest):
    cod = data.codigo.strip().upper()
    try:
        res = db.table("codigo_descuento").select("*").eq("codigo", cod).limit(1).execute()
        if not res.data:
            return {"valido": False, "mensaje": "Código no válido"}
        cod_data = res.data[0]

        if not cod_data.get("activo", True):
            return {"valido": False, "mensaje": "Este código ya no está activo"}

        if cod_data.get("fecha_expiracion"):
            try:
                exp = datetime.fromisoformat(cod_data["fecha_expiracion"])
                if datetime.now() > exp:
                    return {"valido": False, "mensaje": "Este código ha expirado"}
            except:
                pass

        uso_max = cod_data.get("uso_maximo")
        usos_act = cod_data.get("usos_actuales", 0)
        if uso_max is not None and usos_act >= uso_max:
            return {"valido": False, "mensaje": "Este código ya alcanzó su límite de usos"}

        if data.subtotal < float(cod_data.get("monto_minimo", 0)):
            return {
                "valido": False,
                "mensaje": f"Compra mínima de S/ {float(cod_data['monto_minimo']):.2f} para este código"
            }

        tipo = cod_data.get("tipo_descuento", "porcentaje")
        valor = float(cod_data.get("valor", 0))
        if tipo == "porcentaje":
            descuento = round(data.subtotal * valor / 100, 2)
        else:
            descuento = min(valor, data.subtotal)

        # Increment usage
        db.table("codigo_descuento").update({
            "usos_actuales": usos_act + 1
        }).eq("id_codigo", cod_data["id_codigo"]).execute()

        return {
            "valido": True,
            "mensaje": f"Código aplicado: {cod_data['codigo']}",
            "tipo_descuento": tipo,
            "valor": valor,
            "descuento": descuento,
            "subtotal_con_descuento": round(data.subtotal - descuento, 2),
            "id_codigo": cod_data["id_codigo"],
        }
    except Exception as e:
        logger.warning(f"Error validating descuento: {e}")
        return {"valido": False, "mensaje": "Error al validar código"}


def registrar_uso_codigo(pedido_id: int, id_codigo: int, codigo: str, descuento: float, subtotal: float):
    """Called from orders.py to log coupon usage — tries DB first, falls back to JSON"""
    try:
        db.table("pedido").update({
            "codigo_usado": codigo,
            "descuento_aplicado": descuento,
            "id_codigo_descuento": id_codigo,
        }).eq("id_pedido", pedido_id).execute()
    except Exception as e:
        logger.warning(f"No se pudo registrar uso de cupón en pedido (DB): {e}")
        # Fallback: write to JSON file so _get_descuento_por_pedido can read it
        try:
            import json, os
            path = os.path.join(os.path.dirname(__file__), "..", "data", "pedidos_descuentos.json")
            usos = []
            if os.path.exists(path):
                with open(path) as f:
                    usos = json.load(f)
            usos.append({
                "pedido_id": pedido_id,
                "id_codigo": id_codigo,
                "codigo": codigo,
                "descuento": descuento,
                "subtotal": subtotal,
            })
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                json.dump(usos, f, indent=2)
        except Exception as e2:
            logger.warning(f"Tampoco se pudo escribir respaldo JSON: {e2}")


_ensure_files = lambda: None  # compatibility stub
