"""Second-megabyte payload of the topdown feature (2 MB builds only):
the fast terrain streams of the smooth iso view (#266), at ISOFAST."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import iso_fast_streams  # noqa: E402

OFFSET = 0x100000


def build(rom: bytes) -> bytes:
    return iso_fast_streams.build(rom)
