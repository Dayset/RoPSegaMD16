#!/usr/bin/env python3
"""Build phase B1 of the full big rework (patches/b1-vram/).

Migrates the VRAM layout from the PoC-fix2 ROM to allocation B
(DESIGN.md §3.2/§3.4) and falls back to the 36x23 image at the new
base/table (the 40x28 banded image is NOT buildable with the ROM
$E358 tables — see .scratch-big-rework-full/b1-vram/REPORT.md §2 and
verify_banded.py; the R2 check fails, so the brief's fallback applies).

Base: rop-big-rework-poc-fix2.rom (MD5 d4fc661f333ca2425987d2407693bce9).
Output: rop-big-rework-full-b1.rom + IPS (base -> B1) + changed-bytes.txt.

Changes (all asserting the base ROM's bytes first):
  Blob at $FD900 (assembled from source.s, 4 entries via nm):
    vbl_entry      VBlank hook ($1272, unchanged bytes — same +0 offset)
    redraw_entry   redraw_check hook ($1B918): install now R4=$07,
                   Plane B table $E000 (was $02/$4000)
    scene_entry    world_map_draw hook ($12C20): reset install state
    mapclose_entry world_map_redraw hook ($16302, NEW): reset install
                   state on map close (the map view's tile reloads
                   clobber the image; without this the fix2 gate would
                   suppress the post-close re-decode)
  Statics:
    $12C9A  move.w #$8402,-(sp) -> #$8407          (R4: Plane B $E000)
    $12E68  pea $004000.w -> pea $00E000.w         (room draw -> Plane B)
    $16326  pea $004000.w -> pea $00E000.w         (redraw room -> Plane B)
    (pea.w $E000 sign-extends to $FFFFE000, but vdp_set_write_addr
    rebuilds all 16 address bits from the low word, so it is correct;
    R16 at $12CDE is already $9001 and is NOT changed.)
  Allocator re-sequence in world_map_draw ($12D00-$12DE7, 232 bytes,
  rewritten in place with NOP padding; jsr map_decode(pc)
  displacements recomputed for moved blocks):
    font ($134) -> rec 1 ($19B) -> image sys_counter_add($33C) -> $1B4
    -> map tileset decode ($80,$10) -> $4F0 (RELOCATED, not evicted:
       world_sprites_setup $145D8 draws a visible 32x32 HUD sprite
       from $FF867C tiles during gameplay — see REPORT §3)
    -> move.w #$614,$FF0076 -> shared sys_counter_add($24) -> $614
    -> sprite tiles decode ($60,$B) -> $638
    -> $FF867E decode ($4C,$11) -> $698
    -> move.w #$1B4,$FF8676 (rec 6 EVICTED; $1B4 is its map-view
       reload base — map_view entry/exit reload it there)
    Free: $570-$613 (164 tiles). Sprite-pattern cache $6E4-$6FF and
    $780-$7FF left empty (reserved for phase C).
  Checksums fixed with tools/checksum.py fix-all (no code is shifted,
  so the stock tool's runtime-immediate address stays valid).

Usage: python3 patches/b1-vram/build.py
"""
import hashlib
import os
import re
import subprocess
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(DIR))
SCRATCH = os.path.join(REPO, 'build', 'scratch-b1-vram')
os.makedirs(SCRATCH, exist_ok=True)
WORKTREE = os.path.dirname(os.path.dirname(DIR))
BASE = os.environ.get('ROP_BASE', os.path.join(REPO, 'build', 'rop-big-rework-poc-fix2.rom'))
ORIG = os.environ.get('ROP_ORIGINAL', os.path.join(REPO, 'rop-original.gen'))
OUT_ROM = os.environ.get('ROP_OUT', os.path.join(REPO, 'build', 'rop-big-rework-full-b1.rom'))
MAIN = REPO
CHECKSUM = os.path.join(MAIN, "tools", "checksum.py")
VENV_PY = os.environ.get('ROP_VENV_PY', os.path.join(REPO, 'tools', '.venv', 'bin', 'python'))
if not os.path.exists(VENV_PY):
    VENV_PY = sys.executable

