#!/usr/bin/env python3
"""Python port of map_terrain_tile_lookup ($E358, disasm/src/rop.s:2433).

$E358 decodes one terrain stream into the $FF1EC0 decode buffer
(26,496 bytes = 36x23 tiles x 32 bytes), which map_chunk_pos ($1BA4E)
DMA-uploads to VRAM. One call = ~22 handler dispatches.

Call signature (stack args, all words):
    $E358(stream_id, d0, d1, d3)
      stream_id  index into the $5F524 offset table (944 streams,
                   streams tile ROM $603E4-$9611F exactly)
      d0         X-ish position word (callers: $FFAE7A table value;
                   ANDed with $FFFE, then -$40 path A / -$26 path B)
      d1         Y-ish position word (callers: $FFAF42 table value
                   minus 7*height; <0 runs the skip walk, <-21 exits)
      d3         variant: 0 -> path A ($E3B0 loop), !=0 -> path B ($E412)

Mechanics (from the disassembly, verified against live captures — see
tools/tests/test_e358.py):
  * d1 < -21 exits at once, no writes. d1 < 0 runs the skip walk:
    -d1 entries, each consuming 1 dispatch byte + (hi nibble) bytes.
  * Each dispatch byte b: lo nibble selects a shape, hi nibble selects
    a handler (handler stream-byte count == hi nibble). The handler is
    dispatched via the $DF58 longword table; index =
    (hi<<4) | ((2*lo + LOG_D0) & 6)       path A (even indices)
    (hi<<4) | (((-2*lo + LOG_D0) & 6)|1)  path B (odd indices)
    where LOG_D0 = d0 - $40 (A) / d0 - $26 (B).
  * Destination a5 = $FF1EC0 + $436E0[d1] + $435C0[d3w], where
    $436E0[i] = (i//8)*0x480 + (i%8)*4 and d3w = +/-2*lo + LOG_D0;
    d1 advances by 2 per dispatch (one $436E0 word per dispatch).
  * Handlers are straight-line code over a tiny op set (see _decode):
    read a stream byte, optionally remap it through the (a6) byte table
    ($434C0 in path B; path A handlers never use a6), look up its mask
    in $433C0, and write (old & mask) | byte at a5, with a5 strides
    (+0x1D row steps etc.). Writes are and/or composites, so neighbour
    cells overlap — there is no per-tile result (#231).
  * The 144/256 dispatch indices that point at the loop heads ($E3E2 /
    $E43C) are no-ops: the dispatch byte is consumed, nothing is drawn.

The handlers are decoded from the ROM bytes themselves by a small
68k decoder (_decode_handler) with a strict allowlist: any opcode
outside the observed handler set raises UnknownOpcode. The decoder
output was cross-checked against disasm/src/rop.s for all 112 live
handlers (see tools/tests/test_e358.py).

Usage:
    e = E358(open("rop-original.gen", "rb").read())
    buf, stats = e.call_buffer(stream, d0, d1, d3)   # fresh zeroed RAM
    # or, to accumulate calls into one render (map_chunk_pos does
    # ~118 calls per render into the same buffer):
    ram = bytearray(65536)                            # $FF0000-$FFFFFF
    e.call(stream, d0, d1, d3, ram)
    buf = bytes(ram[0x1EC0:0x1EC0 + 26496])
"""
import struct

BUF_BASE = 0xFF1EC0
BUF_LEN = 26496
BUF_END = BUF_BASE + BUF_LEN
RAM_BASE = 0xFF0000
RAM_LEN = 65536

TABLE_STREAM = 0x5F524
STREAM_BASE = 0x603E4
N_STREAMS = 944
TABLE_MASK = 0x433C0      # a3: 256 mask bytes
TABLE_B = 0x434C0         # a6 in path B: 256 remap bytes
TABLE_X = 0x435C0         # a1: X-offset words, indexed by d3w
TABLE_Y = 0x436E0         # a2: Y-offset words, indexed by d1
TABLE_DISPATCH = 0xDF58   # a6 in path A / dispatch table: 256 longs
LOOP_A = 0xE3E2
LOOP_B = 0xE43C


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


