#!/usr/bin/env python3
"""VDP snapshot from a Genesis Plus GX savestate (stable-retro get_state()).

Layout found by anchoring the window name table of the game layout:
work RAM at +16 (little-endian words), VRAM at +74789 (64 KB,
little-endian words), CRAM 64 words right after VRAM, VSRAM after
CRAM, then the 32 VDP registers. Offsets are for GPGX 1.7.5 in
stable-retro 1.0.1; `vdp_from_state` checks the version string.
"""
import numpy as np

VRAM_OFF = 74789


def vdp_from_state(st):
    st = bytes(st)
    assert st.startswith(b"GENPLUS-GX 1.7.5"), st[:16]
    v = VRAM_OFF
    vram_w = np.frombuffer(st[v:v + 0x10000], dtype="<u2")
    vram = vram_w.astype(">u2").tobytes()            # big-endian bytes
    cram = np.frombuffer(st[v + 0x10000:v + 0x10080], dtype="<u2")
    vsram = np.frombuffer(st[v + 0x10080:v + 0x10100], dtype="<u2")
    regs = np.frombuffer(st[v + 0x10100:v + 0x10120], dtype=np.uint8)
    return {"vram": vram, "cram": cram, "vsram": vsram, "regs": regs}


def cram_rgb(c):
    # GPGX stores CRAM as 9-bit BBBGGGRRR
    r = (c & 7) * 36
    g = ((c >> 3) & 7) * 36
    b = ((c >> 6) & 7) * 36
    return (r, g, b)


def tile_pixels(vram, idx):
    t = np.frombuffer(vram[idx * 32:idx * 32 + 32], dtype=np.uint8)
    hi = t >> 4
    lo = t & 15
    return np.stack([hi, lo], axis=1).reshape(8, 8)


def render_plane(vdp, base, w, h, cols=None, rows=None):
    """Render a name table (w x h cells) to an RGB array; colour 0
    pixels are magenta so transparency is visible."""
    vram, cram = vdp["vram"], vdp["cram"]
    cols = cols or w
    rows = rows or h
    out = np.zeros((rows * 8, cols * 8, 3), dtype=np.uint8)
    pal = np.array([cram_rgb(int(c)) for c in cram], dtype=np.uint8)
    for r in range(rows):
        for c in range(cols):
            o = base + (r * w + c) * 2
            word = (vram[o] << 8) | vram[o + 1]
            px = tile_pixels(vram, word & 0x7FF)
            if word & 0x800:
                px = px[:, ::-1]
            if word & 0x1000:
                px = px[::-1, :]
            p = (word >> 13) & 3
            rgb = pal[p * 16 + px]
            rgb[px == 0] = (255, 0, 255)
            out[r * 8:r * 8 + 8, c * 8:c * 8 + 8] = rgb
    return out


if __name__ == "__main__":
    import sys
    from PIL import Image
    st = open(sys.argv[1], "rb").read()
    vdp = vdp_from_state(st)
    print("regs", " ".join("%02x" % x for x in vdp["regs"][:24]))
    Image.fromarray(render_plane(vdp, 0x1000, 64, 32, 40, 28)).save(sys.argv[2] + "_win.png")
    Image.fromarray(render_plane(vdp, 0x0000, 64, 32, 64, 32)).save(sys.argv[2] + "_ab.png")
