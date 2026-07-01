import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from models import Pedido, PedidoCreate, PedidoUpdate, DetallePedido, Envio, Pago
from database import db
from typing import List, Optional

logger = logging.getLogger(__name__)


class ItemPedido(BaseModel):
    id_producto: int
    cantidad: int
    precio_unitario: float


class PedidoConItems(PedidoCreate):
    items: list[ItemPedido] = []
    direccion_entrega: str = ""
    codigo_usado: Optional[str] = None
    descuento_aplicado: float = 0
    id_codigo_descuento: Optional[int] = None
    metodo_pago: str = "tarjeta"
    fecha_programada: str = ""
    hora_programada: str = ""

router = APIRouter(prefix="/api/pedidos", tags=["Pedidos"])

ESTADOS_VALIDOS = {"Preparando", "En despacho", "Entregado", "Cancelado"}
ESTADOS_BLOQUEADOS = {"En despacho", "Entregado"}


def _get_descuento_por_pedido(pedido_id: int):
    """Look up discount info from JSON file (fallback when DB columns don't exist)"""
    try:
        import json, os
        path = os.path.join(os.path.dirname(__file__), "..", "data", "pedidos_descuentos.json")
        if os.path.exists(path):
            with open(path) as f:
                usos = json.load(f)
            for u in usos:
                if u.get("pedido_id") == pedido_id:
                    return {
                        "codigo_usado": u.get("codigo"),
                        "descuento_aplicado": u.get("descuento", 0),
                        "id_codigo_descuento": u.get("id_codigo"),
                    }
    except:
        pass
    return {}


def _formatear_pedido(p: dict, incluir_tracking: bool = False) -> dict:
    usuario = p.get("usuario") or {}
    cliente = (
        usuario.get("username") or
        usuario.get("email") or
        f"Usuario #{p['id_usuario']}"
    )
    codigo = f"MG-{p['id_pedido']:06d}" if incluir_tracking else None
    desc = _get_descuento_por_pedido(p["id_pedido"])
    return {
        "id_pedido": p["id_pedido"],
        "id_usuario": p["id_usuario"],
        "fecha": str(p.get("fecha")) if p.get("fecha") else None,
        "estado": p.get("estado", "Pendiente"),
        "total": float(p["total"]),
        "cliente_nombre": cliente,
        "codigo_seguimiento": codigo,
        "codigo_usado": p.get("codigo_usado") or desc.get("codigo_usado"),
        "descuento_aplicado": float(p.get("descuento_aplicado") or 0) or desc.get("descuento_aplicado", 0),
        "id_codigo_descuento": p.get("id_codigo_descuento") or desc.get("id_codigo_descuento"),
        "detalles": [],
        "envio": None,
        "pagos": [],
    }


@router.get("/", response_model=List[Pedido])
async def listar_pedidos(
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    estado: Optional[str] = Query(None),
):
    res = db.get_pedidos(limite, offset)
    pedidos = res.data if res.data else []

    if estado:
        if estado not in ESTADOS_VALIDOS:
            raise HTTPException(400, f"Estado inválido. Válidos: {', '.join(sorted(ESTADOS_VALIDOS))}")
        pedidos = [p for p in pedidos if p.get("estado") == estado]

    resultado = []
    for p in pedidos:
        fp = _formatear_pedido(p)
        # Cargar detalles
        det_res = db.get_detalle_pedido(p["id_pedido"])
        if det_res.data:
            fp["detalles"] = [
                {
                    "id_detalle": d["id_detalle"],
                    "id_pedido": d["id_pedido"],
                    "id_producto": d["id_producto"],
                    "cantidad": d["cantidad"],
                    "precio_unitario": float(d["precio_unitario"]),
                    "producto_nombre": (d.get("producto") or {}).get("nombre"),
                    "producto_imagen": (d.get("producto") or {}).get("imagen_url"),
                }
                for d in det_res.data
            ]
        # Cargar envío
        env_res = db.get_envio_por_pedido(p["id_pedido"])
        if env_res.data:
            fp["envio"] = {
                "id_envio": env_res.data["id_envio"],
                "id_pedido": env_res.data["id_pedido"],
                "direccion_entrega": env_res.data["direccion_entrega"],
                "estado": env_res.data.get("estado", "Pendiente"),
                "fecha_envio": str(env_res.data.get("fecha_envio")) if env_res.data.get("fecha_envio") else None,
                "fecha_entrega": str(env_res.data.get("fecha_entrega")) if env_res.data.get("fecha_entrega") else None,
            }
        # Cargar pagos
        pag_res = db.get_pagos_por_pedido(p["id_pedido"])
        if pag_res.data:
            fp["pagos"] = [
                {
                    "id_pago": pg["id_pago"],
                    "id_pedido": pg["id_pedido"],
                    "monto": float(pg["monto"]),
                    "fecha": str(pg.get("fecha")) if pg.get("fecha") else None,
                    "metodo_pago": (pg.get("metodopago") or {}).get("nombre"),
                }
                for pg in pag_res.data
            ]
        resultado.append(fp)

    return resultado


