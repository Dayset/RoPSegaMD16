#!/usr/bin/env python3
"""$DD5C LZSS compressor — the exact inverse of dd5c_decompress in
tools/extract_text.py (the $DD5C decompressor, re-implemented from the ROM
routine at $DD5C and verified against the game's streams).

Format (from the decompressor):
  - 4-byte little-endian u32 decompressed length n (must be >= 16).
  - 4096-byte ring pre-filled with 0x20, write position starts at 0xFEE.
  - Mask bytes, bits LSB-first: bit=1 literal (1 byte), bit=0 match (2 bytes).
  - Match: offset = b1 | ((b2 & 0xF0) << 4) (12 bits), length = (b2 & 0x0F) + 3
    (3..18). The match copies byte-by-byte from the ring with wraparound,
    updating the ring as it goes, so a match may overlap itself.

Encoder (default): Haruhiko Okumura's LZSS (lzzs.c, 1989)
--------------------------------------------------------
The 1992 $DD5C encoder IS Okumura's encoder, reproduced exactly: it
reproduces the original streams byte-identically on all 404/404 known
records ($96120 62, $B86AE 90, $43850 252) and agrees on the match offset
for 76,069/76,069 match tokens (verified 2026-11-11, see
tools/tests/test_dd5c.py). The encoder keeps a binary search tree over
ring positions (roots keyed by first byte, N+1+key[0]); InsertNode descends
the tree comparing strings and records the FIRST longest match found on
the descent path — that descent order is the tie-break, and it is what
makes the output byte-identical where a greedy longest-match encoder is
not (greedy gets the same compressed length on every record but picks
different offsets). Parameters: N=4096, F=18, THRESHOLD=2 (min match 3),
NIL=4096; text_buf is N+F-1 bytes, [0, N-F) pre-filled with 0x20, the
rest zero-initialised (C static); s=0, r=N-F; nodes r-F..r are inserted
before the first token. The 14 "suboptimal" tokens in the corpus (a
shorter match than the longest available, all in $96120, the longer match
only at d in [4080, 4096]) are a consequence of the tree search, not a
bug — the Okumura encoder reproduces all 14, so do NOT "fix" them.

Encoder (fallback): greedy longest-match (``method="greedy"`` or the
``--greedy`` CLI flag). Same format, same round-trip guarantee, but a
different tie-break (``prefer``: 'recent' = smallest distance back,
default; 'oldest' = largest distance back). It produces the same
compressed length as the original on every record but different offsets,
so it is byte-identical on 0/90 $B86AE records ('recent') or 29/90
('oldest'). Kept for comparison and as a fallback if the Okumura tree
ever needs to be bypassed. It does not maintain an explicit ring
bytearray for searching: the ring byte ``d`` back from position ``i`` is
``data[i-d]`` if ``i-d >= 0``, else ``0x20`` (the initial space-filled
region) — the exact equivalence that follows from the ring being filled
with the input stream in order, including overlapping matches.

The decompressor is imported from tools/extract_text.py (single
implementation). That module reads sys.argv at import time to set its
ROM/OUT defaults, so argv is shielded during the import.
"""

import struct
import sys
from pathlib import Path

# --- import the canonical decompressor (single implementation) ---
_here = Path(__file__).resolve().parent
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))
_argv = sys.argv
sys.argv = ["extract_text.py"]  # extract_text.py binds ROM/OUT from argv at import
try:
    from extract_text import dd5c_decompress
finally:
    sys.argv = _argv

RING_SIZE = 4096
RING_FILL = 0x20
WPOS0 = 0xFEE
MIN_MATCH = 3
MAX_MATCH = 18

# Okumura encoder constants (lzzs.c): N=4096 ring, F=18 max match,
# THRESHOLD=2 (min match 3), NIL=4096 (one past the last ring position).
_OKU_N = 4096
_OKU_F = 18
_OKU_THRESHOLD = 2
_OKU_NIL = _OKU_N


