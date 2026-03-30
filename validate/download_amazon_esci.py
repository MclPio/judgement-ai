"""Download Amazon ESCI source files into the local validation data cache."""

from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

DEFAULT_FILES = {
    "shopping_queries_dataset_examples.parquet": (
        "https://github.com/amazon-science/esci-data/raw/main/"
        "shopping_queries_dataset_examples.parquet"
    ),
    "shopping_queries_dataset_products.parquet": (
        "https://github.com/amazon-science/esci-data/raw/main/"
        "shopping_queries_dataset_products.parquet"
    ),
}


def download_esci_data(output_dir: str | Path) -> list[Path]:
    """Download the default Amazon ESCI raw files if missing."""
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    downloaded: list[Path] = []
    for filename, url in DEFAULT_FILES.items():
        destination = target_dir / filename
        if not destination.exists():
            urlretrieve(url, destination)  # noqa: S310
        downloaded.append(destination)
    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Amazon ESCI source files into validate/data."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).with_name("data") / "amazon_esci",
        help="Directory where the raw Amazon ESCI files will be stored.",
    )
    args = parser.parse_args()

    files = download_esci_data(args.output_dir)
    for file in files:
        print(file)


if __name__ == "__main__":
    main()
