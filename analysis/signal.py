from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import pandas as pd

COL_ID = "tweet_id"
COL_TIMESTAMP = "timestamp"
ENGAGEMENT_COLS = ("likes", "retweets", "replies", "views")


@dataclass(frozen=True)
class SignalWeights:
    sentiment: float = 0.5
    tfidf_weight: float = 0.3
    volume: float = 0.2

    def normalized(self) -> "SignalWeights":
        total = self.sentiment + self.tfidf_weight + self.volume
        return SignalWeights(
            self.sentiment / total, self.tfidf_weight / total, self.volume / total
        )


def compute_engagement_weight(df: pd.DataFrame) -> np.ndarray:
    likes = df.get("likes", pd.Series(0, index=df.index)).fillna(0)
    retweets = df.get("retweets", pd.Series(0, index=df.index)).fillna(0)
    replies = df.get("replies", pd.Series(0, index=df.index)).fillna(0)
    raw = likes + 2.0 * retweets + 1.5 * replies
    return np.log1p(raw.to_numpy(dtype=float))


def _minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def build_feature_frame(
    sentiment_results: list[dict],
    tfidf_weights: np.ndarray,
    ids_in_tfidf_order: list,
    timestamps: pd.Series,
    engagement_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    sent_df = pd.DataFrame(sentiment_results)
    # sentiment.SentimentResult always names its key column "id" regardless
    # of the source schema's actual id column name; align it to COL_ID here.
    if "id" in sent_df.columns and COL_ID != "id":
        sent_df = sent_df.rename(columns={"id": COL_ID})
    tfidf_df = pd.DataFrame({COL_ID: ids_in_tfidf_order, "tfidf_weight": tfidf_weights})
    merged = sent_df.merge(tfidf_df, on=COL_ID, how="inner", validate="one_to_one")
    if len(merged) != len(sent_df):
        missing = len(sent_df) - len(merged)
        raise ValueError(
            f"{missing} ids in sentiment results had no matching TF-IDF row; "
            "check that both stages ran over the same record set."
        )
    merged[COL_TIMESTAMP] = timestamps.reset_index(drop=True)
    if engagement_df is not None:
        eng_cols = [c for c in ENGAGEMENT_COLS if c in engagement_df.columns]
        eng = engagement_df[[COL_ID] + eng_cols].copy()
        merged = merged.merge(eng, on=COL_ID, how="left", validate="one_to_one")
    return merged


def _bootstrap_ci(
    values: np.ndarray,
    weights: np.ndarray | None = None,
    n_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    if len(values) == 0:
        return (np.nan, np.nan)
    if len(values) == 1:
        return (float(values[0]), float(values[0]))
    rng = np.random.default_rng(seed)
    n = len(values)
    if weights is not None and weights.sum() > 0:
        p = weights / weights.sum()
    else:
        p = None
    means = np.empty(n_resamples)
    idx_range = np.arange(n)
    for i in range(n_resamples):
        idx = rng.choice(idx_range, size=n, replace=True, p=p)
        means[i] = values[idx].mean()
    alpha = (1 - ci) / 2
    lo, hi = np.quantile(means, [alpha, 1 - alpha])
    return float(lo), float(hi)


def composite_signal_per_record(
    df: pd.DataFrame, weights: SignalWeights = SignalWeights()
) -> pd.DataFrame:
    w = weights.normalized()
    out = df.copy()
    sent_norm = _minmax(df["compound"].to_numpy())
    tfidf_norm = _minmax(df["tfidf_weight"].to_numpy())
    out["composite"] = w.sentiment * sent_norm + w.tfidf_weight * tfidf_norm
    return out


def aggregate_signal(
    df: pd.DataFrame,
    freq: str = "1h",
    weights: SignalWeights = SignalWeights(),
    n_resamples: int = 1000,
) -> pd.DataFrame:
    scored = composite_signal_per_record(df, weights)
    scored["engagement_weight"] = compute_engagement_weight(scored)
    scored = scored.set_index(pd.to_datetime(scored[COL_TIMESTAMP]))
    w = weights.normalized()

    rows = []
    for bucket_start, group in scored.groupby(pd.Grouper(freq=freq)):
        if len(group) == 0:
            continue
        values = group["composite"].to_numpy()
        eng_w = group["engagement_weight"].to_numpy()
        mean_signal = (
            float(np.average(values, weights=eng_w)) if eng_w.sum() > 0 else float(values.mean())
        )
        ci_low, ci_high = _bootstrap_ci(values, weights=eng_w, n_resamples=n_resamples)
        rows.append(
            {
                "bucket_start": bucket_start,
                "signal_raw": mean_signal,
                "ci_low_raw": ci_low,
                "ci_high_raw": ci_high,
                "n_tweets": len(group),
            }
        )
    agg = pd.DataFrame(rows).set_index("bucket_start")
    if agg.empty:
        return agg

    vol_norm = _minmax(agg["n_tweets"].to_numpy())
    agg["volume_weight"] = vol_norm
    agg["signal"] = (1 - w.volume) * agg["signal_raw"] + w.volume * agg["volume_weight"]
    # shift the CI band by the same volume adjustment applied to the mean,
    # so width (uncertainty) is preserved rather than recomputed against
    # the shifted center
    shift = agg["signal"] - agg["signal_raw"]
    agg["ci_low"] = agg["ci_low_raw"] + shift
    agg["ci_high"] = agg["ci_high_raw"] + shift
    return agg[["signal", "ci_low", "ci_high", "n_tweets", "volume_weight"]]
