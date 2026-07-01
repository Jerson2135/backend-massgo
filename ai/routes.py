import httpx, logging, base64, re
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from .recommendations import recomendador
from .predictions import predictor, PredecirVentasRequest
from .chatbot import chatbot
from .nlp_utils import analizar_sentimiento, extraer_palabras_clave
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["IA / Machine Learning"])


class RecomendacionRequest(BaseModel):
    producto_id: int
    top_n: int = 5


class RecomendacionUsuarioRequest(BaseModel):
    historial_ids: Optional[List[int]] = None
    usuario_id: Optional[int] = None
    auth_id: Optional[str] = None
    top_n: int = 5


class ChatRequest(BaseModel):
    mensaje: str
    usuario_id: Optional[int] = None


class SentimientoRequest(BaseModel):
    texto: str


@router.post("/recomendar/producto")
async def recomendar_producto(data: RecomendacionRequest):
    if not recomendador.entrenado:
        raise HTTPException(400, "Modelo de recomendaciones no entrenado. POST /api/ai/entrenar/recomendaciones primero.")
    return recomendador.recomendar(data.producto_id, data.top_n)


@router.post("/recomendar/usuario")
async def recomendar_para_usuario(data: RecomendacionUsuarioRequest):
    from database import db

    if not recomendador.entrenado:
        res = db.get_productos(500)
        productos = res.data if res.data else []
        if productos:
            recomendador.entrenar(productos)

    historial_ids = data.historial_ids
    if not historial_ids:
        uid = data.usuario_id
        if not uid and data.auth_id:
            uid = db.get_usuario_id_por_auth(data.auth_id)
        if uid:
            historial_ids = db.get_historial_usuario(uid, limite=20) or []

    if not historial_ids:
        return recomendador._populares(data.top_n)

    return recomendador.recomendar_para_usuario(historial_ids, data.top_n)


@router.post("/predecir/ventas")
async def predecir_ventas(data: PredecirVentasRequest = PredecirVentasRequest()):
    if not predictor.entrenado_ventas:
        raise HTTPException(400, "Modelo de ventas no entrenado. POST /api/ai/entrenar/predicciones primero.")
    return {"predicciones": predictor.predecir_ventas(data.dias)}


@router.post("/predecir/stock-critico")
async def predecir_stock_critico():
    from database import db
    res = db.get_productos(200)
    productos = res.data if res.data else []
    if not productos:
        return {"en_riesgo": []}
    return {"en_riesgo": predictor.predecir_stock_critico(productos)}


@router.post("/chat")
async def chat(data: ChatRequest):
    respuesta = await chatbot.responder(data.mensaje, data.usuario_id)
    return {"respuesta": respuesta, "intencion": chatbot.detectar_intencion(data.mensaje)}


@router.post("/sentimiento")
async def sentimiento(data: SentimientoRequest):
    return analizar_sentimiento(data.texto)


@router.post("/palabras-clave")
async def palabras_clave(data: SentimientoRequest):
    return {"palabras_clave": extraer_palabras_clave(data.texto)}


@router.post("/entrenar/recomendaciones")
async def entrenar_recomendaciones():
    from database import db
    res = db.get_productos(500)
    productos = res.data if res.data else []
    if not productos:
        raise HTTPException(400, "No hay productos en la base de datos")
    recomendador.entrenar(productos)
    return {"mensaje": f"Modelo entrenado con {len(productos)} productos"}


@router.post("/entrenar/predicciones")
async def entrenar_predicciones():
    from database import db
    res = db.get_pedidos(500)
    pedidos = res.data if res.data else []
    if pedidos:
        predictor.entrenar_ventas(pedidos)
    res_prod = db.get_productos(200)
    productos = res_prod.data if res_prod.data else []
    if productos:
        predictor.entrenar_stock(productos)
    return {"mensaje": f"Modelos entrenados: {len(pedidos)} pedidos, {len(productos)} productos"}


class GeminiProxyRequest(BaseModel):
    contents: list
    generationConfig: Optional[dict] = None
    safetySettings: Optional[list] = None


@router.post("/gemini-proxy")
async def gemini_proxy(data: GeminiProxyRequest):
    """Proxy para Gemini API — la key nunca sale del backend."""
    if not settings.GEMINI_API_KEY:
        raise HTTPException(503, "Gemini API key no configurada en el servidor")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": data.contents,
        "generationConfig": data.generationConfig or {"temperature": 0.7, "maxOutputTokens": 500, "topP": 0.9},
        "safetySettings": data.safetySettings or [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
            data_res = res.json()
            if not res.is_success:
                raise HTTPException(502, data_res.get("error", {}).get("message", f"Gemini HTTP {res.status_code}"))
            return data_res
    except httpx.TimeoutException:
        raise HTTPException(504, "Gemini API no respondió a tiempo")


@router.post("/escanear-producto")
async def escanear_producto(file: UploadFile = File(...)):
    """Recibe una imagen, la analiza con Gemini y retorna productos coincidentes de la BD."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Solo se permiten imágenes (PNG, JPG, WebP, etc.)")
    if not settings.GEMINI_API_KEY:
        raise HTTPException(503, "Gemini API no configurada")

    contents = await file.read()
    if len(contents) > 4 * 1024 * 1024:
        raise HTTPException(413, "La imagen no puede superar los 4 MB")

    b64 = base64.b64encode(contents).decode()
    mime = file.content_type

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [{
            "parts": [
                {"text": "Eres un asistente de identificación de productos. Identifica el producto en esta imagen. Responde ÚNICAMENTE con el nombre del producto y hasta 4 palabras clave separadas por comas, en español. Ejemplo: 'arroz extra, costeño, bolsa 1kg' o 'yogurt, gloria, fresa, pack 4'. No des explicaciones ni texto adicional."},
                {"inline_data": {"mime_type": mime, "data": b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 100, "topP": 0.9},
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            res = await client.post(url, params={"key": settings.GEMINI_API_KEY}, json=payload)
            gemini_data = res.json()
            if not res.is_success:
                raise HTTPException(502, gemini_data.get("error", {}).get("message", f"Gemini error {res.status_code}"))
    except httpx.TimeoutException:
        raise HTTPException(504, "Gemini no respondió a tiempo")

    # Extraer texto de la respuesta de Gemini
    try:
        texto = gemini_data["candidates"][0]["content"]["parts"][0]["text"]
        texto = re.sub(r'[^\w\s,áéíóúñü]', '', texto).strip()
    except (KeyError, IndexError):
        raise HTTPException(502, "No se pudo analizar la imagen con Gemini")

    keywords = [kw.strip().lower() for kw in texto.split(",") if kw.strip()]
    if not keywords:
        raise HTTPException(502, "Gemini no pudo identificar el producto")

    # Buscar productos en la BD
    from database import db
    prods_res = db.get_productos(500)
    productos = prods_res.data if prods_res.data else []
    if not productos:
        return []

    def puntuar(p):
        nombre = ((p.get("nombre") or "") + " " + (p.get("descripcion") or "")).lower()
        cat = (p.get("categoria") or {}).get("nombre", "").lower() if isinstance(p.get("categoria"), dict) else str(p.get("categoria", "")).lower()
        texto_completo = f"{nombre} {cat}"
        score = sum(2 if kw in nombre else 1 if kw in texto_completo else 0 for kw in keywords)
        return score

    scored = [(puntuar(p), p) for p in productos if puntuar(p) > 0]
    scored.sort(key=lambda x: x[0], reverse=True)
    matches = [p for _, p in scored[:10]]

    if not matches:
        raise HTTPException(404, f"No se encontraron productos para: {', '.join(keywords)}")

    return matches
