import hashlib, hmac, json, httpx, logging, re, time
from fastapi import APIRouter, Request
from models import WhatsAppMessage, WhatsAppResponse
from database import db
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

OPENWA_BASE = settings.OPENWA_BASE
OPENWA_API_KEY = settings.OPENWA_API_KEY
WEBHOOK_SECRET = settings.WEBHOOK_SECRET
GEMINI_API_KEY = settings.GEMINI_API_KEY
GEMINI_MODEL = settings.GEMINI_MODEL

SYSTEM_PROMPT = """Eres el asistente virtual oficial de MassGo (massgo.pe), un supermercado de barrio a domicilio en Trujillo, Perú.

Tu función es ÚNICAMENTE ayudar con temas relacionados a MassGo. NO respondas preguntas fuera de este contexto.

## Lo que SÍ puedes hacer:
- Ayudar a encontrar productos por nombre, descripción o tipo de plato
- Consultar disponibilidad de productos en stock
- Ayudar a modificar pedidos en curso
- Explicar cómo rastrear un delivery
- Resolver reclamos o dudas sobre devoluciones y cambios
- Ayudar a armar pedidos recurrentes
- Explicar promociones, ofertas flash y medios de pago
- Dar información sobre horarios, zonas de reparto, tiempos de entrega

## Reglas:
- Sé amable, cercano y con estilo peruano
- Sé conciso (máximo 3 párrafos)
- Si no sabes algo, sugiere contactar por WhatsApp o visitar massgo.pe
- Usa emojis moderadamente
- Si preguntan algo fuera de contexto, responde que solo puedes ayudar con MassGo"""


def _obtener_catalogo() -> str:
    try:
        res = db.get_productos(limite=200)
        prods = res.data if res.data else []
        if not prods:
            return "\n## CATALOGO: (no hay productos disponibles)\n"
        partes = ["\n## CATALOGO DE PRODUCTOS (precios en Soles):\n"]
        for p in prods:
            nombre = p.get("nombre", "?")
            precio = p.get("precio", 0)
            stock = p.get("stock", 0)
            estado = p.get("estado", "Disponible")
            cat = p.get("categoria", {})
            categoria = cat.get("nombre", "") if isinstance(cat, dict) else str(cat) if cat else ""
            oferta = " 🏷️ OFERTA" if p.get("es_oferta_flash") else ""
            if estado == "Disponible" and stock > 0:
                partes.append(f"  - {nombre} - S/{float(precio):.2f} ({stock} und){' [' + categoria + ']' if categoria else ''}{oferta}")
            else:
                partes.append(f"  - {nombre} - AGOTADO")
        return "\n".join(partes)
    except Exception as e:
        logger.warning(f"No se pudo obtener catalogo: {e}")
        return "\n## CATALOGO: (error al cargar)\n"


_catalogo_cache = None

def _system_prompt() -> str:
    global _catalogo_cache
    if _catalogo_cache is None:
        _catalogo_cache = _obtener_catalogo()
    return (
        "Eres el asistente virtual oficial de MassGo (massgo.pe), un supermercado de barrio a domicilio en Trujillo, Peru.\n\n"
        "Tu funcion es UNICAMENTE ayudar con temas relacionados a MassGo. NO respondas preguntas fuera de este contexto.\n\n"
        "## Lo que SI puedes hacer:\n"
        "- Ayudar a encontrar productos por nombre, descripcion o tipo de plato\n"
        "- Consultar disponibilidad de productos en stock\n"
        "- Ayudar a modificar pedidos en curso\n"
        "- Explicar como rastrear un delivery\n"
        "- Resolver reclamos o dudas sobre devoluciones y cambios\n"
        "- Ayudar a armar pedidos recurrentes\n"
        "- Explicar promociones, ofertas flash y medios de pago\n"
        "- Dar informacion sobre horarios, zonas de reparto, tiempos de entrega\n\n"
        "## Reglas:\n"
        "- Se amable, cercano y con estilo peruano\n"
        "- Se conciso (maximo 3 parrafos)\n"
        "- Si no sabes algo, sugiere contactar por WhatsApp o visitar massgo.pe\n"
        "- Usa emojis moderadamente\n"
        "- Si preguntan algo fuera de contexto, responde que solo puedes ayudar con MassGo"
        + _catalogo_cache +
        "\n\n## Importante: USA EL CATALOGO de arriba para responder sobre productos. Si alguien busca algo, indicale el precio exacto y si hay stock. Si no hay stock, sugierile alternativas del mismo catalogo."
    )

# Cada conversación es una lista de mensajes con: {role, content, source, timestamp}
# source = "user" | "gemini" | "fallback"
conversaciones: dict[str, list[dict]] = {}

def _get_historial(numero: str) -> list[dict]:
    if numero not in conversaciones:
        conversaciones[numero] = []
    return conversaciones[numero][-40:]

def _ahora() -> float:
    return time.time()

