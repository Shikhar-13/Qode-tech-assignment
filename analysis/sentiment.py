from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Iterable
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- schema knobs: matches processing pipeline output ---
COL_ID = "tweet_id"
COL_TEXT = "content_clean"

# crude but cheap ASCII-ratio heuristic to flag likely non-English content
# (reuses the same "don't lie about confidence" principle as the dedup module)
_ASCII_RE = re.compile(r"[\x00-\x7F]")


@dataclass(frozen=True)
class SentimentResult:
    id: object
    compound: float      # VADER compound score, in [-1, 1]
    pos: float
    neu: float
    neg: float
    lang_confidence: float  # fraction of characters that are ASCII; low = treat compound cautiously


_analyzer = None  # lazy singleton; VADER lexicon load is the only "heavy" part


def _get_analyzer() -> SentimentIntensityAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentIntensityAnalyzer()
    return _analyzer


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_chars = len(_ASCII_RE.findall(text))
    return ascii_chars / max(len(text), 1)


def score_text(text: str) -> tuple[float, float, float, float]:
    analyzer = _get_analyzer()
    if not text or not text.strip():
        return 0.0, 0.0, 1.0, 0.0
    scores = analyzer.polarity_scores(text)
    return scores["compound"], scores["pos"], scores["neu"], scores["neg"]


def score_records(records: Iterable[dict]) -> list[SentimentResult]:
    out = []
    for rec in records:
        text = rec.get(COL_TEXT, "") or ""
        compound, pos, neu, neg = score_text(text)
        out.append(
            SentimentResult(
                id=rec.get(COL_ID),
                compound=compound,
                pos=pos,
                neu=neu,
                neg=neg,
                lang_confidence=round(_ascii_ratio(text), 3),
            )
        )
    return out


def score_batch_worker(batch: list[dict]) -> list[dict]:
    return [r.__dict__ for r in score_records(batch)]