def _pack_tokens(tokens, n):
    """Pack (is_match, byte_or_off, length) tokens into $DD5C bytes."""
    out = bytearray(struct.pack("<I", n))
    for g in range(0, len(tokens), 8):
        grp = tokens[g:g + 8]
        mask = 0
        body = bytearray()
        for k, (is_match, a, b) in enumerate(grp):
            if is_match:
                # bit=0 -> match; b1 = off low byte,
                # b2 = off high nibble | (len-3)
                body.append(a & 0xFF)
                body.append(((a >> 4) & 0xF0) | (b - 3))
            else:
                mask |= (1 << k)  # bit=1 -> literal
                body.append(a)
        out.append(mask)
        out += body
    return bytes(out)


# ---------------------------------------------------------------------------
# Okumura encoder (default). Faithful port of Haruhiko Okumura's lzzs.c
# Encode / InsertNode / DeleteNode / InitTree (1989). Do not "improve"
# the tie-break: InsertNode records the FIRST longest match on the
# descent path (only a strictly longer match replaces match_position),
# and that exact behaviour is what reproduces the 1992 streams.
# ---------------------------------------------------------------------------

class _OkumuraEncoder:
    def __init__(self, data):
        self.data = bytes(data)
        self.n = len(self.data)
        self.text_buf = bytearray(_OKU_N + _OKU_F - 1)  # C static: zero-init
        for i in range(_OKU_N - _OKU_F):
            self.text_buf[i] = 0x20
        self.lson = [_OKU_NIL] * (_OKU_N + 1)
        self.rson = [_OKU_NIL] * (_OKU_N + 257)
        self.dad = [_OKU_NIL] * (_OKU_N + 1)
        self.match_length = 0
        self.match_position = 0
        self.tokens = []  # (is_match, offset_or_byte, length)

    def init_tree(self):
        for i in range(_OKU_N + 1, _OKU_N + 257):
            self.rson[i] = _OKU_NIL
        for i in range(_OKU_N):
            self.dad[i] = _OKU_NIL

    def insert_node(self, r):
        lson, rson, dad = self.lson, self.rson, self.dad
        tb = self.text_buf
        cmp = 1
        key0 = tb[r]
        p = _OKU_N + 1 + key0
        rson[r] = lson[r] = _OKU_NIL
        self.match_length = 0
        while True:
            if cmp >= 0:
                if rson[p] != _OKU_NIL:
                    p = rson[p]
                else:
                    rson[p] = r
                    dad[r] = p
                    return
            else:
                if lson[p] != _OKU_NIL:
                    p = lson[p]
                else:
                    lson[p] = r
                    dad[r] = p
                    return
            # compare key[1..F-1] with text_buf[p+1..p+F-1]
            i = 1
            while i < _OKU_F:
                cmp = tb[r + i] - tb[p + i]
                if cmp != 0:
                    break
                i += 1
            if i > self.match_length:
                self.match_position = p
                self.match_length = i
                if self.match_length >= _OKU_F:
                    break
        # replace p with r in the tree
        dad[r] = dad[p]
        lson[r] = lson[p]
        rson[r] = rson[p]
        dad[lson[p]] = r
        dad[rson[p]] = r
        if rson[dad[p]] == p:
            rson[dad[p]] = r
        else:
            lson[dad[p]] = r
        dad[p] = _OKU_NIL

    def delete_node(self, p):
        lson, rson, dad = self.lson, self.rson, self.dad
        if dad[p] == _OKU_NIL:
            return
        if rson[p] == _OKU_NIL:
            q = lson[p]
        elif lson[p] == _OKU_NIL:
            q = rson[p]
        else:
            q = lson[p]
            if rson[q] != _OKU_NIL:
                while rson[q] != _OKU_NIL:
                    q = rson[q]
                rson[dad[q]] = lson[q]
                dad[lson[q]] = dad[q]
                lson[q] = lson[p]
                dad[lson[p]] = q
            rson[q] = rson[p]
            dad[rson[p]] = q
        dad[q] = dad[p]
        if rson[dad[p]] == p:
            rson[dad[p]] = q
        else:
            lson[dad[p]] = q
        dad[p] = _OKU_NIL

    def encode(self):
        data, n = self.data, self.n
        tb = self.text_buf
        self.init_tree()
        s = 0
        r = _OKU_N - _OKU_F
        # read first F bytes into tb[r..r+len)
        length = 0
        inpos = 0
        while length < _OKU_F and inpos < n:
            tb[r + length] = data[inpos]
            inpos += 1
            length += 1
        if length == 0:
            return self.tokens
        for i in range(1, _OKU_F + 1):
            self.insert_node(r - i)
        self.insert_node(r)
        while length > 0:
            ml = self.match_length
            if ml > length:
                ml = length
            if ml <= _OKU_THRESHOLD:
                ml = 1
                self.tokens.append((False, tb[r], 0))
            else:
                self.tokens.append((True, self.match_position, ml))
            last = ml
            i = 0
            while i < last and inpos < n:
                c = data[inpos]
                inpos += 1
                self.delete_node(s)
                tb[s] = c
                if s < _OKU_F - 1:
                    tb[s + _OKU_N] = c
                s = (s + 1) & (_OKU_N - 1)
                r = (r + 1) & (_OKU_N - 1)
                self.insert_node(r)
                i += 1
            while i < last:
                self.delete_node(s)
                s = (s + 1) & (_OKU_N - 1)
                r = (r + 1) & (_OKU_N - 1)
                length -= 1
                if length:
                    self.insert_node(r)
                i += 1
        return self.tokens


