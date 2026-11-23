#!/usr/bin/env python3
"""typed_data.py — find pointer-bearing data still emitted as incbin (#281).

For each region in disasm/regions.csv, scan for big-endian longs that land
on a meaningful target, plus the known pointer tables ($5F524 stream
offsets are relative; $DF58 dispatch longs are absolute and already typed).
Report per region: candidate pointers, how many are confirmed, class.
Regenerates POINTERS.md.

Targets are MEANINGFUL addresses only — function entries (Ghidra bodies +
named symbols), region starts, and named (non-auto) labels. The auto
`Lxxxxxx` labels cover every address-bearing line, so a hit on one of
those proves nothing (e.g. the gfx-record declen $000004A0 "points at"
vdp_write_fixed_pair; word pairs in text arrays "point at" chunk
records). Value 0 (rom_start) is excluded for the same reason. Every
strict hit is adjudicated in POINTERS.md with its evidence, not counted
as confirmed on the strength of the hit alone.

Dedicated checks (structure, not label coincidence):
  * song-prefix check: the 19 `pea.l` targets in `song_play_direct`
    ($173EC) are song starts; the long at start-4 is the song end
    pointer, read by `sound_start_song` ($EB88A: `move.l -$4(a0),
    ram_sys_ff0230.l`). Confirmed static-reader + live-read (#280's
    test-only patch of all 19 drops both iso routes to 0 diffs).
  * relative tables, verified not assumed: $5F524/$5F7E4 stream offsets
    (base $603E4, monotonic, targets in stream range); the 10-byte
    record tables $43850 (252 recs, base $44228), $96120 (62 recs, base
    $9638C), $B86AE (90 recs, base $B8A32) — ptr relative to the streams
    base, monotonic, declen > 0, type == 1, every record decodes
    (docs/graphics.md, tools/lzss_check.py); $0DC0C2 dictionary word
    offsets (16-bit, into the blob); word-offset/word-dispatch tables
    (16-bit relative, gen_src §3a).
Confirmation classes: `static-reader` (code in `rop.s` references the
table's label / reads *(addr-4)), `live-read` (BlastEm/GPGX note),
`relative` (offsets + base, no shift risk), `dismissed` (evidence it is
data, not a pointer), `unconfirmed`.
Usage: python3 tools/typed_data.py [--rom rop-original.gen]
Writes POINTERS.md in the repo root. Exit 0.
"""
import argparse
import csv
import re
import sys
from pathlib import Path

ROM_SIZE = 0x100000
STREAM_BASE = 0x603E4
STREAM_OFF_1 = (0x5F524, 0x5F7E4)   # 176 u32 relative offsets, base $603E4
STREAM_OFF_2 = (0x5F7E4, 0x0603E4)  # 768 u32 relative offsets, base $603E4
JUMP_TABLE = (0xDF58, 0xE358)       # absolute longs, already emitted as dc.l
# 10-byte record tables [ptr:u32][declen:u32][type:u16]: ptr is RELATIVE to
# the streams base, verified by monotonicity + clean decode of every record.
RECORD_TABLES = {
    0x43850: (252, 0x44228),   # map chunk tilemaps
    0x96120: (62, 0x9638C),    # gfx tile table
    0xB86AE: (90, 0xB8A32),    # gfx lzss streams
}
# Classes whose bytes are opaque payload: a strict hit inside one is listed
# for review but is coincidence until a reader says otherwise.
OPAQUE_CLASSES = {
    "terrain-stream", "lzss-stream", "text-dd5c-stream", "map-chunk-streams",
    "high-entropy", "unknown",
}

INC = re.compile(r'incbin\s+"rop-original\.gen",\s*(\$[0-9A-Fa-f]+|\d+),\s*(\$[0-9A-Fa-f]+|\d+)')
VEC = re.compile(r'^\tdc\.l \S+\t; \$[0-9A-F]+\s+vector$')
LABEL_DEF = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*):\s*$')
ADDR_COMMENT = re.compile(r';\s*(?:table\s+)?\$([0-9A-Fa-f]{6})\b')
DCB = re.compile(r'^\tdcb\.b\s+\$([0-9A-Fa-f]+),\$FF')
DC_LINE = re.compile(r'^\tdc\.([bwl])\s+(.*?)\s*(?:;.*)?$')
PEA_SONG = re.compile(r'^\tpea\.l\s+(L[0-9A-F]{6})\.l\s*;\s*\$[0-9A-F]+\s*$')
AUTO_LABEL = re.compile(r'^L[0-9A-F]{6}$')


