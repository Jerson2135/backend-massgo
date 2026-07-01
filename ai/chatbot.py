"""
MASSGO - Chatbot adaptado al negocio
"""

import logging
from typing import List, Dict, Optional
from config import settings

logger = logging.getLogger(__name__)

INTENCIONES = {
    "seguimiento_pedido": ["dónde está mi pedido", "seguimiento", "rastrear", "cómo va mi pedido", "estado del pedido"],
    "cancelar_pedido": ["cancelar", "cancelación", "cancelar pedido", "quiero cancelar"],
    "horario": ["horario", "abren", "cierran", "qué horas atienden", "cuándo abren"],
    "producto": ["producto", "precio", "cuánto cuesta", "disponible", "tienes", "stock", "categoría"],
    "devolucion": ["devolver", "devolución", "cambio", "reclamo", "garantía"],
    "contacto": ["contacto", "teléfono", "whatsapp", "correo", "dirección"],
    "saludo": ["hola", "buenas", "buenos días", "buenas tardes", "qué tal"],
    "despedida": ["chao", "adiós", "gracias", "hasta luego", "bye"],
}


class ChatbotMassGo:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.contexto: List[Dict] = [
            {"role": "system", "content": (
                "Eres un asistente virtual amable y profesional de MASSGO, un supermercado de barrio "
                "a domicilio en Trujillo, Perú. Respondes en español peruano de forma clara y concisa. "
                "Ayudas con: seguimiento de pedidos, información de productos, horarios (lun-dom 7am-10pm), "
                "devoluciones, cancelaciones y contacto (whatsapp, teléfono). "
                "Si no sabes algo, indica amablemente que consultes al área correspondiente."
            )}
        ]

    def detectar_intencion(self, mensaje: str) -> str:
        msg = mensaje.lower()
        for intencion, patrones in INTENCIONES.items():
            if any(p in msg for p in patrones):
                return intencion
        return "general"

    def responder_sin_openai(self, mensaje: str) -> str:
        msg = mensaje.lower()
        if "horario" in msg or "abren" in msg:
            return "Atendemos de lunes a domingo, de 7:00 a.m. a 10:00 p.m. ¿En qué más puedo ayudarte?"
        if "contacto" in msg or "teléfono" in msg or "whatsapp" in msg:
            return "Puedes contactarnos al (044) 123-4567 o escribirnos a hola@massgo.pe. También estamos en WhatsApp."
        if "devolución" in msg or "devolver" in msg:
            return "Para devoluciones, escríbenos al WhatsApp con tu número de pedido y te ayudaremos en máximo 24 horas."
        if "gracias" in msg or "chao" in msg or "adiós" in msg:
            return "¡Gracias por contactarnos! Que tengas un excelente día. Vuelve pronto."
        if "hola" in msg or "buenos" in msg:
            return "¡Hola! Soy el asistente virtual de MASSGO. ¿En qué puedo ayudarte hoy? Puedo informarte sobre pedidos, productos, horarios y más."
        return "Entiendo tu consulta. Por favor, escríbeme con más detalle o contáctanos directamente al (044) 123-4567 para ayudarte mejor."

    async def responder(self, mensaje: str, usuario_id: Optional[int] = None) -> str:
        intencion = self.detectar_intencion(mensaje)

        if not self.api_key:
            return self.responder_sin_openai(mensaje)

        try:
            import openai
            openai.api_key = self.api_key

            messages = self.contexto + [{"role": "user", "content": mensaje}]
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            respuesta = response.choices[0].message.content
            self.contexto.append({"role": "user", "content": mensaje})
            self.contexto.append({"role": "assistant", "content": respuesta})
            return respuesta

        except Exception as e:
            logger.warning(f"OpenAI no disponible, usando fallback: {e}")
            return self.responder_sin_openai(mensaje)


chatbot = ChatbotMassGo()