def _okumura_compress(data):
    """Okumura $DD5C encoder (the 1992 encoder, byte-identical)."""
    enc = _OkumuraEncoder(data)
    return _pack_tokens(enc.encode(), len(data))


# ---------------------------------------------------------------------------
# Greedy longest-match encoder (fallback / comparison). Kept verbatim in
# behaviour from the first-pass implementation; only the packing was
# factored out into _pack_tokens.
# ---------------------------------------------------------------------------

def _match_len(data, i, d, max_len):
    """Longest match at data[i:] with ring distance d (1..window).

    Source byte at step k is data[i-d+k] if i-d+k >= 0 else 0x20 (initial
    ring fill). Exact per the decompressor's byte-by-byte ring copy,
    including overlapping matches (k >= d reads bytes this match wrote).
    """
    n = len(data)
    L = 0
    while L < max_len and i + L < n:
        p = i - d + L
        src = RING_FILL if p < 0 else data[p]
        if src != data[i + L]:
            break
        L += 1
    return L


def _build_index(data):
    """3-byte sequence -> sorted list of data positions where it occurs."""
    idx = {}
    for j in range(len(data) - 2):
        idx.setdefault(data[j:j + 3], []).append(j)
    return idx


def _best_match(data, i, idx, min_match, max_match, window, prefer):
    """Longest match at position i. Returns (distance, length) or None."""
    n = len(data)
    maxlen = min(max_match, n - i)
    if maxlen < min_match:
        return None
    cands = []
    if i <= n - 3:
        for j in idx.get(data[i:i + 3], ()):
            if j >= i:
                continue
            d = i - j
            if d > window:
                continue
            cands.append(d)
    # Matches into the initial space-filled ring (distance d > i).
    # Only possible when the next 3 bytes are spaces (a match needs >= 3).
    if data[i:i + 3] == b" " * 3:
        for s in range(1, min(maxlen, window - i) + 1):
            d = i + s
            if d > window:
                break
            cands.append(d)
    if not cands:
        return None
    cands.sort(reverse=(prefer == "oldest"))
    best_L, best_d = 0, None
    for d in cands:
        L = _match_len(data, i, d, maxlen)
        if L > best_L:
            best_L, best_d = L, d
            if best_L == maxlen:
                break  # cannot improve
    if best_L >= min_match:
        return best_d, best_L
    return None


def _greedy_compress(data, min_match, max_match, window, prefer):
    """Greedy longest-match $DD5C encoder (fallback). Returns bytes."""
    n = len(data)
    idx = _build_index(data)
    tokens = []  # (is_match, byte_or_off, length)
    i = 0
    while i < n:
        m = _best_match(data, i, idx, min_match, max_match, window, prefer)
        if m is not None:
            d, L = m
            wpos = (WPOS0 + i) & 0xFFF
            off = (wpos - d) & 0xFFF
            tokens.append((True, off, L))
            i += L
        else:
            tokens.append((False, data[i], 0))
            i += 1
    return _pack_tokens(tokens, n)