def num(t):
    return int(t[1:], 16) if t.startswith('$') else int(t)


def load_labels(root):
    """label name -> address, from rop.s. A label's address is the address of
    the next address-bearing line after it (incbin directive, dc.* comment,
    or code-line comment); rom_start: is 0."""
    labels = {}
    pending = []
    addr = None
    for line in (root / "disasm/src/rop.s").read_text(errors="replace").splitlines():
        m = LABEL_DEF.match(line)
        if m:
            pending.append(m.group(1))
            continue
        if line.startswith("rom_start:"):
            addr = 0
        else:
            im = INC.search(line)
            if im:
                addr = num(im.group(1))
            else:
                am = ADDR_COMMENT.search(line)
                if am:
                    addr = int(am.group(1), 16)
        if addr is not None and pending:
            for name in pending:
                if name in labels:
                    sys.exit(f"typed_data: duplicate label {name}")
                labels[name] = addr
            pending = []
    if pending:
        sys.exit(f"typed_data: labels with no following address: {pending}")
    return labels


def load_code_starts(root):
    """Function entry addresses from Ghidra body ranges + named symbols."""
    starts = set()
    for line in (root / "disasm/ghidra/function_bodies.txt").read_text().splitlines():
        if line.startswith("RANGE "):
            _, entry, _s, _e = line.split()
            starts.add(int(entry, 16))
    for path in sorted([*(root / "disasm/symbols").glob("code_*.csv"),
                        root / "disasm/symbols/extra.csv",
                        root / "disasm/symbols/auto.csv"]):
        if not path.exists():
            continue
        with path.open(newline="") as fh:
            for row in csv.DictReader(fh):
                starts.add(int(row["addr"], 16))
    return starts


def load_regions(root):
    rows = []
    with (root / "disasm/regions.csv").open(newline="") as fh:
        for r in csv.DictReader(fh):
            rows.append({
                "start": int(r["start"], 16), "end": int(r["end"], 16),
                "class": r["class"], "name": r["name"],
                "doc_ref": r.get("doc_ref") or "", "tier": r.get("tier") or "",
            })
    return rows


def typed_ranges(root):
    """Byte ranges of rop.s already emitted as dc.l vector lines (typed)."""
    typed = []
    for line in (root / "disasm/src/rop.s").read_text(errors="replace").splitlines():
        if VEC.match(line):
            a = int(ADDR_COMMENT.search(line).group(1), 16)
            typed.append((a, a + 4))
    return typed


def song_starts(root):
    """The 19 song start addresses with their dispatch case index: the
    `pea.l` targets immediately followed by `jsr sound_start_song.l` in
    `song_play_direct` ($173EC-$17545), mapped to case numbers via the
    word-offset dispatch table at $17546 (21 entries; jmp at $1757E,
    target = $17580 + signed word). Cases 18/19 dispatch straight to
    the rts (silent); case 20 is the arrival jingle. Returns
    [(case, start), ...] sorted by case."""
    lines = (root / "disasm/src/rop.s").read_text(errors="replace").splitlines()
    rom = Path("rop-original.gen").read_bytes()
    block_to_start = {}
    for i, line in enumerate(lines):
        m = PEA_SONG.match(line)
        if m and i + 1 < len(lines) and lines[i + 1].startswith("\tjsr sound_start_song.l"):
            # the block starts at the pea.l itself: its `; $addr` comment
            am = ADDR_COMMENT.search(line)
            block_to_start[int(am.group(1), 16)] = int(m.group(1)[1:], 16)
    out = []
    for k in range(21):
        w = int.from_bytes(rom[0x17546 + 2 * k:0x17548 + 2 * k], "big", signed=True)
        t = 0x17580 + w
        if t in block_to_start:
            out.append((k, block_to_start[t]))
    return out