@router.get("/{pedido_id}", response_model=Pedido)
async def obtener_pedido(pedido_id: int):
    res = db.get_pedido(pedido_id)
    if not res.data:
        raise HTTPException(404, "Pedido no encontrado")
    fp = _formatear_pedido(res.data)
    det_res = db.get_detalle_pedido(pedido_id)
    if det_res.data:
        fp["detalles"] = [{
            "id_detalle": d["id_detalle"],
            "id_pedido": d["id_pedido"],
            "id_producto": d["id_producto"],
            "cantidad": d["cantidad"],
            "precio_unitario": float(d["precio_unitario"]),
            "producto_nombre": (d.get("producto") or {}).get("nombre"),
            "producto_imagen": (d.get("producto") or {}).get("imagen_url"),
        } for d in det_res.data]
    env_res = db.get_envio_por_pedido(pedido_id)
    if env_res.data:
        fp["envio"] = {
            "id_envio": env_res.data["id_envio"],
            "id_pedido": env_res.data["id_pedido"],
            "direccion_entrega": env_res.data["direccion_entrega"],
            "estado": env_res.data.get("estado", "Pendiente"),
            "fecha_envio": str(env_res.data.get("fecha_envio")) if env_res.data.get("fecha_envio") else None,
        }
    pag_res = db.get_pagos_por_pedido(pedido_id)
    if pag_res.data:
        fp["pagos"] = [{
            "id_pago": pg["id_pago"],
            "id_pedido": pg["id_pedido"],
            "monto": float(pg["monto"]),
            "metodo_pago": (pg.get("metodopago") or {}).get("nombre"),
        } for pg in pag_res.data]
    return fp


@router.post("/", response_model=Pedido, status_code=201)
async def crear_pedido(data: PedidoConItems):
    # 1. Validate stock for all items first
    if data.items:
        for item in data.items:
            res = db.get_producto(item.id_producto)
            if not res.data:
                raise HTTPException(400, f"Producto #{item.id_producto} no encontrado")
            stock_actual = res.data.get("stock", 0)
            if stock_actual < item.cantidad:
                raise HTTPException(400, f"Stock insuficiente para '{res.data.get('nombre', 'Producto')}'. Disponible: {stock_actual}, solicitado: {item.cantidad}")

    # 2. Create pedido (exclude fields stored elsewhere)
    payload = data.model_dump(exclude={'items', 'direccion_entrega', 'codigo_usado', 'descuento_aplicado', 'id_codigo_descuento', 'metodo_pago', 'fecha_programada', 'hora_programada'})
    payload.setdefault("estado", "Preparando")
    res = db.crear_pedido(payload)
    if not res.data:
        raise HTTPException(500, "Error al crear pedido")
    pedido_creado = res.data[0]
    pedido_id = pedido_creado["id_pedido"]

    # 3. Deduct stock and create detalles
    if data.items:
        for item in data.items:
            db.descontar_stock(item.id_producto, item.cantidad)
            db.crear_detalle_pedido({
                "id_pedido": pedido_id,
                "id_producto": item.id_producto,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
            })

    # 4. Create envio record with schedule info
    envio_data = {"id_pedido": pedido_id, "estado": "Preparando", "direccion_entrega": data.direccion_entrega or "Sin dirección"}
    if data.fecha_programada:
        envio_data["fecha_envio"] = f"{data.fecha_programada} {data.hora_programada or '08:00 - 09:00'}"
    else:
        from datetime import datetime as dt
        envio_data["fecha_envio"] = dt.now().isoformat()
    try:
        db.table("envio").insert(envio_data).execute()
    except Exception as e:
        logger.warning(f"No se pudo crear registro de envio: {e}")

    # 5. Create pago record + auto-generar comprobante
    if data.metodo_pago:
        try:
            mp_res = db.table("metodopago").select("id_metodo").eq("nombre", data.metodo_pago).limit(1).execute()
            id_metodo = mp_res.data[0]["id_metodo"] if mp_res.data else None
            if not id_metodo:
                ins = db.table("metodopago").insert({"nombre": data.metodo_pago}).execute()
                id_metodo = ins.data[0]["id_metodo"] if ins.data else None
            pago_res = db.table("pago").insert({
                "id_pedido": pedido_id,
                "monto": float(data.total),
                "id_metodo": id_metodo,
            }).execute()
            if pago_res.data:
                id_pago = pago_res.data[0]["id_pago"]
                try:
                    from api.comprobantes import _generar_numero
                    db.table("comprobante").insert({
                        "tipo": "Boleta",
                        "numero": _generar_numero("Boleta"),
                        "id_pago": id_pago,
                    }).execute()
                except Exception as e2:
                    logger.warning(f"No se pudo auto-generar comprobante: {e2}")
        except Exception as e:
            logger.warning(f"No se pudo crear registro de pago: {e}")

    # 6. Log coupon usage to JSON file (fallback until DB columns are added)
    if data.codigo_usado and data.descuento_aplicado > 0:
        try:
            from api.descuentos import registrar_uso_codigo
            registrar_uso_codigo(pedido_id, data.id_codigo_descuento or 0, data.codigo_usado, data.descuento_aplicado, float(data.total) + data.descuento_aplicado)
        except Exception as e:
            logger.warning(f"No se pudo registrar uso de cupon: {e}")

    return _formatear_pedido(pedido_creado, incluir_tracking=True)