def _agregar_mensaje(numero: str, role: str, content: str, source: str):
    if numero not in conversaciones:
        conversaciones[numero] = []
    conversaciones[numero].append({
        "role": role,
        "content": content,
        "source": source,
        "timestamp": _ahora(),
    })
    # mantener últimos 40 mensajes
    if len(conversaciones[numero]) > 40:
        conversaciones[numero] = conversaciones[numero][-40:]

def _procesar_accion_pedido(msg: str) -> str:
    patrones = [r'#MG[-\s]*(\d+)', r'MG[-\s]*(\d+)', r'pedido\s*#?\s*(\d+)', r'n[°º]\s*(\d+)']
    id_pedido = None
    for patron in patrones:
        m = re.search(patron, msg, re.IGNORECASE)
        if m:
            id_pedido = int(m.group(1))
            break
    if not id_pedido:
        return None

    es_cancelar = bool(re.search(r'cancela|cancelar|cancelo|anula|anular|anulo', msg))
    es_rastrear = bool(re.search(r'rastrea|rastrear|rastreo|donde.*est[aá]|estado', msg, re.IGNORECASE))

    if es_cancelar:
        try:
            import httpx
            r = httpx.post(f"{settings.INTERNAL_BASE}/api/pedidos/{id_pedido}/cancelar", timeout=10)
            if r.status_code == 200:
                return f"Tu pedido *#MG-{id_pedido}* ha sido cancelado exitosamente."
            else:
                detail = r.json().get("detail", "No se pudo cancelar.") if r.headers.get("content-type","").startswith("application/json") else "No se pudo cancelar."
                return f"No pude cancelar el pedido *#MG-{id_pedido}*: {detail}"
        except Exception:
            return f"Hubo un error al cancelar el pedido #MG-{id_pedido}. Inténtalo de nuevo."

    if es_rastrear:
        try:
            import httpx
            r = httpx.get(f"{settings.INTERNAL_BASE}/api/pedidos/{id_pedido}", timeout=10)
            if r.status_code == 200:
                p = r.json()
                info = f"*Estado del pedido #MG-{id_pedido}*\n"
                info += f"Estado: *{p.get('estado')}*\n"
                info += f"Total: S/{p.get('total', 0):.2f}\n"
                envio = p.get("envio")
                if envio:
                    info += f"Dirección: {envio.get('direccion_entrega', '—')}\n"
                    info += f"Envío: {envio.get('estado', 'Pendiente')}\n"
                    if envio.get("fecha_envio"):
                        info += f"Fecha estimada: {str(envio['fecha_envio'])[:16]}\n"
                if p.get("codigo_seguimiento"):
                    info += f"Código: {p['codigo_seguimiento']}\n"
                return info
            else:
                return f"No encontré el pedido *#MG-{id_pedido}*."
        except Exception:
            return f"No pude obtener información del pedido #MG-{id_pedido}."

    return None


def _responder_sin_gemini(mensaje: str) -> str:
    msg = mensaje.lower()
    accion = _procesar_accion_pedido(msg)
    if accion:
        return accion
    if "horario" in msg or "abren" in msg or "atienden" in msg:
        return "Atendemos de lunes a domingo, de 7:00 a.m. a 10:00 p.m. ¿En qué más puedo ayudarte?"
    if "contacto" in msg or "teléfono" in msg or "whatsapp" in msg:
        return "Puedes contactarnos al (044) 123-4567 o escribirnos a hola@massgo.pe."
    if "devolución" in msg or "devolver" in msg or "reclamo" in msg:
        return "Para devoluciones y reclamos, escríbenos a soporte@massgo.pe con tu número de pedido y te ayudamos en max. 24 horas."
    if "oferta" in msg or "promoción" in msg or "descuento" in msg:
        return "Actualmente tenemos ofertas en nuestra sección de productos seleccionados. Visitá massgo.pe/ofertas para verlas todas."
    if "gracias" in msg or "chao" in msg or "adiós" in msg:
        return "¡Gracias por contactarnos! Que tengas un excelente día. Vuelve pronto."
    if "hola" in msg or "buenos" in msg or "buenas" in msg:
        return "¡Hola! Soy el asistente virtual de MassGo. ¿En qué puedo ayudarte hoy? Podés consultarme sobre productos, pedidos, horarios, promociones y más."
    if "producto" in msg or "tienen" in msg or "venden" in msg:
        return "Tenemos una gran variedad de productos: lácteos, carnes, verduras, bebidas, abarrotes y más. Visitá massgo.pe para ver nuestro catálogo completo."
    return "Gracias por escribirnos. Por contáctanos directamente al (044) 123-4567 o escribinos a hola@massgo.pe para ayudarte mejor."

