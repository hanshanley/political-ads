# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mlx==0.32.4",
#     "mlx-vlm==0.3.12",
#     "mlx-lm==0.30.7",
#     "transformers==5.1.0",
# ]
# ///
"""Batch local claim inference over a separately frozen copy of existing inputs."""

import argparse
import json
from pathlib import Path

from political_ads.claims import extract_claims


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / "data/local-claims/full-fast")
    parser.add_argument(
        "--frozen-from", type=Path, default=root / "data/local-claims/full/manifest.json"
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--initial-tokens", type=int, default=2048)
    parser.add_argument("--ad-id", action="append")
    parser.add_argument("--max-new-blocks", type=int, default=0)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--replay", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    args = parser.parse_args()
    summary = extract_claims(
        root,
        args.output,
        frozen_from=args.frozen_from,
        batch_size=args.batch_size,
        initial_tokens=args.initial_tokens,
        ad_ids=args.ad_id,
        max_new_blocks=args.max_new_blocks,
        prepare_only=args.prepare_only,
        replay=args.replay,
        retry_failed=args.retry_failed,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
