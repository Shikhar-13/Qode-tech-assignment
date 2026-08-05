from pathlib import Path
import pandas as pd
from analysis import sentiment
from analysis import tfidf_features
from analysis import signal
from analysis import plots


def run_analysis(parquet_path, outdir="data/processed", freq="30min"):

    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    parquet_path = Path(parquet_path)

    # --------------------------------------------------
    # Load only required columns
    # --------------------------------------------------

    cols = [
        "tweet_id",
        "content_clean",
        "timestamp",
        "likes",
        "retweets",
        "replies",
        "views",
    ]

    df = pd.read_parquet(
        parquet_path,
        columns=cols,
    )

    print(f"Loaded {len(df)} records")

    # --------------------------------------------------
    # Sentiment Analysis
    # --------------------------------------------------

    records = df.to_dict(orient="records")

    sent_results = [
        r.__dict__
        for r in sentiment.score_records(records)
    ]

    print("Sentiment scoring completed.")

    # --------------------------------------------------
    # TF-IDF
    # --------------------------------------------------

    vectorizer, matrix = tfidf_features.fit_tfidf(
        df["content_clean"].fillna("")
    )

    weights = tfidf_features.all_doc_weights(matrix)

    print("TF-IDF completed.")

    # --------------------------------------------------
    # Feature Engineering
    # --------------------------------------------------

    engagement_df = df[
        [
            "tweet_id",
            "likes",
            "retweets",
            "replies",
            "views",
        ]
    ]

    feature_df = signal.build_feature_frame(
        sent_results,
        weights,
        df["tweet_id"].tolist(),
        df["timestamp"],
        engagement_df=engagement_df,
    )

    # --------------------------------------------------
    # Aggregate Trading Signal
    # --------------------------------------------------

    aggregated = signal.aggregate_signal(
        feature_df,
        freq=freq,
        n_resamples=500,
    )

    aggregated_path = outdir / "signal_timeseries.csv"

    aggregated.to_csv(
        aggregated_path,
        index=True,
    )

    print(
        f"Signal saved to {aggregated_path}"
    )

    raw_sample = feature_df.copy()

    raw_sample["composite"] = (
        signal.composite_signal_per_record(
            feature_df
        )["composite"]
    )

    if len(raw_sample) > 2000:
        raw_sample = raw_sample.sample(
            2000,
            random_state=42,
        )

    plot_path = plots.plot_signal_with_ci(
        aggregated,
        raw_sample=raw_sample[
            [
                "timestamp",
                "composite",
            ]
        ].rename(
            columns={
                "timestamp": "created_at"
            }
        ),
        out_path=outdir / "signal_plot.png",
    )

    print(f"Plot saved to {plot_path}")

    return {
        "feature_frame": feature_df,
        "aggregated_signal": aggregated,
        "plot": plot_path,
        "csv": aggregated_path,
    }