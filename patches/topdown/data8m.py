"""8 MB payload of the topdown feature (#307): the pre-drawn overworld
(tools/ow_atlas.py), generated from the original ROM at build time."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import ow_atlas  # noqa: E402

OFFSET = ow_atlas.OFFSET


def build(rom: bytes) -> bytes:
    return ow_atlas.build(rom)