PAD_BASE = 0xFD900
BASE_MD5 = "d4fc661f333ca2425987d2407693bce9"
ORIG_MD5 = "30c18fdbe2183f64702ae9f1a45d63f9"
OLD_BLOB_END = 0xFDE26  # fix2 blob: $FD900 + 1318
MAP_DECODE = 0x1383C

VBL_SITE = 0x1272
REDRAW_SITE = 0x1B918
SCENE_SITE = 0x12C20
MAPCLOSE_SITE = 0x16302
STATIC_R4 = 0x12C9A
STATIC_DRAW = 0x12E68
STATIC_REDRAW = 0x16326
ALLOC_START = 0x12D00
ALLOC_END = 0x12DE8  # exclusive


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")
    return r


def nm_offsets(obj):
    out = run(["m68k-linux-gnu-nm", obj]).stdout
    offs = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in (
                "vbl_entry", "redraw_entry", "scene_entry", "mapclose_entry"):
            offs[parts[2]] = int(parts[0], 16)
    missing = {"vbl_entry", "redraw_entry", "scene_entry",
               "mapclose_entry"} - set(offs)
    if missing:
        raise RuntimeError(f"nm did not report entries: {missing}\n{out}")
    return offs


def apply_ips(orig, ips):
    assert ips[:5] == b"PATCH", "bad IPS header"
    out = bytearray(orig)
    i = 5
    while ips[i:i + 3] != b"EOF":
        off = int.from_bytes(ips[i:i + 3], "big")
        ln = int.from_bytes(ips[i + 3:i + 5], "big")
        i += 5
        if ln == 0:  # RLE record (not emitted by this builder)
            rle_len = int.from_bytes(ips[i:i + 2], "big")
            val = ips[i + 2]
            out[off:off + rle_len] = bytes([val]) * rle_len
            i += 3
        else:
            out[off:off + ln] = ips[i:i + ln]
            i += ln
    return bytes(out)


