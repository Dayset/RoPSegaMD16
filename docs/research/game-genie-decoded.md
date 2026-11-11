# Game Genie codes decoded (from #033 cheats.htm, via #021)

Written 2026-11-09. Tool: `tools/decode_gamegenie.py` (Genesis
Game Genie decoder; `--selftest` passes on two published worked
examples from the codehut code-making guide — 97JT-EVSG ↔
0x0251E6:0xA8FF and AFJT-EVSG ↔ 0x0251E6:0xA801 — and on an encode
round-trip of every code below).

Unlike the Gens/PAR codes on the same fan page (which write
**RAM**), Game Genie codes patch **ROM** words: the Genie
substitutes the word whenever the CPU reads that address. Address
== file offset in this flat 1 MB ROM.

## The master code is the runtime-checksum bypass — VERIFIED

| Code | Decodes to | Original word | Meaning |
|---|---|---|---|
| R1JA-86Y6 | **0x0FD09C: 0x4E75 (RTS)** | 0x6602 (`bne.b $FD0A0`) | See below |

The checksum routine at 0xFD07C (#001/#002) ends:
`cmpi.l #$8F33608C, d0` at 0xFD096, then at **0xFD09C**
`bne` to the hang path at 0xFD0A0, with `rts` at 0xFD09E on
success. The master code replaces the `bne` with `rts`, so the
routine **always returns as if the checksum passed**. That is
exactly why "the game won't boot without it": every other Genie
code changes a ROM word, which changes the runtime sum, which
would otherwise hang the game at boot. This also independently
confirms the repo's checksum analysis (and matches the Russian
translation's approach of NOP-ing this same area, #035).

## Per-character / resource codes

All remaining codes land in one block, **0x009C14–0x00A45A** —
inside map.md's `0x001300–0x00FFFF` "Code (handlers, subroutines,
tables) [likely]" range. This block is **not yet function-mapped**
(#011 recursive analysis is still owed), and the linear sweep is
misaligned over much of it, so the *instruction* each code patches
cannot yet be named reliably. What can be said from the decoded
pairs themselves:

- Replacement words are mostly **0x60xx (BRA.W)** — a branch that
  skips a stretch of code — or small words (0x00xx). That is the
  classic shape of "neutralise the routine that decreases /
  recomputes this stat".
- Addresses cluster and interleave by character (Buc
  0x9C14–0x9C2C with Slash-exp at 0x9C1E inside the same span;
  Alexi/Mortimer/Obliki interleaved at 0xA21E–0xA27E; Feather at
  0xA402–0xA45A), suggesting shared stat-write routines with
  per-character entry points rather than one block per character.

| Code | Address : word | Fan description |
|---|---|---|
| KWVA-AA7W | 0x00A2B2 : 0x604C | unlimited money |
| RWVT-AAC4 | 0x00A35A : 0x0074 | unlimited water |
| AWVT-AA8C | 0x00A3C2 : 0x6004 | unlimited food |
| HWRA-AA2Y | 0x009C14 : 0x603C | Buc unlimited health |
| HWRA-AA3L | 0x009C2A : 0x603C | Buc unlimited power |
| AWRA-ABVN | 0x009C2C : 0xC004 | Buc unlimited exp |
| RWRA-AA5W | 0x009C72 : 0x6074 | Slash unlimited health |
| TWRA-AA5L | 0x009C6A : 0x6084 | Slash unlimited power |
| DWRA-AAA8 | 0x009C1E : 0x001C | Slash unlimited exp |
| PWWA-AA22 | 0x00A418 : 0x606C | Feather unlimited health |
| AWWA-AAC4 | 0x00A45A : 0x0004 | Feather unlimited power |
| PWWA-AAAC | 0x00A402 : 0x006C | Feather unlimited exp |
| KWVA-AACG | 0x00A246 : 0x004C | Obliki unlimited health |
| EWVA-AACW | 0x00A252 : 0x0024 | Obliki unlimited power |
| KWVA-AADT | 0x00A270 : 0x004C | Obliki unlimited exp |
| AWVA-AAD8 | 0x00A27E : 0x0004 | Mortimer unlimited health |
| TWVA-AADM | 0x00A26B : 0x0084 | Mortimer unlimited power — **ANOMALY, below** |
| DWVA-AA3Y | 0x00A234 : 0x601C | Mortimer unlimited exp |
| KWVA-AAA8 | 0x00A21E : 0x004C | Alexi unlimited health |
| TWVA-AABW | 0x00A232 : 0x0084 | Alexi unlimited power |
| KWVA-AABG | 0x00A226 : 0x004C | Alexi unlimited exp |

## Two anomalies in the fan-published list (do not "fix" silently)

1. **TWVA-AADM (Mortimer power) decodes to an ODD address,
   0x00A26B** — impossible for a word patch. A one-symbol
   transcription error in the fan list is almost certain.
   Changing only the last symbol M→L yields 0x00A26A with the
   same word 0x0084 as its sibling power codes (Alexi's decodes
   to 0xA232:0x0084) — a plausible correction, labelled
   **conjecture**, not applied to the table above.
2. **1NTB-AEL8 ("food/water low; health/power never decrease")
   decodes to 0x10205E: 0x22BB — outside the 1 MB ROM.** On a
   real cart that address aliases the ROM mirror
   (0x10205E & 0xFFFFF = 0x00205E), where the word is 0xE00F in
   a table-like region the linear sweep cannot decode — or this
   code is also mis-transcribed. **Unverified** either way.

## Region coverage note

Flagged per #021: apart from the master code (0xFD09C, inside the
verified checksum block), **every decoded address lands in a
region the repo has NOT function-mapped** (the 0x1300–0xFFFF
"likely code" block). Naming the patched instructions is new
#011 work: recursive disassembly of 0x9C00–0xA500 would convert
this table from "plausible BRA-skip cheats" to proven mechanics.
