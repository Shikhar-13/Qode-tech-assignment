from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set
from datasketch import MinHash, MinHashLSH
from utils.logging_config import get_logger


logger = get_logger(__name__)

NUM_PERM = 128          # MinHash permutations: accuracy/speed tradeoff
SHINGLE_SIZE = 4         # character n-gram size for shingling
JACCARD_THRESHOLD = 0.72  # empirically: catches the garbled-template spam
                          # pattern without merging genuinely different
                          # tweets that happen to share hashtags/cashtags


def _shingles(text: str, k: int = SHINGLE_SIZE) -> Set[str]:
    text = text.replace(" ", "")
    if len(text) < k:
        return {text} if text else set()
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def _minhash_for(text: str) -> MinHash:
    mh = MinHash(num_perm=NUM_PERM)
    for shingle in _shingles(text):
        mh.update(shingle.encode("utf-8"))
    return mh


@dataclass
class DedupResult:
    kept: List[dict] = field(default_factory=list)
    exact_duplicates_removed: int = 0
    near_duplicates_flagged: int = 0
    clusters: Dict[str, List[str]] = field(default_factory=dict)  # cluster_id -> [tweet_id]


def compute_minhash_batch(records: List[dict]) -> List[dict]:
    out = []
    for r in records:
        mh = _minhash_for(r["content_clean"])
        out.append({**r, "_minhash": mh})
    return out


def deduplicate(records: List[dict]) -> DedupResult:
    result = DedupResult()

    # --- Stage 1: exact tweet_id ---
    seen_ids: Set[str] = set()
    stage1_survivors = []
    for r in records:
        if r["tweet_id"] in seen_ids:
            result.exact_duplicates_removed += 1
            continue
        seen_ids.add(r["tweet_id"])
        stage1_survivors.append(r)

    # --- Stage 2: exact content hash ---
    seen_hashes: Set[str] = set()
    stage2_survivors = []
    for r in stage1_survivors:
        h = r["content_hash"]
        if h in seen_hashes:
            result.exact_duplicates_removed += 1
            continue
        seen_hashes.add(h)
        stage2_survivors.append(r)

    logger.info(
        "stage1+2 exact dedup: %d -> %d (removed %d)",
        len(records), len(stage2_survivors), result.exact_duplicates_removed,
    )

    # --- Stage 3: MinHash/LSH near-duplicate clustering ---
    lsh = MinHashLSH(threshold=JACCARD_THRESHOLD, num_perm=NUM_PERM)
    cluster_of: Dict[str, str] = {}  # tweet_id -> cluster representative tweet_id

    for r in stage2_survivors:
        tid = r["tweet_id"]
        mh = r.get("_minhash") or _minhash_for(r["content_clean"])
        matches = lsh.query(mh)

        if matches:
            representative = cluster_of.get(matches[0], matches[0])
            cluster_of[tid] = representative
            result.clusters.setdefault(representative, []).append(tid)
            result.near_duplicates_flagged += 1
        else:
            lsh.insert(tid, mh)
            cluster_of[tid] = tid  # representative of its own (so-far) singleton cluster

    for r in stage2_survivors:
        tid = r["tweet_id"]
        representative = cluster_of[tid]
        r["duplicate_cluster_id"] = representative
        r["is_duplicate"] = representative != tid
        r.pop("_minhash", None)  # not serializable to Parquet, drop before storage
        result.kept.append(r)

    logger.info(
        "stage3 near-dup clustering: flagged %d near-duplicates across %d clusters",
        result.near_duplicates_flagged, len(result.clusters),
    )
    return result