def build_allocator(base):
    """Rebuild the $12D00-$12DE7 allocator region in the new order.
    Returns 232 bytes. Slices are copied from the base ROM; any
    jsr map_decode(pc) (4EBA) inside a moved slice gets its
    displacement recomputed for its new address."""
    # (old_start, old_end, first_bytes) — first_bytes sanity-checks the block
    order = [
        ("init",    0x12D00, 0x12D08, bytes.fromhex("33fc0134")),
        ("font",    0x12D08, 0x12D24, bytes.fromhex("3f3c0067")),
        ("rec1",    0x12D24, 0x12D42, bytes.fromhex("3f3c0019")),
        ("image",   0x12D72, 0x12D84, bytes.fromhex("3f3c033c")),
        ("mapset",  0x12DA2, 0x12DCA, bytes.fromhex("3f3c0080")),
        ("CURSOR",  None, None, bytes.fromhex("33fc061400ff0076")),
        ("shared",  0x12D60, 0x12D72, bytes.fromhex("3f3c0024")),
        ("sprite",  0x12D84, 0x12DA2, bytes.fromhex("3f3c0060")),
        ("ff867e",  0x12DCA, 0x12DE8, bytes.fromhex("3f3c004c")),
        ("SET8676", None, None, bytes.fromhex("33fc01b400ff8676")),
    ]
    # the dropped rec-6 block: verify it is what we think it is
    rec6 = base[0x12D42:0x12D60]
    assert rec6[:4] == bytes.fromhex("3f3c01b6"), \
        f"rec6 block does not start with move.w #$1B6: {rec6[:4].hex()}"
    out = bytearray()
    for name, a, b, head in order:
        if a is None:  # synthetic instruction
            chunk = bytearray(head)
            print(f"  allocator: {name} (new {len(chunk)} bytes)")
        else:
            chunk = bytearray(base[a:b])
            assert chunk[:len(head)] == head, \
                f"allocator block {name} ${a:05X}: expected start " \
                f"{head.hex()}, got {chunk[:len(head)].hex()}"
            print(f"  allocator: {name} ${a:05X}-${b-1:05X} "
                  f"({len(chunk)} bytes) -> ${ALLOC_START + len(out):05X}")
        # fix jsr map_decode(pc) displacements inside this chunk
        # (68000 PC-relative EA = address of the extension word + disp,
        # i.e. jsr_at + 2; the original ROM's disps confirm this:
        # font jsr at $12D0E has disp $0B2C -> $12D10 + $0B2C = $1383C)
        new_base = ALLOC_START + len(out)
        for m in re.finditer(b"\x4e\xba", bytes(chunk)):
            jsr_at = new_base + m.start()
            # disp = target - (address of the extension word)
            disp = MAP_DECODE - (jsr_at + 2)
            assert -0x8000 <= disp < 0x8000, \
                f"jsr disp out of range at ${jsr_at:05X}: {disp}"
            chunk[m.start() + 2:m.start() + 4] = disp.to_bytes(2, "big",
                                                              signed=True)
            print(f"    jsr map_decode(pc) at ${jsr_at:05X}: disp ${disp & 0xFFFF:04X}")
        out += chunk
    assert len(out) <= ALLOC_END - ALLOC_START, \
        f"allocator overflow: {len(out)} > {ALLOC_END - ALLOC_START}"
    pad = (ALLOC_END - ALLOC_START) - len(out)
    assert pad % 2 == 0, f"odd NOP pad {pad}"
    out += b"\x4e\x71" * (pad // 2)
    print(f"  allocator: NOP pad {pad} bytes; total {len(out)} bytes")
    return bytes(out)


def main():
    base = open(BASE, "rb").read()
    assert len(base) == 0x100000, f"base size {len(base)}"
    assert hashlib.md5(base).hexdigest() == BASE_MD5, "base MD5 mismatch"
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5, \
        "original MD5 mismatch"
    assert all(b == 0xFF for b in base[OLD_BLOB_END:0xFE000]), \
        "padding not 0xFF after old blob end $FDE26"
    # allocator region in the base must equal the original ROM's
    orig = open(ORIG, "rb").read()
    assert base[ALLOC_START:ALLOC_END] == orig[ALLOC_START:ALLOC_END], \
        "allocator region in base != original (unexpected prior edit)"
    # exactly six jsr map_decode(pc) in the region (one per decode block)
    n_jsr = len(re.findall(b"\x4e\xba", base[ALLOC_START:ALLOC_END]))
    assert n_jsr == 6, f"expected 6 jsr map_decode(pc) in allocator, got {n_jsr}"

    src = os.path.join(DIR, "source.s")
    obj = os.path.join(SCRATCH, "source.o")
    binp = os.path.join(SCRATCH, "source.bin")
    run(["m68k-linux-gnu-as", "-m68000", "-o", obj, src])
    run(["m68k-linux-gnu-objcopy", "-O", "binary", obj, binp])
    offs = nm_offsets(obj)
    blob = open(binp, "rb").read()
    os.remove(obj)
    print(f"blob: {len(blob)} bytes at 0x{PAD_BASE:05X} "
          f"(vbl +0x{offs['vbl_entry']:X}, redraw +0x{offs['redraw_entry']:X}, "
          f"scene +0x{offs['scene_entry']:X}, "
          f"mapclose +0x{offs['mapclose_entry']:X})")
    assert offs["vbl_entry"] == 0, "vbl_entry must be first in the blob"
    assert PAD_BASE + len(blob) <= 0xFE000, "blob overruns $FDFFF"
    assert PAD_BASE > 0xFD07B, "blob must stay past the runtime checksum range"

    vbl_addr = PAD_BASE + offs["vbl_entry"]
    redraw_addr = PAD_BASE + offs["redraw_entry"]
    scene_addr = PAD_BASE + offs["scene_entry"]
    mapclose_addr = PAD_BASE + offs["mapclose_entry"]

    rom = bytearray(base)
    rom[PAD_BASE:PAD_BASE + len(blob)] = blob

    def patch(off, expected, new, what):
        got = bytes(rom[off:off + len(expected)])
        assert got == expected, f"{what} 0x{off:05X}: expected {expected.hex()}, got {got.hex()}"
        rom[off:off + len(new)] = new
        print(f"patched {what}: 0x{off:05X} {expected.hex()} -> {new.hex()}")

    # VBlank hook: unchanged (vbl_entry still at +0)
    patch(VBL_SITE,
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71"),
          "vblank hook $1272 (verify unchanged)")
    # redraw_check hook
    patch(REDRAW_SITE,
          bytes.fromhex("4eb9") + (PAD_BASE + 0x254).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big"),
          "redraw_check hook $1B918")
    # world_map_draw hook
    patch(SCENE_SITE,
          bytes.fromhex("4eb9") + (PAD_BASE + 0x4EC).to_bytes(4, "big"),
          bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big"),
          "world_map_draw hook $12C20")
    # world_map_redraw hook (NEW): jsr wait_vblank.l -> jsr mapclose
    patch(MAPCLOSE_SITE,
          bytes.fromhex("4eb90001386a"),
          bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big"),
          "world_map_redraw hook $16302 (NEW)")
    # Static: R4 $8402 -> $8407 (Plane B $E000)
    patch(STATIC_R4, bytes.fromhex("3f3c8402"), bytes.fromhex("3f3c8407"),
          "R4 Plane B $12C9A")
    # Static: room draws Plane B $4000 -> $E000 (pea.w sign-extends, but
    # vdp_set_write_addr rebuilds all 16 address bits — verified safe)
    patch(STATIC_DRAW, bytes.fromhex("48784000"), bytes.fromhex("4878e000"),
          "room draw dest $12E68")
    patch(STATIC_REDRAW, bytes.fromhex("48784000"), bytes.fromhex("4878e000"),
          "redraw draw dest $16326")
    # R16 already $01: assert only
    assert bytes(rom[0x12CDE:0x12CE2]) == bytes.fromhex("3f3c9001"), \
        "R16 site $12CDE is not $9001"
    print("R16 $12CDE verified $9001 (unchanged)")

    # Allocator re-sequence
    print("allocator re-sequence $12D00-$12DE7:")
    new_alloc = build_allocator(base)
    assert bytes(rom[ALLOC_START:ALLOC_END]) == base[ALLOC_START:ALLOC_END]
    rom[ALLOC_START:ALLOC_END] = new_alloc

    tmp = os.path.join(SCRATCH, "rop-big-rework-full-b1.gen.tmp")
    open(tmp, "wb").write(rom)
    run([VENV_PY, CHECKSUM, "fix-all", tmp, OUT_ROM])
    os.remove(tmp)
    v = run([VENV_PY, CHECKSUM, "verify-all", OUT_ROM]).stdout.strip()
    print(f"patched ROM: {OUT_ROM} — {v}")

    chk = open(OUT_ROM, "rb").read()
    assert chk[PAD_BASE:PAD_BASE + len(blob)] == blob
    assert chk[VBL_SITE:VBL_SITE + 8] == bytes.fromhex("4ef9") + vbl_addr.to_bytes(4, "big") + bytes.fromhex("4e71")
    assert chk[REDRAW_SITE:REDRAW_SITE + 6] == bytes.fromhex("4eb9") + redraw_addr.to_bytes(4, "big")
    assert chk[SCENE_SITE:SCENE_SITE + 6] == bytes.fromhex("4eb9") + scene_addr.to_bytes(4, "big")
    assert chk[MAPCLOSE_SITE:MAPCLOSE_SITE + 6] == bytes.fromhex("4eb9") + mapclose_addr.to_bytes(4, "big")
    assert chk[STATIC_R4:STATIC_R4 + 4] == bytes.fromhex("3f3c8407")
    assert chk[STATIC_DRAW:STATIC_DRAW + 4] == bytes.fromhex("4878e000")
    assert chk[STATIC_REDRAW:STATIC_REDRAW + 4] == bytes.fromhex("4878e000")
    assert chk[ALLOC_START:ALLOC_END] == new_alloc
    print("hook bytes + blob + statics + allocator verified in place")

    # ---- IPS: diff base -> patched, one record per maximal changed run ----
    records = []
    i = 0
    n = len(base)
    while i < n:
        if base[i] != chk[i]:
            j = i
            while j < n and base[j] != chk[j] and j - i < 0xFFFF:
                j += 1
            records.append((i, chk[i:j]))
            i = j
        else:
            i += 1
    ips = bytearray(b"PATCH")
    for off, data in records:
        ips += off.to_bytes(3, "big") + len(data).to_bytes(2, "big") + data
    ips += b"EOF"
    ips_path = os.path.join(DIR, "rings-of-power-big-rework-full-b1.ips")
    open(ips_path, "wb").write(ips)
    print(f"IPS: {ips_path} — {len(ips)} bytes, {len(records)} records")

    # ---- IPS round-trip: applying the IPS to the base must reproduce the ROM ----
    rt = apply_ips(base, bytes(ips))
    assert rt == chk, "IPS round-trip FAILED: applied IPS != patched ROM"
    print("IPS round-trip verified: base + IPS == ROM exactly")

    # ---- changed-bytes.txt ----
    lines = [
        "Changed bytes: rop-big-rework-poc-fix2.rom (MD5 d4fc661f333ca2425987d2407693bce9)"
        " -> rop-big-rework-full-b1.rom (big-rework-full phase B1: VRAM layout to"
        " allocation B, 36x23 image fallback — see .scratch-big-rework-full/b1-vram/REPORT.md)",
        "IPS applies to rop-big-rework-poc-fix2.rom, NOT to the original ROM.",
        "All addresses are 68000 ROM offsets (= file offsets). Values are hex bytes.",
        "",
        f"Trampoline blob: 0x{PAD_BASE:05X}-0x{PAD_BASE + len(blob) - 1:05X} "
        f"({len(blob)} bytes, source.s; old fix2 blob was 1318 bytes to $FDE25)",
        f"  vbl_entry      0x{vbl_addr:05X} (VBlank hook: D-pad scroll, unchanged)",
        f"  redraw_entry   0x{redraw_addr:05X} (redraw_check hook: Plane B $E000 install + gate)",
        f"  scene_entry    0x{scene_addr:05X} (world_map_draw hook: reset install state)",
        f"  mapclose_entry 0x{mapclose_addr:05X} (world_map_redraw hook, NEW: reset on map close)",
        "Hooks:",
        f"  0x{VBL_SITE:05X} jmp ${vbl_addr:05X}.l ; nop (unchanged)",
        f"  0x{REDRAW_SITE:05X} jsr $FDB54.l -> jsr ${redraw_addr:05X}.l",
        f"  0x{SCENE_SITE:05X} jsr $FDDEC.l -> jsr ${scene_addr:05X}.l",
        f"  0x{MAPCLOSE_SITE:05X} jsr wait_vblank.l -> jsr ${mapclose_addr:05X}.l (NEW)",
        "Statics:",
        "  0x12C9A move.w #$8402,-(a7) -> #$8407 (R4: Plane B $E000)",
        "  0x12E68 pea $004000.w -> pea $00E000.w (world_map_draw room -> Plane B)",
        "  0x16326 pea $004000.w -> pea $00E000.w (world_map_redraw room -> Plane B)",
        "  0x12CDE R16 $9001 (unchanged, verified)",
        "Allocator ($12D00-$12DE7, re-sequenced in place, NOP-padded):",
        "  font $134 -> rec 1 $19B -> image $1B4 (sys_counter_add $33C)",
        "  -> map tileset $4F0 (decode $80,$10; RELOCATED, not evicted)",
        "  -> move.w #$614,$FF0076 -> shared 36 $614 -> sprite tiles $638",
        "  -> $FF867E $698 -> move.w #$1B4,$FF8676 (rec 6 EVICTED)",
        "Checksums: fixed with tools/checksum.py fix-all (no code shifted)",
        "",
    ]
    for off, data in records:
        lines.append(f"0x{off:05X}-0x{off + len(data) - 1:05X} ({len(data)} bytes):")
        for k in range(0, len(data), 16):
            chunk_o = base[off + k:off + k + 16]
            chunk_n = data[k:k + 16]
            lines.append(f"  0x{off + k:05X}: {' '.join(f'{b:02x}' for b in chunk_o)}  -> "
                         f"{' '.join(f'{b:02x}' for b in chunk_n)}")
        lines.append("")
    open(os.path.join(DIR, "changed-bytes.txt"), "w").write("\n".join(lines))
    print(f"changed-bytes: {len(records)} records")

    # ---- original + base untouched ----
    assert hashlib.md5(open(ORIG, "rb").read()).hexdigest() == ORIG_MD5
    assert hashlib.md5(open(BASE, "rb").read()).hexdigest() == BASE_MD5
    print("original ROM untouched (MD5 re-verified); base ROM untouched")
    print("DONE")


if __name__ == "__main__":
    main()
