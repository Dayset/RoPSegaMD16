#!/usr/bin/env python3
"""Generate the smooth iso view's frame art (#306).

In the original view the window holds the room bitmap and the parchment
frame around it is the world-map background, tilemap rec 9 (28 x 40,
tileset rec 6 at VRAM tile 436, palette 1), drawn on the plane under the
window. The smooth iso view puts its picture on that plane, but rec 6's
tiles stay in VRAM, so the window can show the same art around the hole
(ti_frameword). This writes rec 9's words and a signature of one of its
tiles (checked in VRAM before the art is used) between the
`; ti_art data` markers in patches/topdown/feature.s.

  td_iso_art.py [--check]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode_map  # noqa: E402

FEATURE = Path(__file__).resolve().parent.parent / "patches/topdown/feature.s"
BEGIN, END = "; ti_art data (tools/td_iso_art.py)", "; ti_art data end"
SIG = 31            # a border tile with mixed pixels


def block():
    data = decode_map.read_rom()
    words = decode_map.map_words(data, 9)
    tiles = decode_map.record_bytes(data, 6)
    assert len(words) == 28 * 40
    # a tile with any transparent pixel (the land, the diamond's stone
    # rim) would show the render's incomplete edge cells through it:
    # those cells take parchment (TI_ARTT)
    def clear(t):
        b = tiles[t * 32:t * 32 + 32]
        return any((x >> 4) == 0 or (x & 15) == 0 for x in b)
    # and the stone rim of the original's +-5 diamond (cells next to a
    # partly transparent tile that is not the land): parchment, so the
    # rim does not stand a cell off our +-4 hole
    def compass(r, c):              # under the diamond's bottom tip
        return 21 <= r <= 26 and 20 <= c <= 30 and 2 * r + c > 66
    rim = set()
    for i, w in enumerate(words):
        if clear(w & 0x7FF) and (w & 0x7FF) != 131:
            r, c = divmod(i, 40)
            rim |= {(r + dr) * 40 + c + dc for dr in (-1, 0, 1)
                    for dc in (-1, 0, 1)
                    if 0 <= r + dr < 28 and 0 <= c + dc < 40
                    and not compass(r + dr, c + dc)}
    words = [131 if clear(w & 0x7FF) or i in rim else w
             for i, w in enumerate(words)]
    out = [BEGIN,
           "TI_ARTB\t\tequ $2000+436\t; rec 6's VRAM base, palette 1",
           "TI_ARTT\t\tequ 131\t\t; parchment here (a tile with transparent pixels)",
           f"TI_ARTS\t\tequ 436+{SIG}\t; signature tile",
           "ti_artsig:\t; its first 8 bytes",
           "\tdc.b\t" + ", ".join(f"${b:02X}" for b in tiles[SIG * 32:SIG * 32 + 8]),
           "ti_art:\t; rec 9, 28 rows x 40 columns"]
    for r in range(28):
        row = words[r * 40:(r + 1) * 40]
        for k in range(0, 40, 10):
            out.append("\tdc.w\t" + ",".join(f"${w:04X}" for w in row[k:k + 10]))
    out.append(END)
    return "\n".join(out)


def main():
    s = FEATURE.read_text()
    a, b = s.index(BEGIN), s.index(END) + len(END)
    new = s[:a] + block() + s[b:]
    if "--check" in sys.argv:
        sys.exit(0 if new == s else "ti_art data out of date")
    FEATURE.write_text(new)


if __name__ == "__main__":
    main()
