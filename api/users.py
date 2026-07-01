from fastapi import APIRouter, HTTPException, Query
from models import Usuario
from database import db
from typing import List

router = APIRouter(prefix="/api/usuarios", tags=["Usuarios"])


def _formatear_usuario(u: dict) -> dict:
    nombres = ""
    apellidos = ""
    pu = u.get("personausuario")
    if pu and isinstance(pu, list) and len(pu) > 0:
        persona = pu[0].get("persona") or {}
        nombres = persona.get("nombres", "")
        apellidos = persona.get("apellidos", "")

    roles = []
    ur_list = u.get("usuariorol")
    if ur_list and isinstance(ur_list, list):
        for ur in ur_list:
            rol = ur.get("rol") or {}
            if rol.get("nombre"):
                roles.append(rol["nombre"])

    return {
        "id_usuario": u["id_usuario"],
        "username": u["username"],
        "email": u["email"],
        "estado": u.get("estado", "Activo"),
        "fecha_registro": str(u.get("fecha_registro")) if u.get("fecha_registro") else None,
        "nombres": nombres,
        "apellidos": apellidos,
        "roles": roles,
    }


def _nombres_usuario(u: dict) -> str:
    pu = u.get("personausuario")
    if pu and isinstance(pu, list) and len(pu) > 0:
        p = pu[0].get("persona") or {}
        return " ".join(filter(None, [p.get("nombres", ""), p.get("apellidos", "")]))
    return ""


@router.get("/", response_model=List[Usuario])
async def listar_usuarios(
    limite: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    busqueda: str = Query(None),
):
    res = db.get_usuarios(limite, offset)
    usuarios = res.data if res.data else []

    if busqueda:
        q = busqueda.lower()
        usuarios = [
            u for u in usuarios
            if q in u.get("username", "").lower()
            or q in u.get("email", "").lower()
            or q in _nombres_usuario(u).lower()
        ]

    return [_formatear_usuario(u) for u in usuarios]


@router.get("/{usuario_id}", response_model=Usuario)
async def obtener_usuario(usuario_id: int):
    res = db.get_usuario(usuario_id)
    if not res.data:
        raise HTTPException(404, "Usuario no encontrado")
    return _formatear_usuario(res.data)
