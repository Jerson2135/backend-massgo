from fastapi import APIRouter, HTTPException, Query
from models import Producto, ProductoCreate, ProductoUpdate
from database import db
from typing import List, Optional

router = APIRouter(prefix="/api/productos", tags=["Productos"])


def _formatear_producto(p: dict) -> dict:
    categoria = None
    if p.get("categoria"):
        categoria = {
            "id_categoria": p["categoria"].get("id_categoria"),
            "nombre": p["categoria"].get("nombre"),
            "descripcion": p["categoria"].get("descripcion"),
        }
    return {
        "id_producto": p["id_producto"],
        "nombre": p["nombre"],
        "descripcion": p.get("descripcion"),
        "precio": float(p["precio"]),
        "stock": p["stock"],
        "estado": p.get("estado", "Disponible"),
        "id_categoria": p.get("id_categoria"),
        "es_oferta_flash": p.get("es_oferta_flash", False),
        "imagen_url": p.get("imagen_url"),
        "categoria": categoria,
    }


@router.get("/", response_model=List[Producto])
async def listar_productos(
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    categoria_id: Optional[int] = Query(None),
    busqueda: Optional[str] = Query(None),
    stock_bajo: Optional[bool] = Query(None),
):
    if stock_bajo:
        res = db.get_productos_stock_bajo()
    else:
        res = db.get_productos(limite, offset)
    productos = res.data if res.data else []

    if categoria_id:
        productos = [p for p in productos if p.get("id_categoria") == categoria_id]
    if busqueda:
        q = busqueda.lower()
        productos = [
            p for p in productos
            if q in p.get("nombre", "").lower()
            or q in (p.get("descripcion") or "").lower()
            or q in ((p.get("categoria") or {}).get("nombre") or "").lower()
        ]

    return [_formatear_producto(p) for p in productos]


@router.get("/categorias")
async def listar_categorias():
    res = db.get_categorias()
    return res.data if res.data else []


@router.get("/{producto_id}", response_model=Producto)
async def obtener_producto(producto_id: int):
    res = db.get_producto(producto_id)
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return _formatear_producto(res.data)


@router.post("/", response_model=Producto, status_code=201)
async def crear_producto(data: ProductoCreate):
    payload = data.model_dump(exclude_none=True)
    res = db.crear_producto(payload)
    if not res.data:
        raise HTTPException(500, "Error al crear producto")
    return _formatear_producto(res.data[0])


@router.put("/{producto_id}", response_model=Producto)
async def actualizar_producto(producto_id: int, data: ProductoUpdate):
    limpio = data.model_dump(exclude_none=True)
    if not limpio:
        raise HTTPException(400, "No hay campos para actualizar")
    res = db.actualizar_producto(producto_id, limpio)
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return _formatear_producto(res.data[0])


@router.delete("/{producto_id}", status_code=204)
async def eliminar_producto(producto_id: int):
    res = db.eliminar_producto(producto_id)
    if not res.data:
        raise HTTPException(404, "Producto no encontrado")
    return None


@router.get("/stock/check")
async def verificar_stock(ids: str = Query(..., description="IDs separados por coma"), cantidades: str = Query(..., description="Cantidades separadas por coma")):
    id_list = [int(x.strip()) for x in ids.split(",")]
    cant_list = [int(x.strip()) for x in cantidades.split(",")]
    if len(id_list) != len(cant_list):
        raise HTTPException(400, "IDs y cantidades deben tener la misma longitud")
    res = db.get_productos_stock_multi(id_list)
    stock_map = {p["id_producto"]: p for p in (res.data or [])}
    return [{
        "id_producto": pid,
        "nombre": stock_map[pid].get("nombre", "") if pid in stock_map else "",
        "stock": stock_map[pid].get("stock", 0) if pid in stock_map else 0,
        "solicitado": cant,
        "disponible": stock_map[pid].get("stock", 0) >= cant if pid in stock_map else False,
    } for pid, cant in zip(id_list, cant_list)]
