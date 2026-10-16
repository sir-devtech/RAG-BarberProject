"""Normalizacao de texto para a busca por palavras (portugues)."""

from __future__ import annotations

import re
import unicodedata

WORD = re.compile(r"[a-z0-9]+")
# Palavras muito comuns que nao ajudam a distinguir um chunk de outro.
STOPWORDS = frozenset(
    [
        "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
        "em", "no", "na", "nos", "nas", "para", "por", "com", "sem", "e", "ou",
        "que", "se", "eu", "voce", "vcs", "voces", "meu", "minha", "seu", "sua",
        "ao", "aos", "r", "ha", "ja", "mais", "ser", "tem",
    ]  # fmt: skip
)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """minusculas, sem acento, sem palavras comuns e com plural simplificado.

    "Preços" e "preco" viram o mesmo token; "barbeiros" vira "barbeiro". Numeros ficam
    inteiros ("250"), e e isso que permite achar um valor exato.
    """
    tokens: list[str] = []
    for word in WORD.findall(strip_accents(text).lower()):
        if word in STOPWORDS:
            continue
        if len(word) > 3 and word.endswith("s"):
            word = word[:-1]
        tokens.append(word)
    return tokens