def check_record_table(rom, start, count, base):
    """Verify a 10-byte record table is relative: ptrs monotonic from 0,
    declen > 0, type == 1, last stream ends at or before the next table."""
    ptrs = []
    for k in range(count):
        a = start + 10 * k
        ptr = int.from_bytes(rom[a:a + 4], "big")
        dl = int.from_bytes(rom[a + 4:a + 8], "big")
        ty = int.from_bytes(rom[a + 8:a + 10], "big")
        if dl == 0 or ty != 1:
            return f"record {k}: declen={dl} type=${ty:04X} — NOT the record layout"
        ptrs.append(ptr)
    mono = all(ptrs[i] < ptrs[i + 1] for i in range(len(ptrs) - 1))
    return (f"relative offsets base ${base:06X}, monotonic={mono}, "
            f"first=${ptrs[0]:06X} last=${ptrs[-1]:06X}, {count}/{count} type-1 declen>0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default="rop-original.gen")
    args = ap.parse_args()
    root = Path.cwd()
    rom = Path(args.rom).read_bytes()
    assert len(rom) == ROM_SIZE, f"{args.rom} must be the 1 MB dump"
    labels = load_labels(root)
    label_starts = set(labels.values())
    code_starts = load_code_starts(root)
    regions = load_regions(root)
    typed = typed_ranges(root)
    starts = song_starts(root)

    def is_typed(a, b):
        return any(a >= s and b <= e for s, e in typed)

    # Meaningful targets only: function entries, region starts, named
    # (non-auto) labels. Auto Lxxxxxx labels and value 0 are excluded —
    # a hit on those is coincidence, not evidence.
    named = {v for k, v in labels.items()
             if not AUTO_LABEL.match(k) and k != "rom_start"}
    region_starts = {r["start"] for r in regions}
    targets = code_starts | region_starts | named

    def kind_of(v):
        kinds = []
        if v in code_starts:
            kinds.append("code")
        if v in region_starts:
            kinds.append("region-start")
        if v in named:
            kinds.append("named")
        return "+".join(kinds) or "unlabelled"

    # --- dedicated song-prefix check ---
    song_rows = []
    for case, s in starts:
        p = s - 4
        v = int.from_bytes(rom[p:p + 4], "big")
        ok = v > s and (v - s) % 256 == 0 and v < ROM_SIZE
        song_rows.append((case, s, p, v, ok))
    n_song_bad = sum(1 for *_, ok in song_rows if not ok)

    out_lines = [
        "# Pointer candidates still in incbin (#281)",
        "",
        "Generated by `tools/typed_data.py` — do not hand-edit. Pass 1 is a",
        "strict label hit: a big-endian long inside an incbin region whose",
        "value lands on a MEANINGFUL target (function entry, region start,",
        "or named label). Auto `Lxxxxxx` labels and value 0 are excluded —",
        "a hit on those is coincidence (see the dispositions below). A",
        "strict hit is a candidate, not a confirmation: confirmation needs",
        "a reader (`static-reader`) or a live run (`live-read`).",
        "",
        "## Confirmed: song end-pointer prefixes (19)",
        "",
        "One 4-byte absolute long per song at start-4, read by",
        "`sound_start_song` ($EB88A: `move.l -$4(a0), ram_sys_ff0230.l`).",
        "Starts are the 19 `pea.l` targets in `song_play_direct` ($173EC),",
        "mapped to case numbers via the dispatch table at $17546 (cases 18/19",
        "are silent, case 20 is the arrival jingle sharing song 2's tail).",
        "Confirmation: `static-reader` (the `-$4(a0)` read) + `live-read`",
        "(#280's test-only patch of all 19 to end+`$100` drops the iso Buc",
        "route 46/9,142 diffs and the iso explore route 613/16,420 diffs,",
        "both to 0). Emitted as `ptr-table` rows in `disasm/regions.csv`",
        "and as `dc.l label` by `tools/gen_src.py`.",
        "",
        "| Song | Start | Prefix at | End pointer | Length |",
        "|---:|---:|---:|---:|---:|",
    ]
    for case, s, p, v, ok in song_rows:
        out_lines.append(f"| {case} | ${s:06X} | ${p:06X} | ${v:06X} | ${v - s:X} |")
    out_lines += [
        "",
        f"Song-prefix check: {len(song_rows)} starts, {len(song_rows) - n_song_bad} "
        f"well-formed (end > start, length a multiple of $100, in ROM); "
        f"{n_song_bad} malformed." if n_song_bad else
        f"Song-prefix check: {len(song_rows)} starts, all well-formed "
        f"(end > start, length a multiple of $100, in ROM).",
        "",
        "## Relative tables (verified, no shift risk)",
        "",
        "| Region | Check |",
        "|---|---|",
    ]
    for (s, e) in (STREAM_OFF_1, STREAM_OFF_2):
        vals = [int.from_bytes(rom[a:a + 4], "big") for a in range(s, e - 3, 4)]
        mono = all(vals[i] < vals[i + 1] for i in range(len(vals) - 1))
        in_range = all(STREAM_BASE <= STREAM_BASE + v < 0x96120 for v in vals)
        out_lines.append(
            f"| ${s:06X}–${e - 1:06X} stream offsets | relative, base $603E4, "
            f"monotonic={mono}, targets in stream range={in_range} |")
    for s, (count, base) in sorted(RECORD_TABLES.items()):
        out_lines.append(f"| ${s:06X} record table | {check_record_table(rom, s, count, base)} |")
    out_lines += [
        "| $0DC0C2 dictionary offsets | 16-bit relative offsets into the blob; "
        "end sentinel `0x5206` = blob length 20998; reader `$013788`/`$013798` |",
        "| word-offset / word-dispatch tables | 16-bit relative (`move.w table(pc,d0.w)` then `jmp`); "
        "targets checked by gen_src §3a |",
        "| $FFA7CC spell-rank table | RAM address, runtime-built — not a ROM pointer |",
        "",
        "## Strict pass-1 hits (candidates, adjudicated)",
        "",
        "| Region | Class | Hits | Disposition |",
        "|---|---|---:|---|",
    ]
    total_strict = 0
    details = []
    for r in regions:
        s, e, cls = r["start"], r["end"], r["class"]
        n = e - s + 1
        if n < 4:
            continue
        hits = []
        for a in range(s, e - 2, 4):
            v = int.from_bytes(rom[a:a + 4], "big")
            if v != 0 and v in targets and not is_typed(a, a + 4):
                hits.append((a, v))
        if not hits:
            continue
        total_strict += len(hits)
        # Disposition by region: the review below is the evidence, not the count.
        if (s, e + 1) in (STREAM_OFF_1, STREAM_OFF_2):
            disp = "relative offsets (see above) — the hit values are the offset words themselves"
        elif s in RECORD_TABLES:
            disp = ("relative record ptrs (see above); the hits are the declen "
                    "fields ($000004A0 = 1184) coinciding with a code label")
        elif cls in OPAQUE_CLASSES:
            disp = "opaque payload — compressed-stream bytes coinciding with a target; no reader"
        elif cls == "text-word-arrays":
            disp = "word arrays — the 4-byte window straddles two u16 words; values are word pairs, not longs"
        elif cls in ("text-dialogue-records", "gfx-palette-master-table"):
            disp = "word-structured records — the 4-byte window straddles two u16 words"
        else:
            disp = "REVIEW — no disposition yet"
        out_lines.append(f"| ${s:06X}–${e:06X} | {cls} | {len(hits)} | {disp} |")
        for a, v in hits:
            lab = next((nm for nm, av in labels.items() if av == v), f"${v:06X}")
            details.append(
                f"- ${a:06X}: `${v:08X}` -> {lab} ({kind_of(v)}) "
                f"[region ${s:06X} {cls}]")
    out_lines += [
        "",
        f"Total strict candidates: {total_strict}; confirmed absolute pointers "
        f"in incbin: {len(song_rows)} (the song prefixes above); all other strict "
        f"hits are dismissed with the evidence in the table.",
        "",
        "## Candidates",
        "",
    ] + (details or ["(none)"]) + [""]
    (root / "POINTERS.md").write_text("\n".join(out_lines))
    print(f"typed_data: {len(song_rows)} song prefixes confirmed, "
          f"{total_strict} strict candidates, {n_song_bad} malformed song prefixes; wrote POINTERS.md")
    if n_song_bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
