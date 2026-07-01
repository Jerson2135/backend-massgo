"""
MASSGO - Conexión a Supabase (PostgreSQL)
Adaptado al schema real de BD.sql
"""

from supabase import create_client, Client
from config import settings
import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)


class SupabaseDB:
    def __init__(self, url: str = None, key: str = None):
        self.url = url or settings.SUPABASE_URL
        self.key = key or settings.SUPABASE_KEY
        self.service_key = settings.SUPABASE_SERVICE_ROLE_KEY
        self.client: Client | None = None
        self.admin_client: Client | None = None

    def connect(self) -> Client:
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL y SUPABASE_KEY deben estar configurados en .env")
        self.client = create_client(self.url, self.key)
        if self.service_key:
            self.admin_client = create_client(self.url, self.service_key)
        logger.info("Conectado a Supabase")
        return self.client

    def get_client(self) -> Client:
        if not self.client:
            return self.connect()
        return self.client

    def table(self, name: str):
        return self.get_client().table(name)

    # ==================== CATEGORIAS ====================
    def get_categorias(self):
        return self.table("categoria").select("*").order("nombre").execute()

    def crear_categoria(self, data: dict):
        return self.table("categoria").insert(data).execute()

    def actualizar_categoria(self, categoria_id: int, data: dict):
        return self.table("categoria").update(data).eq("id_categoria", categoria_id).execute()

    def eliminar_categoria(self, categoria_id: int):
        return self.table("categoria").delete().eq("id_categoria", categoria_id).execute()

    # ==================== PRODUCTOS ====================
    def get_productos(self, limite: int = 50, offset: int = 0):
        return (
            self.table("producto")
            .select("*, categoria!inner(id_categoria, nombre)")
            .range(offset, offset + limite - 1)
            .execute()
        )

    def get_producto(self, producto_id: int):
        return (
            self.table("producto")
            .select("*, categoria(id_categoria, nombre)")
            .eq("id_producto", producto_id)
            .single()
            .execute()
        )

    def crear_producto(self, data: dict):
        return self.table("producto").insert(data).execute()

    def actualizar_producto(self, producto_id: int, data: dict):
        return self.table("producto").update(data).eq("id_producto", producto_id).execute()

    def eliminar_producto(self, producto_id: int):
        return self.table("producto").delete().eq("id_producto", producto_id).execute()

    def get_productos_stock_bajo(self, umbral: int = 5):
        return (
            self.table("producto")
            .select("*, categoria(nombre)")
            .lte("stock", umbral)
            .execute()
        )

    # ==================== PEDIDOS ====================
    def get_pedidos(self, limite: int = 50, offset: int = 0):
        return (
            self.table("pedido")
            .select("*, usuario(id_usuario, username, email)")
            .order("fecha", desc=True)
            .range(offset, offset + limite - 1)
            .execute()
        )

    def get_pedido(self, pedido_id: int):
        return (
            self.table("pedido")
            .select("*, usuario(id_usuario, username, email)")
            .eq("id_pedido", pedido_id)
            .single()
            .execute()
        )

    def actualizar_estado_pedido(self, pedido_id: int, estado: str):
        return (
            self.table("pedido")
            .update({"estado": estado})
            .eq("id_pedido", pedido_id)
            .execute()
        )

    def crear_pedido(self, data: dict):
        return self.table("pedido").insert(data).execute()

    # ==================== DETALLE PEDIDO ====================
    def get_detalle_pedido(self, pedido_id: int):
        return (
            self.table("detallepedido")
            .select("*, producto!inner(id_producto, nombre, imagen_url)")
            .eq("id_pedido", pedido_id)
            .execute()
        )

    def crear_detalle_pedido(self, data: dict):
        return self.table("detallepedido").insert(data).execute()

    def descontar_stock(self, producto_id: int, cantidad: int):
        res = self.table("producto").select("stock").eq("id_producto", producto_id).single().execute()
        if not res.data:
            return None
        stock_actual = res.data.get("stock", 0)
        if stock_actual < cantidad:
            return None
        nuevo_stock = stock_actual - cantidad
        nuevo_estado = "Agotado" if nuevo_stock == 0 else "Disponible"
        upd = self.table("producto").update({"stock": nuevo_stock, "estado": nuevo_estado}).eq("id_producto", producto_id).execute()
        return upd.data[0] if upd.data else None

    def get_productos_stock_multi(self, ids: list):
        return self.table("producto").select("id_producto, stock, estado").in_("id_producto", ids).execute()

    # ==================== ENVIO ====================
    def get_envio_por_pedido(self, pedido_id: int):
        res = (
            self.table("envio")
            .select("*")
            .eq("id_pedido", pedido_id)
            .execute()
        )
        if res.data:
            return type('obj', (object,), {'data': res.data[0]})()
        return type('obj', (object,), {'data': None})()

    # ==================== USUARIOS ====================
    def get_usuarios(self, limite: int = 50, offset: int = 0):
        return (
            self.table("usuario")
            .select("*, usuariorol(rol(id_rol, nombre)), personausuario(persona(id_persona, nombres, apellidos))")
            .range(offset, offset + limite - 1)
            .execute()
        )

    def get_usuario(self, usuario_id: int):
        return (
            self.table("usuario")
            .select("*, usuariorol(rol(id_rol, nombre)), personausuario(persona(id_persona, nombres, apellidos))")
            .eq("id_usuario", usuario_id)
            .single()
            .execute()
        )

    # ==================== PAGOS ====================
    def get_pagos_por_pedido(self, pedido_id: int):
        return (
            self.table("pago")
            .select("*, metodopago(nombre)")
            .eq("id_pedido", pedido_id)
            .execute()
        )

    # ==================== MÉTRICAS DASHBOARD ====================
    def get_total_pedidos(self):
        res = self.table("pedido").select("id_pedido", count="exact").execute()
        return res.count if hasattr(res, "count") else len(res.data)

    def get_pedidos_pendientes(self):
        res = (
            self.table("pedido")
            .select("id_pedido", count="exact")
            .in_("estado", ["Pendiente", "Preparando"])
            .execute()
        )
        return res.count if hasattr(res, "count") else len(res.data)

    def get_usuarios_activos(self):
        res = self.table("usuario").select("id_usuario", count="exact").eq("estado", "Activo").execute()
        return res.count if hasattr(res, "count") else len(res.data)

    def get_pedidos_recientes(self, limite: int = 5):
        return (
            self.table("pedido")
            .select("*, usuario(id_usuario, username)")
            .order("fecha", desc=True)
            .limit(limite)
            .execute()
        )

    def get_ventas_ultimos_dias(self, dias: int = 7):
        from datetime import timedelta
        desde = (date.today() - timedelta(days=dias)).isoformat()
        res = (
            self.table("pedido")
            .select("fecha, total")
            .gte("fecha", desde)
            .order("fecha")
            .execute()
        )
        return res.data if res.data else []

    # ==================== HISTORIAL USUARIO ====================
    def get_historial_usuario(self, usuario_id: int, limite: int = 20):
        """Obtiene los IDs de productos que un usuario ha comprado, del más reciente al más antiguo."""
        res = (
            self.table("detallepedido")
            .select("id_producto, pedido!inner(id_usuario, fecha)")
            .eq("pedido.id_usuario", usuario_id)
            .order("pedido.fecha", desc=True)
            .limit(limite * 3)
            .execute()
        )
        if not res.data:
            return []
        seen = set()
        historial = []
        for d in res.data:
            pid = d["id_producto"]
            if pid not in seen:
                seen.add(pid)
                historial.append(pid)
            if len(historial) >= limite:
                break
        return historial

    def get_usuario_id_por_auth(self, auth_id: str):
        """Busca el id_usuario (serial) a partir del auth_id (UUID de Supabase)."""
        try:
            res = (
                self.table("usuario")
                .select("id_usuario")
                .eq("auth_id", auth_id)
                .limit(1)
                .execute()
            )
            return res.data[0]["id_usuario"] if res.data else None
        except Exception:
            return None

    # ==================== COMPROBANTES ====================
    def get_comprobantes(self, limite: int = 50, offset: int = 0):
        return (
            self.table("comprobante")
            .select("*, pago!inner(*, metodopago(nombre), pedido!inner(id_pedido, total, id_usuario, usuario(id_usuario, username, email)))")
            .order("fecha", desc=True)
            .range(offset, offset + limite - 1)
            .execute()
        )

    def crear_comprobante(self, data: dict):
        return self.table("comprobante").insert(data).execute()

    def get_ultimo_numero_comprobante(self):
        res = self.table("comprobante").select("numero").order("id_comprobante", desc=True).limit(1).execute()
        if res.data and res.data[0].get("numero"):
            return res.data[0]["numero"]
        return None


db = SupabaseDB()