def dd5c_compress(data, method="okumura", min_match=MIN_MATCH,
                  max_match=MAX_MATCH, window=RING_SIZE, prefer="recent"):
    """$DD5C encoder. Returns the compressed bytes.

    ``data`` must be >= 16 bytes (the format's length prefix requires
    n >= 16). ``method`` is 'okumura' (default — the 1992 encoder,
    byte-identical on all 404 known records) or 'greedy' (longest-match
    fallback; ``min_match``/``max_match``/``window``/``prefer`` apply
    only to it). ``prefer`` is 'recent' (smallest distance back, default)
    or 'oldest' (largest distance back) for greedy tie-breaking.
    """
    data = bytes(data)
    n = len(data)
    if n < 16:
        raise ValueError(f"$DD5C stream needs n >= 16, got {n}")
    if method not in ("okumura", "greedy"):
        raise ValueError(f"method must be 'okumura' or 'greedy', got {method!r}")
    if method == "okumura":
        return _okumura_compress(data)
    if not (3 <= min_match <= max_match <= MAX_MATCH):
        raise ValueError(f"need 3 <= min_match <= max_match <= 18, "
                         f"got {min_match}/{max_match}")
    if not (1 <= window <= RING_SIZE):
        raise ValueError(f"need 1 <= window <= 4096, got {window}")
    if prefer not in ("recent", "oldest"):
        raise ValueError(f"prefer must be 'recent' or 'oldest', got {prefer!r}")
    return _greedy_compress(data, min_match, max_match, window, prefer)


def _cmd_compress(inp, outp, method="okumura"):
    data = Path(inp).read_bytes()
    comp = dd5c_compress(data, method=method)
    Path(outp).write_bytes(comp)
    print(f"compress ({method}): {len(data)} -> {len(comp)} bytes "
          f"({len(comp) / len(data):.3f}x)")


def _cmd_decompress(inp, outp):
    data = Path(inp).read_bytes()
    # The decompressor's default max_out is 60000; read the stream's own
    # length prefix and allow exactly that many output bytes.
    (n,) = struct.unpack_from("<I", data, 0)
    res = dd5c_decompress(data, 0, max_out=n)
    if res is None:
        print("decompress: FAILED (invalid stream)")
        return 1
    dec, consumed = res
    Path(outp).write_bytes(dec)
    print(f"decompress: {len(data)} -> {len(dec)} bytes "
          f"(consumed {consumed}/{len(data)})")
    return 0


def _cmd_roundtrip(inp, method="okumura"):
    data = Path(inp).read_bytes()
    comp = dd5c_compress(data, method=method)
    res = dd5c_decompress(comp, 0, max_out=len(data))
    if res is None:
        print(f"roundtrip ({method}): FAIL (decompressor rejected our output) "
              f"in={len(data)} comp={len(comp)}")
        return 1
    dec, _ = res
    ok = dec == data
    print(f"roundtrip ({method}): {'OK' if ok else 'FAIL'} "
          f"in={len(data)} comp={len(comp)} ({len(comp)/len(data):.3f}x)")
    return 0 if ok else 1


def main(argv):
    if len(argv) < 2:
        print(__doc__.split("\n\n")[0])
        print("usage: dd5c.py compress [--greedy] <in.bin> <out.dd5c> | "
              "decompress <in.dd5c> <out.bin> | roundtrip [--greedy] <in.bin>")
        return 2
    cmd = argv[1]
    rest = argv[2:]
    method = "okumura"
    if rest and rest[0] == "--greedy":
        method = "greedy"
        rest = rest[1:]
    if cmd == "compress" and len(rest) == 2:
        _cmd_compress(rest[0], rest[1], method)
        return 0
    if cmd == "decompress" and len(rest) == 2:
        return _cmd_decompress(rest[0], rest[1])
    if cmd == "roundtrip" and len(rest) == 1:
        return _cmd_roundtrip(rest[0], method)
    print("usage: dd5c.py compress [--greedy] <in.bin> <out.dd5c> | "
          "decompress <in.dd5c> <out.bin> | roundtrip [--greedy] <in.bin>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
