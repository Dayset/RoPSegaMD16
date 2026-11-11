# Save system — issue #019 (Save/SRAM validation)

**Status:** done 2026-11-09 (M2 complete). Confidence labels as in
`docs/logic.md` / `docs/logic-audit.md`: **verified** = reproduced by a
harness run or read instruction-for-instruction from the ROM;
**likely** = strong inference from code + a corroborating source;
**open** = not proven.

## Verdict

The save medium is a **128-byte serial EEPROM**, bit-banged
Microwire-style through the cartridge `$200000` window — **not** SRAM,
not passwords, not "none". The header declares **no backup RAM**
(bytes `0x1B0–0x1BF` are spaces), so the EEPROM is only discoverable
from the code (and from BlastEm's `rom.db`, which lists this ROM,
`T-50176`, as `EEPROM { type i2c, size 128 }` with `bits_read { 7 sda }`
and `bits_write { 6 scl, 7 sda }` — an independent match for the
wiring derived here: **DI = D7, CLK = D6, DO = D7**).

The boot-time check `$4323C` and the real save format are
**incompatible by construction**: a valid, loadable save (magic
`0x2A`, parity OK, load returns `0x49`) **fails `$4323C`'s byte-sum
check on all three counts**, while `$FF0168` (the check's result
flag) stays 0. The byte-sum check is **vestigial** — a leftover from
an earlier save format — and its result is **never read by any code**
(#021 proved the never-read claim; #019 re-verified it by grep and
adds the reason: the check it records is meaningless for the current
format). The real save validation is `$177B4`'s **magic byte
(`0x2A`) + `$176A0` parity**.

Chip identity is **open**: the command format (8-bit `[A6..A0, R/W]`,
7-bit address, 128 bytes, DI/DO on D7, CLK on D6) is consistent with
the 93C46 family, but nothing in the code or header names a chip.
What would confirm it: a hardware-level trace of the cart's EEPROM
part number, or a dump of the cart's PCB. BlastEm's `rom.db` calls it
I2C (not Microwire) — the game's bit-bang is Microwire-shaped, so
treat the `rom.db` `type i2c` label as the emulator's modelling
choice, not a chip identification.

---

## 1. `$4323C` — the boot-time save check (full trace, verified)

`$4323C` (`0x4323C–0x433BE`, 386 bytes) is called **once**, from entry
at `0x30C`. Entry ignores the return value and resets the stack
(`movea.l #0, a7` at `0x312`). It is the only caller.

### 1.1 Entry and the `$E0` clear path

```
0x4323C  movem.l d0-d1, -(a7)
0x43240  clr.w   $FF0168            ; = 0 (valid/clean default)
         jsr     $42FC8             ; EEPROM init
         jsr     $DCE2              ; pad-2 read -> d0
         cmp.b   #$E0, d0
         beq     $432B6             ; A+C+Start -> clear-save path
```

**Clear path (`$432B6`):** `$FF0168 = 1`; zero the 128-byte `$FF016A`
buffer (`moveq #$7F, d0` loop); `move.b #$FF, $FF01E8`; then a write
loop via `$430F4` (`d0` = address 0..127, `and.w #$7F, d0`,
`bne $432DE` until wrap) — 128 zero bytes written to the EEPROM. On
`$FF014E < 0` → failure path `$432F6`; else → exit path A `$43316`.
**The cleared save is checksum-INVALID by `$4323C`'s own rules**
(all-zero image: sum = 0, byte[127] = 0 == sum ✓, byte[126] = 0 vs
`~0 = 0xFF` ✗, byte[127] = 0 vs `~byte[126] = 0xFF` ✗ → d1 = 2) —
see §7 for the BlastEm-observed exception (byte 126 reads back as
`0xFF`, making the cleared image pass with errcount 0).

### 1.2 Normal path — read + byte-sum check

```
         d0 = 0 (EEPROM address), d1 = $80 (128), a0 = $FF016A
         jsr     $43012             ; READ 128 bytes
         tst.w   $FF014E
         bmi     $432F6             ; EEPROM error -> failure
         ; checksum: d1 = $7D loop, add.b (a0)+, d0 over bytes[0..125]
         ; three checks, error count in d1:
         ;   byte[127] == sum?          (0x43284-0x4328A)
         ;   byte[126] == ~sum?         (0x4328C-0x43292, after not.w d0)
         ;   byte[127] == ~byte[126]?   (0x43294-0x432A0, swap/move.b/not.b)
         tst.w   d1
         beq     $43316             ; valid -> exit path A
         ; invalid: re-read pad 2 (jsr $DCE2 at 0x432A8)
         ;   if $B0 -> $432F6 (failure, $FF0168 = -1)
         ;   else   -> $43316 (exit path A, $FF0168 stays 0)
```

**So on an invalid checksum with neither combo held, `$FF0168` stays
0 — the −1 is only reached via the `$B0` re-read or an EEPROM
error.** A corrupt save is never rejected at boot: the check's
outcome changes nothing except which exit path is taken, and the
exit paths differ only in whether they hang (see §1.3).

### 1.3 Failure path, exit paths, and the `$4333A` hang

- **Failure path (`$432F6`):** `$FF0168 = -1`; re-read pad 2: if
  `$B0` → d0 = `$F` → `$4333A`; if `$E0` → d0 = `$F` → `$4333A`;
  else exit path B (`$4332E`: a0 = `$FF016A`, restore d0–d1, `rts`).
- **Exit path A (`$43316`):** re-read pad 2: if `$B0` or `$E0` →
  d0 = `$F0` → `$4333A`; else exit path B.
- **Exit path B** restores d0/d1 from the stack — `$4323C` returns
  the caller's original d0; the `$F0`/`$F` values only matter on the
  `$4333A` path.
- **`$4333A` tail (`0x4333A–0x433BE`):** `move.w #$2700, sr`; VDP
  writes `$8004`/`$8104`/`$8200`/`$8300`/`$8400`/`$8500`/`$8600`/
  `$8700`/`$8800`/`$8900`/`$8AFF`/`$8B00`/`$8C00`/`$8D00`/`$8E00`/
  `$8F02`/`$9000`/`$9100`/`$9200` (display off, blank);
  `move.l #$C0000000, $C00004` (VRAM write addr 0);
  `move.w d0, $C00000` (writes `$F0` or `$F` as VRAM word 0);
  `move.l #$40000000, $C00004`; loop writing `0xFFF` longwords of 0
  to `$C00000` (clears VRAM — wipes the `$F0`/`$F` word just written,
  so the `$F0`/`$F` distinction is meaningless in effect);
  `move.w #$8144, (a0)` (display on); `bra $433BE` — **infinite loop,
  interrupts masked: holding `$B0`/`$E0` at any of the three re-reads
  hangs the game on a blank screen until reset.**

### 1.4 `$FF0168` — the flag, mapped (verified)

| `$FF0168` | Set at | Meaning |
|---|---|---|
| `0` | `0x43240` (entry clear) | Default. Also the value after a valid checksum, after an invalid checksum with neither combo held, and after a successful save/load (the save/load driver never touches it). |
| `1` | `0x432B6` (`$E0` clear path) | The `$E0` (A+C+Start) clear-save path was taken at boot. |
| `−1` | `0x432F6` (failure path) | EEPROM error (`$FF014E < 0` after the boot read), or an invalid checksum with `$B0` held at the re-read. |

