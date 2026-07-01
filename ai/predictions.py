"""
MASSGO - Predicciones con Machine Learning
Adaptado a schema real: pedido.fecha, pedido.total, producto.stock
"""

import numpy as np
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.preprocessing import StandardScaler
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)


class PredecirVentasRequest(BaseModel):
    dias: int = 7


class PredictorMassGo:
    def __init__(self):
        self.modelo_ventas = LinearRegression()
        self.modelo_stock = LogisticRegression(max_iter=500)
        self.scaler = StandardScaler()
        self.entrenado_ventas = False
        self.entrenado_stock = False

    def entrenar_ventas(self, pedidos: List[Dict]):
        if len(pedidos) < 7:
            logger.warning("Datos insuficientes para entrenar modelo de ventas")
            return

        dias = np.array(range(len(pedidos))).reshape(-1, 1)
        ventas = np.array([float(p["total"]) for p in pedidos])
        self.modelo_ventas.fit(dias, ventas)
        self.entrenado_ventas = True
        logger.info(f"Modelo de ventas entrenado con {len(pedidos)} pedidos")

    def predecir_ventas(self, dias_futuros: int = 7) -> List[float]:
        if not self.entrenado_ventas:
            return []
        ultimo = len(range(len(self.modelo_ventas.coef_)))
        futuros = np.array(range(ultimo, ultimo + dias_futuros)).reshape(-1, 1)
        return [max(0, round(v, 2)) for v in self.modelo_ventas.predict(futuros)]

    def entrenar_stock(self, productos: List[Dict]):
        if len(productos) < 5:
            logger.warning("Datos insuficientes para entrenar modelo de stock")
            return

        X, y = [], []
        for p in productos:
            precio = float(p.get("precio", 0))
            stock = p.get("stock", 0)
            X.append([precio, stock])
            y.append(1 if stock <= 5 else 0)

        X = np.array(X)
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.modelo_stock.fit(X_scaled, y)
        self.entrenado_stock = True
        logger.info(f"Modelo de stock crítico entrenado con {len(productos)} productos")

    def predecir_stock_critico(self, productos: List[Dict]) -> List[Dict]:
        if not self.entrenado_stock:
            return [p for p in productos if p.get("stock", 0) <= 5]

        X = [[float(p.get("precio", 0)), p.get("stock", 0)] for p in productos]
        X_scaled = self.scaler.transform(np.array(X))
        probas = self.modelo_stock.predict_proba(X_scaled)[:, 1]

        return [
            {**productos[i], "probabilidad_riesgo": round(float(probas[i]), 3)}
            for i in range(len(productos))
            if probas[i] > 0.5
        ]

    def detectar_tendencias(self, pedidos: List[Dict]) -> List[Dict]:
        if not pedidos:
            return []
        ventas_diarias = {}
        for p in pedidos:
            fecha = str(p.get("fecha", ""))[:10] if p.get("fecha") else ""
            if fecha:
                ventas_diarias[fecha] = ventas_diarias.get(fecha, 0) + float(p["total"])

        fechas = sorted(ventas_diarias.keys())
        if len(fechas) < 3:
            return []

        valores = [ventas_diarias[f] for f in fechas]
        pendiente = np.polyfit(range(len(valores)), valores, 1)[0]

        return [{
            "periodo": f"{fechas[0]} a {fechas[-1]}",
            "dias": len(fechas),
            "tendencia": round(pendiente, 2),
            "direccion": "creciente" if pendiente > 0 else ("decreciente" if pendiente < 0 else "estable"),
        }]


predictor = PredictorMassGo()
