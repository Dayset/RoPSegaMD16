#!/usr/bin/env python3
"""Fix song 13 (the true Academy) in a patched ROM — v4: one more timbre
softening (DT/MULT) on top of v3.

Built from rop-original.gen (like v1/v2/v3 — NOT patched on top of the v3 ROM).
Keeps v1 + v2 + v3 and adds the MULT change Dayset asked for after v3
("It's getting better, one more softening on top?"):

  v1. Bass voice on ch4: ch2's line two octaves down (p1 - 24), velocity
     110, inserted before each ch2 pitch-change note the melody DWELLS on.
  v2. ch5 one octave down: p1 - 12 on every ch5 note event ($85 and $95).
     ch5 velocity 124 -> 80 (v1).
  v3. Soften the instruments (FM timbre) — see the investigation below.
  v4. DT/MULT softening — see the v4 investigation below.

INSTRUMENT INVESTIGATION (v3):
  The $CX setup [(1,0),(2,14),(4,28),(5,16),(6,2)] selects voices by index
  into the voice-pointer table at Z80 $0382 (ROM 0x0EBEF0). The driver
  ($07F0) does IY = word[$0382 + 2*param]; voice structs are 36 bytes apart
  (Z80 $0E78 + 36*idx, ROM 0x0ECE52 + 36*idx). The YM write loop ($04CC)
  reads operator params from IY+$0C..$23 (DT/MULT, TL, RS/AR, AM/DR, SR,
  SL/RR) and FB/ALG+pan from IY+$2C/$2D — which is the NEXT struct's
  $08/$09 (layout quirk: the 36-byte blocks overlap by 12 bytes).
  Voice 14 (ch2 melody) = Z80 $12E4 (ROM 0x0ECE52): FB=7 (MAX), ALG=2,
  TL op1/op3/op2/op4 = 16/14/2F/00, AR all 31 (instant attack),
  DT/MULT 0C/41/1F/53 (op1 MULT 12, op2 MULT 15 — very high multiples).
  Voice 16 (ch5) = Z80 $132C (ROM 0x0ECE9A): FB=7 (MAX), ALG=3,
  TL 1D/35/2C/03, AR 1B/1F/19/10, DT/MULT 75/72/31/31.
  Both lead voices run at MAXIMUM feedback — the prime harshness suspect:
  feedback on op1 (a modulator in ALG 2/3, where only op4 is a carrier
  per $05F0) builds a bright, sawtooth-like harmonic stack. The octave
  drop (v2) moved the fundamentals but not the harmonics — hence p90
  stayed ~2,354 Hz.

  CRITICAL — SHARED INSTRUMENTS (verified by parsing ALL $CX events in
  all 18 songs, plus the SFX slide path $0A78 which selects only voices
  0/1/2/128/129/130 via the $00EB table): voice 14 is used by songs
  5, 12, 13, 14, 15; voice 16 by songs 5, 11, 12, 13, 14, 15; voice 28
  (ch4 bass) by songs 1, 2, 5, 7, 10, 11, 12, 13, 14, 15, 17. In-place
  edits to voices 14/16 would change five other songs — NOT done.
  Instead v3 uses PRIVATE COPIES in unused voice slots: slot 15 (ch2)
  and slot 17 (ch5). Unused indices (no song, no SFX path): 5, 7, 9, 10,
  11, 15, 17, 20, 22, 25, 30, 31. Song 13's $CX is repointed ch2 14->15,
  ch5 16->17 (2 bytes, size-neutral, stream length/seek unchanged).
  The copies' FB/ALG+pan bytes live in the NEXT blocks' $08/$09
  (slot 15's at voice 16's $08 = ROM 0x0ECEA2; slot 17's at voice 18's
  $08 = ROM 0x0ECEEA) — those bytes belong to the unused voices 15/17,
  so writing them touches no other song's sound.
  ONLY the operator params ($0C-$23, 24 bytes) are copied into the
  target slots: each block's $00-$0B header belongs to the PREVIOUS
  voice (its $08/$09 are that voice's FB/ALG+pan, its $04/$05 the
  F-num runtime slot), so the headers are left untouched — that is
  what keeps the shared voices 14/16 byte-identical, including their
  FB/ALG bytes (voice 14's 0x3A at slot 15 $08, voice 16's 0x3B at
  slot 17 $08). (Copying the full 36 bytes would clobber exactly those
  FB/ALG bytes — caught by the verification asserts, fixed to the
  $0C-$23 copy.)

  THE SOFTENING (per private copy):
  - Feedback FB 7 -> 2 (ALG unchanged: 2 for ch2, 3 for ch5).
  - Modulator TLs +8 (~6 dB quieter modulators -> less modulation depth
    -> fewer upper harmonics): voice 14 op1 16->1E, op3 14->1C,
    op2 2F->37; voice 16 op1 1D->25, op3 35->3D, op2 2C->34.
    Carrier op4 TL untouched (00 / 03).
  - Attack softened on the ch2 copy only (its ARs were all 31, instant):
    RS/AR 1F/1F/DF/9F -> 18/18/D8/98 (AR 31 -> 24, RS bits kept).
    Voice 16's ARs (1B/1F/19/10) are already varied — left alone.
  - NOT changed in v3: DT/MULT (the high multiples were the fallback
    if p90 did not move), DR/SR/SL/RR, pan (kept C0 stereo).

MULT INVESTIGATION (v4):
  The v3 doc's carrier map ($05F0) is confirmed against the hardware:
  the YM2612 algorithm table (MAME fm2612.c setup_connection) gives
  carriers {op4} for ALG 0-3, {op2, op4} for ALG 4, {op2, op3, op4}
  for ALG 5-6, all four for ALG 7 — exactly the driver's velocity
  map (op4 always; op2 iff ALG >= 4; op3 iff ALG >= 5; op1 iff
  ALG == 7). So for voice 14 (ALG 2) and voice 16 (ALG 3) ops 1-3
  are ALL modulators and only op4 is a carrier. A modulator's MULT
  sets its sideband spacing around the carrier (f_c +/- k*M*f0):
  MULT 12/15 throws sidebands far up the spectrum (bright, harsh);
  MULT 1 clusters them at the fundamental (warm). A carrier's MULT
  sets the pitch itself — op4 is NEVER touched.
  Voice-struct DT/MULT byte order is op1, op3, op2, op4 (slot order);
  DT is the high 3 bits, MULT the low 4. v4 (private copies only):
  - ch2 copy (slot 15, from voice 14, ALG 2, carrier op4 MULT 3):
    op1 MULT 12 -> 1 (0x0C -> 0x01, DT 0 kept),
    op2 MULT 15 -> 1 (0x1F -> 0x11, DT 1 kept);
    op3 MULT 1 and op4 MULT 3 unchanged. DT/MULT 0C/41/1F/53 -> 01/41/11/53.
  - ch5 copy (slot 17, from voice 16, ALG 3, carrier op4 MULT 1):
    op1 MULT 5 -> 1 (0x75 -> 0x71, DT 7 kept),
    op3 MULT 2 -> 1 (0x72 -> 0x71, DT 7 kept);
    op2 MULT 1 and op4 MULT 1 unchanged. DT/MULT 75/72/31/31 -> 71/71/31/31.
  DT left alone in v4: detune only nudges operator frequencies by a
  few cents (chorus/beating), it does not create the high-harmonic
  harshness — that is MULT + FB + TL depth. Changing DT would risk
  pitch drift on the carrier (op4 DT 5 / DT 3) and buys no softening.
  FB (2), TLs (+8), AR (ch2 24) stay exactly as v3 — v4 is one more
  softening, not a re-tune.

LENGTH CONSTRAINT: same as v2 — re-emitted stream + $FC $80 seek must end
in the window [9983, 10176] so the seek lands on +10240; the dead span
(song 14's data) is NEVER written. The $CX repoint changes 2 bytes
in-place, so the seek stays +10120.

Verification: song_check_rs.py (RS-aware) 18/18 on the patched ROM,
song-13 event diff vs the original (only bass inserts + ch5 velocity
scale + ch5 octave drop + the 2 $CX repoints, ticks identical),
$CX usage survey on the patched ROM (slots 15/17 used ONLY by song 13),
voice-table diff listing, tools/song_check.py strict grammar (flags the
RS bytes — expected, same as v2), checksums fixed.

Reads rop-original.gen, writes rop-academy-fix13-v4.gen + fix_song13_v4_patch.json.
No repo files are touched.
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROM_PATH = HERE / 'rop-original.gen'
OUT_PATH = HERE / 'rop-academy-fix13-v4.gen'
PATCH_PATH = HERE / 'fix_song13_v4_patch.json'
OCTAVE_DROP = 12  # v2: ch5 pitches down one octave (p1 - 12), p1 >= 12 only

START, LENGTH = 0x0F6844, 10240
END = START + LENGTH
PREFIX_OFF = 0x0F9006 - START  # 10178: song 14's end-pointer prefix — do not write
SEEK_LO, SEEK_HI = 9983, 10176  # stream-bytes window for the seek to land at +10240
BASS_VEL = 110
BASS_CH = 4
VEL_SCALE = 80 / 124    # ch5 $9X p2: median 124 -> 80

# ---- v3: voice table (driver blob) ----
Z80_BASE_ROM = 0x0EBB6E          # ROM offset of Z80 $0000 (driver blob base)
VOICE_TABLE_ROM = 0x0EBEF0       # Z80 $0382: 32 x 2-byte pointers
CH2_VOICE, CH5_VOICE = 14, 16    # shared voices song 13 uses
CH2_COPY, CH5_COPY = 15, 17      # unused slots (verified) for the private copies
FB_NEW = 2                       # feedback 7 -> 2 (v3, kept)
TL_ADD = 8                       # modulator TLs +8 (~6 dB quieter) (v3, kept)
AR_NEW = 24                      # ch2 copy attack 31 -> 24 (RS bits kept) (v3, kept)
# v4: MULT overrides, keyed by DT/MULT slice offset (0=op1, 1=op3, 2=op2, 3=op4).
# DT bits (high nibble) are preserved; only the low-nibble MULT changes.
MULT_CH2 = {0: 1, 2: 1}           # op1 12->1, op2 15->1 (op3 1, op4/carrier 3 kept)
MULT_CH5 = {0: 1, 1: 1}           # op1 5->1, op3 2->1 (op2 1, op4/carrier 1 kept)


def voice_ptr(rom, idx):
    return rom[VOICE_TABLE_ROM + 2 * idx] | (rom[VOICE_TABLE_ROM + 2 * idx + 1] << 8)


def voice_rom(rom, idx):
    return Z80_BASE_ROM + voice_ptr(rom, idx)


def soften_params(params24, ar=None):
    """Soften one 24-byte operator-params slice ($0C-$23 of a voice struct).
    Offsets relative to the slice: DT/MULT $00-03, TL $04-07, RS/AR
    $08-0B, AM/DR $0C-0F, SR $10-13, SL/RR $14-17.
    TL: op1 $04, op3 $05, op2 $06 (modulators for ALG 2/3); carrier op4
    $07 untouched. AR (low 5 bits of $08-$0B) optionally softened."""
    b = bytearray(params24)
    assert len(b) == 24
    for off in (0x04, 0x05, 0x06):
        b[off] = min(0x7F, b[off] + TL_ADD)
    if ar is not None:
        for off in (0x08, 0x09, 0x0A, 0x0B):
            b[off] = (b[off] & 0xE0) | ar
    return bytes(b)


def set_mults(params24, mults):
    """Lower the MULT of selected operators in a 24-byte operator-params
    slice. DT/MULT live at slice offsets $00-$03 (op1, op3, op2, op4);
    DT is the high 3 bits, MULT the low 4 — keep DT, set MULT."""
    b = bytearray(params24)
    assert len(b) == 24
    for off, mult in mults.items():
        assert 0 <= off <= 3 and 1 <= mult <= 15, (off, mult)
        assert off != 3, 'never touch the carrier (op4) MULT'
        b[off] = (b[off] & 0xF0) | mult
    return bytes(b)


def set_fb_alg(rom, voice_idx, fb, alg, pan=0xC0):
    """Write voice N's FB/ALG+pan — they live at voice (N+1)'s $08/$09."""
    nxt = voice_rom(rom, voice_idx + 1)
    rom[nxt + 0x08] = (fb << 3) | alg
    rom[nxt + 0x09] = pan


def parse(rom, start, length):
    """Strict parse (song_check.py grammar). Returns (lead, events, seek_off)."""
    end = start + length
    i = start
    lead = rom[i]
    assert lead < 0x80, 'expected leading byte < 0x80'
    i += 1
    events = []  # (offset, evbyte, kind, ch, p1, p2, delay)
    while i < end:
        b = rom[i]
        hi = b & 0xF0
        ch = b & 0x0F
        off = i - start
        if hi in (0x80, 0x90):
            events.append([off, b, 'note', ch, rom[i + 1], rom[i + 2], rom[i + 3]])
            i += 4
        elif hi == 0xC0:
            events.append([off, b, 'setup', ch, rom[i + 1], None, rom[i + 2]])
            i += 3
        elif b == 0xFC:
            assert rom[i + 1] == 0x80, f'$FC end at offset {off}'
            return lead, events, off
        else:
            raise ValueError(f'invalid byte 0x{b:02X} at offset {off}')
    raise ValueError('ran off the region end without a seek')


def reemit(events, total_ticks, times, bass_at, vel_scale):
    """Re-emit the stream with RS collapse + bass + ch5 velocity scale
    + v2 octave drop + v3 $CX repoint (ch2 14->15, ch5 16->17).
    Returns (stream_bytes_without_lead, rs_saved, ch5_scaled, bass_count,
    ch5_shifted, repointed)."""
    out = bytearray()
    last_ev = None
    rs_saved = 0
    ch5_scaled = 0
    ch5_shifted = 0
    repointed = 0
    new_ticks = 0
    for k, e in enumerate(events):
        off, ev, kind, ch, p1, p2, d = e
        if k in bass_at:
            out += bytes([0x90 | BASS_CH, bass_at[k], BASS_VEL, 0])
            last_ev = 0x90 | BASS_CH
        if kind == 'setup':
            # v3: repoint song 13's $CX at its private softened voice copies
            if ch == 2 and p1 == CH2_VOICE:
                p1 = CH2_COPY
                repointed += 1
            elif ch == 5 and p1 == CH5_VOICE:
                p1 = CH5_COPY
                repointed += 1
        if kind == 'note' and ch == 5:
            # v2: octave drop on BOTH $85 and $95 (they are paired note
            # on/off with identical p1 — shifting only one would strand
            # the other). p1=0 (2 events, loop-seam rest) left alone.
            if p1 >= OCTAVE_DROP:
                p1 -= OCTAVE_DROP
                ch5_shifted += 1
            if (ev >> 4) == 9:
                p2 = max(1, round(p2 * vel_scale))
                ch5_scaled += 1
        if kind == 'note':
            if ev == last_ev:
                out += bytes([p1, p2, d])
                rs_saved += 1
            else:
                out += bytes([ev, p1, p2, d])
            last_ev = ev
        else:
            assert ev != last_ev, 'unexpected RS-able setup event'
            out += bytes([ev, p1, d])
            last_ev = ev
        new_ticks += d
    assert new_ticks == total_ticks, (new_ticks, total_ticks)
    return bytes(out), rs_saved, ch5_scaled, len(bass_at), ch5_shifted, repointed


def cx_usage(rom):
    """All $CX params used, per song (RS-aware parse)."""
    sys.path.insert(0, str(HERE))
    import song_check_rs as rs_mod
    used = {}
    for idx, s, ln, ends in rs_mod.SONGS:
        evs, result, pos, ticks = rs_mod.parse(rom, s, ln)
        for e in evs:
            if e['kind'] == 'setup':
                used.setdefault((idx, e['ch']), set()).add(e['p1'])
    return used


def main():
    rom = bytearray(ROM_PATH.read_bytes())
    assert len(rom) == 1048576
    assert rom[0x0F6840:0x0F6844] == struct.pack('>I', 0x0F9044), 'end-pointer prefix'
    lead, events, seek_off = parse(bytes(rom), START, LENGTH)
    print(f'parsed song 13: {len(events)} events, seek at +{seek_off}, '
          f'next-region prefix at +{PREFIX_OFF}')

    # ---- v3 voice sanity: the shared voices are what we decoded ----
    v14 = bytes(rom[voice_rom(rom, CH2_VOICE):voice_rom(rom, CH2_VOICE) + 36])
    v16 = bytes(rom[voice_rom(rom, CH5_VOICE):voice_rom(rom, CH5_VOICE) + 36])
    print(f'voice 14 struct ROM 0x{voice_rom(rom, CH2_VOICE):06X}: {v14.hex(" ")}')
    print(f'voice 16 struct ROM 0x{voice_rom(rom, CH5_VOICE):06X}: {v16.hex(" ")}')
    assert v14[0x0C:0x10] == bytes.fromhex('0c 41 1f 53'), 'voice 14 DT/MULT'
    assert v14[0x10:0x14] == bytes.fromhex('16 14 2f 00'), 'voice 14 TL'
    assert v14[0x14:0x18] == bytes.fromhex('1f 1f df 9f'), 'voice 14 RS/AR'
    assert rom[voice_rom(rom, CH2_COPY) + 0x08] == 0x3A, 'voice 14 FB/ALG byte'
    assert rom[voice_rom(rom, CH2_COPY) + 0x09] == 0xC0, 'voice 14 pan byte'
    assert v16[0x0C:0x10] == bytes.fromhex('75 72 31 31'), 'voice 16 DT/MULT'
    assert v16[0x10:0x14] == bytes.fromhex('1d 35 2c 03'), 'voice 16 TL'
    assert v16[0x14:0x18] == bytes.fromhex('5b 1f 19 50'), 'voice 16 RS/AR (raw; AR 27/31/25/16, RS 2/0/0/2)'
    assert rom[voice_rom(rom, CH5_COPY) + 0x08] == 0x3B, 'voice 16 FB/ALG byte'
    assert rom[voice_rom(rom, CH5_COPY) + 0x09] == 0xC0, 'voice 16 pan byte'
    # slots 15/17 unused by every song (all $CX events) on the original ROM
    orig_usage = cx_usage(bytes(rom))
    for (idx, ch), ps in orig_usage.items():
        assert CH2_COPY not in ps and CH5_COPY not in ps, \
            f'slot 15/17 used by song {idx} ch{ch}: {ps}'
    print('slots 15/17 confirmed unused by every song on the original ROM')

    # ---- timeline + ch2 pitch changes (cyclic) ----
    t = 0
    times = []
    for e in events:
        times.append(t)
        t += e[6]
    total_ticks = t
    print(f'total ticks {total_ticks} = {total_ticks / 60:.2f} s')
    assert total_ticks == 14487, total_ticks

    ch2_idx = [k for k, e in enumerate(events) if e[2] == 'note' and e[3] == 2]
    changes = []  # (event index, dwell, p1)
    for pos, k in enumerate(ch2_idx):
        e = events[k]
        if e[4] == events[ch2_idx[pos - 1]][4]:
            continue
        if pos + 1 < len(ch2_idx):
            dwell = times[ch2_idx[pos + 1]] - times[k]
        else:
            dwell = (total_ticks - times[k]) + times[ch2_idx[0]]
        changes.append((k, dwell, e[4]))
    print(f'ch2 pitch changes: {len(changes)}')

    # ---- choose the dwell threshold: seek must land in [SEEK_LO, SEEK_HI] ----
    centre = (SEEK_LO + SEEK_HI) // 2
    best = None
    for cut in range(16, 23):
        bass_at = {k: p1 - 24 for k, dwell, p1 in changes
                   if dwell >= cut and p1 >= 24}
        stream, rs_saved, ch5_scaled, n_bass, ch5_shifted, repointed = reemit(
            events, total_ticks, times, bass_at, VEL_SCALE)
        seek_pos = 1 + len(stream)  # lead byte + stream; seek sits here
        in_window = SEEK_LO <= seek_pos <= SEEK_HI
        print(f'  dwell >= {cut:2d}: bass {n_bass:3d} notes, RS saved {rs_saved}, '
              f'ch5 shifted {ch5_shifted}, repointed {repointed}, stream {len(stream)} B, '
              f'seek at +{seek_pos} {"IN WINDOW" if in_window else "OUT"}')
        assert repointed == 2, f'expected 2 $CX repoints, got {repointed}'
        if in_window and (best is None or abs(seek_pos - centre) < abs(best[0] - centre)):
            best = (seek_pos, cut, bass_at, stream, rs_saved, ch5_scaled, ch5_shifted)
    assert best is not None, 'no dwell threshold lands the seek in the window'
    seek_pos, cut, bass_at, stream, rs_saved, ch5_scaled, ch5_shifted = best
    print(f'chosen dwell >= {cut}: {len(bass_at)} bass notes, '
          f'seek at +{seek_pos} (window [{SEEK_LO}, {SEEK_HI}])')

    # ---- build the region: lead + stream + $FC $80; dead span UNTOUCHED ----
    out = bytearray([lead]) + bytearray(stream) + bytes([0xFC, 0x80])
    assert len(out) == seek_pos + 2, (len(out), seek_pos)
    assert len(out) <= PREFIX_OFF, 'stream overruns song-14 prefix!'
    # the seek must land exactly on the region end (+10240)
    rel = len(out)
    nxt = ((rel + 255) // 256) * 256
    assert nxt == LENGTH, f'seek lands on {nxt}, not {LENGTH}'

    # ---- write patched ROM (stream only; dead span = song 14 data, untouched) ----
    orig_prefix = bytes(rom[0x0F9006:0x0F900A])
    rom[START:START + len(out)] = out
    assert bytes(rom[0x0F9006:0x0F900A]) == orig_prefix, 'song-14 prefix disturbed!'
    assert bytes(rom[START + len(out):END]) == bytes(ROM_PATH.read_bytes()[START + len(out):END]), \
        'dead span disturbed!'

    # ---- v3: private softened voice copies + FB/ALG ----
    # ONLY the operator params ($0C-$23) are copied: each block's $00-$0B
    # header belongs to the PREVIOUS voice (its $08/$09 are that voice's
    # FB/ALG+pan), so the headers stay untouched.
    params14 = soften_params(v14[0x0C:0x24], ar=AR_NEW)
    params16 = soften_params(v16[0x0C:0x24], ar=None)
    # v4: DT/MULT softening on the private copies only (carriers untouched)
    assert params14[0x00:0x04] == bytes.fromhex('0c 41 1f 53'), 'ch2 copy DT/MULT source'
    assert params16[0x00:0x04] == bytes.fromhex('75 72 31 31'), 'ch5 copy DT/MULT source'
    params14 = set_mults(params14, MULT_CH2)
    params16 = set_mults(params16, MULT_CH5)
    assert params14[0x00:0x04] == bytes.fromhex('01 41 11 53'), 'ch2 copy DT/MULT v4'
    assert params16[0x00:0x04] == bytes.fromhex('71 71 31 31'), 'ch5 copy DT/MULT v4'
    print(f'ch2 copy DT/MULT (slot 15 $0C-$0F): 0c/41/1f/53 -> '
          f'{params14[0x00:0x04].hex("/")} (op1 12->1, op2 15->1)')
    print(f'ch5 copy DT/MULT (slot 17 $0C-$0F): 75/72/31/31 -> '
          f'{params16[0x00:0x04].hex("/")} (op1 5->1, op3 2->1)')
    rom[voice_rom(rom, CH2_COPY) + 0x0C:voice_rom(rom, CH2_COPY) + 0x24] = params14
    rom[voice_rom(rom, CH5_COPY) + 0x0C:voice_rom(rom, CH5_COPY) + 0x24] = params16
    set_fb_alg(rom, CH2_COPY, FB_NEW, 2)   # FB 7->2, ALG 2, pan C0
    set_fb_alg(rom, CH5_COPY, FB_NEW, 3)   # FB 7->2, ALG 3, pan C0
    print(f'ch2 copy params (slot 15 $0C-$23): {params14.hex(" ")}')
    print(f'ch5 copy params (slot 17 $0C-$23): {params16.hex(" ")}')
    print(f'FB/ALG slot15 @0x{voice_rom(rom, CH2_COPY + 1) + 8:06X}: '
          f'0x{rom[voice_rom(rom, CH2_COPY + 1) + 8]:02X} '
          f'(was 0x3C), pan 0x{rom[voice_rom(rom, CH2_COPY + 1) + 9]:02X} (was 0x40)')
    print(f'FB/ALG slot17 @0x{voice_rom(rom, CH5_COPY + 1) + 8:06X}: '
          f'0x{rom[voice_rom(rom, CH5_COPY + 1) + 8]:02X} '
          f'(was 0x38), pan 0x{rom[voice_rom(rom, CH5_COPY + 1) + 9]:02X} (was 0xC0)')
    # the shared voices must be untouched: voice 14's block fully, and
    # both voices' FB/ALG+pan (at slots 15/17 $08/$09). Voice 16's block
    # $08/$09 belong to voice 15 (the ch2 copy) — they are the copy's
    # FB/ALG+pan (0x12/0xC0), so that block is compared excluding $08/$09.
    assert bytes(rom[voice_rom(rom, CH2_VOICE):voice_rom(rom, CH2_VOICE) + 36]) == v14, \
        'voice 14 block changed!'
    v16_now = bytes(rom[voice_rom(rom, CH5_VOICE):voice_rom(rom, CH5_VOICE) + 36])
    assert v16_now[:0x08] == v16[:0x08] and v16_now[0x0A:] == v16[0x0A:], \
        'voice 16 block changed outside the voice-15 FB/ALG bytes!'
    assert rom[voice_rom(rom, CH2_COPY) + 0x08] == 0x3A, 'voice 14 FB/ALG not preserved'
    assert rom[voice_rom(rom, CH2_COPY) + 0x09] == 0xC0, 'voice 14 pan not preserved'
    assert rom[voice_rom(rom, CH5_COPY) + 0x08] == 0x3B, 'voice 16 FB/ALG not preserved'
    assert rom[voice_rom(rom, CH5_COPY) + 0x09] == 0xC0, 'voice 16 pan not preserved'
    assert rom[voice_rom(rom, CH2_COPY + 1) + 0x08] == 0x12, 'copy15 FB/ALG wrong'
    assert rom[voice_rom(rom, CH2_COPY + 1) + 0x09] == 0xC0, 'copy15 pan wrong'
    assert rom[voice_rom(rom, CH5_COPY + 1) + 0x08] == 0x13, 'copy17 FB/ALG wrong'
    assert rom[voice_rom(rom, CH5_COPY + 1) + 0x09] == 0xC0, 'copy17 pan wrong'
    # the target slots' headers ($00-$0B) are untouched originals
    assert bytes(rom[voice_rom(rom, CH2_COPY):voice_rom(rom, CH2_COPY) + 0x0C]) == \
        bytes(ROM_PATH.read_bytes()[voice_rom(rom, CH2_COPY):voice_rom(rom, CH2_COPY) + 0x0C])
    assert bytes(rom[voice_rom(rom, CH5_COPY):voice_rom(rom, CH5_COPY) + 0x0C]) == \
        bytes(ROM_PATH.read_bytes()[voice_rom(rom, CH5_COPY):voice_rom(rom, CH5_COPY) + 0x0C])

    sys.path.insert(0, str(HERE / 'tools'))
    import checksum
    rt = checksum.fix_runtime_checksum(rom)
    hd = checksum.fix_checksum(rom)
    OUT_PATH.write_bytes(bytes(rom))
    print(f'wrote {OUT_PATH} ({len(rom)} B); runtime sum 0x{rt:08X}, header 0x{hd:04X}')
    assert checksum.verify(str(OUT_PATH)) and checksum.verify_all(str(OUT_PATH))

    # ---- verification: RS-aware parse + song-13 event diff ----
    sys.path.insert(0, str(HERE))
    import song_check_rs as rs_mod
    patched = bytes(rom)
    agree = 0
    for idx, s, ln, ends in rs_mod.SONGS:
        evs, result, pos, ticks = rs_mod.parse(patched, s, ln)
        ok = (result == 'end') if ends else (result == 'loops-to-length')
        agree += ok
        if idx == 13:
            s13_events, s13_ticks = evs, ticks
            print(f'song 13 patched: {result} at +{pos}, {len(evs)} events, '
                  f'{sum(1 for e in evs if e["rs"])} RS, {ticks} ticks')
    print(f'RS-aware check: {agree}/{len(rs_mod.SONGS)} songs agree')
    assert agree == len(rs_mod.SONGS)
    # diff vs original event sequence
    j = 0
    bass = 0
    scaled = 0
    shifted = 0
    repointed = 0
    bad = []
    for e in s13_events:
        if e['kind'] == 'seek':
            continue
        if e['ev'] == 0x94 and e['ch'] == 4:
            bass += 1
            continue
        if j >= len(events):
            bad.append(f'extra event past original end: {e}')
            continue
        ob = events[j]
        j += 1
        exp_p1 = ob[4]
        exp_p2 = ob[5]
        if ob[2] == 'setup':
            if ob[3] == 2 and ob[4] == CH2_VOICE:
                exp_p1 = CH2_COPY
                repointed += 1
            elif ob[3] == 5 and ob[4] == CH5_VOICE:
                exp_p1 = CH5_COPY
                repointed += 1
        if ob[2] == 'note' and ob[3] == 5:
            if ob[4] >= OCTAVE_DROP:
                exp_p1 = ob[4] - OCTAVE_DROP
                if e['p1'] == exp_p1:
                    shifted += 1
            if (ob[1] >> 4) == 9:
                exp_p2 = max(1, round(ob[5] * VEL_SCALE))
                if e['p2'] == exp_p2:
                    scaled += 1
        if (e['ev'], e['kind'], e['ch'], e['p1'], e['p2'], e['delay']) != \
           (ob[1], ob[2], ob[3], exp_p1, exp_p2, ob[6]):
            bad.append(f'mismatch at orig #{j}: patched {e} vs orig {ob}')
    print(f'diff vs original: bass inserts {bass}, ch5 $9X scaled {scaled}, '
          f'ch5 pitch shifted {shifted}, $CX repointed {repointed}, '
          f'orig events consumed {j}/{len(events)}, mismatches {len(bad)}')
    for b in bad[:10]:
        print('  BAD:', b)
    assert not bad and j == len(events) and bass == len(bass_at) and repointed == 2
    assert s13_ticks == total_ticks, (s13_ticks, total_ticks)
    # $CX usage survey on the patched ROM: slots 15/17 used ONLY by song 13
    new_usage = cx_usage(patched)
    for (idx, ch), ps in new_usage.items():
        if CH2_COPY in ps or CH5_COPY in ps:
            assert idx == 13, f'slot 15/17 used by song {idx} ch{ch}!'
    assert new_usage[(13, 2)] == {CH2_COPY} and new_usage[(13, 5)] == {CH5_COPY}
    assert orig_usage != new_usage
    diff_keys = [k for k in set(orig_usage) | set(new_usage)
                 if orig_usage.get(k) != new_usage.get(k)]
    print(f'$CX usage diff vs original (only song 13 ch2/ch5 expected): {diff_keys}')
    assert set(diff_keys) == {(13, 2), (13, 5)}, diff_keys

    # ---- patch record ----
    import hashlib
    orig = ROM_PATH.read_bytes()
    diff = [i for i in range(len(orig)) if orig[i] != rom[i]]
    # group the diff into ranges
    ranges = []
    for i in diff:
        if ranges and i == ranges[-1][1] + 1:
            ranges[-1][1] = i
        else:
            ranges.append([i, i])
    rec = {
        'song': 13,
        'version': 'v4 (DT/MULT softening on top of v3)',
        'region': [hex(START), hex(END)],
        'changes': {
            'bass_notes': len(bass_at),
            'bass_rule': f"ch2 pitch-change, dwell >= {cut} ticks, p1 >= 24; "
                         f"$94 [p1-24] [{BASS_VEL}] [0] before the ch2 note",
            'bass_channel': BASS_CH,
            'bass_velocity': BASS_VEL,
            'ch5_velocity_scale': f'{VEL_SCALE:.4f} (median 124 -> 80)',
            'ch5_9x_scaled': ch5_scaled,
            'ch5_octave_drop': f'p1 - {OCTAVE_DROP} on every ch5 note event '
                               f'($85 and $95, p1 >= {OCTAVE_DROP} only; '
                               f'p1=0 rest events untouched)',
            'ch5_pitch_shifted': ch5_shifted,
            'cx_repoint': f'ch2 setup p1 {CH2_VOICE}->{CH2_COPY}, '
                          f'ch5 setup p1 {CH5_VOICE}->{CH5_COPY} '
                          f'(private softened voice copies in unused slots)',
            'mult_softening': {
                'ch2_slot_15': 'op1 MULT 12->1, op2 MULT 15->1 '
                               '(DT/MULT 0C/41/1F/53 -> 01/41/11/53)',
                'ch5_slot_17': 'op1 MULT 5->1, op3 MULT 2->1 '
                               '(DT/MULT 75/72/31/31 -> 71/71/31/31)',
                'carriers_untouched': 'op4 MULT kept (ch2 3, ch5 1); '
                    'DT kept everywhere (detune adds chorus, not harshness)',
                'fb_tl_ar': 'unchanged from v3 (FB 2, modulator TLs +8, ch2 AR 24)',
            },
            'voice_copies': {
                'ch2_slot_15_from_voice_14': {
                    'fb_alg': '0x3A -> 0x12 (FB 7->2, ALG 2)',
                    'pan': '0x40 -> 0xC0 (stereo, matches voice 14)',
                    'tl_modulators': 'op1 0x16->0x1E, op3 0x14->0x1C, '
                                     'op2 0x2F->0x37 (+8 each); carrier op4 0x00 untouched',
                    'ar': 'RS/AR 1F/1F/DF/9F -> 18/18/D8/98 (AR 31->24, RS kept)',
                    'dt_mult': '01/41/11/53 (v4: op1 12->1, op2 15->1; DT kept)',
                    'dr_sr_slrr': 'unchanged',
                },
                'ch5_slot_17_from_voice_16': {
                    'fb_alg': '0x3B -> 0x13 (FB 7->2, ALG 3)',
                    'pan': '0xC0 unchanged',
                    'tl_modulators': 'op1 0x1D->0x25, op3 0x35->0x3D, '
                                     'op2 0x2C->0x34 (+8 each); carrier op4 0x03 untouched',
                    'ar': 'unchanged (raw 5B/1F/19/50; AR 27/31/25/16, RS 2/0/0/2)',
                    'dt_mult': '71/71/31/31 (v4: op1 5->1, op3 2->1; DT kept)',
                    'dr_sr_slrr': 'unchanged',
                },
            },
            'shared_voices_untouched': {
                'voice_14_used_by_songs': [5, 12, 13, 14, 15],
                'voice_16_used_by_songs': [5, 11, 12, 13, 14, 15],
                'voice_28_used_by_songs': [1, 2, 5, 7, 10, 11, 12, 13, 14, 15, 17],
                'voice_14_block_identical': True,
                'voice_14_fb_alg_pan_identical': '0x3A/0xC0 at slot 15 $08/$09',
                'voice_16_block_identical_except': '$08/$09 (those bytes are '
                    'voice 15\'s FB/ALG+pan — the ch2 copy\'s, now 0x12/0xC0)',
                'voice_16_fb_alg_pan_identical': '0x3B/0xC0 at slot 17 $08/$09',
                'copy_headers_untouched': 'slots 15/17 $00-$0B are the originals',
            },
            'running_status_bytes_saved': rs_saved,
            'seek_position': seek_pos,
            'seek_window': [SEEK_LO, SEEK_HI],
            'dead_span_untouched': True,
            'total_ticks_before': total_ticks,
            'total_ticks_after': s13_ticks,
            'region_bytes': LENGTH,
            'rom_diff_bytes': len(diff),
            'rom_diff_ranges': [f'0x{a:06X}-0x{b:06X}' for a, b in ranges],
        },
        'rom_md5': hashlib.md5(bytes(rom)).hexdigest(),
        'rom_sha256': hashlib.sha256(bytes(rom)).hexdigest(),
        'verification': 'song_check_rs.py (RS-aware parser) 18/18 + song-13 event '
                        'diff + $CX usage survey (slots 15/17 only by song 13) + '
                        'voice-table diff; tools/song_check.py strict grammar does '
                        'not model running-status and will flag the RS bytes (expected)',
    }
    PATCH_PATH.write_text(json.dumps(rec, indent=2))
    print(f'wrote {PATCH_PATH}')
    print(f'patched ROM MD5 {rec["rom_md5"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