async def _consultar_gemini(mensaje: str, historial: list[dict]) -> str:
    # Convertir historial (formato interno) al formato que espera Gemini
    gemini_history = []
    for msg in historial:
        role = "model" if msg["role"] == "assistant" else msg["role"]
        gemini_history.append({"role": role, "parts": [{"text": msg["content"]}]})

    contents = [
        {"role": "user", "parts": [{"text": _system_prompt()}]},
        {"role": "model", "parts": [{"text": "Entendido. Soy el asistente de MassGo y solo responderé sobre eso."}]},
        *gemini_history,
        {"role": "user", "parts": [{"text": mensaje}]},
    ]

    async with httpx.AsyncClient(timeout=8) as client:
        res = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
            params={"key": GEMINI_API_KEY},
            json={
                "contents": contents,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500, "topP": 0.9},
                "safetySettings": [
                    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
                ],
            },
        )

        data = res.json()

        if not res.is_success:
            raise Exception(data.get("error", {}).get("message", f"HTTP {res.status_code}"))

        return (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "Lo siento, no pude procesar tu mensaje.")
        )

async def _enviar_whatsapp(session_id: str, chat_id: str, texto: str) -> bool:
    url = f"{OPENWA_BASE}/api/sessions/{session_id}/messages/send-text"
    headers = {"Content-Type": "application/json", "x-api-key": OPENWA_API_KEY}
    payload = {"chatId": chat_id, "text": texto}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.is_success:
                return True
            logger.error(f"Error enviando WhatsApp: {res.status_code} {res.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Excepción enviando WhatsApp: {e}")
        return False

@router.post("/webhook")
async def webhook_whatsapp(request: Request):
    raw = await request.body()
    logger.info(f"WEBHOOK RAW (primeros 300): {raw[:300]!r}")
    try:
        body = json.loads(raw)
    except Exception as e:
        logger.error(f"Error parseando JSON: {e}")
        return {"status": "error", "reason": "json_invalido"}

    logger.info(f"Evento webhook: {body.get('event')} sessionId={body.get('sessionId')}")

    if body.get("event") != "message.received":
        return {"status": "ignored", "event": body.get("event")}

    data = body.get("data", {})
    session_id = body.get("sessionId", "")
    chat_id = data.get("from", "")
    mensaje = data.get("body", "").strip()

    logger.info(f"WEBHOOK PROC: chat_id={chat_id!r} body={mensaje!r} type={data.get('type')} fromMe={data.get('fromMe')}")

    # Saltar mensajes del propio bot para evitar loops
    if data.get("fromMe"):
        logger.info(f"Mensaje propio ignorado")
        return {"status": "ignored", "reason": "fromMe"}

    if not chat_id or not mensaje:
        logger.info(f"Mensaje ignorado: sin chat_id o body")
        return {"status": "ignored", "reason": "sin_chat_id_o_body"}

    if data.get("type") not in (None, "chat", "text"):
        logger.info(f"Tipo ignorado: {data.get('type')}")
        return {"status": "ignored", "reason": "tipo_no_soportado"}

    if "@g.us" in chat_id:
        if not re.search(r"(^|\s)@\S+", mensaje):
            logger.info(f"Mensaje de grupo sin mencion: {mensaje!r}")
            return {"status": "ignored", "reason": "no_mention"}
        mensaje = re.sub(r"(^|\s)@\S+", "", mensaje).strip()
        logger.info(f"GRUPO: mencion detectada, mensaje limpio={mensaje!r}")

    numero = chat_id.split("@")[0]

    # Intentar Gemini
    respuesta = None
    fuente = "fallback"
    accion = _procesar_accion_pedido(mensaje.lower())
    if accion:
        respuesta = accion
        fuente = "accion_api"
    else:
        try:
            _agregar_mensaje(numero, "user", mensaje, "user")
            respuesta = await _consultar_gemini(mensaje, _get_historial(numero)[:-1])
            fuente = "gemini"
        except Exception as e:
            logger.warning(f"Gemini falló: {e}")

    if respuesta is None:
        respuesta = _responder_sin_gemini(mensaje)

    _agregar_mensaje(numero, "assistant", respuesta, fuente)

    ok = await _enviar_whatsapp(session_id, chat_id, respuesta)
    logger.info(f"RESPUESTA ENVIADA: ok={ok} chat={chat_id} fuente={fuente}")
    return {"status": "ok" if ok else "error_envio", "to": chat_id, "fuente": fuente}

@router.get("/conversations")
async def get_conversations():
    result = []
    for numero, msgs in conversaciones.items():
        result.append({
            "numero": numero,
            "mensajes": msgs,
        })
    return result

@router.get("/health")
async def health():
    return {"status": "ok", "service": "MassGo WhatsApp Webhook", "openwa": OPENWA_BASE}

@router.post("/test")
async def test_webhook(msg: WhatsAppMessage):
    numero = msg.numero
    mensaje = msg.mensaje

    _agregar_mensaje(numero, "user", mensaje, "user")

    try:
        respuesta = await _consultar_gemini(mensaje, _get_historial(numero))
        source = "gemini"
    except Exception:
        respuesta = _responder_sin_gemini(mensaje)
        source = "fallback"

    _agregar_mensaje(numero, "assistant", respuesta, source)
    return WhatsAppResponse(numero=numero, respuesta=respuesta)