class UnknownOpcode(Exception):
    pass


class E358:
    def __init__(self, rom):
        self.rom = bytes(rom)
        if len(self.rom) < 0x100000:
            raise ValueError("ROM too short: %d bytes" % len(self.rom))
        self.stream_offs = list(struct.unpack_from(">944I", self.rom, TABLE_STREAM))
        self.dispatch = list(struct.unpack_from(">256I", self.rom, TABLE_DISPATCH))
        self._handlers = {}   # target addr -> op list (decoded lazily)

    # -- ROM word reads (hardware reads whatever bytes are there) --
    def _word(self, addr):
        if addr < 0 or addr + 2 > len(self.rom):
            raise ValueError("ROM word read out of range: $%X" % addr)
        return struct.unpack_from(">H", self.rom, addr)[0]

    def stream_bytes(self, stream_id):
        """Raw bytes of one terrain stream (tiling: next offset - this)."""
        if not 0 <= stream_id < N_STREAMS:
            raise ValueError("stream id out of range: %d" % stream_id)
        start = STREAM_BASE + self.stream_offs[stream_id]
        end = (STREAM_BASE + self.stream_offs[stream_id + 1]
               if stream_id + 1 < N_STREAMS else 0x96120)
        return self.rom[start:end]

    # -- handler decoding (68k subset, from ROM bytes) --
    # Op tuples: ('read',) ('xform',) ('mask',)
    #   ('write', addr_off, a5_delta)  byte at a5+addr_off = (old & d6) | d5,
    #                     then a5 += a5_delta. The four and/or pair shapes:
    #                     (a5)/(a5) -> (0,0); (a5)/(a5)+ -> (0,+1);
    #                     -(a5)/(a5)+ -> (-1,0); -(a5)/(a5) -> (-1,-1).
    #   ('adda', imm) / ('suba', imm)  a5 += / -= signed imm
    def _decode_handler(self, target):
        if target in self._handlers:
            return self._handlers[target]
        ops = []
        pc = target
        guard = target + 512
        while pc < guard:
            w = struct.unpack_from(">H", self.rom, pc)[0]
            if w == 0x1A18:                       # move.b (a0)+,d5
                ops.append(("read",))
                pc += 2
            elif w in (0x1A36, 0x1C33):           # move.b (a6/a3,d5.w),d5/d6
                ext = struct.unpack_from(">H", self.rom, pc + 2)[0]
                if ext != 0x5000:
                    raise UnknownOpcode("$%X: bad index ext $%04X" % (pc, ext))
                ops.append(("xform",) if w == 0x1A36 else ("mask",))
                pc += 4
            elif w in (0xCD15, 0xCD25):           # and.b d6,(a5) / -(a5)
                w2 = struct.unpack_from(">H", self.rom, pc + 2)[0]
                if w2 not in (0x8B15, 0x8B1D):
                    raise UnknownOpcode("$%X: and.b not followed by or.b ($%04X)" % (pc, w2))
                # (and, or): (15,15)->(0,0) (15,1D)->(0,+1)
                #            (25,1D)->(-1,0) (25,15)->(-1,-1)
                off = -1 if w == 0xCD25 else 0
                delta = (1 if w2 == 0x8B1D else 0) + off
                ops.append(("write", off, delta))
                pc += 4
            elif w == 0xDAFC:                     # adda.w #imm,a5
                ops.append(("adda", s16(struct.unpack_from(">H", self.rom, pc + 2)[0])))
                pc += 4
            elif w == 0x9AFC:                     # suba.w #imm,a5
                ops.append(("suba", s16(struct.unpack_from(">H", self.rom, pc + 2)[0])))
                pc += 4
            elif w == 0x6000:                     # bra.w disp
                disp = s16(struct.unpack_from(">H", self.rom, pc + 2)[0])
                dest = pc + 2 + disp
                if dest not in (LOOP_A, LOOP_B):
                    raise UnknownOpcode("$%X: handler bra to $%X (not a loop head)" % (pc, dest))
                self._handlers[target] = ops
                return ops
            else:
                raise UnknownOpcode("$%X: unexpected handler opcode $%04X" % (pc, w))
        raise UnknownOpcode("$%X: handler runs past %d bytes without bra" % (target, guard - target))

    def handler_ops(self, target):
        """Decoded op list for a handler target (None for the loop heads)."""
        if target in (LOOP_A, LOOP_B):
            return None
        return self._decode_handler(target)

    def live_handlers(self):
        """{target: ops} for every distinct non-loop dispatch target."""
        out = {}
        for t in sorted(set(self.dispatch)):
            if t not in (LOOP_A, LOOP_B):
                out[t] = self._decode_handler(t)
        return out

    # -- the call --
    def call(self, stream_id, d0, d1, d3, ram, trace=None):
        """Reproduce one $E358 call into `ram` (bytearray, 64 KB at $FF0000).

        Returns a stats dict: dispatches, handler_calls, bytes_written,
        out_of_range (list of (addr, value) writes outside $FF0000-$FFFF),
        exited (why the call stopped: 'terminator', 'skip-zero',
        'd1-lt--21', 'stream-end').

        If `trace` is a list, every in-range write appends
        (addr, mask, value) -- the (old & mask) | value triple the
        hardware applies -- so callers can replay the write onto a
        different canvas (atlas stamping). Out-of-range writes are
        not traced.
        """
        stats = {"dispatches": 0, "handler_calls": 0, "bytes_written": 0,
                 "out_of_range": [], "exited": None}
        if not 0 <= stream_id < N_STREAMS:
            raise ValueError("stream id out of range: %d" % stream_id)
        d0u = d0 & 0xFFFE & 0xFFFF
        d1s = s16(d1)
        d3u = d3 & 0xFFFF
        if d1s < -21:
            stats["exited"] = "d1-lt--21"
            return stats
        a0 = STREAM_BASE + self.stream_offs[stream_id]
        rom = self.rom

        def rd():
            nonlocal a0
            b = rom[a0]
            a0 += 1
            return b

        if d1s < 0:
            for _ in range(-d1s):
                b = rd()
                if b == 0:
                    stats["exited"] = "skip-zero"
                    return stats
                a0 += b >> 4
            d1s = 0
        path_b = d3u != 0
        d1u = (d1s * 2) & 0xFFFF
        log_d0 = s16((d0u - (0x26 if path_b else 0x40)) & 0xFFFF)
        a6base = TABLE_B if path_b else TABLE_DISPATCH
        while True:
            if a0 >= len(rom):
                stats["exited"] = "stream-end"
                return stats
            b = rd()
            if b == 0:
                stats["exited"] = "terminator"
                return stats
            stats["dispatches"] += 1
            lo = b & 0xF
            d3w = (-2 * lo + log_d0) if path_b else (2 * lo + log_d0)
            d3w_u = d3w & 0xFFFF
            d4 = s16(self._word(TABLE_X + s16(d3w_u)))
            a5 = BUF_BASE + s16(self._word(TABLE_Y + s16(d1u))) + d4
            d1u = (d1u + 2) & 0xFFFF
            idx = (b & 0xF0) | ((d3w_u & 6) | (1 if path_b else 0))
            target = self.dispatch[idx]
            if target in (LOOP_A, LOOP_B):
                continue
            stats["handler_calls"] += 1
            ops = self._decode_handler(target)
            d5 = 0
            d6 = 0
            for op in ops:
                kind = op[0]
                if kind == "read":
                    d5 = rd()
                elif kind == "xform":
                    d5 = rom[a6base + d5]
                elif kind == "mask":
                    d6 = rom[TABLE_MASK + d5]
                elif kind == "write":
                    # addr_off is -1 for the -(a5) forms (byte lands one
                    # below a5); a5_delta is the net a5 movement.
                    addr = a5 + op[1]
                    if RAM_BASE <= addr < RAM_BASE + RAM_LEN:
                        ram[addr - RAM_BASE] = (ram[addr - RAM_BASE] & d6) | d5
                        stats["bytes_written"] += 1
                        if trace is not None:
                            trace.append((addr, d6, d5))
                    else:
                        stats["out_of_range"].append((addr, d5))
                    a5 += op[2]
                elif kind == "adda":
                    a5 += op[1]
                elif kind == "suba":
                    a5 -= op[1]
                else:  # pragma: no cover - decoder only emits the above
                    raise AssertionError(op)

    def call_buffer(self, stream_id, d0, d1, d3):
        """One call into a fresh zeroed 64 KB RAM; returns (buffer, stats).

        buffer is the 26,496 bytes at $FF1EC0, as bytes."""
        ram = bytearray(RAM_LEN)
        stats = self.call(stream_id, d0, d1, d3, ram)
        return bytes(ram[BUF_BASE - RAM_BASE:BUF_END - RAM_BASE]), stats


