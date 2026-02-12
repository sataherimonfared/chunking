#!/usr/bin/env python3
"""
CLI entry point for DESY chunking pipeline.
Reads MD files from desy_crawled/<run_id>/depth_*/, produces JSONL chunks + metadata.

Usage (from project root):
    python -m chunking.run_chunking [--run-id 2] [--write-index]

Usage (from chunking directory):
    cd /home/taheri/crawl4ai/chunking && python run_chunking.py [--run-id 2] [--write-index]

See PLAN.md for specification.
"""

import argparse
import json
import sys
from pathlib import Path

# Project root = parent of chunking/ (so chunking package can be found when run from chunking/)
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from chunking.chunker import process_md_file
from chunking import config


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chunk DESY crawled MD files with metadata."
    )
    parser.add_argument(
        "--run-id",
        default=config.RUN_ID,
        help=f"Run ID (subfolder under desy_crawled). Default: {config.RUN_ID}",
    )
    parser.add_argument(
        "--write-index",
        action="store_true",
        help="Write chunks_index.json summary.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Override input base path (default: desy_crawled)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Override output base path (default: chunking/output)",
    )
    args = parser.parse_args()

    input_base = args.input or config.INPUT_BASE
    output_base = args.output or config.OUTPUT_BASE
    run_id = args.run_id

    run_dir = input_base / run_id
    if not run_dir.is_dir():
        print(f"[ERROR] Run directory not found: {run_dir}")
        return 1

    # Find depth_* directories
    depth_dirs = sorted(
        d for d in run_dir.iterdir()
        if d.is_dir() and d.name.startswith("depth_")
    )
    if not depth_dirs:
        print(f"[ERROR] No depth_* directories in {run_dir}")
        return 1

    out_run = output_base / run_id
    out_run.mkdir(parents=True, exist_ok=True)

    index_entries = []
    total_chunks = 0
    total_files = 0

    for depth_dir in depth_dirs:
        # Parse depth number
        try:
            depth = int(depth_dir.name.replace("depth_", ""))
        except ValueError:
            depth = 0

        md_files = list(depth_dir.glob("*.md"))
        out_depth = out_run / depth_dir.name
        out_depth.mkdir(parents=True, exist_ok=True)

        for md_path in md_files:
            try:
                chunks = process_md_file(md_path, depth, run_id)
            except Exception as e:
                print(f"[WARN] Failed to process {md_path}: {e}")
                continue

            if not chunks:
                continue

            out_file = out_depth / f"{md_path.name}.jsonl"
            with open(out_file, "w", encoding="utf-8") as f:
                for text, meta in chunks:
                    record = {"text": text, "metadata": meta}
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            total_chunks += len(chunks)
            total_files += 1
            index_entries.append({
                "file_path": str(chunks[0][1]["file_path"]),
                "chunk_count": len(chunks),
                "source_url": chunks[0][1]["source_url"],
            })

    if args.write_index:
        index_path = out_run / "chunks_index.json"
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": run_id,
                    "total_files": total_files,
                    "total_chunks": total_chunks,
                    "files": index_entries,
                },
                f,
                indent=2,
                ensure_ascii=False,
            )
        print(f"[INFO] Wrote index to {index_path}")

    print(f"[INFO] Processed {total_files} files, {total_chunks} chunks -> {out_run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
