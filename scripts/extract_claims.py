# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "mlx==0.32.4",
#     "mlx-vlm==0.3.12",
#     "mlx-lm==0.30.7",
#     "transformers==5.1.0",
# ]
# ///
"""Run claim extraction in the isolated local MLX environment."""

import sys

from political_ads.cli import main

if __name__ == "__main__":
    sys.argv.insert(1, "extract-claims")
    main()