**Re-verified by grep 2026-11-09: exactly 3 references to `$FF0168`
in the whole ROM, all writes inside `$4323C`. It is never read by
any code** — the #021 "never read" claim stands. The `$F0`/`$F`
return values are likewise ignored (entry resets the stack).

**`$FF01E8` is write-only:** exactly one reference in the ROM, the
write at `0x432CE` (`move.b #$FF, $FF01E8`) in the clear path. Its
`$FF` has no observable effect in code.

---

## 2. EEPROM bit-bang helpers (full trace, verified)

All helpers live in `0x42E00–0x43238` and talk to the EEPROM through
the cartridge `$200000` window. **Data bit lands on bit 7 of the
`$200000` word, clock on bit 6 — DI = D7, CLK = D6. This corrects
`docs/architecture.md`, which said "DI = D0"** (that likely misread
CPU register d0 — the data travels in d0's bit 15 — as data-bus bit
D0). **DO = D7 as well — DI and DO share data-bus bit D7** (typical
cheap Microwire wiring: DI/DO tied together on one cart line).
BlastEm's `rom.db` independently agrees (`bits_read { 7 sda }`,
`bits_write { 6 scl, 7 sda }`).

### 2.1 Init and idle sequences

- **`$42FC8` (`0x42FC8–0x43004`):** `$FF014C = 10` (retry limit),
  `$FF014E = 0` (error count), delay loop `move.w #$1964, d0; nop;
  dbra` (`0x1964` = 6500), then 8× {write `$80` to `$200000`, NOPs,
  `jsr $42E34`}, then `jsr $42E76`, `rts`.
- **`$42E34`:** NOPs, write `$C0`, NOPs, write `$40`, NOPs, write
  `$00` (clock/idle sequence ending `$00`).
- **`$42E76`:** write `$00`, NOPs, write `$40`, NOPs, write `$C0`,
  NOPs, write `$80` (reverse sequence ending `$80`).
- **`$42F26`:** write `$00`, NOPs, write `$40`, NOPs, write `$00`.
- **`$42F5E`:** write `$80`, NOPs, write `$C0`, NOPs, write `$80`.
- **`$42FD8`:** delay loop `move.w #$1964, d0; nop; dbra`.

### 2.2 Bit-out, bit-in, ACK

- **`$42EBA` (bit-out, `0x42EBA–0x42EEC`):** `lsl.w #1, d0` (d0 bit
  15 → X); `roxr.b #1, d1` (X → d1 bit 7); `bclr #6, d1; move.w d1,
  $200000` (CLK low); NOPs; `bset #6, d1; move.w d1, $200000` (CLK
  high); NOPs; `bclr #6, d1; move.w d1, $200000` (CLK low).
- **`$42EEE` (bit-in, `0x42EEE–0x42F24`):** write `$80`, NOPs, write
  `$C0`, NOPs, `move.w $200000, d1`, write `$80`, `asl.b #1, d1`
  (d1 bit 7 → X), `roxl.w #1, d0` (X → d0 bit 0).
- **`$42F96` (ACK read, `0x42F96–0x42FC6`):** write `$80`, write
  `$C0`, `move.w $200000, d1`, write `$80`. Caller does `tst.b d1;
  bpl` — **ACK = DO bit 7 LOW (0)**; bit 7 = 1 means no-ACK/error.

### 2.3 `$43012` — EEPROM READ (block)

`0x43012–0x430E0`. Entry clears `$FF014E`; param block
`$FF0150` = buffer (a0), `$FF0154` = EEPROM address (d0),
`$FF0158` = count long (d1), `$FF015C` = remaining count word.
Retry loop: `jsr $42E34`; `and.w #$7F, d0` (**7-bit address,
0..127**); `lsl.w #1, d0; or.w #1, d0` (read bit); `lsl.w #8, d0`;
8× `$42EBA` — command byte sent MSB-first is
`[A6 A5 A4 A3 A2 A1 A0 R]` with R = 1. ACK via `$42F96`; on no-ACK:
`$FF014E++` (the `bmi` → fail is dead in practice since the count
starts at 0), compare vs `$FF014C` (10) → fail at `$430E2`
(`$FF014E = -1`) after 10 retries, else `$42FD8` delay and retry.
Data: 8× `$42EEE` → byte, `move.b d0, (a0)+`, `$FF015C--`, if not
done `jsr $42F26` between bytes, loop. Tail: `$42F5E` + `$42E76`,
restore params from `$FF0150`/`$FF0154`/`$FF0158`, `rts`.

