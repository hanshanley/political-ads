"""Publish a complete offline checkpoint without interrupting local inference."""

import argparse
import json
from pathlib import Path

from political_ads.claim_checkpoints import publish_claim_checkpoint

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = publish_claim_checkpoint(Path.cwd(), args.input, args.output)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in ("ads", "blocks", "blocks_by_status", "claims", "targets", "status")
            },
            indent=2,
        )
    )
