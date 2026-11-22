"""Image-to-Design prototype with a pinned, local shared validation snapshot."""

from pathlib import Path
import sys

SHARED = Path(__file__).resolve().parents[1] / "shared"
sys.path.insert(0, str(SHARED))
