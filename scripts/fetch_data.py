"""Fetch raw connectome and annotation data for Fly in a Jar.

Downloads:
1. Connectivity_783.parquet from philshiu/Drosophila_brain_model
2. Completeness_783.csv from philshiu/Drosophila_brain_model
3. Supplemental_file1_neuron_annotations.tsv from flyconnectome/flywire_annotations

Saves into data/raw/
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
import urllib.request

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

FILES = {
    "Connectivity_783.parquet": (
        "https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Connectivity_783.parquet"
    ),
    "Completeness_783.csv": (
        "https://raw.githubusercontent.com/philshiu/Drosophila_brain_model/main/Completeness_783.csv"
    ),
    "Supplemental_file1_neuron_annotations.tsv": (
        "https://raw.githubusercontent.com/flyconnectome/flywire_annotations/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv"
    ),
}


def download_file(url: str, dest: Path, force: bool = False) -> None:
    if dest.exists() and not force:
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"[SKIP] {dest.name} already exists ({size_mb:.2f} MB)")
        return

    print(f"[DOWNLOADING] {dest.name} from {url} ...")
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest.with_suffix(dest.suffix + ".tmp")

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        downloaded = block_num * block_size
        if total_size > 0:
            percent = downloaded / total_size * 100
            sys.stdout.write(f"\r  {downloaded / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB ({percent:.1f}%)")
        else:
            sys.stdout.write(f"\r  {downloaded / (1024*1024):.1f} MB")
        sys.stdout.flush()

    try:
        urllib.request.urlretrieve(url, tmp_path, reporthook=_reporthook)
        print()
        tmp_path.replace(dest)
        size_mb = dest.stat().st_size / (1024 * 1024)
        print(f"[OK] Saved {dest.name} ({size_mb:.2f} MB)")
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        print(f"\n[ERROR] Failed to download {dest.name}: {e}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Download raw connectome data.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Target directory: {RAW_DIR}")

    for filename, url in FILES.items():
        dest = RAW_DIR / filename
        download_file(url, dest, force=args.force)

    print("All downloads finished successfully.")


if __name__ == "__main__":
    main()
