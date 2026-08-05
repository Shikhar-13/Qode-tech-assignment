"""
cleaner.py
----------
Cleans and normalizes raw tweet records prior to deduplication and storage.

Design notes
------------
- Runs as a pure function per-record (`clean_record`) so it is trivially
  parallelizable across a ProcessPoolExecutor: no shared state, no I/O,
  deterministic output for identical input.
- Unicode NFKC normalization handles Devanagari (Hindi) text, emoji,
  and visually-similar "confusable" characters consistently -- important
  since our source data is heavily code-mixed (Hindi/English) financial
  Twitter content.
- We deliberately keep two text fields:
    content        -> original, untouched (for display / audit trail)
    content_clean  -> normalized, lowercased-where-safe, whitespace-collapsed
                       (used for hashing, TF-IDF, and dedup matching)
  We never mutate the original so nothing is lost for downstream use cases
  we haven't anticipated yet.
"""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Zero-width and control characters sometimes used to break naive
# duplicate-detection (zero-width space/joiner, soft hyphen, BOM, etc.)
_INVISIBLE_CHARS_RE = re.compile(
    "[\u200b\u200c\u200d\u200e\u200f\ufeff\u00ad\u2060]"
)

_WHITESPACE_RE = re.compile(r"\s+")
_URL_RE = re.compile(r"https?://\S+")
_CASHTAG_RE = re.compile(r"(?<![\w$])\$[A-Za-z]{2,6}(?:-[A-Za-z])?\b")
_HASHTAG_RE = re.compile(r"#(\w+)")
_MENTION_RE = re.compile(r"@(\w+)")


def _strip_invisible(text: str) -> str:
    return _INVISIBLE_CHARS_RE.sub("", text)


def _normalize_unicode(text: str) -> str:
    """NFKC normalization: folds compatibility characters, fixes many
    obfuscation tricks (fullwidth chars, combining marks) while preserving
    Devanagari and other scripts correctly."""
    return unicodedata.normalize("NFKC", text)


def normalize_text(raw: str) -> str:
    """
    Produce the canonical form of tweet text used for hashing / TF-IDF /
    near-duplicate matching. NOT used for display.
    """
    if not raw:
        return ""
    text = html.unescape(raw)
    text = _strip_invisible(text)
    text = _normalize_unicode(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def extract_hashtags(text: str) -> List[str]:
    return sorted({f"#{m}" for m in _HASHTAG_RE.findall(text)})


def extract_mentions(text: str) -> List[str]:
    return sorted({f"@{m}" for m in _MENTION_RE.findall(text)})


def extract_cashtags(text: str) -> List[str]:
    return sorted(set(_CASHTAG_RE.findall(text)))


def content_hash(normalized_text: str) -> str:
    """Stable hash of normalized content, used for exact-duplicate detection."""
    return hashlib.sha256(normalized_text.lower().encode("utf-8")).hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        # Handles "...Z" ISO format from the scraper
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


class RecordValidationError(ValueError):
    """Raised when a raw record is missing required fields."""


REQUIRED_FIELDS = ("tweet_id", "username", "content")


def clean_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean a single raw tweet dict into the canonical schema used downstream.
    Pure function -> safe to run inside a worker process.

    Raises RecordValidationError for unusable records (caller decides
    whether to log-and-skip or fail the batch).
    """
    missing = [f for f in REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise RecordValidationError(f"missing required fields: {missing}")

    raw_content = str(raw["content"])
    clean_content = normalize_text(raw_content)

    ts = _parse_timestamp(raw.get("timestamp"))
    engagement = raw.get("engagement") or {}

    return {
        "tweet_id": str(raw["tweet_id"]).strip(),
        "username": str(raw["username"]).strip().lstrip("@"),
        "timestamp": ts,
        "date": ts.date().isoformat() if ts else None,
        "content": raw_content,
        "content_clean": clean_content,
        "content_hash": content_hash(clean_content),
        "hashtags": raw.get("hashtags") or extract_hashtags(raw_content),
        "mentions": raw.get("mentions") or extract_mentions(raw_content),
        "cashtags": extract_cashtags(raw_content),
        "likes": _safe_int(engagement.get("likes")),
        "replies": _safe_int(engagement.get("replies")),
        "retweets": _safe_int(engagement.get("retweets")),
        "views": _safe_int(engagement.get("views")),
        "tweet_url": raw.get("tweet_url", ""),
        "ingested_at": datetime.now(timezone.utc),
    }


def clean_batch(raw_records: List[Dict[str, Any]]) -> Dict[str, list]:
    """
    Clean a batch of records. Designed to be the unit of work submitted to
    a ProcessPoolExecutor -- one call per chunk, not one call per record,
    to keep IPC overhead low relative to the (cheap) per-record work.

    Returns {"cleaned": [...], "errors": [...]} rather than raising, so a
    handful of malformed records never take down an entire worker's batch.
    """
    cleaned, errors = [], []
    for raw in raw_records:
        try:
            cleaned.append(clean_record(raw))
        except RecordValidationError as exc:
            errors.append({"raw": raw, "error": str(exc)})
    return {"cleaned": cleaned, "errors": errors}
