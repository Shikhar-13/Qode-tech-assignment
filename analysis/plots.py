from __future__ import annotations

import random
from pathlib import Path

import matplotlib
import pandas as pd
matplotlib.use("Agg")  # headless-safe for scripts/CI
import matplotlib.pyplot as plt  # type: ignore[import]
import pyarrow.dataset as ds


def stream_column_batches(parquet_path: str | Path, columns: list[str], batch_size: int = 10_000):
    dataset = ds.dataset(str(parquet_path), format="parquet")
    scanner = dataset.scanner(columns=columns, batch_size=batch_size)
    for batch in scanner.to_batches():
        yield batch


def reservoir_sample(
    parquet_path: str | Path, columns: list[str], sample_size: int = 5000, seed: int = 42
) -> "pd.DataFrame":
      # local import: keep this module importable without pandas at load time

    rng = random.Random(seed)
    reservoir: list[dict] = []
    seen = 0
    for batch in stream_column_batches(parquet_path, columns):
        batch_df = batch.to_pandas()
        for _, row in batch_df.iterrows():
            seen += 1
            record = row.to_dict()
            if len(reservoir) < sample_size:
                reservoir.append(record)
            else:
                j = rng.randint(0, seen - 1)
                if j < sample_size:
                    reservoir[j] = record
    return pd.DataFrame(reservoir)


def plot_signal_with_ci(
    agg_df: "pd.DataFrame",
    raw_sample: "pd.DataFrame | None" = None,
    out_path: str | Path = "signal_plot.png",
    title: str = "Composite Sentiment Signal",
):
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    ax1.plot(agg_df.index, agg_df["signal"], color="#2563eb", linewidth=1.6, label="Composite signal")
    ax1.fill_between(
        agg_df.index, agg_df["ci_low"], agg_df["ci_high"], color="#2563eb", alpha=0.18, label="95% CI"
    )
    if raw_sample is not None and len(raw_sample):
        ax1.scatter(
            raw_sample["created_at"],
            raw_sample["composite"],
            s=6,
            color="#94a3b8",
            alpha=0.35,
            label=f"Per-tweet (sampled n={len(raw_sample)})",
            zorder=1,
        )
    ax1.set_ylabel("Signal (0-1)")
    ax1.set_title(title)
    ax1.legend(loc="upper left", fontsize=8)
    ax1.grid(alpha=0.2)

    ax2.bar(agg_df.index, agg_df["n_tweets"], width=0.03, color="#64748b")
    ax2.set_ylabel("Tweet volume")
    ax2.set_xlabel("Time")
    ax2.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)
    return str(out_path)