**Exactly 2 `jsr` call sites:** `0x431E8` (inside `$430F4`'s verify)
and `0x43264` (boot validation in `$4323C`). Stack-arg wrapper at
`$43006` (`move.l $4(a7), d0; move.l $8(a7), d1; movea.l $C(a7), a0`,
falls into `$43012`) — called from gameplay code at `0x177E0`,
`0x17806`, `0x1782C` (inside `$177B4`).

### 2.4 `$430F4` — EEPROM WRITE (one byte)

`0x430F4–0x43230`. Entry clears `$FF014E`; stores a0 → `$FF0160`,
d0 → `$FF0164`, saves d1 on the stack. Retry loop: `jsr $42E34`;
`and.w #$7F, d0; lsl.w #1, d0` (**NO `or #1` — write bit 0**);
`lsl.w #8, d0`; `move.w d0, $FF015E` (saves the command word); 8×
`$42EBA`; ACK via `$42F96` (same retry logic, fail at `$43232`);
`move.b (a0), d0; lsl.w #8, d0`; 8× `$42EBA` (data MSB-first);
second ACK via `$42F96` (same retry logic); `jsr $42E76`;
write-cycle delay `move.w #$1518, d0; nop; dbra` (`0x1518` = 5400).

**Read-back verify (`0x431D2–0x43230`):** `jsr $43012` reads 1 byte
into `$FF015F` from the address saved at entry in `$FF0164`
(`move.l $FF0164, d0; moveq #1, d1`), then `cmp.b (a0), d0; bpl
$43222` — **the verify is a SIGNED `>=` comparison, not equality:
it passes unless read_byte < written_byte (signed).** (The two
instructions just above — `move.b $FF015E, d0; lsr.l #1, d0` —
recompute the address from the saved command word, but the result
is dead: d0 is reloaded from `$FF0164` before the `jsr`.) For the
clear path (written = 0) it passes iff the read byte's top bit is
clear — i.e. it reliably catches only the erased-state `$FF`. On
verify fail: `$FF014E++`, retry up to 10, else `$FF014E = -1`
(`$43232`).

**Exactly 1 `jsr` call site: `0x432DE`** (inside `$4323C`'s clear
loop). Stack-arg wrapper at `$430EC` (`move.l $4(a7), d0; movea.l
$8(a7), a0`, falls into `$430F4`) — called from gameplay code at
`0x17716`, `0x1773E`, `0x17774` (inside `$17706`).

**Callers of the wrappers:** READ = push buffer (a0), push count
(d1), push address (d0), `jsr $43006`; WRITE = push source (a0),
push address (d0), `jsr $430EC`.

### 2.5 `$FF014E` — the error counter

`$FF014E` is the EEPROM error count, cleared at the entry of
`$43012`/`$430F4`, incremented on ACK failure or verify failure,
compared against the retry limit `$FF014C` (10), and set to −1 on
final failure. Outside the EEPROM code it is read at exactly six
`cmpi.w #$FFFF, $FF014E` sites, all inside `$17706`/`$177B4`
(`0x1771E`, `0x17746`, `0x1777C`, `0x177EA`, `0x17810`, `0x17836`) —
the in-game save/load driver's per-call error checks. No other
`$FF014E` readers.

---

## 3. `$DCE2` — joypad port-2 read (full trace, verified)

`0xDCE2–0xDD1A`. `move.w #$100, $A11100` (Z80 bus request);
two-phase read on `$A10005`: phase 1 write `$40` to `$A1000B`,
write `$00` to `$A10005`, `bsr $DCCA` (delay: `move.w #0, $A11100;
moveq #10, d1; dbra; move.w #$100, $A11100`), read `$A10005` → d0,
`asl.b #2, d0; and.b #$C0, d0`; phase 2 write `$40` to `$A10005`,
`bsr $DCCA`, read `$A10005` → d1, then `bra $DCB8` (shared tail:
`and.b #$3F, d1; move.w #0, $A11100; or.b d1, d0; not.b d0; rts` —
combines phases and inverts, returns the **inverted button byte**
in d0). Ghidra xrefs: 8 call sites (`0x4324A`, `0x432A8`,
`0x432FE`, `0x43316` inside `$4323C`; `0x11BC8`, `0x12420`,
`0x16B10`, `0x12F58` in game code).

**Pad-2 button decoding — CORRECTED 2026-11-10 (the main-line labels
were swapped; the PR #1 branch line was right): `$E0` = A+C+Start,
`$B0` = B+C+Start.** `$DCE2` reads pad 2 in two phases: phase 1 drives
TH=0 (`move.b #$0,$A10005.l` after setting TH as an output via
`move.b #$40,$A1000B.l`) and reads `$A10005` → d0, `asl.b #2;
and.b #$C0` (keeps bits 6,7); phase 2 drives TH=1
(`move.b #$40,$A10005.l`) and reads `$A10005` → d1, `and.b #$3F`
(keeps bits 0–5); the shared tail `or.b d1,d0; not.b d0` returns the
inverted button byte (1 = pressed). Genesis 3-button protocol (TH=0 →
A/Start on data bits 4/5; TH=1 → B/C on bits 4/5; data bits PD0=Up,
PD1=Down, PD2=Left, PD3=Right, PD4=TL, PD5=TR) gives the result byte:
bit 7 = Start, bit 6 = A, bit 5 = C, bit 4 = B, bits 3–0 =
Right/Left/Down/Up. So `$E0` = bits 7,6,5 = Start+A+C =
**A+C+Start** (the clear-save path at `$432B6`), and `$B0` = bits
7,5,4 = Start+C+B = **B+C+Start** (the failure path at `$432F6`).
[live, 2026-11-10, 8/8]: an injection harness
(`.scratch022/harness_dce2_inj.s`, test ROM
`c7c94fce21b84043e9c88556cb58430e`) patched the two `$DCE2` reads to
RAM (`$FFD010`/`$FFD011`, same 6-byte length) and fed controlled raw
bytes — A+C+Start → `$E0`, B+C+Start → `$B0`, A → `$40`, B → `$10`,
C → `$20`, Start → `$80`, no keys → `$00`, all four → `$F0`. (An
end-to-end test with real key presses was blocked: XTEST keyboard
events do not reach BlastEm's SDL in this Xvfb — `esc` (ui.exit) and
`p` (ui.screenshot) have no effect even with the window focused and
the pointer inside it — and there is no /dev/uinput for a virtual
joystick. The injection test verifies the decode logic live; the
protocol half rests on the hardware spec, confirmed by three
independent references.) `$DCE2` is a shared joypad utility, not a
save routine — #003's "not a save routine" label stands.

---

## 4. The real save format — `$17706` / `$177B4` / `$176A0` (verified)

The boot check's 128-byte `$FF016A` buffer is a **copy of the
EEPROM image**; the working save buffer is **`$FFA800`** (128
bytes). The real format is defined by the in-game save/load driver,
not by `$4323C`.

### 4.1 Layout (EEPROM image)

| EEPROM bytes | Content |
|---|---|
| `[0]` | Magic `0x2A` (42) |
| `[1]` | Parity byte (see §4.3) |
| `[2..127]` | `$FFA800[0..125]` — the bit-packed game state (1001 bits) |

### 4.2 SAVE — `$17706` (`0x17706–0x177B3`)

Frame link `#-8`. (1) Local byte = `0x2A`; `jsr $430EC` →
**EEPROM[0] = `0x2A` (magic)**; on `$FF014E == -1` → return `0x4A`
(74). (2) `jsr $176A0` → d0; `jsr $430EC` → **EEPROM[1] = parity
byte**; on error → `0x4A`. (3) Loop i = 2..127: `jsr $430EC` →
**EEPROM[i] = `$FFA800[i-2]`**; on error → `0x4A`. (4) Tail: calls
`$177B4` (args passed through but ignored by `$177B4`); if `$177B4`
returns `0x49` → **return `0x48` (72) = success**, else `0x4A`. So
SAVE = write 128 bytes, then read-back-verify the whole save.
Callers (Ghidra): only `$2F11A`.

### 4.3 LOAD + VERIFY — `$177B4` (`0x177B4–0x1785E`)

(1) Zero `$FFA800` (128 bytes). (2) `jsr $43006` READ 1 byte:
EEPROM[0] → local −6 (magic). (3) READ 1 byte: EEPROM[1] → local
−5 (stored parity). (4) READ 126 bytes: EEPROM[2..127] →
`$FFA800[0..125]`. Any `$FF014E == -1` → return `0x4B` (75).
(5) `jsr $176A0`, compare with the stored parity; mismatch →
`0x4B`. (6) Check magic == `0x2A`; mismatch → `0x4B`. Success →
**return `0x49` (73)**. Callers (Ghidra): `$17706` (its verify
tail) and `$2F896`.

### 4.4 Parity — `$176A0` (`0x176A0–0x17704`)

For each bit position d4 = 0..7: parity = XOR of **ALL bits** of the
16 bytes `$FFA800[d4*16 .. d4*16+15]` (inner loops d5 = 0..15 bytes,
d6 = 0..7 bits); result bit d4 = that block parity. Returns a byte
whose bit d4 = parity of 16-byte block d4 of `$FFA800` (all 128
bytes covered, 8 blocks × 16).

**Round-trip subtlety:** at SAVE time `$176A0` runs over `$FFA800`
as filled by `$2F082` (bytes [126..127] included); at LOAD time
`$177B4` zeroes `$FFA800` then reads only 126 bytes, so [126..127]
= 0 when parity is recomputed — the round-trip only works if
`$FFA800[126..127]` are 0 at save time (the `$2F11A` fill zeroes the
buffer first and packs only 1001 bits, so bytes 126–127 stay 0
except possibly bit 1000 — see §4.6).

### 4.5 Bit packer / unpacker — `$2F082` / `$2F0D0`

- **`$2F082(buffer, value, offset, size, flags)`** (`0x2F082–
  0x2F0CE`): packs `(value >> flags)` LSB-first into `size` bits
  starting at bit-offset `offset`, via `$2B68C` (single-bit set) per
  bit. Verified instruction-for-instruction: d0 = value >> flags;
  loop i = 0..size−1 takes bit `(value>>flags) & 1` (LSB), calls
  `$2B68C(buffer, offset+i, bit)`, then shifts the value right by 1.
- **`$2F0D0(buffer, offset, size, flags)`** (`0x2F0D0–0x2F11A`):
  reads `size` bits MSB-first from `offset` (loop i = size−1 down to
  0, bit = `$2B656(buffer, offset+i)`, result = (result<<1)|bit),
  then `result << flags`. Exact inverse of `$2F082`.
- `$2B68C`/`$2B656` are the single-bit set/get helpers (internals
  not traced — the packer/unpacker pair is self-consistent, so the
  layout is defined by the call sequence).

### 4.6 SAVE serialiser — `$2F11A` (`0x2F11A–0x2F892`)

Requires `$FF00AE == 1`, else return `0x4C` (76). Zeroes `$FFA800`
(128 bytes). Then a long sequence of `$2F082` calls with a running
bit cursor (−2(a6)); then `cmpi.w #$3F0, cursor` — **if cursor >
`0x3F0` (1008 bits = 126 bytes) → `$12FA0(0xC8)` error** (size
guard). Then `jsr $17706` (args 0, 2 — vestigial, ignored) and
returns `$17706`'s code (`0x48`/`0x4A`) via the shared epilogue at
`$2F12E`.

**Cursor accounting (hand-tracked through the full `$2F11A` dump):
total = 1001 bits** (7 bits spare, bits 1001..1007, zero):

| Bits | Section |
|---|---|
| 61 | Header: 9 leader `$FF02C0` word + 8 `$FF02C2` + 3 `$FF02BA` + 3 `$FF0E16` step counter + 1 `$FF0116` Direct + 1 `$FF0132` Help + 1 `$FF0134` Diags + 1 `$FF013A` Combat + 14 gold `$FF02DE` + 10 `$FFC364` + 10 `$FFC366` |
| 96 | Merchants 6×16 (14 XP `$1A` + 2 HP-ratio per merchant from `$FF02B4`-based structs via `$FF0E82`; empty slot writes `0x3FFF` + 0 — same width) |
| 95 | Party 5×19 (per recorded type-2 member: 9 `$FF02C0` + 8 `$FF02C2` + 2 (`$FF02BA`−1); skipped members padded by (5−count)×19 at `0x2F56A–0x2F574`) |
| 120 | Inventory: spell cats 1–6 × 20 bits (1 bit per spell via `$2C8F2`, code = cat×64 + spell_idx) |
| 15 | Rings cat 10: 11 items padded to 15 |
| 15 | Keys cat 12: 15 items padded to 15 |
| 40 | Items cat 13: 33 items padded to 40 |
| 40 | Papers cat 17: 33 items padded to 40 |
| 175 | Goods cat 14: 25 items × 7-bit counts |
| 200 | `$FFC326` copy: 184 bits + 16 pad (loop `0x2F7E8–0x2F824`: reads 1-bit values from `$FFC326` via `$2B656`, `0xB8` = 184 iterations, then `addi.w #$10, cursor`) |
| 144 | `$FF00C0` table: 36×4-bit values of (`$FF00C0[i]` + `0x80`) |

The party HP-ratio field is computed inline: `((curHP*5 + curPow)
<< 2) / ((maxHP*5 + maxPow))`, clamped to [1,3], forced to 0 if
struct `+0x2C` bit 3 (`rol #3 & 1`) is set. Inventory counts come
from the category table +7 bytes (verified ROM bytes: `$D66AD`/
`$D66B7`/`$D66C1`/`$D66CB`/`$D66D5`/`$D66DF` = 20 each for spell
cats 1–6; `$D6707` = 11 rings; `$D671B` = 15 keys; `$D6725` = 33
items; `$D674D` = 33 papers; `$D672F` = 25 goods — these ARE the
`$D66A6` record +7 bytes).

**`$FF00C0` 36-word table: RESOLVED (2026-11-10) [static] — the
persistent merchant-attitude table.** 36 words, indices 0–35, one
per merchant identity; each entry is a value in [−100, +100],
saved as 36×4-bit values of (`$FF00C0[i]` + `0x80`). The entry is
indexed by the entity struct's `+0x20` field (the merchant's
identity, 0–35 — set at spawn from template word 6 (`$CF1B8`), or
from the global `$FFC408` when that word is `0x24` = 36, the
out-of-range sentinel). The merchant struct's `+0x22` is the LIVE
attitude (0–100, used by the price function `$2EA92`: `m22 =
att−50`, `price = v − m22·v/140`); `+0x22` is initialised at spawn
(`$23B84` tail) from the persistent entry —
`clamp(ROM base `$CF1BC` + (byte `$CF1BE` × `$FF00C0[idx]`) / 100,
−100, +100)` — and `$FF00C0` is the persistent backing store,
saved to / loaded from EEPROM. Writers: CAMP (`$03019a`) raises
each entry by +3 toward 10 (entry 34 skipped) — the attitude
recovery; battle-end (`$035656`) lowers an entry by 40; `$030628`
lowers an entry by 5; `$02CE74` (called from conversation code
`$029C66`/`$029C8A`/`$02A04C`/`$02A076`) adjusts an entry by a
percentage of the event delta and the live `+0x22` by the full
delta. Readers: spawn (`$23DF6`), `$02CE74`, the save serialiser
(`$02F842`) and loader (`$0300C8`/`$0300DE`). The `+0x20 == 32`
price-doubling check in `$2EA92` is merchant identity 32 (the
Commerce merchant). Template indices read from ROM confirm the
range: the first 40 templates use indices {1, 2, 10, 15, 19, 29,
32, 34}, max 34 — all within 0–35.

**`$2C8F2` inventory count (`0x2C8F2–0x2CA16`, fully traced):**
`$2C8F2(char_idx, code)` returns the inventory count of item
(category = code/64, index = code%64); 1-bit fields store count&1,
goods store the full 7-bit count. Type 4 → reads `+0x27` byte →
`$2CA26` (rank==category check for categories < 10, else
`$2CA74`); type != 1 → `$12FA0(0x32)`; type 1 → group loop
`0x2C97A–0x2CA0C` over `+0x14..+0x1E` words, recursing
`$2C8F2(word, code)` on each nonzero word (**no rank guard** —
unlike `$2BBD2`'s guarded version, which only recurses if the
target's rank `+0x18` low nibble == category). `$2C8F2`'s callers in
`$2F11A`: six sites `0x2F5A0`, `0x2F626`, `0x2F676`, `0x2F6D6`,
`0x2F736`, `0x2F78E` (spell cats 1–6, char_idx = `$FF02B2` leader).

### 4.7 LOAD entry — `$2F896` (`0x2F896+`)

Requires `$FF00AE == 1`, else return `0x4D` (77). Calls `$177B4`(0,
2); result in −0xE(a6); **if result == `0x49` OR `0x4E` → continue,
else return the result code** (the `0x4E` acceptance is unexplained
— `$177B4` returns only `0x49`/`0x4B` as traced; **open**). Then
`$20CF6`, `$23A9E`, zeroes 6 merchant structs (`$FF0E82` + i×2),
`$2B5F4`, `$2E9A6`, `$2CDD4`, clears `$FFC34A`/`$FFC34B`, then
`$2F0D0` unpack calls mirroring `$2F11A` field-for-field (9 bits →
leader word, 8 bits, 3 bits + `$1C21A` position set, 3 bits →
`$FF0E16`, 1 bit → `$FF0116`, 1 bit → `$FF0132`, 1 bit → `$FF0134`,
1 bit → `$FF013A`, 14 bits → gold, 10 bits → `$FFC364`, 10 bits →
`$FFC366`, merchant loop with `0x3FFF`-empty check at `0x2FB80`,
etc.), reconstructs the leader via `$23B84`, calls `$25456`/
`$243D6`/`$2595A`/`$2A454`.

**Tail (traced):** ends `clr.w $FF0112; jsr $2EE2A; move.w #$FFFF,
$FF0124; move.w -$E(a6), d0; bra $2F8AA` (unlk/rts) — **`$2F896`
returns `$177B4`'s code (`0x49` on success, `0x4B` on error).**
`$FF00C0` restore: unpacked 4-bit value → `$FF00C0[i] = value;
$FF00C0[i] -= 0x80` (`0x300C8–0x300E6`).

---

## 5. The incompatibility — `$4323C`'s check vs the real format (verified)

**`$4323C`'s byte-sum check and the real save format are
INCOMPATIBLE by construction.** `$4323C` requires
EEPROM[126] == `~sum` and EEPROM[127] == sum, where sum is over
EEPROM[0..125]. But the real format (`$17706`/`$177B4`) is
EEPROM[0] = `0x2A` magic, EEPROM[1] = parity, EEPROM[2..127] =
`$FFA800[0..125]` — and `$2F11A` never writes sum/complement bytes
anywhere in the payload (all `$2F082` values come from game state;
final cursor 1001 bits, 7 spare zero bits). `$FFA800[124]`/`[125]`
(= EEPROM[126]/[127]) are just the tail of the packed data (the
last `$FF00C0` 4-bit values + spare bits). A real save passes
`$4323C`'s check only by ~1/65536 coincidence. **The real save
validation is `$177B4`'s magic (`0x2A`) + `$176A0` parity;
`$4323C`'s byte-sum check is vestigial** (probably from an earlier
save format where bytes 126/127 WERE sum/complement, left behind
when the bit-packer was introduced, and `$4323C` was never updated)
— which explains WHY `$FF0168` is never read: the check it records
is meaningless for the current format. The `$E0`-clear path's 128
zero bytes likewise fail it (d1 = 2 on a true all-zero image).

**Harness proof (see §8):** a valid, loadable save (magic `0x2A`,
parity `0x1B` verified by independent recomputation, load returns
`0x49`) fails `$4323C`'s check on **all three counts** (errcount 3)
while `$FF0168` stays 0.

---

## 6. In-game Load/Save verb routing — correction to #021 (verified)

The `$2068E` dispatch (walked instruction-by-instruction
`0x2068E–0x20758`, subtract-and-branch chain) maps **case 81 →
`$20652` (calls `$2F896` = LOAD)** and **case 82 → `$20670`
(calls `$2F11A` = SAVE)**. Both cases end with `push d0, push
0x51; jsr $35612` (result code → message display).

**The #021 audit's table "14 → `$202CC` Load, 15 → `$202FA` Save"
has the ADDRESSES right but the LABELS wrong: case 14 → `$202CC`
is the 'Goods' shop verb handler (Goods has C = `0x0E` in the verb
table), and `$202CC` calls the random-picker `$2A22A` + `$298D2` —
it does NOT load a save and touches no EEPROM routine.** Case 15 →
`$202FA` is likewise not Save (no verb record with C = 15 in the
MAIN table; SYSTEM Save has B = 15, C = 0). The #021 audit doc §5
phrase "the Load handler (C=14 → `0x202CC`, calls `$2A22A`/
`$298D2`)" is corrected in this doc and in `docs/logic-audit.md`
(the never-read-`$FF0168` claim itself still holds — the real Load
`$2F896` never touches `$FF0168` either).