@router.post("/{pedido_id}/despachar")
async def despachar_pedido(pedido_id: int):
    """Marca pedido como 'En despacho' y asigna repartidor automático"""
    res = db.actualizar_estado_pedido(pedido_id, "En despacho")
    if not res.data:
        raise HTTPException(404, "Pedido no encontrado")
    from datetime import datetime, timedelta
    return {
        "mensaje": "Pedido en despacho",
        "eta": (datetime.now() + timedelta(minutes=25)).isoformat(),
        "repartidor": "Carlos R.",
        "telefono": "+51972097791"
    }


@router.patch("/{pedido_id}/cancelar")
async def cancelar_pedido(pedido_id: int):
    res_actual = db.get_pedido(pedido_id)
    if not res_actual.data:
        raise HTTPException(404, "Pedido no encontrado")
    estado_actual = res_actual.data.get("estado")
    if estado_actual in ESTADOS_BLOQUEADOS:
        raise HTTPException(403, f"No se puede cancelar un pedido en estado '{estado_actual}'.")
    if estado_actual == "Cancelado":
        raise HTTPException(400, "El pedido ya está cancelado.")
    res = db.actualizar_estado_pedido(pedido_id, "Cancelado")
    return {"mensaje": f"Pedido #{pedido_id} cancelado exitosamente", "pedido": _formatear_pedido(res.data[0]) if res.data else None}


@router.patch("/{pedido_id}/estado")
async def actualizar_estado(pedido_id: int, data: PedidoUpdate):
    if data.estado and data.estado not in ESTADOS_VALIDOS:
        raise HTTPException(400, f"Estado inválido. Válidos: {', '.join(sorted(ESTADOS_VALIDOS))}")
    limpio = data.model_dump(exclude_none=True)
    if not limpio:
        raise HTTPException(400, "No hay campos para actualizar")

    res_actual = db.get_pedido(pedido_id)
    if res_actual.data:
        estado_actual = res_actual.data.get("estado")
        if estado_actual in ESTADOS_BLOQUEADOS:
            raise HTTPException(403, f"No se puede modificar un pedido en estado '{estado_actual}'. Está bloqueado.")

    res = db.actualizar_estado_pedido(pedido_id, data.estado)
    if not res.data:
        raise HTTPException(404, "Pedido no encontrado")
    return _formatear_pedido(res.data[0])


@router.get("/exportar/csv")
async def exportar_pedidos_csv(estado: Optional[str] = Query(None)):
    import io
    import csv
    from datetime import datetime
    res = db.get_pedidos(500, 0)
    pedidos = res.data if res.data else []
    if estado:
        pedidos = [p for p in pedidos if p.get("estado") == estado]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID Pedido", "Cliente", "Total", "Fecha", "Estado"])
    for p in pedidos:
        fecha = str(p.get("fecha", ""))[:10] if p.get("fecha") else ""
        usuario = p.get("usuario") or {}
        cliente = usuario.get("username", f"Usuario #{p['id_usuario']}")
        writer.writerow([
            f"#{p['id_pedido']}",
            cliente,
            float(p["total"]),
            fecha,
            p.get("estado", ""),
        ])
    return output.getvalue()
