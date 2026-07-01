from fastapi import APIRouter, HTTPException
from models import Categoria, CategoriaCreate, CategoriaUpdate
from database import db
from typing import List

router = APIRouter(prefix="/api/categorias", tags=["Categorías"])


@router.get("/", response_model=List[Categoria])
async def listar_categorias():
    res = db.get_categorias()
    return res.data if res.data else []


@router.get("/{categoria_id}", response_model=Categoria)
async def obtener_categoria(categoria_id: int):
    res = db.table("categoria").select("*").eq("id_categoria", categoria_id).single().execute()
    if not res.data:
        raise HTTPException(404, "Categoría no encontrada")
    return res.data


@router.post("/", response_model=Categoria, status_code=201)
async def crear_categoria(data: CategoriaCreate):
    res = db.crear_categoria(data.model_dump())
    if not res.data:
        raise HTTPException(400, "No se pudo crear la categoría")
    return res.data[0] if isinstance(res.data, list) else res.data


@router.put("/{categoria_id}", response_model=Categoria)
async def actualizar_categoria(categoria_id: int, data: CategoriaUpdate):
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(400, "No hay campos para actualizar")
    res = db.actualizar_categoria(categoria_id, payload)
    if not res.data:
        raise HTTPException(404, "Categoría no encontrada")
    return res.data[0] if isinstance(res.data, list) else res.data


@router.delete("/{categoria_id}")
async def eliminar_categoria(categoria_id: int):
    res = db.eliminar_categoria(categoria_id)
    if not res.data:
        raise HTTPException(404, "Categoría no encontrada")
    return {"mensaje": "Categoría eliminada"}
