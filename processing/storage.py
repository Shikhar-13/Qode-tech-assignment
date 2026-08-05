from __future__ import annotations
from pathlib import Path
from typing import List
import pyarrow as pa
import pyarrow.parquet as pq
from utils.logging_config import get_logger


logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_PATH = DATA_DIR / "tweets.parquet"

SCHEMA = pa.schema(
    [
        pa.field("tweet_id", pa.string()),
        pa.field("username", pa.string()),
        pa.field("timestamp", pa.timestamp("us", tz="UTC")),
        pa.field("date", pa.string()),  # ISO date string; partition key when we split
        pa.field("content", pa.string()),
        pa.field("content_clean", pa.string()),
        pa.field("content_hash", pa.string()),
        pa.field("hashtags", pa.list_(pa.string())),
        pa.field("mentions", pa.list_(pa.string())),
        pa.field("cashtags", pa.list_(pa.string())),
        pa.field("likes", pa.int32()),
        pa.field("replies", pa.int32()),
        pa.field("retweets", pa.int32()),
        pa.field("views", pa.int32()),
        pa.field("tweet_url", pa.string()),
        pa.field("duplicate_cluster_id", pa.string()),
        pa.field("is_duplicate", pa.bool_()),
        pa.field("ingested_at", pa.timestamp("us", tz="UTC")),
    ]
)


def _to_table(records: List[dict]) -> pa.Table:
    # Build column-wise to match SCHEMA field order/types exactly, so
    # malformed records fail loudly here rather than corrupting the file.
    columns = {field.name: [] for field in SCHEMA}
    for r in records:
        for field in SCHEMA:
            columns[field.name].append(r.get(field.name))
    arrays = [pa.array(columns[f.name], type=f.type) for f in SCHEMA]
    return pa.Table.from_arrays(arrays, schema=SCHEMA)


def write(records: List[dict], path: Path = DEFAULT_PATH, mode: str = "append") -> None:
    if not records:
        logger.info("write() called with 0 records, skipping")
        return

    new_table = _to_table(records)

    if mode == "append" and path.exists():
        existing = pq.read_table(path)
        combined = pa.concat_tables([existing, new_table])
        pq.write_table(combined, path, compression="snappy")
        logger.info("appended %d rows -> %d total in %s", len(records), combined.num_rows, path)
    else:
        pq.write_table(new_table, path, compression="snappy")
        logger.info("wrote %d rows to %s (mode=%s)", len(records), path, mode)


def read(path: Path = DEFAULT_PATH, columns: List[str] | None = None) -> pa.Table:
    if not path.exists():
        raise FileNotFoundError(f"no Parquet store at {path} -- run the pipeline first")
    return pq.read_table(path, columns=columns)


def read_pandas(path: Path = DEFAULT_PATH, columns: List[str] | None = None):
    return read(path, columns=columns).to_pandas()
