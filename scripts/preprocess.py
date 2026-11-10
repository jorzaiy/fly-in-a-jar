"""Preprocess FlyWire connectome data into CSR matrix and neuron metadata.

Usage:
    python scripts/preprocess.py [--synapse-threshold 5]

Input:
    data/raw/Connectivity_783.parquet
    data/raw/Completeness_783.csv
    data/raw/Supplemental_file1_neuron_annotations.tsv

Output:
    data/connectome_v783_t{threshold}.npz (CSR format: indptr, indices, weights, shape)
    data/neurons.parquet (index, root_id, cell_type, super_class, side)
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import scipy.sparse as sp

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_OUT_DIR = REPO_ROOT / "data"


def preprocess(raw_dir: Path, out_dir: Path, threshold: int = 5) -> None:
    conn_path = raw_dir / "Connectivity_783.parquet"
    comp_path = raw_dir / "Completeness_783.csv"
    anno_path = raw_dir / "Supplemental_file1_neuron_annotations.tsv"

    for path in (conn_path, comp_path, anno_path):
        if not path.exists():
            print(f"[ERROR] Required input file not found: {path}")
            print("Please run scripts/fetch_data.py first.")
            sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"--- Preprocessing FlyWire v783 with synapse threshold >= {threshold} ---")

    # 1. Process neurons metadata
    print("Reading Completeness_783.csv and neuron annotations...")
    df_comp = pd.read_csv(comp_path)
    # The first column is root_id
    root_id_col = df_comp.columns[0]
    num_neurons = len(df_comp)
    print(f"Total neurons in Completeness_783: {num_neurons}")

    df_neurons = pd.DataFrame({
        "index": np.arange(num_neurons, dtype=np.int32),
        "root_id": df_comp[root_id_col].astype(np.int64),
    })

    df_anno = pd.read_csv(anno_path, sep="\t", low_memory=False)
    anno_cols = ["root_id", "cell_type", "super_class", "side"]
    available_anno_cols = [c for c in anno_cols if c in df_anno.columns]
    df_anno_subset = df_anno[available_anno_cols].drop_duplicates(subset=["root_id"])

    df_merged = df_neurons.merge(df_anno_subset, on="root_id", how="left")
    neurons_out_path = out_dir / "neurons.parquet"
    df_merged.to_parquet(neurons_out_path, compression="zstd")
    neurons_size_mb = neurons_out_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Saved neurons metadata: {neurons_out_path} ({neurons_size_mb:.2f} MB)")
    annotated_count = df_merged["cell_type"].notna().sum()
    print(f"  Neurons with cell_type annotation: {annotated_count}/{num_neurons} ({annotated_count/num_neurons*100:.1f}%)")

    # 2. Process connectivity into CSR matrix
    print(f"Reading Connectivity_783.parquet and filtering threshold >= {threshold}...")
    df_conn = pd.read_parquet(
        conn_path,
        columns=["Presynaptic_Index", "Postsynaptic_Index", "Connectivity", "Excitatory x Connectivity"],
    )
    raw_edges = len(df_conn)
    print(f"Total raw connections: {raw_edges:,}")

    filtered = df_conn[df_conn["Connectivity"] >= threshold]
    filtered_edges = len(filtered)
    print(f"Connections with synapse count >= {threshold}: {filtered_edges:,} ({filtered_edges/raw_edges*100:.2f}%)")

    pre = filtered["Presynaptic_Index"].to_numpy(dtype=np.int32)
    post = filtered["Postsynaptic_Index"].to_numpy(dtype=np.int32)
    weights = filtered["Excitatory x Connectivity"].to_numpy(dtype=np.float32)

    # Build CSR matrix
    print("Constructing Compressed Sparse Row (CSR) matrix...")
    csr = sp.csr_matrix((weights, (pre, post)), shape=(num_neurons, num_neurons), dtype=np.float32)
    csr.sum_duplicates()
    csr.sort_indices()

    matrix_out_path = out_dir / f"connectome_v783_t{threshold}.npz"
    np.savez_compressed(
        matrix_out_path,
        indptr=csr.indptr.astype(np.int32),
        indices=csr.indices.astype(np.int32),
        weights=csr.data.astype(np.float32),
        shape=csr.shape,
    )
    matrix_size_mb = matrix_out_path.stat().st_size / (1024 * 1024)
    print(f"[OK] Saved connectome matrix: {matrix_out_path} ({matrix_size_mb:.2f} MB)")

    print("\n--- Summary ---")
    print(f"Neuron count (N): {num_neurons:,}")
    print(f"Filtered directed connections (NNZ): {csr.nnz:,}")
    print(f"CSR indptr: {len(csr.indptr):,} elements (int32)")
    print(f"CSR indices: {len(csr.indices):,} elements (int32)")
    print(f"CSR weights: {len(csr.data):,} elements (float32)")
    print(f"Matrix file size: {matrix_size_mb:.2f} MB")
    print(f"Neurons file size: {neurons_size_mb:.2f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess FlyWire connectome into CSR format.")
    parser.add_argument("--synapse-threshold", "-t", type=int, default=5, help="Minimum synapse count per connection")
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR, help="Path to raw data directory")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR, help="Path to output data directory")
    args = parser.parse_args()

    preprocess(args.raw_dir, args.output_dir, threshold=args.synapse_threshold)


if __name__ == "__main__":
    main()
