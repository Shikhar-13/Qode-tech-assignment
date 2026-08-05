import json
from concurrent.futures import ProcessPoolExecutor

from processing.cleaner import clean_batch
from processing.dedup import (
    compute_minhash_batch,
    deduplicate
)
from processing.storage import write
from processing.storage import DEFAULT_PATH

def chunk(lst, size):

    for i in range(0, len(lst), size):
        yield lst[i:i + size]


def process_pipeline(raw_json):

    print("\n========== Processing ==========")

    with open(raw_json, encoding="utf-8") as f:
        raw_records = json.load(f)

    # ------------------------------------
    # Cleaning
    # ------------------------------------

    cleaned = []

    with ProcessPoolExecutor() as executor:

        batches = executor.map(
            clean_batch,
            chunk(raw_records, 200)
        )

        for batch in batches:
            cleaned.extend(batch["cleaned"])

    print(f"Cleaned : {len(cleaned)}")

    # ------------------------------------
    # MinHash
    # ------------------------------------

    with ProcessPoolExecutor() as executor:

        batches = executor.map(
            compute_minhash_batch,
            chunk(cleaned, 200)
        )

        records = []

        for batch in batches:
            records.extend(batch)

    print("MinHash computed")

    # ------------------------------------
    # Deduplication
    # ------------------------------------

    result = deduplicate(records)

    print(
        f"Removed : "
        f"{result.exact_duplicates_removed}"
    )

    print(
        f"Near duplicates : "
        f"{result.near_duplicates_flagged}"
    )

    # ------------------------------------
    # Storage
    # ------------------------------------



    write(
        result.kept,
        mode="overwrite"
    )

    print(f"Parquet Saved -> {DEFAULT_PATH}")

    return str(DEFAULT_PATH)