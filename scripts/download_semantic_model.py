"""Download and verify the project-local multilingual embedding model."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from concordia_riverbend.memory import DEFAULT_SEMANTIC_MODEL
from concordia_riverbend.memory import FastEmbedTextEmbedder
from concordia_riverbend.memory import semantic_model_cache


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Riverbend's local ONNX semantic model."
    )
    parser.add_argument("--model-name", default=DEFAULT_SEMANTIC_MODEL)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        help="Defaults to models/fastembed under the project root.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    project_root = Path(__file__).resolve().parents[1]
    cache_dir = args.cache_dir or semantic_model_cache(project_root)
    embedder = FastEmbedTextEmbedder(
        cache_dir=cache_dir,
        model_name=args.model_name,
        local_files_only=False,
    )
    probe = embedder("River pollution affected the community.")
    manifest = {
        "model_name": embedder.model_name,
        "backend": "fastembed",
        "dimensions": int(probe.shape[0]),
        "downloaded_at": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "runtime_network_policy": "local_files_only",
    }
    manifest_path = cache_dir / "riverbend_model.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Semantic model ready: {embedder.model_name}")
    print(f"Dimensions: {probe.shape[0]}")
    print(f"Cache: {cache_dir}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
