"""Busca hibrida: junta o ranking por significado com o ranking por palavras exatas.

Aprendizado da avaliacao (docs/aprendizado/04): fundir sempre as duas listas PIORA as
perguntas parafraseadas, porque o BM25 devolve chunks fracos que casam por palavras comuns
("valor", "comecar") e, no RRF, posicoes vizinhas valem quase o mesmo. Dar menos peso ao
BM25 nao resolve. O que resolve e usar o BM25 so quando ele esta CONFIANTE.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.ingest.chunking import Chunk
from app.retrieval.hit import Hit

RRF_K = 60  # valor classico: suaviza a diferenca entre 1o e 2o lugar
CONFIDENCE_RATIO = 1.5  # o 1o do BM25 precisa valer pelo menos 1,5x o 2o
AGREE_WITHIN = 5  # ... e estar entre os 5 primeiros da busca por significado


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[Hit]], *, top: int = 3, k: int = RRF_K
) -> list[Hit]:
    """Cada ranking da 1/(k + posicao) ao chunk. Quem esta bem nas duas listas sobe.

    Usa so a POSICAO, nao a pontuacao: cosseno (0 a 1) e BM25 (0 a dezenas) tem escalas
    diferentes e nao podem ser somados diretamente.
    """
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}
    for ranking in rankings:
        for position, hit in enumerate(ranking, start=1):
            chunks[hit.chunk.id] = hit.chunk
            scores[hit.chunk.id] = scores.get(hit.chunk.id, 0.0) + 1.0 / (k + position)
    ordered = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [Hit(chunks[chunk_id], scores[chunk_id]) for chunk_id in ordered[:top]]


def is_confident(hits: Sequence[Hit], *, ratio: float = CONFIDENCE_RATIO) -> bool:
    """True quando o 1o resultado se destaca do 2o (ou e o unico que casou).

    Um valor como "R$ 250" casa com um unico chunk: destaque claro. Palavras comuns casam
    com varios chunks de pontuacao parecida: ruido.
    """
    if not hits:
        return False
    if len(hits) == 1:
        return True
    return hits[0].score >= ratio * hits[1].score


def hybrid_search(
    dense_hits: Sequence[Hit],
    bm25_hits: Sequence[Hit],
    *,
    top: int = 3,
    ratio: float = CONFIDENCE_RATIO,
    agree_within: int | None = AGREE_WITHIN,
) -> list[Hit]:
    """Significado como base; o BM25 entra na fusao so quando merece confianca.

    Duas condicoes, porque so a pontuacao nao basta (um unico resultado fraco e um forte
    pontuam parecido): o BM25 precisa estar CONFIANTE (se destaca do 2o) e CONCORDAR com o
    significado (o 1o dele esta entre os `agree_within` primeiros do significado). Assim o
    BM25 resgata palavras raras e numeros exatos, mas nao arrasta chunks sem relacao.
    `agree_within=None` desliga a segunda condicao.
    """
    if not is_confident(bm25_hits, ratio=ratio):
        return list(dense_hits[:top])
    if agree_within is not None:
        plausible = {hit.chunk.id for hit in dense_hits[:agree_within]}
        if bm25_hits[0].chunk.id not in plausible:
            return list(dense_hits[:top])
    return reciprocal_rank_fusion([dense_hits, bm25_hits], top=top)
