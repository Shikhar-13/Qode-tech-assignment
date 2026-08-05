from __future__ import annotations
from typing import Iterable
import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

COL_ID = "tweet_id"
COL_TEXT = "content_clean"

DEFAULT_VECTORIZER_KWARGS = dict(
    max_features=5000,
    ngram_range=(1, 2),
    min_df=2,          # drop hapax legomena (typos, one-off garbage tokens)
    max_df=0.6,         # drop near-universal tokens (stopword-like noise)
    sublinear_tf=True,  # log-scale term frequency, standard for short docs
)


def fit_tfidf(
    texts: Iterable[str], **vectorizer_kwargs
) -> tuple[TfidfVectorizer, sp.csr_matrix]:
    kwargs = {**DEFAULT_VECTORIZER_KWARGS, **vectorizer_kwargs}
    vectorizer = TfidfVectorizer(**kwargs)
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def top_terms_per_doc(
    vectorizer: TfidfVectorizer, matrix: sp.csr_matrix, row_idx: int, k: int = 5
) -> list[tuple[str, float]]:
    feature_names = vectorizer.get_feature_names_out()
    row = matrix.getrow(row_idx)
    if row.nnz == 0:
        return []
    top_indices = row.data.argsort()[::-1][:k]
    cols = row.indices[top_indices]
    vals = row.data[top_indices]
    return [(feature_names[c], float(v)) for c, v in zip(cols, vals)]


def doc_tfidf_weight(matrix: sp.csr_matrix, row_idx: int) -> float:
    row = matrix.getrow(row_idx)
    if row.nnz == 0:
        return 0.0
    return float(row.data.mean())


def all_doc_weights(matrix: sp.csr_matrix) -> np.ndarray:
    sums = np.asarray(matrix.sum(axis=1)).ravel()
    nnz_per_row = np.diff(matrix.indptr)
    with np.errstate(divide="ignore", invalid="ignore"):
        means = np.where(nnz_per_row > 0, sums / np.maximum(nnz_per_row, 1), 0.0)
    return means