- **`$2A22A` is a random-target picker** (uses `$12B82` RNG, reads
  `$FF02C8`/`$FF02DA` tables; callees `$12B82`, `$308C6` only) — NOT
  a save routine. `$298D2` is a general routine (callees include
  `$26B58` message queue, `$35612`, `$2BBD2`, `$2A2CA`, itself
  recursively) — also not a save routine.
- **SYSTEM submenu records** (parsed programmatically, ROM
  `0xCCFF4` header + 14-byte items from `0xCD000`): Load A=0
  B=`0x0E`(14) C=0 grp=1; Save A=0 B=`0x0F`(15) C=0 grp=1; Combat
  A=0 B=0 C=`0x37`(55) grp=1; Direct A=0 B=0 C=`0x14`(20) grp=1;
  Diags A=0 B=0 C=`0x36`(54) grp=1; Music A=0 B=`0x16`(22) C=`0x50`(80)
  grp=1; Help A=0 B=0 C=`0x12`(18) grp=1; Quit A=0 B=`0x09` C=0
  grp=1. (Music's C=80 matches `$2068E` case 80 → `$2063C`, which
  plays the song index from `$FFBB6F` — consistent with d0 being the
  C byte for those records; Load/Save's C=0 hits no `$2068E` case,
  hence the open routing question below.)
