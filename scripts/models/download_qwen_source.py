"""Download one pinned Qwen snapshot for the isolated conversion environment."""

from __future__ import annotations

import argparse
from pathlib import Path

MODEL_ID = "Qwen/Qwen3-0.6B"
MODEL_REVISION = "c1899de289a04d12100db370d81485cdf75e47ca"


def main() -> int:
    import truststore

    truststore.inject_into_ssl()
    from huggingface_hub import snapshot_download

    parser = argparse.ArgumentParser()
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    arguments.destination.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        local_dir=arguments.destination,
        allow_patterns=[
            "LICENSE",
            "config.json",
            "generation_config.json",
            "merges.txt",
            "model.safetensors",
            "tokenizer.json",
            "tokenizer_config.json",
            "vocab.json",
        ],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
