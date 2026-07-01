from fastapi import APIRouter
from models import MetricasDashboard, PedidoResumen, AlertaStock, DashboardData
from database import db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/metricas", response_model=MetricasDashboard)
async def obtener_metricas():
    pendientes = db.get_pedidos_pendientes()
    pedidos = db.get_total_pedidos()
    usuarios = db.get_usuarios_activos()
    return MetricasDashboard(
        pedidos_pendientes=pendientes,
        total_pedidos=pedidos,
        usuarios_activos=usuarios,
    )


@router.get("/data", response_model=DashboardData)
async def obtener_dashboard_completo():
    """Retorna métricas + pedidos recientes + alertas stock en una sola llamada"""
    pendientes = db.get_pedidos_pendientes()
    pedidos_count = db.get_total_pedidos()
    usuarios = db.get_usuarios_activos()

    # Pedidos recientes
    res_pedidos = db.get_pedidos_recientes(5)
    pedidos_recientes = []
    if res_pedidos.data:
        for p in res_pedidos.data:
            usuario = p.get("usuario") or {}
            cliente = usuario.get("username", f"Usuario #{p['id_usuario']}")
            pedidos_recientes.append(PedidoResumen(
                id_pedido=p["id_pedido"],
                cliente=cliente,
                total=float(p["total"]),
                fecha=str(p.get("fecha", ""))[:16] if p.get("fecha") else None,
                estado=p.get("estado", "Pendiente"),
            ))

    # Alertas stock
    res_stock = db.get_productos_stock_bajo(5)
    alertas_stock = []
    if res_stock.data:
        for p in res_stock.data:
            cat = (p.get("categoria") or {}).get("nombre") if p.get("categoria") else None
            alertas_stock.append(AlertaStock(
                id_producto=p["id_producto"],
                nombre=p["nombre"],
                stock=p["stock"],
                estado=p.get("estado", "Disponible"),
                categoria=cat,
            ))

    return DashboardData(
        metricas=MetricasDashboard(
            pedidos_pendientes=pendientes,
            total_pedidos=pedidos_count,
            usuarios_activos=usuarios,
        ),
        pedidos_recientes=pedidos_recientes,
        alertas_stock=alertas_stock,
    )