def fingerprint(buf):
    """(H1, H2) of a 26,496-byte $FF1EC0 buffer, as computed by the
    harness in tools/e358_harness.s immediately after the call:
    H1 = djb2-xor over the 6,624 big-endian longwords (h = h*33 ^ w,
    init 5381); H2 = rol(h,7) ^ w + 0x9E3779B9 per word (init 0).
    Two independent 32-bit hashes = 64 bits combined."""
    h1 = 5381
    h2 = 0
    for i in range(0, len(buf), 4):
        w = struct.unpack_from(">I", buf, i)[0]
        h1 = (((h1 << 5) + h1) ^ w) & 0xFFFFFFFF
        h2 = ((((h2 << 7) | (h2 >> 25)) & 0xFFFFFFFF) ^ w) + 0x9E3779B9
        h2 &= 0xFFFFFFFF
    return h1, h2


# -- ground-truth sweep case list (mirrored by tools/e358_harness.s) --
STREAMS_B = [0, 1, 2, 5, 17, 100, 175, 176, 200, 288, 400, 500, 600, 700, 800, 900, 943]
D0_B = [0x54, 0x80, 0xE0]
D1_B = [27, 50, 98, -1, -5]
EDGE_CASES = [
    (0, 0x40, -21, 0), (0, 0x40, -22, 0), (0, 0x40, -100, 0),
    (0, 0x40, 200, 0), (0, 0x40, 200, 1),
    (943, 0x40, 0, 0), (943, 0x40, -1, 1),
    (500, 0x40, 0, 2), (500, 0x40, 0, 0xFFFF),
    (0, 0x00, 0, 0), (0, 0x02, 0, 1), (0, 0x40, 0, 0),
]
N_SWEEP_A = 944 * 4
N_SWEEP_B = len(STREAMS_B) * len(D0_B) * len(D1_B) * 2
N_SWEEP = N_SWEEP_A + N_SWEEP_B + len(EDGE_CASES)


def sweep_cases():
    """The 4,298 harness cases as (stream, d0, d1, d3) tuples.

    Phase A (0..3775): all 944 streams x (d0,d3) in {(0x40,0),(0x42,0),
    (0x40,1),(0x42,1)}, d1=0. Phase B (3776..4285): STREAMS_B x D0_B x
    D1_B x d3 {0,1}. Phase C (4286..4297): EDGE_CASES."""
    out = []
    for stream in range(N_STREAMS):
        for d0, d3 in ((0x40, 0), (0x42, 0), (0x40, 1), (0x42, 1)):
            out.append((stream, d0, 0, d3))
    for stream in STREAMS_B:
        for d0 in D0_B:
            for d1 in D1_B:
                for d3 in (0, 1):
                    out.append((stream, d0, d1, d3))
    out.extend(EDGE_CASES)
    assert len(out) == N_SWEEP
    return out