- **How SYSTEM→Load (record C=0) reaches action code 81 — CLOSED:**
  `$FFBB6C` (the d0 source for `$2068E`) **is** written — the setter
  exists: `move.b $C(a0), $FFBB6C` at five sites inside `$1F296`'s
  switches (`0x1F3C0`, `0x1F548`, `0x1F868`, `0x1F99A`, `0x1FA42`),
  copying the current menu record's C byte into `$FFBB6C`; plus
  `clr.b $FFBB6C` at `0x20920`/`0x20B6E` and `move.b #$10, $FFBB6C`
  at `0x20966`. (An earlier draft of this doc said no writer was
  found — wrong; the grep output was truncated.) The routing is the
  **B byte → submenu offset table → Yes/No submenu**: the B byte is
  a submenu index, not a verb. `L01FEB8` (`$01FEB8`, the submenu-open
  tail of `$1F296`) computes the next table as `$CCDB8 +
  offset_table[B]`, where `offset_table` is 26 u16 in RAM at
  `$FF01EA`, copied at boot by `main_init` (`$0011E8`, 288 words
  `$FCE3C`→`$FF0000`) from ROM `$FD026`. Entry 14 = `0x0356` → LOAD
  table `$CD10E`; entry 15 = `0x037E` → SAVE table `$CD136` (entry 8
  = `0x023C` → SYSTEM `$CCFF4`; entry 0 = 0 → MAIN `$CCDB8`). Both
  tables have header A=78 grp=2 and exactly two records: "Yes" A=0
  B=0 **C=81** (LOAD) / **C=82** (SAVE) grp=1, "No" A=0 B=0 C=0
  grp=1. So SYSTEM→Load (B=14, C=0) sets `$FFA7F8`=14 and opens the
  LOAD table; picking "Yes" runs the A=78 handler `L01F45E`, whose
  grp=1 case (`$01F532`) writes the record's C byte to `$FFBB6C` —
  **81** — and sets `$FFA7F8`=0; `L01FEB8` then opens MAIN (offset
  0) and, with `$FFA7F8`==0, falls through to `L020172`, which loads
  d0=`$FFBB6C`=81 and `bra $2068E` → case 81 → `save_menu_load`
  `$20652` → `$2F896`. Likewise Save → B=15 → SAVE table → "Yes"
  C=82 → case 82 → `save_menu_save` `$20670` → `$2F11A`. "No"
  (C=0) writes `$FFBB6C`=0 and dispatches to no `$2068E` case — it
  cancels. The same B→table lookup is used by `sys_state_clear`
  (`$01E562`), `menu_record_reload` (`$01E5A0`), and the `$D28E`
  case-25 handler `cmd25_handler` (`$020A36`). The
  `$FFBB6C`/`$FFBB82`/`$FFBB6F` grep shows `$FFBB82` (record
  pointer) written at `0x1E596`/`0x1E5D2` and read widely, `$FFBB6F`
  read at `0x1EA50`/`0x1EB00`/`0x1EB1E`/`0x1EB70`/`0x1EBD8`/`0x1EC50`
  (Music case `$2063C` reads `$FFBB6F` as the song index).

