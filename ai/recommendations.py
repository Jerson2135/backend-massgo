"""
MASSGO - Sistema de Recomendaciones con IA
Usa productos de la BD real (id_producto, nombre, descripcion, id_categoria)
"""

import numpy as np
from typing import List, Dict, Optional
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
import logging

logger = logging.getLogger(__name__)


class RecomendadorMassGo:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=200, stop_words=None, max_df=0.85, min_df=1)
        self.productos: List[Dict] = []
        self.matriz_tfidf = None
        self.entrenado = False

    def entrenar(self, productos: List[Dict]):
        self.productos = productos
        if len(productos) < 2:
            self.entrenado = False
            return

        docs = []
        for p in productos:
            cat = (p.get("categoria") or {}).get("nombre", "") if isinstance(p.get("categoria"), dict) else str(p.get("categoria", ""))
            texto = f"{p.get('nombre', '')} {p.get('descripcion', '')} {cat}"
            docs.append(texto)

        self.matriz_tfidf = self.vectorizer.fit_transform(docs)
        self.entrenado = True
        logger.info(f"Modelo de recomendaciones entrenado con {len(productos)} productos")

    def recomendar(self, producto_id: int, top_n: int = 5) -> List[Dict]:
        if not self.entrenado:
            return []

        idx = self._buscar_indice(producto_id)
        if idx is None:
            return []

        sim = cosine_similarity(self.matriz_tfidf[idx], self.matriz_tfidf).flatten()
        indices = np.argsort(sim)[::-1][1:top_n + 1]

        return [
            {**self.productos[i], "similitud": float(sim[i])}
            for i in indices
            if sim[i] > 0.05
        ]

    def recomendar_para_usuario(self, historial_ids: List[int], top_n: int = 5) -> List[Dict]:
        if not self.entrenado or not historial_ids:
            return self._populares(top_n)

        scores = {}
        for pid in historial_ids:
            recs = self.recomendar(pid, top_n=3)
            for r in recs:
                pid_key = r.get("id_producto") or r.get("id")
                scores[pid_key] = scores.get(pid_key, 0) + r["similitud"]

        ordenados = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [
            self._buscar_producto(pid)
            for pid, _ in ordenados[:top_n]
            if self._buscar_producto(pid)
        ]

    def _populares(self, n: int) -> List[Dict]:
        return sorted(self.productos, key=lambda p: p.get("stock", 0), reverse=True)[:n]

    def _buscar_indice(self, producto_id: int) -> Optional[int]:
        for i, p in enumerate(self.productos):
            pid = p.get("id_producto") or p.get("id")
            if pid == producto_id:
                return i
        return None

    def _buscar_producto(self, producto_id: int) -> Optional[Dict]:
        for p in self.productos:
            pid = p.get("id_producto") or p.get("id")
            if pid == producto_id:
                return p
        return None


recomendador = RecomendadorMassGo()
