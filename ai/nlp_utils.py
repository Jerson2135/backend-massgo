"""
MASSGO - NLP Utils
"""

import re
from typing import List, Dict, Tuple
from collections import Counter

try:
    import nltk
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)
    try:
        nltk.data.find("sentiment/vader_lexicon")
    except LookupError:
        nltk.download("vader_lexicon", quiet=True)

    from nltk.sentiment import SentimentIntensityAnalyzer
    from nltk.corpus import stopwords
    from nltk.tokenize import word_tokenize
    NLTK_DISPONIBLE = True
except Exception:
    NLTK_DISPONIBLE = False


STOPWORDS_ES = set(stopwords.words("spanish")) if NLTK_DISPONIBLE else set()


def analizar_sentimiento(texto: str) -> Dict:
    if not NLTK_DISPONIBLE:
        return {"sentimiento": "neutral", "score": 0, "positivo": 0, "negativo": 0, "neutral": 1}
    sia = SentimentIntensityAnalyzer()
    scores = sia.polarity_scores(texto)
    if scores["compound"] >= 0.05:
        sentimiento = "positivo"
    elif scores["compound"] <= -0.05:
        sentimiento = "negativo"
    else:
        sentimiento = "neutral"
    return {
        "sentimiento": sentimiento,
        "score": round(scores["compound"], 3),
        "positivo": round(scores["pos"], 3),
        "negativo": round(scores["neg"], 3),
        "neutral": round(scores["neu"], 3),
    }


def extraer_palabras_clave(texto: str, top_n: int = 10) -> List[Tuple[str, int]]:
    if not NLTK_DISPONIBLE:
        palabras = re.findall(r'\b[a-záéíóúñ]{3,}\b', texto.lower())
        return Counter(palabras).most_common(top_n)

    tokens = word_tokenize(texto.lower(), language="spanish")
    limpios = [
        t for t in tokens
        if t.isalpha() and t not in STOPWORDS_ES and len(t) > 2
    ]
    return Counter(limpios).most_common(top_n)
