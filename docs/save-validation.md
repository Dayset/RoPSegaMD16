# Save / EEPROM validation (issue #019)

Written 2026-11-09 (agent session) from the call-graph-level trace
already verified in `docs/architecture.md` (#003, §$4323C). The
deep trace (buffer layout, chip identity) remains blocked on the
ROM + emulator; this doc consolidates everything the repo proves,
answers two of the four acceptance items, and pins the rest.

## 1. `$DCE2`, `$42FC8`, `$43012` — traced (acceptance item 1: MET at call-graph level)

| Routine | What it does (verified, `docs/architecture.md`) |
|---|---|
| `$42FC8` | Serial-EEPROM **enable/init**: `$FF014C=10` (retry limit), `$FF014E=0` (error count), `$1964` delay loop, then 8× {write `$80` to `$200000`, NOPs, `jsr $42E34`}, then `jsr $42E76`. Helpers `$42E34`/`$42E76` write clock/idle sequences (`$C0/$40/$00`, resp. `$00/$40/$C0/$80`) to `$200000`. |
| `$43012` | EEPROM **write**: address/buffer args from the stack → `$FF0150–$FF015C`; clocks the command out via `$42EBA` ×8 (bit-out: DI=D0, CLK=D6 on the `$200000` word); reads an ACK bit via `$42F96` (bit-in: DO=D7); on error `$FF014E++`, retries up to `$FF014C` (10). `$430F4` is the matching **read**. |
| `$DCE2` | **Joypad port-2 read — NOT save code.** Same two-phase pattern as `$3AA` on `$A10005`; returns the inverted button byte in d0. 8 call sites: 4 inside `$4323C`, 4 in game code (`0x11BC8` → `$FF8646`; `0x12420` compares `$FF8646` to `$FA`). It appears in the save routine only because the save-clear combo is read on pad 2. |

## 2. The magic bytes `$E0` / `$B0` — decoded (part of acceptance item 1)

Compared against the `$DCE2` result inside `$4323C`
(at `0x432AE`/`0x43304`/`0x4331C` and the head compare):
- `$E0` = **B + C + Start held on pad 2**
- `$B0` = **A + C + Start held on pad 2**

If `$E0` is held at boot: `$FF0168=1`, the 128-byte buffer at
`$FF016A` is zeroed, `$FF01E8=$FF`, and a fill loop runs via
`$430F4` — i.e. a hidden pad-2 combo **forces a fresh/blank save**.
`$4323C` returns `$F0` if either combo is held, else the raw pad-2
byte. Whether this is a deliberate "clear save" feature or a
validation-path side effect is still open (intent, not mechanism).

## 3. Save medium — DECIDED (acceptance item 2: MET)

**Serial EEPROM, Microwire-style, bit-banged through the cartridge
`$200000` window. Not SRAM, not passwords.** Evidence chain:
1. Separate DI (D0) / CLK (D6) / DO (D7) lines on `$200000`
   accesses in `$42EBA`/`$42F96` — a 3-wire serial EEPROM protocol
   (architecture.md §$4323C).
2. The ROM header declares **no backup RAM** (bytes `0x1B0–0x1BF`
   are spaces) — the EEPROM is discoverable only from code.
3. BlastEm **auto-detected an EEPROM** from the `$200000` access
   pattern and created a **128-byte** `save.eeprom` (all `$FF` =
   erased state) — matching the 128-byte `$FF016A` buffer exactly.
Chip identity (93C46 family suspected) is **unconfirmed** — that
needs the write-command bit pattern decoded against datasheets,
blocked here (no ROM). Note for #031/#035: Russian commenters on
the 2012 translation asked for an EEPROM→SRAM rework — consistent
with EEPROM being the shipped medium.

## 4. The 128-byte `$FF016A` buffer + byte-sum check (acceptance item 3: PARTIAL)

What is verified: on the non-combo path, `$4323C` validates the
buffer by **byte-sum: 126 bytes summed, with NOT/swap variants
checked, error count accumulated in d1; `d1==0` = valid**. BlastEm's
log shows the validation branches (`0x43316`, `0x4333A`, `0x4332E`,
`0x432F6`, `0x432B6`) all executing on a clean boot. This is a
presence/format check, not a real integrity check
(`docs/overview.md` weak points) — a single-byte sum catches
random corruption only probabilistically and is trivially forgeable
**as a format** (the exact variant arithmetic still needs the deep
trace before anyone claims a forged save boots).
What is **not** known: the buffer's internal layout (which bytes
are party/position/flags, what the 2 unsummed bytes are — likely
the stored sum itself, unproven), and the exact NOT/swap variant
formulas. **Blocker: needs ROM + BlastEm save-state experiments
(write a save, corrupt bytes, observe) on the owner's machine.**

## 5. `$FF0168` flag (acceptance item 4: PARTIAL)

Verified: `$4323C` clears `$FF0168` on entry and sets it to
**0, 1, or −1** across its paths; the one fully-decoded assignment
is `$FF0168=1` on the `$E0` combo path (fresh/blank save forced).
The mapping of 0 and −1 to game states (plausibly "valid save" /
"no save or invalid") is **not** proven in any committed doc —
callers of `$4323C`'s result and `$FF0168` readers were not traced.
Recorded as an open sub-item, not filled in by guessing.

## 6. Remaining work list (for the owner's machine)

1. Decode `$43012`/`$430F4` command bit patterns → chip identity.
2. Dump a real (emulated) save: play to a save point, read back the
   128-byte EEPROM image, diff against `$FF016A` buffer writes.
3. Trace `$FF0168` readers → state mapping (item 4 above).
4. Byte-corruption matrix on the sum check → forgeability verdict
   for the #021 audit question 1.

## BlastEm EEPROM experiments (issue #019, 2026-11-09)

Run in the VM against both the original ROM and the M5 rebuild
(identical behaviour, as expected — the rebuild is byte-equal).

**Save file.** Booting creates
`~/.local/share/blastem/<rom-name>/save.eeprom`, exactly
**128 bytes** — matching the serial-EEPROM size the code
expects. After attract-mode-only boots its contents are
**all 0xFF** (erased EEPROM; no save is written without
gameplay input). On later boots BlastEm logs
`Loaded EEPROM from …/save.eeprom`.

**Bus activity at boot.** BlastEm's log line
`EEPROM address 200000: sda read: 7, sda write: 80, scl: 40`
shows the game's init/validation bit-banging the $200000 bus
during boot even with an erased EEPROM — consistent with the
$42FC8 enable/init + $4323C validation path running on every
boot, not only when a save exists.

**Debugger inspection (PTY, BlastEm -d).** A breakpoint at
$4323C (save validation) hits during boot. At that first hit,
`p/x $ff0168` (the save-present flag) reads **0** and the
buffer at $FF016A+ reads **0** — i.e. at validation entry the
RAM buffer is still in its cleared state; the EEPROM read
($430F4) that fills it happens inside the routine, as the
static trace said. A breakpoint at $D28E did **not** hit
within 20–30 s in debugger mode (the main loop IS reached in
plain headless runs — see the #014 address log), so
post-validation buffer contents and the new-game save flow
were not captured headless; they need input injection or a
human at the emulator. That is the precise reachability limit
of this session, not a gap in the static analysis.
