"""TF-IDF con coseno, sin dependencias: preselecciona candidatos antes de gastar una llamada al modelo."""
import math
import re
import unicodedata
from collections import Counter

_STOP = set("""a al algo como con cuando de del desde donde el ella en entre es esta este esto hay la las le
lo los me mi muy no o para pero por que se sin sobre su sus también te tiene un una y ya yo nos cliente
clientes favor buenas tardes dias días hola gracias saludos ayuda""".split())


def tokens(text):
    plain = unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode()
    words = [w for w in re.findall(r"[a-z0-9]+", plain) if w not in _STOP and len(w) > 2]
    # Raíz pobre pero suficiente: "cupones" y "cupón" caen en la misma palabra.
    return [w[:-2] if w.endswith("es") and len(w) > 5 else w[:-1] if w.endswith("s") and len(w) > 4 else w
            for w in words]


class Index:
    def __init__(self, documents):
        """documents: [(id, texto)]"""
        self.ids = [d for d, _ in documents]
        counts = [Counter(tokens(text)) for _, text in documents]
        df = Counter(w for c in counts for w in c)
        n = len(documents)
        self.idf = {w: math.log((1 + n) / (1 + f)) + 1 for w, f in df.items()}
        self.vectors = [self._vector(c) for c in counts]

    def _vector(self, counts):
        vec = {w: tf * self.idf.get(w, 0) for w, tf in counts.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1
        return {w: v / norm for w, v in vec.items()}

    def search(self, text, k=5):
        query = self._vector(Counter(tokens(text)))
        scored = [(doc_id, sum(query.get(w, 0) * v for w, v in vec.items()))
                  for doc_id, vec in zip(self.ids, self.vectors)]
        return sorted((s for s in scored if s[1] > 0), key=lambda s: -s[1])[:k]
