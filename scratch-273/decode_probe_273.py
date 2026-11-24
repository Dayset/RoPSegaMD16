#!/usr/bin/env python3
"""Decode a probe_273 log file (words at $FFD800) into human-readable form.
Usage: decode_probe_273.py <name>  (reads scratch-273/probe_273_<name>.log.txt)
Prints the header, the before/after char tables (mode 0/1) with template
names resolved via the renderer's tables, or the timing series (mode 2).
"""
import csv, struct, sys, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.path.join(HERE, "scratch-273")
NAME = sys.argv[1]
WORDS = []
for line in open(os.path.join(SCRATCH, "probe_273_%s.log.txt" % NAME)):
    line = line.strip()
    WORDS.append(int(line, 16) if line != "None" else None)

rom = open(os.path.join(HERE, "rop-original.gen"), "rb").read()

def s16(v):
    return v - 0x10000 if v is not None and v >= 0x8000 else v

def tmpl_name(t):
    # template t: first spawn word -> spawn record -> name_idx -> name table
    off = 0xCF1AC + 24 * t
    sp0 = struct.unpack_from(">H", rom, off)[0]
    soff = 0xCECF0 + 6 * sp0
    ni = struct.unpack_from(">H", rom, soff)[0]
    noff = 0xCD430 + 16 * ni
    nm = rom[noff:noff + 16].split(b"\x00")[0].decode("ascii", "replace")
    return nm, sp0

hdr = WORDS[:16]
print("magic=0x%04X start_frame=%d phase=%d done=%d test_id=%d" % tuple(hdr[:5]))
print("frame_at_test=%d mode=$FF00AE=%d $FF0E92=0x%04X $FF0E98=%d $FF0E16(after)=%d $FFC408(after)=%d" % (
    hdr[5], hdr[6], hdr[7], hdr[8], hdr[9], hdr[10]))
print("before_count=%d after_count=%d probe_mode=%d" % (hdr[11], hdr[12], hdr[13]))
TEST_MODE = hdr[13]

FIELDS = ["slot", "+00", "+02", "+06", "+0A", "+0C", "+0E", "+14", "+16",
          "+18", "+1C", "+1E", "+20", "+22", "+24", "+26"]

def show_records(base_word, count, label):
    print("--- %s (%d records) ---" % (label, count))
    for r in range(count):
        rec = WORDS[base_word + 16 * r: base_word + 16 * r + 16]
        if rec[0] is None:
            print("  (missing words at record %d)" % r)
            continue
        slot, w00, w02, w06 = rec[0], rec[1], rec[2], rec[3]
        mode = w00 & 0xF
        lvl = (w00 >> 4) & 0xF
        extra = ""
        if mode == 1 and w02 is not None and 0 <= w02 < 462:
            try:
                nm, sp0 = tmpl_name(w02)
                extra = " tmpl %d = %s (spawn0 %d)" % (w02, nm, sp0)
            except Exception as e:
                extra = " tmpl %d (name lookup failed: %s)" % (w02, e)
        elif mode == 5:
            extra = " MODE-5 ev=%s code-field +06=0x%04X" % (rec[7], w06)
        print("  slot %2d mode %d lvl %2d +02=%s +06=0x%04X +0A=%s +0C(X)=%s +0E(Y)=%s +14=%s +16=%s +18=0x%04X +1C=%s +1E=%s +20=%s +22=%s +24=%s +26=%s%s" % (
            slot, mode, lvl,
            ("0x%04X" % w02) if w02 is not None else "None",
            w06 if w06 is not None else 0,
            rec[4], rec[5], rec[6], rec[7], rec[8],
            rec[9] if rec[9] is not None else 0,
            rec[10], rec[11], rec[12], rec[13], rec[14], rec[15], extra))

if TEST_MODE == 2:
    n = hdr[11]
    print("--- timing (%d records: frame, $FF0E16, $FF00AC, $FF02A2) ---" % n)
    prev = None
    for r in range(n):
        rec = WORDS[16 + 4 * r: 16 + 4 * r + 4]
        if rec[0] is None:
            print("  (missing at record %d)" % r)
            continue
        d = "" if prev is None else " dE16=%+d dframe=%d rate=%.3f/frame" % (
            rec[1] - prev[1], rec[0] - prev[0],
            (rec[1] - prev[1]) / max(1, rec[0] - prev[0]))
        print("  frame %5d $FF0E16=%4d $FF00AC=%d $FF02A2=0x%04X%s" % (rec[0], rec[1], rec[2], rec[3], d))
        prev = rec
else:
    bc, ac = hdr[11], hdr[12]
    show_records(16, bc, "BEFORE")
    show_records(16 + 16 * bc, ac, "AFTER")
