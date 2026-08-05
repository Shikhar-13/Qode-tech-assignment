from scraper.scraper import scrape
from processing.pipeline import process_pipeline
from analysis.pipeline import run_analysis


def main():

    # Phase 1
    raw_json = scrape()

    # Phase 2
    parquet_path = process_pipeline(raw_json)

    # Phase 3
    run_analysis(parquet_path)

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()