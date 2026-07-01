from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ==================== CATEGORIAS ====================
class Categoria(BaseModel):
    id_categoria: int
    nombre: str
    descripcion: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== PRODUCTOS ====================
class ProductoBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None
    precio: float = Field(gt=0)
    stock: int = Field(ge=0)
    estado: str = "Disponible"
    id_categoria: Optional[int] = None
    es_oferta_flash: bool = False
    imagen_url: Optional[str] = None


class ProductoCreate(ProductoBase):
    pass


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    precio: Optional[float] = None
    stock: Optional[int] = None
    estado: Optional[str] = None
    id_categoria: Optional[int] = None
    es_oferta_flash: Optional[bool] = None
    imagen_url: Optional[str] = None


class Producto(ProductoBase):
    id_producto: int
    categoria: Optional[Categoria] = None

    class Config:
        from_attributes = True


# ==================== DETALLE PEDIDO ====================
class DetallePedido(BaseModel):
    id_detalle: int
    id_pedido: int
    id_producto: int
    cantidad: int
    precio_unitario: float
    producto_nombre: Optional[str] = None
    producto_imagen: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== ENVIO ====================
class Envio(BaseModel):
    id_envio: int
    id_pedido: int
    direccion_entrega: str
    estado: str = "Pendiente"
    fecha_envio: Optional[datetime] = None
    fecha_entrega: Optional[datetime] = None

    class Config:
        from_attributes = True


# ==================== PAGO ====================
class Pago(BaseModel):
    id_pago: int
    id_pedido: int
    monto: float
    fecha: Optional[datetime] = None
    metodo_pago: Optional[str] = None

    class Config:
        from_attributes = True


# ==================== PEDIDOS ====================
class PedidoCreate(BaseModel):
    id_usuario: int
    total: float
    estado: str = "Preparando"


class PedidoUpdate(BaseModel):
    estado: Optional[str] = None


class Pedido(BaseModel):
    id_pedido: int
    id_usuario: int
    fecha: Optional[datetime] = None
    estado: str = "Pendiente"
    total: float
    cliente_nombre: Optional[str] = None
    codigo_seguimiento: Optional[str] = None
    detalles: List[DetallePedido] = []
    envio: Optional[Envio] = None
    pagos: List[Pago] = []
    codigo_usado: Optional[str] = None
    descuento_aplicado: float = 0
    id_codigo_descuento: Optional[int] = None

    class Config:
        from_attributes = True


# ==================== USUARIOS ====================
class Usuario(BaseModel):
    id_usuario: int
    username: str
    email: str
    estado: str = "Activo"
    fecha_registro: Optional[datetime] = None
    nombres: Optional[str] = None
    apellidos: Optional[str] = None
    roles: List[str] = []

    class Config:
        from_attributes = True


# ==================== DASHBOARD ====================
class MetricasDashboard(BaseModel):
    pedidos_pendientes: int
    total_pedidos: int
    usuarios_activos: int
    tendencia_pendientes: float = 0.0
    tendencia_pedidos: float = 8.3
    tendencia_usuarios: float = 3.2


class CategoriaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None


class CategoriaUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None


class ComprobanteResumen(BaseModel):
    id_comprobante: int
    tipo: str
    numero: str
    fecha: Optional[datetime] = None
    monto: float
    metodo_pago: Optional[str] = None
    id_pedido: int
    cliente: Optional[str] = None
    email: Optional[str] = None
    total_pedido: Optional[float] = None


class PedidoResumen(BaseModel):
    id_pedido: int
    cliente: str
    total: float
    fecha: Optional[str] = None
    estado: str


class AlertaStock(BaseModel):
    id_producto: int
    nombre: str
    stock: int
    estado: str
    categoria: Optional[str] = None


class DashboardData(BaseModel):
    metricas: MetricasDashboard
    pedidos_recientes: List[PedidoResumen]
    alertas_stock: List[AlertaStock]


# ==================== WHATSAPP ====================
class WhatsAppMessage(BaseModel):
    numero: str
    mensaje: str


class WhatsAppResponse(BaseModel):
    numero: str
    respuesta: str