- **Region note:** the offset table truly starts at ROM `$FD026`,
  but `disasm/regions.csv`'s `word-offset-table` row starts at
  `$FD036` — it misses entries 0–7 (`$FD026–$FD035`), which sit
  inside the `snd-sfx-records` region's last record (SFX record 61,
  `$FD020–$FD035`; only SFX indices 0–38 are ever called, so the
  overlap is inert). The `doc_regions.csv` SFX row still claims
  62 records to `$FD036`. Correcting the boundary is a follow-up,
  not done here.

---

## 7. BlastEm behaviour — what the emulator does (verified)

BlastEm 0.6.3-pre (this build) is the test vehicle. Three of its
behaviours matter for interpreting the harness results:

### 7.1 Fresh EEPROM reads as `0x00`, not `0xFF` (verified)

A real erased 93C46 reads `0xFF`; BlastEm presents virgin EEPROM as
zeros. Proven by the boot harness, which reads `$FF016A` all-zero on
a fresh EEPROM. (Oddity, unexplained: the original ROM's
`save.eeprom`, created by an earlier blank boot and never written by
the game, is all `0xFF` — so the emulator's file-writing path
initialises to the erased state even though its fresh-read state
presents zeros. Do not use that file as evidence about the game's
reads.) **Consequence:** a fresh-EEPROM boot has checksum errcount
2 (not 3 as a true `0xFF` erased image would give — see §1.1).

### 7.2 BlastEm writes `save.eeprom` on exit but does NOT reload it (verified)

`save.eeprom` lives at `~/.local/share/blastem/<rom-basename>/
save.eeprom` and is flushed on a clean exit (debugger `q` command);
SIGTERM does not reliably flush it. **But the file is never read
back on the next launch** — proven by the `0x55` test: the file was
overwritten with `0x55` × 128, the boot harness still read
`$FF016A` = 0 (errcount 2), and the file's atime never advanced
past its creation time across multiple runs (the file was never
opened for reading). The same ROM bytes re-run also read zeros.

**Consequence for #019:** a live "boot from a valid save" in
BlastEm is not possible with this build. Persistence is proven at
the **file level** (the flushed `save.eeprom` contains the valid
save — magic `0x2A`, parity `0x1B` verified by independent
recomputation, correct tail bytes; see §8.1) and the boot-read path
is proven via `$43012` (the same routine `$4323C` uses) reading the
saved image correctly in the save harness's re-read. The only
unproven link is the emulator's file-load step, which is an
emulator property, not a game property. Do not claim a live
reboot-from-save was observed in BlastEm.

### 7.3 The clear-path byte-126 anomaly — a BlastEm artifact (verified)

The clear harness (128 × `$430F4` with byte 0, `$FF014E` = 0, all
verifies passed) leaves **EEPROM[126] = `0xFF`, all other bytes 0**
— proven by the harness re-read AND the flushed `save.eeprom`
(exactly one nonzero byte, at 126). The cleared image therefore has
checksum errcount **0** (it passes `$4323C`'s check by coincidence:
sum = 0, byte[127] = 0 == sum ✓, byte[126] = `0xFF` == `~0` ✓,
byte[127] = 0 == `~byte[126]` = 0 ✓), **not** errcount 2 as a true
all-zero image would give.

**This is an artifact of BlastEm's I2C EEPROM emulation during the
long sequential write loop, not a property of the game's save
code.** Three targeted probes prove the individual writes are
correct:

| Probe | Test | Result |
|---|---|---|
| 1 (`test_save_probe126_harness.s`) | Write `0x33`→126, read 126; write `0x44`→127, read 126 and 127; write `0x11`→125, read 125 | 126 = `0x33` ✓, 126 stays `0x33` after the 127 write ✓, 127 = `0x44` ✓, 125 = `0x11` ✓, `$FF014E` = 0 |
| 2 (`test_save_probe126b_harness.s`) | Write `0x33`→126 then `0x00`→126, read 126; write `0x33`→126 then `0x00`→127, read 126 and 127 | 126 = `0x00` ✓ (writing zero to 126 works), 126 stays `0x33` ✓, 127 = `0x00` ✓, `$FF014E` = 0 |
| 3 (`test_save_probe126c_harness.s`) | Write `0x00`→126 then `0x00`→127 (the clear loop's tail, alone), read both | 126 = `0x00` ✓, 127 = `0x00` ✓, `$FF014E` = 0 |

The game's bit stream is correct (verified by disassembly of
`$430F4`: command `0xFC` for address 126, `0xFE` for 127), each
`$430F4` verify passes at write time, and the isolated writes all
land. The `0xFF` at 126 appears only in the full 128-write
sequential loop — a cumulative state/timing effect in BlastEm's
I2C model. **On the game's side the clear writes 128 zeros; the
code-level expectation for a true all-zero image is errcount 2
(§1.1).** The doc records the BlastEm-observed image (errcount 0)
and flags the 126 byte as an emulator artifact; do not present the
`0xFF` at 126 as a game behaviour.

---

## 8. Harness results (verified)

All harnesses follow the #007/#008/#021 pattern: hook at `0x35C`
(replacing `move.w $C00004, d1` with `jsr $FD0CC.l`), harness in the
`0xFF` padding at `0xFD0CC+`, results as words at `$FFD000+`, hook
exits use **`rts`, never `jmp`** (#021 Q13). All test ROMs have
runtime checksum `0x7C7B5FDB` (the harness lives outside the summed
range). Driver: `/tmp/ropre/run019.py` (pty BlastEm debugger driver
with clicker thread, breakpoint/trace/diagnostic/peek modes,
clean-quit via `q` so BlastEm flushes the save file);
builder: `/tmp/ropre/build019.py` (always writes
`/tmp/ropre/test019.gen` so BlastEm persists the same EEPROM file
across runs). Harness sources: `tools/test_save_harness.s`,
`tools/test_save_boot_harness.s`, `tools/test_save_clear_harness.s`,
`tools/test_save_probe126_harness.s`,
`tools/test_save_probe126b_harness.s`,
`tools/test_save_probe126c_harness.s`.

### 8.1 Full save harness — PASSING (21 result words)

`tools/test_save_harness.s` (494 B assembled, `done` at `$FD2B2`).
Sets up the attract-context preconditions (see §8.4), calls
`$2F11A` (save), then `$2F896` (load), re-reads the EEPROM via
`$43012`, and recomputes `$4323C`'s checksum-error count over the
re-read image:

| # | Result | Value | Note |
|---|---|---|---|
| 0 | `$FFD000` flag | `0xBEEF` | harness ran |
| 1 | canary 1 | `0xA5A5` | intact |
| 2 | `$FF0168` at boot | 0 | |
| 3 | `$FF016A[0]` | 0 | fresh EEPROM = zeros (§7.1) |
| 4 | `$FF016A[1]` | 0 | |
| 5 | `$FF016A[126]` | 0 | |
| 6 | `$FF016A[127]` | 0 | |
| 7 | **`$2F11A` return** | **`0x48` (72)** | **SAVE SUCCEEDED** |
| 8 | `$FFA800[124]` | `0x11` | matches the bit-layout prediction exactly |
| 9 | `$FFA800[125]` | `0x00` | see §8.5 |
| 10 | `$FFA800[0]` | 0 | |
| 11 | `$FFA800[1]` | 0 | |
| 12 | **`$2F896` return** | **`0x49` (73)** | **LOAD SUCCEEDED** |
| 13 | **EEPROM[0] re-read** | **`0x2A` (42)** | **the magic** |
| 14 | **EEPROM[1] re-read** | **`0x1B` (27)** | **the parity byte** |
| 15 | EEPROM[126] re-read | `0x11` | matches `$FFA800[124]` |
| 16 | EEPROM[127] re-read | `0x00` | matches `$FFA800[125]` |
| 17 | **checksum-error count over the re-read valid-save image** | **3** | **ALL THREE `$4323C` checks fail** — the headline proof (§5) |
| 18 | `$FF014E` | 0 | no EEPROM errors |
| 19 | `$FF0168` final | 0 | untouched by save/load |
| 20 | canary | `0xA5A5` | intact |

**The flushed `save.eeprom` confirms the file-level round-trip:**
magic `0x2A`, parity `0x1B`, tail bytes 120..126 = `0x11`, byte 127
= `0x00`; sum over bytes[0..125] = `0x29`, errcount = 3 (matches
the harness). **The parity byte was independently recomputed in
Python from the file (`$176A0`'s algorithm: bit d4 = XOR of all
bits of `$FFA800` block d4) — computed `0x1B` == stored `0x1B`.**

### 8.2 Boot harness — fresh EEPROM — PASSING (9 words)

`tools/test_save_boot_harness.s` (194 B, `done` at `$FD186`):
`$FF0168` = 0, `$FF016A[0/1/126/127]` all 0, checksum-error count =
**2** (all-zero image: sum = 0, byte[127] = 0 == sum ✓, byte[126]
= 0 vs `0xFF` ✗, byte[127] = 0 vs `~byte[126]` = `0xFF` ✗).
Proves BlastEm fresh EEPROM reads as zeros and the boot check fails
(d1 = 2) with `$FF0168` staying 0.

### 8.3 Clear harness — PASSING (12 words)

`tools/test_save_clear_harness.s` (294 B, `done` at `$FD1EA`).
Replicates `$4323C`'s `$E0` clear block (`$432B6–$432F4`) inline
(jumping into the middle of `$4323C` would break its
`movem.l`/`rts` epilogue, so the block is replicated, not called):
`$FF0168` pre-clear = 0, `$FF016A[0]` pre-clear = 0 (fresh
EEPROM), `$FF0168` post-clear = **1** ✓, `$FF014E` post-clear = 0
✓, EEPROM[0] re-read = 0 ✓, EEPROM[126] re-read = **`0xFF`**
(§7.3), EEPROM[127] re-read = 0, checksum-error count = **0**
(§7.3), `$FF014E` after re-read = 0, canary `0xA5A5` ✓. The
flushed `save.eeprom` has exactly one nonzero byte (126 = `0xFF`).

### 8.4 Attract-context traps found and fixed in the harness

Four traps were diagnosed with the driver's trace/diagnostic modes:

1. **`$2C8F2` type requirement:** `$2F11A` counts spells via
   `$2C8F2($FF02B2, code)`; `$2C8F2` requires the slot to be type 1
   or type 4 — cold-attract slot 0 (type 0) takes the `$12FA0(0x32)`
   error path → `$12072` → `$1386A` VBlank wait → hangs (SR=`$2700`
   masks VBlank). Fix: pin slot 0 to type 1 before `$2F11A`. Type 4
   would NOT work: its path requires the slot's rank (`+0x18` low
   nibble) to equal the category being counted, and the save counts
   six spell categories 1–6. Diagnosed via `$12FA0` breakpoint:
   return address `$2CA24`, `jsr` site `$2CA1E`, arg `0x32`.
2. **`$1C21A` divide-by-zero:** `$2F896` calls `$1C21A(6, X, Y)`;
   mode 6 divides by the location record's words via `$1C83E`
   (`divs.w $4(a0), d0`); in attract `$FFA7FC` is NULL (set only
   once, at `0x1B74E`, when a location loads), so the divisor is the
   word at address 4 = `0x0000` → 68000 divide-by-zero exception →
   vector 5 at `0x14` (= 0, no fault handlers) → PC=0. Diagnosed via
   trace (`$1C21A` entered, then PC=0) + peek (`$FFA7FC` = 0, args
   mode 6, X=0, Y=0). Fix: fabricate a minimal location record in
   scratch RAM (`$FFD280`: [0]=[2]=`0x100`, [4]=[6]=`0x10`) and
   point `$FFA7FC` at it — a fixture supplying the precondition
   real play guarantees.
3. **`$2C8F2`/`$2BBD2` group-list recursion:** `$2C8F2`'s type-1
   path recurses on every nonzero `+0x14` word with NO rank guard
   (unlike `$2BBD2`'s guarded version). Template 0's only nonzero
   `+0x14` word is `+0x14` = 1 (name "Man"). If the loaded leader
   lands in slot 1, `+0x14` = 1 = its own slot → `$2C8F2(1)` →
   `$2C8F2(1)` → … infinite self-recursion (diagnosed: `$2C8F2`
   hit 200+ times rapidly). Fix: restore slot 0 to type 0 before
   the load so `$23B84` puts the leader in slot 0 (as in real
   play), and pin slot 1 to type 1 with `+0x14..+0x1E` all zero
   (cold RAM) so the one-level recursion `$2C8F2(1)` returns 0 and
   `$2BBD2`'s rank guard (slot 1 rank 0 ≠ category) skips its
   recursion.
4. **`$2EE2A` VBlank wait:** `$2F896`'s tail calls `$2EE2A` (redraw
   after load), which waits for VBlank via `$1386A` (and `$138A8`,
   which also calls `$1386A`) — `$1386A` polls `$FF0016`, which
   only the VBlank handler clears; SR=`$2700` in attract masks
   VBlank → spins forever (same freeze mechanism as `$12072`).
   Diagnosed via trace (load reached `$2EE2A`, never reached
   epilogue `$2F8AA`). Fix: set SR=`$2000` before `jsr $2F896`,
   restore SR=`$2700` right after (the VBlank handler only touches
   the frame flag, joypad ring and sound state — none of the harness
   results, save buffer, or char slots).

Supporting traces (all verified by disassembly):
- **`$12FA0`:** takes its argument on the STACK (`link a6,#0;
  move.w $8(a6),-(a7); jsr $12072`) — d0 is meaningless at its
  entry. Callers push the error code (`0x1C`, `0x32`, `0xC8`, …)
  then `jsr`.
- **`$1C21A` mode 6:** `$FFA7FC`-record[0]/[2] are divisors
  (remainders → `$FF0E8E`/`$FF0E90`); `$1C83E` divides by
  record[4] and multiplies by record[6]; `$1BA16` (called from the
  `$1C7DA` tail) is trivial (sets `$FF0098`=-1, returns).
  `$FFA7FC` written at exactly one site: `0x1B74E`
  (`move.l a0, $FFA7FC`).
- **`$2BBD2` head:** same shape as `$2C8F2` (major = code/64,
  minor = code%64; type 4 → redirect via `+0x27` → `$2BCFE`;
  type 1 → −$6(a6) = char_idx, major >= 10 → `$2BCF0`, else the
  group loop at `0x2BC5A` which tests `+0x14` words and recurses
  `$2BBD2(g, code, value, flag)` only if `struct[g].+0x18 & 0xF`
  == major).
- **Template 0** (verified from ROM bytes): `+0x14` = 1, `+0x16` =
  0, `+0x18` = `0x0000`, `+0x1A` = 0, `+0x1C` = 0, `+0x1E` = 0 —
  the only nonzero `+0x14` word is the name index 1.

### 8.5 The `$FFA800[125]` / `$FF00C0[35]` detail (open)

`$FFA800[125]` measured `0x00`, but the field math predicts `0x01`
(field 35 = ((`$FF00C0[35]`+`0x80`)>>4)&`0xF` = 8 for a zero table
entry, bit 3 at bit 1000 = byte 125 bit 0). Byte 124 = `0x11`
matches fields 33/34 exactly, so field 35 specifically differs.
The flushed `save.eeprom` resolves the bit pattern: file bytes
120..126 = `0x11`, byte 127 = `0x00` — i.e. in `$FFA800` terms the
`$FF00C0` fields 21..34 have bit 3 = 1 and fields 0..20 and 35 have
bit 3 = 0. But a peek at `$2F11A` entry in a different (diagnostic)
run showed `$FF00C0[0]`/`[1]`/`[33]`/`[34]`/`[35]` all 0 — and
`[33]`/`[34]` = 0 is consistent with field bit 3 = 1 while
`[0]`/`[1]`/`[35]` = 0 is not consistent with field bit 3 = 0.
**So the `$FF00C0` table's attract-time contents vary between
runs** (it is written during boot/attract from a run-dependent
source); the packed tail is therefore state-dependent. The doc
records the measured tail from the successful save run
(`$FFA800[124]` = `0x11`, `[125]` = `0x00`; EEPROM[126] = `0x11`,
[127] = `0x00`) and leaves the `$FF00C0` table's meaning and exact
attract contents **open** (the table's meaning was already open —
see §4.6).

---

## 9. Acceptance (all four boxes)

| # | Criterion | Status |
|---|---|---|
| 1 | `$DCE2`, `$42FC8`, `$43012` traced and documented (what they read, what the `$E0`/`$B0` magic bytes mean) | **DONE** — §2 (§2.1–2.4: init, bit-out/in, ACK, READ, WRITE + verify), §3 (`$DCE2` + `$E0` = A+C+Start, `$B0` = B+C+Start — labels corrected 2026-11-10, were swapped). |
| 2 | Save medium decided: SRAM / EEPROM / passwords / none, with evidence | **DONE** — Verdict + §2: **128-byte serial EEPROM**, Microwire bit-bang via `$200000`, DI/DO = D7, CLK = D6; header declares no SRAM; BlastEm `rom.db` (`T-50176`, I2C, size 128) corroborates. Chip identity **open** (93C46 family is the suspect, unproven). |
| 3 | The 128-byte `$FF016A` buffer format + its byte-sum check explained | **DONE** — §1.2 (the check), §4 (the real format: magic + parity + 1001-bit packed `$FFA800`), §5 (the incompatibility). |
| 4 | `$FF0168` flag values (0 / 1 / −1) mapped to game states | **DONE** — §1.4 (table + the never-read re-verification). |

---

## 10. Open items

- **EEPROM chip identity** — 93C46 family is the suspect, unproven.
  What would confirm it: a hardware-level trace / cart PCB part
  number. BlastEm's `rom.db` `type i2c` is the emulator's modelling
  choice, not a chip ID.
- **`$FF00C0` 36-word table: meaning** — saved as 36×4-bit values;
  its attract-time contents vary between runs (§8.5); the exact
  setter(s) and semantics are open.
- **`$2F896`'s `0x4E` acceptance** — `$177B4` returns only
  `0x49`/`0x4B` as traced; why `$2F896` also accepts `0x4E` is open
  (§4.7).
- **Boot-from-save in BlastEm** — blocked by the emulator not
  reloading `save.eeprom` (§7.2); the file-level + `$43012` proofs
  stand in its place.
- **BlastEm byte-126 clear artifact** — mechanism not fully pinned
  down (probes 1–3 rule out the individual writes; it appears only
  in the full 128-write sequential loop); recorded as an emulator
  artifact, not a game property (§7.3).

## 11. Remake notes (for Epic 5, #031)

- Save to a 128-byte serial EEPROM image with the layout of §4.1:
  magic `0x2A`, parity byte (XOR-of-bits per 16-byte block, §4.3),
  then the 1001-bit packed state (§4.6). Do **not** reproduce
  `$4323C`'s byte-sum check as a gate — it is vestigial and fails
  on real saves; if classic mode reproduces it, reproduce it as a
  dead check whose result is ignored, exactly as the ROM does.
- The in-game save/load return codes are `0x48` (save OK), `0x4A`
  (save error), `0x49` (load OK), `0x4B` (load error), `0x4C`/`0x4D`
  (called with `$FF00AE != 1`).
- The `$E0` (A+C+Start on pad 2) clear-save at boot is a real,
  deliberate-feeling feature (it sets `$FF0168 = 1` and writes 128
  zeros); reproduce it in classic mode. Note the `$B0`/`$E0`
  re-read hang (`$4333A`) is a bug — holding either combo at any of
  the three re-reads hangs the game on a blank screen; a remake
  should not reproduce the hang.
- `$430F4`'s verify is a signed `>=`, not equality — a remake that
  reimplements the EEPROM driver should use an equality check
  (the signed compare only reliably catches the erased `$FF`
  state on the clear path).
- The save serialiser's 1008-bit guard (`cursor > 0x3F0` →
  `$12FA0(0xC8)`) and the 1001-bit total are the format's size
  contract; any added field must fit in the 7 spare bits or the
  format must version.

## 12. Corrections made by this issue

- **`docs/architecture.md`:** "DI = D0" → **DI = D7** (the data bit
  is on data-bus bit D7; the old text likely misread CPU register
  d0 as bus bit D0); `$42F96` is the **ACK read**, `$42EEE` is the
  **bit-in** (the old text conflated them); the `$4323C` section now
  points at this doc for the full analysis.
- **`docs/logic-audit.md` §5 + §11 dispatch table:** the "Load
  handler (C=14 → `0x202CC`)" label is **wrong** — case 14 is the
  'Goods' shop verb; the real Load is **case 81 → `$20652` →
  `$2F896`** and the real Save is **case 82 → `$20670` →
  `$2F11A`** (§6). The never-read-`$FF0168` claim is unaffected.
- **The SYSTEM Load/Save (C=0) → 81/82 bridge is closed (§6, §10
  open item removed):** the B byte is a submenu index; `L01FEB8`
  opens `$CCDB8 + offset_table[B]` (26 u16 in RAM `$FF01EA`,
  copied at boot by `main_init` from ROM `$FD026`); the LOAD
  `$CD10E` / SAVE `$CD136` "Yes" records carry C=81/82, which the
  A=78 handler writes to `$FFBB6C`, reaching `$2068E` cases 81/82.
- **`docs/overview.md`:** no change needed — it does not carry the
  C=14 label.
