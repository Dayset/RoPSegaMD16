# Sound: Z80 driver + music/SFX map (L018)

**Status:** done 2026-11-10. **Milestone M3 is now complete** (#004–#006, #015–#018, #037 all done).
**Confidence convention:** **[live]** = verified by running the ROM in BlastEm;
**[static]** = read from the disassembly and cross-checked; **[open]** = hypothesis or
unfinished work, listed in §12.

## 1. Headline findings

- **The Z80 driver is a 0x1576-byte blob at ROM `0xEBB6E–0xED0E4`**, uploaded by the
  68000 to Z80 RAM `$0000` and started by releasing the Z80 reset. Entry is Z80
  `$0000` (`ld hl,$1FFF; ld sp,hl; jp $017D`). It is an **FM (YM2612) driver** —
  the 68k writes YM registers through the Z80's `$4000` (address) / `$4001` (data)
  ports, with a `push af / pop af` delay between the two writes. The driver is
  by **S. Hayes, 1991** — the signature string `SHayes1991` sits at Z80 `$00DA`
  in the ROM image (see the §2.4 quirk: the 68k overwrites its first byte at
  runtime).
- **The 0x0E0000–0x0EB771 "song/SFX data" hypothesis from L011 is WRONG.**
  That range is not song data. Songs live at **`$ED0E8–$FCB7C+`** (19 songs, right
  after the driver blob) plus one song at **`$00692E`** (embedded in the low
  code region); SFX records live at **`$FCAE2`** (62 records × 22 bytes).
  What `0x0E0000–0x0EB771` actually is remains open (§12) — it is not music.
- **The 68000 streams song data to the Z80** through a 1 KB ring buffer at Z80
  `$1600–$1A00`, refilling 256-byte chunks whenever the Z80's chunk byte at
  `$00DA` changes. The song player on the Z80 is a blocking loop: while a song
  plays, the Z80 does nothing else except service SFX commands once per tempo
  tick.
- **19 playable songs** (indices 0–17 and 20) plus two silent indices (18, 19).
  Index 18 is the music menu's "Quiet". Index 20 is a 10-byte one-shot arrival
  jingle that shares its tail with song 2.
- **62 SFX records** (indices 0–61) in a 22-byte table at `$FCAE2`, delivered as
  23-byte command blocks to Z80 `$003A` on two alternating slots (commands 6/7);
  **SFX 90–96 are special**: they carry a 68k ROM pointer (banked into the Z80's
  `$8000` window) instead of a table record.
- **The driver is uploaded lazily, not at reset.** During the attract/title
  loop the Z80 RAM holds no driver at all **[live]**; the first upload happens
  on the attract→game transition (`0x1260`), and every song start re-uploads
  it (`$EB88A` → `$EB806`).
- **The VBlank sound tick `$EB772` is the only 68k→Z80 clock.** It writes a
  tempo byte to Z80 `$00E6` once per frame (NTSC) or 1.2× per frame (PAL), and
  the Z80's song player advances one tick per tempo-byte increment. The tick
  does not run during the attract loop (interrupts masked) — the first song
  only starts advancing after `$D25C` enables VBlank interrupts.

## 2. The Z80 driver

### 2.1 Location and entry [static + live]

| Item | Address |
|---|---|
| Driver blob in ROM | `0xEBB6E–0xED0E4` (0x1576 = 5494 bytes) |
| Upload destination | Z80 RAM `$0000` (via `$EB806`, 0x1576 bytes) |
| Entry (Z80 reset vector) | Z80 `$0000`: `21 FF 1F` `ld hl,$1FFF`, `F9` `ld sp,hl`, `C3 7D 01` `jp $017D` |
| Main code | Z80 `$017D` |
| Interrupt vectors `$0008–$0066` | all `ED 4D` (`reti`) — the driver is polled, never interrupt-driven; main starts with `di` |

**[live]** A snapshot harness (`.scratch018/harness018.s`, hooked at the attract
loop `0x35C`) called the real song path `$173BC(0)` and read Z80 RAM back through
the proper bus discipline. After the call: Z80 `$000A=0x00`, `$000B=0x0D`,
`$000C=0x00`, `$00DA=0x16`, and the first song bytes at Z80 `$1600` are
`00 C1 06 78 C1 06 78` — exactly song 0's data. The 68k side at the same moment:
`$FF012E=0`, `$FF022C=$0ED0E8`, `$FF0230=$0ED5E8`, `$FF021E=$FF16`.

**[live]** Before any song start (attract context), Z80 `$0000` reads `0xE1`
(not `0x21`) and `$00DA` reads `0x3A` (not `0x53`): **the driver is not in Z80
RAM yet**. The only `$EB806` callers are `0x1260` (attract→game transition),
`$EB88A` (every song start) and `$EBB04` (SFX when sound is off). So the driver
is uploaded lazily.

### 2.2 Code / data layout of the blob [static]

Ghidra headless Z80 analysis (see §11) disassembled 1067 instructions covering
2118 of the 5494 bytes. Code lives in `$0000–$0B80` (with data gaps); the rest
is tables.

| Z80 range | Contents |
|---|---|
| `$0000–$0039` | Reset entry + interrupt vectors (`reti`) |
| `$003A–$0066` | Runtime state: SFX command-block area `$003A–$0050` (23 bytes, written by the 68k), two SFX slot states at `$0051–$0055`, slot voice pointers at `$0068–$006B` |
| `$0068–$017D` | Tables: `SHayes1991` at `$00DA`, note table at `$00EB`, per-channel state table `$014D` (16 bytes) |
| `$017D–$02C8` | Main loop `$017D`, YM write helpers `$01B4`/`$01BA`, `$000A` handlers `$01C0`/`$01E1`, song-pointer advance `$046A` (in the next block) |
| `$02C9–$046A` | Tables, incl. the 91-entry × 2-byte note/frequency table at `$02CB` |
| `$046A–$08CA` | `$046A` (advance song pointer + chunk byte), `$048B` (channel table), `$0498` (bank setup), `$04B7`/`$04BD` (YM part-2 writes), FM voice routines `$0506–$07F0` |
| `$08CB–$08EA` | 31 bytes data (jump-table area for the song-event parser) |
| `$08EB–$0B80` | Song init `$0804`, event parser `$084C`, song player `$08F8`, per-tick `$0B22`/`$0B49`, SFX block installers `$0A04`/`$0A08` |
| `$0B81–$1576` | Data only (2549 B): FM patch/note tables |

### 2.3 Main loop [static]

```
$017D: di
       ld a,$27; call $01B4        ; YM register $27 = $00 (timers off)
       ld a,$00; call $01BA
$0188: ld a,($000A); and a; jr z,$019D
       cp $FF; jp z,$0198          ; $000A == $FF -> $01E1
       call $01C0                  ; $000A == other -> $01C0
       jr $0188
$0198: call $01E1; jr $0188
$019D: ld a,($000B); and a; jr z,$01B1   ; $000B == 0 -> loop
       cp $0D; jr nz,$01AC               ; $000B != $0D -> clear it, loop
       call $08F8                        ; $000B == $0D -> play song (BLOCKS)
$01AC: ld a,$00; ld ($000B),a; jp $0188
```

So `$000A` is the SFX-pointer command (handled even when idle) and `$000B=$0D`
is the song-start command. `$08F8` runs the whole song: it busy-waits on the
tempo byte `$00E6` and returns only when the song ends (`$00EA` set), at which
point the main loop clears `$000B` — which is how the 68k's watchdog learns
the song finished (§4.4).

`$01B4` / `$01BA` are the YM2612 write pair: `A → ($4000)` (register select)
and `A → ($4001)` (data), each preceded by `push af / pop af` as a write
delay. `$04B7` / `$04BD` are the same pair for the YM's second register set
(`$4002` / `$4003`).

### 2.4 The `SHayes1991` signature and the `$00DA` quirk [static + live]

The string `SHayes1991` sits at Z80 `$00DA` in the ROM image — but `$00DA` is
also the song-stream chunk byte (§5). `$EBA7E` writes `$16` to `$00DA` on every
song load, clobbering the `S` (`0x53`). The signature is only intact before the
first song load, and only in the ROM image / a freshly uploaded driver. It is
an identification marker, not data the driver reads.

A second overlap in the same area: the blob byte at `$00E6` is `0x00`, not
`0x8F` as first misread — the `0x8F` is at `$00E7` (the song parser's
last-event-byte variable). `$00E6`'s initial value is therefore `0x00`.

## 3. The 68000 sound API

All routines live at `$EB772–$EBB6E`. The 68k touches the Z80 only through the
bus-request register `$A11100` (bit 8 = request) and the reset register
`$A11200` (bit 8 = run), with Z80 RAM visible at `$A00000–$A01FFF` while the
bus is held. The bus discipline is: `SR=$2700`, write `$100` to `$A11100`,
access `$A00000+`, write `$0` to `$A11100`, restore SR. Helper `$EB92A` does
the first half (sets SR, requests the bus, `a0=$A00000`); callers release the
bus and restore SR themselves.

### 3.1 Routines [static]

| 68k routine | Purpose |
|---|---|
| `$EB772` | Per-frame sound tick (called from the VBlank handler `0x1272` at `0x12F2`). Tempo tick to Z80 `$00E6`, `jsr $EBAC6` (SFX queue), frame counter `$FF0220`++, every 16th frame `jsr $EBA00` (music streamer). **Not** the draw dispatch (see L015/L020). |
| `$EB7C8` | Stop-sound. Clears `$FF021E`, writes 0 to Z80 `$000A`/`$000B`, asserts the Z80 reset (`$A11200=0`), delays, releases reset. Dead code in the game (zero callers) — the music-off patch revives it. |
| `$EB806` | Upload the Z80 driver: copies 0x1576 bytes from ROM `$EBB6E` to Z80 `$0000`, then reset/releases the Z80 so it starts at `$0000`. Also reads `$A10001` bit 6 into `$FF0222` (PAL flag) and clears `$FF022C`/`$FF0236`/`$FF023A`. Called at `0x1260` (attract→game), from `$EB88A`, and from `$EBB04` when sound is off. |
| `$EB88A(addr)` | Start-song. Calls `$EB806` (re-uploads the driver), sets `$FF022C=addr`, `$FF0230=*(addr-4)` (song end pointer), calls `$EBA7E` (loads the first 1024 song bytes into Z80 `$1600`), writes `$000B=$0D`, `$000A=0` to the Z80, sets `$FF021E` (sound on). |
| `$EBA7E(addr)` | Load song data: sets `$FF0228=$A01600`, `$FF021F=$16`, writes `$16` to Z80 `$00DA`, copies 1024 bytes from the song address to Z80 `$1600–$1A00`, sets `$FF0224=addr+1024`. |
| `$EBA00` | Music streamer (every 16 frames, only if `$FF021E` set). If Z80 `$000B==0` or `$00DA==$FF021F`, does nothing. Otherwise copies 256 bytes from `$FF0224` to `$FF0228`, wraps `$FF0224` to `$FF022C` at `$FF0230` (song loop) and `$FF0228` to `$A01600` at `$A01A00` (ring wrap). |
| `$EBAC6` | SFX command queue (called every frame from `$EB772`). Drains slots `$FF0236` and `$FF023A` (each holds a pointer to a 23-byte command block) via `$EBB04` / `$EBBFE`. |
| `$EBB04` / `$EBBFE` | SFX deliver (slot 6 / slot 7). If sound is off, re-uploads the driver first. If Z80 `$000C` is nonzero (busy), queues the block pointer in `$FF0236` / `$FF023A`. Else copies the 23-byte block to Z80 `$003A` and sets `$000C=6` / `7`. |
| `$EBAF4(ptr)` / `$EBAFA(ptr)` | Public SFX entry points (called by `$17586`): try `$EBB04` / `$EBBFE` immediately. |
| `$EB8F2(d0)` | Write the 24-bit value in `d0` to Z80 `$016E–$0170` (big-endian) and clear Z80 `$17C`. Called via `bsr` from `$EB93E`/`$EB968`/`$EB986`/`$EB9A0` (the last two are themselves dead — see below). Its no-bus twin `$EB8E0` has no callers. |
| `$EB93E(addr, n)` | SFX-pointer command: `$016E=addr` (via `$EB8F2`), Z80 `$000A=n` (1 if `n==0`). Called only from `$17586`'s non-`$FFFF` branch — which no call site ever takes (all 98 `$17586` sites pass `$FFFF`), so `$EB93E` is unreachable in practice. |
| `$EB968(addr)` | SFX-pointer command: `$016E=addr`, Z80 `$000A=$FF`. The pointer-SFX path every live call takes. |
| `$EB986(addr, n)` | `$016E=addr`, Z80 `$000B=$12`, `$000A=n`. **Dead — no callers anywhere in the ROM** (verified by full-text search of the listing). |
| `$EB9A0(addr)` | `$016E=addr`, Z80 `$000B=$12`, `$000A=$FF`. **Dead — no callers anywhere in the ROM.** |
| `$EB9B4` | Clear Z80 `$000B` (writes 0). **Dead — no callers anywhere in the ROM.** |
| `$EB9C4` | "Is a song playing?" Returns Z80 `$000B` if `$FF021E` is set, else 0. |
| `$EB9EE` | Returns Z80 `$000A` (via `$EB92A`; unlike `$EB9C4` it does not check `$FF021E` first). **4 callers, all in the `$3Dxxx` combat routines** (`0x3D2F8`, `0x3DDD2`, `0x3DEA6`, `0x3DF2C`): an SFX-busy gate — `jsr $EB9EE; tst; bne skip` — a new SFX is only started when `$000A==0` (no pointer-SFX active). Two of the callers then play SFX 95, one plays SFX 33 (`$21`). |
| `$EB920` / `$EB922` | Byte-copy loop (`(a1)+ → (a2)+`, `d0` bytes via the `bra` entry, `d0+1` via the direct entry). |

### 3.2 68k sound state (RAM) [static]

| Address | Contents |
|---|---|
| `$FF012E` | Current song index (`0xFFFF` = none yet). Set by `$173BC` only — the Music menu (`$2063C`) and the `$1DC90` jingle path call `$173EC` directly and do **not** update it, so the watchdog replays the location song when a menu-picked song ends. |
| `$FF021E` | Sound-on flag (`$FF` = on). Cleared by `$EB7C8`/`$EB806`, set by `$EB88A`/`$EBB04`/`$EBBFE`. |
| `$FF021F` | Last `$00DA` chunk value seen by the streamer (init `$16`). |
| `$FF0220` | Frame counter for the 16-frame streamer tick. |
| `$FF0222` | PAL flag (from `$A10001` bit 6). When set, the tempo accumulator gains an extra `$33`/frame (see §4.1). |
| `$FF0224` | 68k song-stream pointer (advances 256 bytes per refill). |
| `$FF0228` | Z80 destination pointer for the next refill (`$A01600–$A01A00`). |
| `$FF022C` | Song start address (loop target). |
| `$FF0230` | Song end address (`*(song-4)`). |
| `$FF0234` | Tempo accumulator (word). `+$100`/frame, `+$33` extra on PAL. Its high byte is written to Z80 `$00E6` each tick. |
| `$FF0236` / `$FF023A` | Deferred SFX command-block pointers (slots for `$EBB04` / `$EBBFE`). |
| `$FF0088` | SFX channel alternator (0/1, flipped per `$17586` call for indices < 90). |

## 4. How the 68000 triggers music/SFX

### 4.1 The tempo clock [static + live]

`$EB772` (every VBlank): if `$FF0222` (PAL) is set, `$FF0234 += $33`; then
`$FF0234 += $100` and the **high byte** of `$FF0234` is written to Z80 `$00E6`.
So `$00E6` increments by exactly 1 per frame on NTSC, ~1.2 per frame on PAL
(the `+$33` low-byte addition carries into the high byte about once every 5
frames — 60/50 compensation). The Z80's song player advances one tick per
`$00E6` increment (§6).

**[live]** In the game context (original ROM, after `$D25C`): `$FF0234` went
`$2100 → $2200` and `$FF0220` went `33 → 34` across two consecutive `$EB772`
hits — exactly `+$100` and `+1` per frame, NTSC.

### 4.2 Playing a song [static + live]

Call chain: location/game code → `$173BC(index)` → `$173EC(index)` → jump
table at `$17546` → `pea.l $songaddr; jsr $EB88A` → `$EB806` (driver upload)
→ `$EBA7E` (first 1024 bytes to Z80 `$1600`) → Z80 `$000B=$0D`.

`$173BC` skips the restart if the requested index already equals `$FF012E`
**and** `$EB9C4()` is nonzero (still playing). That is why "Quiet" (index 18)
does not stop already-playing music: `$173EC(18)` is a no-op jump (`$17582`,
return), and `$173BC` returns early while the old song plays — the music-off
patch fixes this at the `$173EC` level (see `patches/music-off/README.md`).

**[live]** `$173BC(0)` from the snapshot harness: `$FF012E=0`,
`$FF022C=$0ED0E8`, `$FF0230=$0ED5E8`, `$FF021E=$FF16`, Z80 `$000B=$0D`,
`$00DA=$16`, Z80 `$1600` = song 0's first bytes. All as predicted.

### 4.3 Playing an SFX — two paths [static]

**Path A — table SFX (indices 0–89).** `$17586(index, param)` (param is
`$FFFF` at 91 of 98 call sites): for index < 90 it alternates between the two
command slots via `$FF0088` (`$EBAF4` = slot 6, `$EBAFA` = slot 7). The record
address is `$FCAE2 + index*22`. `$EBB04`/`$EBBFE` copy **23 bytes** from the
record to Z80 `$003A` (one byte past the 22-byte record — a 1-byte overread
into the next record) and set Z80 `$000C=6`/`7`. If the Z80 is busy
(`$000C` nonzero), the pointer is queued in `$FF0236`/`$FF023A` and retried
next frame by `$EBAC6`. The Z80's song-player tick (`$0B49` tail) picks up
`$000C` and calls `$0A04` (slot 6) / `$0A08` (slot 7), which install the block
into the slot's voice structure and clear `$000C`.

**Path B — pointer SFX (indices 90–96, and the `$EB93E`/`$EB968` family).**
`$17586` with index ≥ 90 subtracts 90 and indexes a 7-entry jump table at
`$1764E` (indices 90–96 only; ≥ 97 returns). Each entry loads a fixed 68k ROM
address and calls `$EB968` (if param is `$FFFF`) or `$EB93E(addr, param)`:

| SFX index | ROM address | Used at (static sites) |
|---|---|---|
| 90 | `$4502` | — (no immediate site found) |
| 91 | `$1394` | 5 sites |
| 92 | `$3ADA` | 1 site |
| 93 | `$4500` | — |
| 94 | `$4504` | 1 site |
| 95 | `$9A60` | 3 sites |
| 96 | `$AE56` | 1 site |

The 68k writes the address to Z80 `$016E–$0170` (via `$EB8F2`) and a parameter
to `$000A` (`$FF` via `$EB968`, or the caller's value via `$EB93E`). The Z80
reads the data **directly from ROM through its bank window**: `$0498` turns
the 24-bit address into a bank number (written bit-serially to `$6000`, 9 bits)
and a window address `$00E0 = $8000 | (addr & $7FFF)`. `$01C0` (for `$000A`
≠ 0, ≠ `$FF`) and `$01E1` (for `$000A == $FF`) then read the SFX data through
that window. `$01E1` searches the 91-entry table at `$02CB` for the data's
first byte pair (a note→frequency lookup, result in `$0012`); `$01C0` takes
the direct path. Both end by setting up the YM DAC (register `$2B=$80`,
`$017C=$2A`) and reading the tempo byte into `B`.

`$EB986`/`$EB9A0` additionally write `$12` to Z80 `$000B` — but both routines
are **dead code with no callers anywhere in the ROM** (verified by full-text
search of the listing), as are `$EB9B4` and `$EB8E0`. The `$000B=$12` write is
therefore unreachable in the shipped game; its intended purpose is
unknowable from the game itself (§12 item 4). The Z80's main loop clears any
`$000B` that is not `$0D`, so even if the write were reachable it would have
no effect while a song is playing (`$08F8` is running and the main loop is
not polling).

### 4.4 The watchdog [static]

At `0x21608` (inside the `$2155E` world tick): `jsr $EB9C4; tst d0; bne skip;
push $FF012E; jsr $173EC`. When the current song ends, the Z80 clears `$000B`,
`$EB9C4` returns 0, and the watchdog replays the song in `$FF012E`. Songs
therefore loop forever until a location change or menu pick starts another.
Note the menu-pick asymmetry (§3.2): a menu-picked song is **not** in
`$FF012E`, so when it ends the watchdog replays the location song.

## 5. The music streamer [static + live]

- Ring: Z80 RAM `$1600–$1A00` (1024 bytes, 4 chunks of 256). The 68k preloads
  all 4 chunks (`$EBA7E`, 1024 bytes), then refills one 256-byte chunk at a
  time (`$EBA00`, every 16 frames, only when the chunk byte changed).
- Chunk byte: Z80 `$00DA` = the high byte of the song read pointer `$00E2`
  (`$16`–`$19` while reading, `$16` again after the `$1A00 → $1600` wrap).
  `$046A` (the pointer-advance routine) updates `$00DA` exactly when the
  pointer crosses a 256-byte boundary. `$EBA7E` initialises `$00DA=$16` and
  `$FF021F=$16`, so the first refill happens when the Z80 enters chunk `$17`.
- The 68k's destination `$FF0228` always points at the chunk the Z80 just
  finished (one behind the read pointer), so each refill overwrites finished
  data. The song loops because `$FF0224` wraps to `$FF022C` when it reaches
  `$FF0230` (the end pointer stored 4 bytes before the song data).
- Correction to an earlier reading: there is **no wasted chunk** at `$1A00`.
  `$EBA7E` stores `$FF0228=$A01600` *before* the 1024-byte copy, so the first
  refill writes to `$1600` (the finished chunk), not `$1A00`.
  **[live]** After song 0 started, `$FF0224=$0ED4E8` (song+1024, no refill yet)
  and `$FF0228=$A01600` — exactly the pre-refill state.

## 6. The song data format [static]

The Z80 reads the stream at `$00E2` (pointer into the `$1600` ring). The
parser (`$084C`, driven by `$08F8`'s loop) works on event bytes; the high
nibble selects the command and the low nibble is a channel number (0–15).
After each event, the next byte is read as a **delay** (number of tempo ticks
to wait before the next event) and stored in `$00E8`; `$08F8` decrements
`$00E8` once per tempo tick (`$00E6` increment).

| Event byte | Shape | Meaning |
|---|---|---|
| `$8X` | `[$8X][p1][p2][delay]` | Note event, channel X. Two parameter bytes, then `$06DA` (note-on). |
| `$9X` | `[$9X][p1][p2][delay]` | Note event, channel X. If `p2==0` → `$06DA` (note-on); else → `$079E` (writes `$00DB`). Exact musical meaning of `p1`/`p2` is **[open]** — they feed the FM voice routines (`$05C2`/`$0558`/`$067B`/`$06DA`), not fully traced. |
| `$CX` | `[$CX][param][delay]` | Set channel X's state byte (table `$014D+X`) to `param`. The 8 `$CX` events at the head of every song are the channel setup (volumes/instruments). |
| `$FC` | `[$FC][$80 \| other]` | `$FC $80` = skip the read pointer forward to the next 256-byte chunk boundary (the bytes in between, e.g. `00 0E D5 F4`, are skipped). `$FC <other>` = end of song (sets `$00E8=$00EA=1`; `$08F8` returns and the main loop clears `$000B`). |
| anything else | — | `JP $08C8` — an infinite loop. Malformed song data hangs the Z80. |

Two parser details: a leading stream byte `< $80` is skipped by the song
init (`$0804` advances past it — every song starts with `$00`); and if the
next stream byte is `< $80` at event-fetch time, the parser re-dispatches the
last event byte held in `$00E7` (running-status-style behaviour — exact
trigger not pinned down, **[open]**).

Channel state: `$014D` (16 bytes, one per channel) is **not** cleared by the
song init (`$0804` fills `$00FD–$014C` with `$FF` only), so channel state
persists across songs. `$06A9` (called by `$0804` and by the `$FC` handler)
resets the `$00F5–$00F7` voice bytes.

### Z80 song-player RAM [static]

| Z80 addr | Contents |
|---|---|
| `$000A` | SFX-pointer command (0 = none, `$FF` = table-search path, other = direct path) |
| `$000B` | Song command/status (`$0D` = play; cleared by the main loop when the song ends) |
| `$000C` | SFX block command (6/7 = install the `$003A` block into slot 0/1) |
| `$0012` / `$0013` | `$01E1` note-table index / following SFX byte |
| `$003A–$0050` | SFX command block (23 bytes, from the 68k) |
| `$0051–$0055` | SFX slot state bytes |
| `$0068–$006B` | Slot voice pointers (low/high bytes interleaved) |
| `$00A6` | Pointer used by `$0A04` (voice data) |
| `$00DA` | Song-stream chunk byte (`$16–$19`) |
| `$00DB` | Written by `$079E` (effect/note-off variable — exact role **[open]**) |
| `$00E0–$00E1` | SFX data pointer (bank-window address, set by `$0498`) |
| `$00E2–$00E3` | Song-stream read pointer (into `$1600–$1A00`) |
| `$00E4–$00E5` | Read by `$08F8` (`$0967` handler if nonzero — **[open]**) |
| `$00E6` | Tempo byte (written by the 68k, once per frame) |
| `$00E7` | Last event byte (running-status) |
| `$00E8` | Ticks remaining before the next event |
| `$00E9` | Last tempo value processed |
| `$00EA` | Song-done flag |
| `$00EB` | Note lookup table (used by `$04C3`) |
| `$00F5–$00F7` | Voice bytes reset by `$06A9` |
| `$014D` | Per-channel state (16 bytes) |
| `$016E–$0170` | 24-bit 68k ROM address (written by the 68k via `$EB8F2`) |
| `$0174` / `$0176` | Saved `HL`/`DE` (used by `$01C0`/`$01E1` paths) |
| `$017C` | DAC state (`$2A` while a pointer-SFX is active, else 0) |
| `$00E6` init `0x00`, `$00E7` init `0x8F` (blob bytes) | |

## 7. The song map [static + live]

### 7.1 Dispatch table [static]

`$173EC(index)` allows indices 0–20 (`cmp #$15, bcc return`). The jump table
at `$17546` (21 words, offsets relative to `$17580`) maps:

| Index | Song data | End ptr | Stream len (B) | Ends? | Where it plays |
|---|---|---|---|---|---|
| 0 | `$ED0E8` | `$ED5E8` | 1280 | loops | First song (`$11E06`, via `$173BC` at `0x11F2C`); also the boot song seen live |
| 1 | `$EDDBA` | `$EEFBA` | 4608 | loops | Intro/story loops (`$15012` at `0x15020`, `$14FB6` at `0x154F6`) |
| 2 | `$ED4FE` | `$EDDFE` | 2304 | loops | Default/location song (`$32D0E` picker; location table `$D63E7`, mostly 2) |
| 3 | `$EEF8C` | `$EFC8C` | 3328 | loops | (location table arg 52) |
| 4 | `$EFBC8` | `$F07C8` | 3072 | loops | (location table args 12, 20, 35–37, 39, 58–63) |
| 5 | `$FA926` | `$FBD26` | 5120 | loops | (location table arg 45) |
| 6 | `$F0C32` | `$F2732` | 6912 | loops | — |
| 7 | `$F26CC` | `$F36CC` | 4096 | loops | `$16AFC` (song 7) |
| 8 | `$F363E` | `$F373E` | 256 | **ends** (`$FC` at offset 103) | `$15B18` (song 8, short one-shot) |
| 9 | `$F36AC` | `$F51AC` | 6912 | loops | (location table args 43, 45, 49, 50) |
| 10 | `$F5182` | `$F5E82` | 3328 | loops | (location table args 32–34, 40–41, 48, 53, 55–56) |
| 11 | `$00692E` | `$09B2E` | 12800 | loops | `$17B88` (song 11 — the long one; embedded in the low code region) |
| 12 | `$F5DAE` | `$F68AE` | 2816 | loops | (location table arg 46) |
| 13 | `$F6844` | `$F9044` | 10240 | loops | (location table args 47, 50) |
| 14 | `$F900A` | `$F9C0A` | 3072 | loops | — |
| 15 | `$F9B38` | `$FA938` | 3584 | loops | — |
| 16 | `$F075E` | `$F0C5E` | 1280 | **ends** (`$FC` at offset 1229) | — |
| 17 | `$FBC7C` | `$FCB7C` | 3840 | loops | `$32D0E` picker (leader `+0x06` == 2 or 3); `$17B88` path also uses 11 |
| 18 | — (no-op) | — | — | — | "Quiet" (music menu). Dispatch word `$0002` → jump to the return. |
| 19 | — (no-op) | — | — | — | Silent, same as 18. |
| 20 | `$ED4F4` | `$ED5F4` | 256 | **ends** (`$FC` at offset 4) | Arrival jingle (`$1DC90` path when the arrival-type arg is 3; see §7.3). 6 parsed bytes, then song 2's data. |

"Stream len" is the end-pointer minus the start address (the length the
68k streamer loops over). "Ends?" comes from a parser simulation of the event
format (§6): songs 8, 16 and 20 contain a `$FC <non-$80>` terminator and stop
on their own (the watchdog then replays the song in `$FF012E`); every other
song has no terminator in its stream — it plays through, wraps at the end
pointer, and repeats until something else starts a song. The `$FC $80`
seek commands inside the looping songs skip forward to the next 256-byte
chunk boundary (the padding between the seek and the boundary is never
parsed).

Song data region overall: `$ED0E8–$FCB7C` (songs 0–10, 12–17, 20) plus song 11
at `$00692E–$09B2E`. The SFX table starts at `$FCAE2` — 154 bytes *before*
song 17's end (`$FCB7C`), so the first 7 SFX records (`$FCAE2–$FCB7C`)
overlap song 17's tail; the stream's bytes there are mostly zeros and
record headers, consumed via the parser's running-status path (§6).

**[live]** Boot song is index 0 (`$FF012E=0`, `$FF022C=$0ED0E8`,
`$FF0230=$0ED5E8`) — the first `$EB88A` hit in the original ROM is the
`$11E06` song-0 call, not the `$32D0E` picker song (2/17), which comes later
in `$D25C`.

### 7.2 The song picker `$32D0E` [static]

Returns `$11` (17) if the leader's struct word at `+0x06` is 2 or 3, else `$02`
(2). Called from `$D25C` (boot) and from `0x16FCA` / `0x1DE34` (location
changes). The `+0x06` field's meaning (character type? party role?) is
**[open]** — the value, not the semantics, is established.

### 7.3 Location → song table `$D63E7` [static]

At `$1DC90` (location-arrival handler): the song index is the low nibble of
the byte at `$D63E7 + location_id*4` (stride 4; the other 3 bytes per record
are other location fields). Full dump of records 0–151 (verified by reading
the ROM table; earlier drafts only checked 0–63 and had one error):

| Song | Location ids (0–151) | Count |
|---|---|---|
| 2 | 0–11, 13–19, 21–31, 38, 42, 57, 121, 132 | 35 |
| 11 | 54, 68, 89, 93, 94, 99–101, 105–110, 133–136, 144–146 | 21 |
| 7 | 66, 83–87, 90, 113–115, 122–125 | 14 |
| 4 | 12, 20, 35–37, 39, 58–62, 91, 92, 116 | 14 |
| 10 | 32–34, 40, 41, 48, 53, 55, 56, 67, 69, 111, 112 | 13 |
| 15 | 77–79, 81, 119, 120, 130, 131 | 8 |
| 9 | 43, 44, 49, 51, 72, 73, 82, 140 | 8 |
| 12 | 46, 64, 65, 95–98 | 7 |
| 13 | 47, 50, 126, 127, 137–139 | 7 |
| 14 | 70, 71, 74–76, 141–143 | 7 |
| 5 | 45, 102–104, 128, 129 | 6 |
| 3 | 52, 63, 88 | 3 |
| 1 | 117, 118 | 2 |
| 6 | 80 | 1 |
| 0 | 147–151 (padding/terminator run) | 5 |

Correction: an earlier draft said "ids 58–63 → 4" — loc 63 is song 3
(byte `0x03`), not 4; 58–62 → 4. Records 152+ break the pattern (large
b1/b2, high nibbles up to 9) — a different table or coordinate records, not
part of this map. Songs 8, 16, 17, 20 never appear in the location table:
17 is the `$32D0E` alternate map theme, 8/16/20 are event stings/pieces
(§7.4). No location-id → city-name mapping is recoverable from the ROM
tables alone (city names exist only as dictionary words; see the L018
addendum notes in `.scratch018/`). If the arrival-type argument (`$8(a6)`)
is 3, the handler instead plays song 20 directly via `$173EC` (the arrival
jingle) **and** writes the table song into `$FF012E`, so the watchdog loops
the location song after the jingle ends. Otherwise it plays the table song
via `$173BC`.

### 7.4 The 17 named tracks [mapped 2026-11-10, ROM-only]

The rings-of-power.ru soundtrack page lists 17 named tracks: Main theme
(Rings theme), Wizards, Knights, Archers, Sorceresses, Necromancers,
Enchanters (also the map theme), Battle, Castle, Death, Nexus, Quest, At sea,
Someone's home, Tavern, Victory, On the street. (A commenter also names
"Guilds", which is not in the list and is not mapped — no song is left for
it.) The mapping below was established 2026-11-10 using ONLY the ROM
(Dayset's call: "no mp3 needed as we have ROM with all the music and sfx in
it" — the fan-site MP3s were not downloaded or used). Method: (1) context
from the code — the location table (§7.3), the `$32D0E` picker, and every
`$173BC`/`$173EC` call site; (2) the song streams parsed with
`.scratch018/parse_songs.py` (loop length, note density, pitch range,
channels, `$CX` setup family); (3) one audio capture per song, rendered
from the ROM in BlastEm (see "How the audio was captured" below), analysed
for tempo/brightness/tonal centre with `.scratch018/analyze_songs.py`
(numpy FFT + onset autocorrelation). No fan-site audio was used, so the
name assignments that rest on audio character (rather than on a call site
or a location) are marked **guess** and the reasoning is stated. A live
playthrough that drives the game to each named place would upgrade the
guesses; the bytes alone cannot close the class/place assignments because
the location-id → city-name mapping is not recoverable from the ROM tables.

Confidence: **certain** = proven by the bytes; **strong** = the only reading
the evidence supports; **guess** = best-supported character/context fit, not
proven. "Loop" is the parsed loop length (NTSC 60 ticks/s); "notes/s" is the
parsed note density; "BPM" is the audio onset-autocorrelation pulse (it can
be a sub-harmonic — read it with the notes/s beside it); "locs" is the
number of location ids in §7.3 that play the song.

| Idx | Name | Conf. | Loop | Notes/s | BPM | p1avg | Ch | Locs | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| 0 | — (silent) | certain | — | 0 | — | — | 0 | 5* | Stream is `00` + `C1 06 78` × 343 + `$FC $80`: a repeating channel-1 setup with zero notes; the `$FC $80` seek skips the last 248 B of real note data, which is never played. The boot song (`$11E06`); as played it is silent. Audio capture confirms: no music except two non-dispatch bursts (§7.5). *Locs 147–151 are a padding run, not real locations. |
| 1 | Main theme | strong | 78.7 s | 14.4 | ~112 | 43.0 | 10 | 2 | Fullest arrangement (10 channels, the most of any song); plays during the intro/story cinematic (`$15012` at `0x15020`, `$14FB6` at `0x154F6`) — where a main theme belongs. Song 0 is silent and song 2 is Enchanters, so the Main theme is song 1 unless the audio proves otherwise; the capture is a full, flowing, moderate-tempo piece (RMS 0.632, top pitch classes A/F/D). |
| 2 | Enchanters | certain | 63.2 s | 8.8 | ~34 | 47.7 | 4 | 35 | The map theme: the default/location song almost everywhere (§7.3, 35 locations), the `$32D0E` picker default, and the fan-site list itself glosses Enchanters as "also the map theme". |
| 3 | Tavern | guess | 48.0 s | 16.2 | ~207 | 43.6 | 4 | 3 | Fast (~207 BPM), energetic, the widest pitch range of any song (p1 20–73); a lively, jaunty tune. Location song (52, 63, 88). The liveliest of the location themes — the best fit for a tavern. |
| 4 | Knights | guess | 38.8 s | 19.0 | ~207 | 40.1 | 6 | 14 | Busy (19.0 notes/s) and fast (~207 BPM) with a low pitch (40.1) and a distinctive slow rhythm (100× delay-8 notes) — driving and martial. Location song (14 ids). The most martial of the location themes. |
| 5 | At sea | guess | 67.7 s | 18.2 | ~112 | 43.8 | 3 | 6 | Busy melody (18.2 notes/s) over low drones (channels 4/6/9 only) at a moderate ~112 BPM — flowing, wave-like. Shares the `$CX` setup `[0, 14, 28, 16, 2, 0, 14, 28]` with songs 12/13/14/15. Location song (45, 102–104, 128, 129). |
| 6 | Necromancers | guess | 95.6 s | 17.8 | ~41 | 38.5 | 7 | 1 | Lowest average pitch (38.5) and a slow pulse (~41 BPM) with low drones (ch3 0x24 × 402, ch4 0x18 × 199) — the darkest song. Plays at exactly ONE location (id 80), a single specific dark place. The darkest song for the darkest class. |
| 7 | Archers | guess | 77.2 s | 12.7 | ~62 | 54.0 | 6 | 14 | Highest average pitch (54.0) and highest p1 floor (31) — the brightest, lightest song. Location song (14 ids). The lightest/highest song for the lightest, most agile class. |
| 8 | — (sting) | strong | 1.2 s, ends | — | ~152 | 48.4 | 2 | 0 | A 1.2 s sting (24 notes, ends on its own via `$FC` at offset 103). Played at 11 sites after `$26B58`/`$2BBD2` checks and once in the intro (`$15012`) — a short signal, not a track. Too short to be one of the 17 named tracks; unnamed. Audio capture: loud (RMS 0.892, the loudest), brief stings at each song request, then silence. |
| 9 | On the street | guess | 85.7 s | 20.0 | ~199 | 38.6 | 6 | 8 | Busiest song (20.0 notes/s), very fast (~199 BPM), low pitch (38.6) — bustling and urban. Location song (43, 44, 49, 51, 72, 73, 82, 140). The busiest location theme — the best fit for a crowded street. |
| 10 | Wizards | guess | 79.1 s | 9.8 | ~69 | 45.1 | 5 | 13 | Moderate (~69 BPM), balanced (9.8 notes/s, 5 channels), mid pitch (45.1) — a measured, mystical city theme. Location song (13 ids). The most balanced of the class-city candidates. |
| 11 | Castle | guess | 172.1 s | 18.3 | ~101 | 43.5 | 4 | 21 | Longest by content (12,800 B, 3,148 notes, 172.1 s) and the most-played location song after song 2 (21 ids) — a grand, general theme for a major place. Also the only location song played in combat (`$17B88`, called from `FUN_0003d9f8` every 10th map-stream chunk) — a significant-event song. |
| 12 | Nexus | guess | 142.0 s | 4.7 | ~207 | 48.2 | 3 | 7 | Sparsest song (4.7 notes/s) with a fast shimmer pulse (~207 BPM) over a sparse melody — spacious and mystical. Shares the `$CX` setup with 5/13/14/15. Location song (46, 64, 65, 95–98). A temple (Nexus) fits the spacious, mystical character. |
| 13 | Death | guess | 241.5 s | 10.5 | ~32 | 48.1 | 2 | 7 | Slowest (~32 BPM), longest by time (241.5 s), fewest channels (2) — the most minimal and contemplative piece. Location song (47, 50, 126, 127, 137–139). The slowest/most minimal song is the best fit for Death. (Song 16's combat context was considered for Death — see song 16 — but song 16 is fast and bright, the opposite of a dirge.) |
| 14 | Someone's home | guess | 146.7 s | 4.9 | ~67 | 46.6 | 3 | 7 | Sparse (4.9 notes/s), slow-moderate (~67 BPM), gentle, 3 channels — a quiet, intimate piece. Shares the `$CX` setup with 5/12/13/15. Location song (70, 71, 74–76, 141–143). |
| 15 | Sorceresses | guess | 111.5 s | 8.0 | ~43 | 42.8 | 3 | 8 | Slow (~43 BPM), flowing (8.0 notes/s), 3 channels — an enchanting, unhurried theme. Shares the `$CX` setup with 5/12/13/14. Location song (77–79, 81, 119, 120, 130, 131). |
| 16 | Battle | guess | 17.3 s, ends | 17.6 | ~225 | 53.0 | 3 | 0 | A complete 17.3 s piece that ends on its own (304 notes, then `$FC`). Played in combat: `FUN_000362d6` (`0x367D6`, via `$173EC`) — a combat routine that clears the leader's Power (`+0x1E`) and `+0x06` after a confirm (`$26CCA`), triggered when the `$FF012A` counter reaches 11 in the big combat routine `FUN_0003e2d4`. Fast (~225 BPM), bright, high-pitched (53.0) — a battle fanfare, not a dirge. (The same context was the earlier "Death" candidate; the audio character — fast and bright — decides for Battle. The reverse assignment, Victory = 16, is not ruled out by the bytes, but a 17.3 s piece fits a battle better than a 2 s sting does.) |
| 17 | Quest | guess | 53.0 s | 17.3 | ~246 | 49.4 | 6 | 0* | The alternate map theme: the `$32D0E` picker plays song 17 (instead of song 2) when the leader's `+0x06` is 2 or 3. Fastest song (~246 BPM), high pitch (49.4, p1 floor 36 — no low notes), bright — an energetic, adventurous alternate theme for a specific party state. *Not in the location table; selected by the picker, not by location. "Quest" is the best fit for an adventurous alternate map theme; the name is a guess. |
| 18 | — (no-op) | certain | — | — | — | — | — | — | "Quiet" (music menu). Dispatch word `$0002` → jump to the return. Silent. |
| 19 | — (no-op) | certain | — | — | — | — | — | — | Silent, same as 18. |
| 20 | Victory | guess | 2.0 s, ends | 0 | ~38 | — | 0 | 0 | A 2.0 s sting (0 notes, 1 `$CX` event, ends via `$FC` at offset 4). Played as the arrival jingle (`$1DC90` path when the arrival-type arg is 3) and at battle-end (`0x359A4`, just after battle-end XP/gold `$35600`) and in combat (`0x3AB3C`). The battle-end use is the victory moment — a short victory chime. It is a sting, not a full track, but it is the only song that plays at the victory moment, so it carries the "Victory" name. |

Accounting: 17 fan-site names → 17 songs (1–7, 9–17, 20). Song 0 is silent (not a
track) and song 8 is an unnamed sting; songs 18/19 are no-ops. No name is left
unmapped. The six class names (Wizards/Knights/Archers/Sorceresses/
Necromancers/Enchanters) are the six class-city themes; Enchanters is certain
(the map theme) and the other five are guesses by character. "Guilds" (a
commenter's name, not in the 17) has no song.

### 7.5 How the audio was captured [ROM-only, 2026-11-10]

BlastEm 0.6.3.4 with `SDL_AUDIODRIVER=disk` writes the emulated YM2612+PSG
output to `sdlaudio.raw` (44.1 kHz, 16-bit, stereo) in the working directory.
A plain run of the original ROM only ever plays the game's own song sequence
(boot → intro → map), so each song was forced with a data patch, not a code
hook: the `$173EC` song dispatch table at ROM `0x17546` (21 words, offsets
relative to `$17580`; `$17570` bounds-checks the index < 21, loads
`table[index]`, `jmp $17580+offset`) was patched so every entry holds song
*i*'s offset (entries 18/19 left as `0x0002`, the no-op return, so Quiet
stays silent). Every `$173BC`/`$173EC` song request then plays song *i*, from
the very first (boot) request onward. Checksums fixed with
`tools/checksum.py fix-all`. Builder: `.scratch018/build_song_table.py`;
per-song ROMs `.scratch018/songs/rom_songNN.gen` (not committed). Each ROM
was run ~75 s wall (~155–160 s emulated at ~2.1×) with the Vsync dialog
dismissed by an xdotool clicker; the raw output was converted to
`.scratch018/songs/songNN.wav` (44.1 kHz, 16-bit, stereo).
Batch driver: `.scratch018/capture_all_songs.py`; audio analysis:
`.scratch018/analyze_songs.py` (numpy FFT + onset autocorrelation);
stream parsing: `.scratch018/parse_songs.py`; melody dumps:
`.scratch018/dump_melodies.py`.

Verification that the patch forces the song (not the game's own sequence):
a ROM patched to song 0 (silent) is silent from the first song request
onward — the 50–65 s and 75–155 s windows that are music in the original
run are DC (2 unique sample values) in the patched run — while a ROM
patched to song 1 plays music continuously from ~10 s emulated onward.
An earlier `$D28E` jsr-hook approach was abandoned: its 6-byte `jsr` split
the `clr.w` at `$D292`, so the trampoline's `rts` returned mid-instruction
(`$D294`), and the main loop's world tick calls `$32D0E` → `$173BC(2)` and
would have switched the song back to the map theme anyway. The table patch
forces the song at the dispatch itself, so no re-switch can escape it.
(Builder `.scratch018/build_song_harness.py` is kept for the record.)

Two non-dispatch sounds survive even the song-0 patch (so they do not go
through the `$173EC` table). Precise timing (per-100 ms envelope, not the
5 s RMS windows the first draft used — the "~10 s" there was an
overestimate): **burst 1, ~24.4–28.4 s emulated** — 2.7 s of music, a
~0.4 s gap, then 0.8 s more (fundamental ~250 Hz); **burst 2, ~67.6–71.1 s
emulated** — ~3.5 s of music, continuous, no gap (broader spectrum). They
are present in every capture, including the silent song-0 run. They are
not any of the 19 dispatch songs and do not affect the mapping.

**Burst resolution — burst 1 SOLVED (SFX 94), burst 2 narrowed further
(debugger follow-up, 2026-11-10).** A BlastEm debugger run on the song-0
ROM (`rom_song00.gen`, `.scratch018/burst_log2.py`) broke on every
`$17586` (SFX start) call for 45 s wall (~99 s emulated, audio captured in
the same run to calibrate the wall→emulated ratio: 2.197 for the debugger
run, vs 2.058 for a plain run — the ratio is run-dependent, so hit times
were re-mapped from the same run's audio). **Exactly two `$17586` calls
occur in 99 s emulated: SFX 94 at 17.2 s and SFX 1 at 60.4 s** (indices
read from the stack at `$17586` entry: word at `a7+4`; return addresses
`$0129E2` and `$0150F0`). The audio captured in that same run has events
at 17.3–21.3 s and 60.4–63.9 s — matching the hit times to ~0.1 s. A fresh
plain song-0 capture (`.scratch018/songs/capture_song00b.py`,
`song00b.wav`) reproduces the bursts at 24.5–28.5 s and 67.6–71.1 s: both
shift by the same ~7.2 s between runs (a run-to-run attract-timing
offset), so the debugger run's 17.3 s event is burst 1 and its 60.4 s
event is burst 2.

**Burst 1 is SFX 94 [live].** The 17.3 s event, the plain-run burst 1
(24.5–28.5 s), and the SFX 94 harness capture (`sfx94.wav`, 4.4–8.5 s)
share identical spectral peaks (193, 232, 260–263, 318, 490 Hz, within a
few Hz) and an identical low/high band-energy ratio (0.96). SFX 94 is a
pointer SFX (data at `$4504`, dispatch case `$17626`); its call site is
`$0129DC` in `FUN_0123b0` (attract/title animation: `move.w #$5e,-(a7);
jsr $17586`). It is also the ~37.6–41.6 s event in every SFX-harness
capture — the attract loop calls it there too, which is why it recurs.
Correction: the earlier "ruled out by correlation 0.03–0.07" for SFX 94
was a window/alignment artefact of comparing the 4 s event against the
SFX's loudest 1 s; the full-segment spectral match supersedes it.

**Burst 2 is SFX 1 [live, SOLVED (NOP test, 2026-11-10)].**
Correction: the earlier "burst 2 is not SFX 1" (spectrum/correlation
mismatch) is superseded — the rendering is context-dependent, not a
different sound. A test ROM with the SFX 1 call at `$0150EC` NOP'd
(`jsr $17586(pc)`, 4 bytes `4E BA 24 98` → `NOP NOP`, checksums fixed
via `tools/checksum.py fix-all`) removes burst 2 entirely, while
burst 1 is sample-identical (correlation 1.000, identical peaks
[169.8, 193.2, 232.0, 256.2, 277.5, 317.8, 352.8, 490.2], RMS 0.3791
vs 0.3827) — so NOPing the call did not shift the attract timing at
all. In the NOP'd run the 67.6–71.1 s window is just the background
artifact (RMS 0.1623, 20 Hz harmonic series [50.0, 70.3, 90.6, ...]),
vs the original's burst (RMS 0.3805, peaks 112/153/197/254 Hz); the
RMS envelope 60–75 s is constant 0.1623 in the NOP'd run (no burst)
vs the original's jump to 0.39 at 67–71 s. So the SFX 1 call at
`$0150EC` (`move.w #$1,-(a7); jsr $17586`, return `$0150F0`) is the
necessary and sufficient cause of burst 2. SFX 1 is deterministic
within a context: a fresh harness capture reproduces the old peaks
exactly ([85.0, 282.2, 339.7, 423.9, 454.2, 518.3, 612.5, 764.2]) —
so the rendering difference between the silent-harness and cinematic
contexts is real, not run-to-run variation. Burst 2 and the harness
SFX 1 share some low peaks and have nearly identical band energies
(80–300 Hz: 5.231e+07 vs 5.207e+07; 300–4000 Hz: 2.947e+08 vs
3.146e+08) and a similar envelope (corr 0.465), but differ in
mid/high peak frequencies and have ~0 waveform correlation. The
background (song 1) at burst 2's window is a quiet artifact (RMS
~0.16, 20 Hz harmonic series), not musical notes, so burst 2's peaks
are SFX 1's, not song 1's.

**Mechanism — ROOT CAUSE FOUND [live], pitch translation [open]
(2026-11-10).** SFX 1 renders on a **different FM channel** depending
on song context, because the song occupies FM voices. Decoded path
[static, `.scratch018/z80_listing.txt`]: the SFX block is installed by
`$0A04` into slot 0 (data area `$006C`); per-frame playback `$0B22` →
`$0A78` steps (duration, offset) pairs from the block and writes the
running frequency to the slot (`IX+0x1a/1b`) and to the channel struct
(`IY+0x28/29`, IY from the `$0382` table for channel E); the voice is
allocated by `$067B`, which searches the `$FD` table (16 rows × 5 bytes,
`$FF` = free) for the SFX's note byte, and `$04C3` maps the returned
voice index to an FM channel via table `$EB` (`0→$00, 1→$01, 2→$02,
3→$80, 4→$81, 5→$82`). SFX 1's record (ROM `$FCAF8`) is
`08 09 30 f0 28 ff`: note `$09`, then pairs (48, −16), (40, −1), end —
88 steps. **Live** (slot snapshot harness,
`.scratch018/harness_slotonly.s` + `harness_slotonly_abs.s`,
`run_bonly_sonly_out.txt`, `run_s1f_out.txt`, `run_cs_out.txt`;
absolute-address Z80 reads — see harness caveat below): SFX 1 is
installed and playing in both contexts (`$003A=$08, $003B=$09,
$003D=$F0, $000C=$00`, slot0 data `$08/$09`, duration `$1C`, offset
`$FF` at 60 frames), and its frequency state is **identical** — slot
freq `$0930` at 60 frames, `$0C2C` at 1 frame; channel-struct freq
(`$12E4+0x28/29`) `$043C`; `$00A6` `$120C` — in both contexts. The
**base-frequency hypothesis is ruled out**: the pre-trigger base
(`$00A6` channel freq) differs (`$4DED` silent vs `$1DA7` song 1,
ratio 3.8×), but the install-time base is `$0C3C` (note 9) in **both**
runs (slot freq at 1 frame + 1 offset), i.e. SFX 1's own note byte
`$09` sets the base, not the song's last note. **What differs is the
voice allocation [live]:** the `$FD` row for channel E=`$0E`
(`$0143–$0147`) holds SFX 1's note `$09` at **index 0** when silent
(`09 FF FF FF FF`) but at **index 2** when song 1 plays
(`FF FF 09 FF FF`) — song 1 occupies voices 0–1, so SFX 1 is pushed
to voice 2. Via `$EB`, that is **FM channel 0 (silent) vs FM channel 2
(song 1)**. So the context-dependent step is the voice/channel
allocation, not the SFX's frequency computation. **PSG ruled out
[static]:** every PSG (`$7F11`) write is in `$0967–$09AA`, called
only from the song loop (`$0915`); the SFX path (`$0B22`/`$0A78`)
never writes the PSG — SFX 1 is FM-only, so the earlier "PSG voice
only, FM suppressed" hypothesis is dead, not just weakened. **Still
[open]:** the exact pitch translation — how sounding on FM ch 2 vs
ch 0 moves the heard peaks from 282–612 Hz to 112–254 Hz (candidates:
the song's own notes on ch 2 overwriting the SFX's frequency
registers between SFX steps, or a per-channel operator setup
difference). What would settle it: a Z80-side trace of the YM2612
register writes (F-number `$A0–$A6`, key `$28`) for SFX 1 in both
contexts. Also [open]: the 88-step data stream predicts ~1.5 s but
SFX 1 sounds ~3.6 s (step rate or release decay). Harness caveat:
multi-byte `(a0)+` Z80 dumps return an identical byte pattern for
different addresses (unreliable — the `$22/$EE/$BB` pattern is not in
`driver.bin`); all voice-row/channel-struct numbers above are from
**absolute-address** reads, which a single-read sanity check
(`$003A` → `$08`) confirms. See §12 item 12.
items 11–12.

All 19 captures are in `.scratch018/songs/songNN.wav` (not committed; the
`.wav` files are the deliverable audio). The original ROM was re-verified
unchanged after all work (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## 8. The SFX map [static]

### 8.1 Table SFX: `$FCAE2`, 22-byte records, indices 0–61

The table region holds 62 slots (indices 0–61, `$FCAE2–$FD036`, 62 × 22 = 1364 bytes); only indices
0–38 are ever called (see the call-site table below). Past that: indices
62–63 read a 16-bit increasing table at `$FD036` (values `0x023C–0x065E`),
not SFX data; index 64 is zeros; index 65 straddles the runtime-checksum
routine at `$FD07C`; indices 66–68 read the checksum code itself; indices
69–89 read the `0xFF` padding. (An earlier draft said 69 records were real
— that was a scan that counted the checksum-code bytes as records.)
The 68k copies 23 bytes per delivery (1-byte overread into the next record).
Records are mostly zeros after the first 4–6 bytes, e.g. SFX 0:
`14 0c 0a 80 00…`, SFX 1: `08 09 30 f0 28 ff 00…`. The per-byte meaning of
the 22-byte record is **[open]** — `$0A04` reads bytes 0, 1 and 3 of the block
and a slot byte at `$0051`, and calls `$09E0`/`$09ED`/`$09FA`; the full voice
installation (`$067B`/`$0558`/`$0515`/`$052E` FM routines) was not traced to
the per-byte level.

Static call-site counts for `$17586` (immediate index args; 91 sites, plus 7
sites with a computed index):

| SFX | Sites | SFX | Sites | SFX | Sites |
|---|---|---|---|---|---|
| 1 | 7 | 15 | 6 | 26 | 2 |
| 3 | 2 | 17 | 2 | 27 | 1 |
| 9 | 1 | 19 | 5 | 28 | 3 |
| 10 | 4 | 20 | 7 | 30 | 1 |
| 11 | 2 | 21 | 5 | 31 | 4 |
| 12 | 4 | 24 | 2 | 32 | 10 |
| 13 | 1 | 25 | 2 | 33 | 4 |
| 14 | 1 | | | 36 | 1 |
| | | | | 38 | 1 |

SFX 32 (10 sites) and SFX 1 / 20 (7 each) are the most-used table sounds.
The second argument to `$17586` is `$FFFF` at **all 98 call sites** (91
immediate-index sites + 7 computed-index sites, verified by re-scanning the
listing) — so every pointer-SFX goes through `$EB968` (`$000A=$FF`); the
`$EB93E` branch for a non-`$FFFF` parameter is never taken.

### 8.2 Pointer SFX: indices 90–96

See the table in §4.3. 11 of the 91 immediate call sites use indices 90–96
(91: 5 sites, 95: 3, 92/94/96: 1 each). These bypass the `$FCAE2` table
entirely and point the Z80 at ROM data via the bank window (§4.3).

### 8.3 The two SFX slots

`$17586` alternates successive table-SFX calls between slot 6 (`$EBAF4`,
Z80 `$000C=6`, voice slot 0) and slot 7 (`$EBAFA`, `$000C=7`, voice slot 1)
using `$FF0088`. The Z80 installs each block into the corresponding slot's
voice structure (pointers at `$0068–$006B`, state at `$0051–$0055`) and the
per-tick routine `$0B22` services both slots (envelope/decay via `$0A78`).
Two SFX can therefore overlap; a third while both slots are busy is queued
in `$FF0236`/`$FF023A` and retried next frame.

### 8.4 Top table SFX by context [static + live, 2026-11-10]

The most-called table SFX, identified by which routines call `$17586`
with that index (routine names from `disasm/ghidra/functions.txt`). Audio
was captured for this addendum (harness below) — the "Audio" column gives
the measured duration and fundamental, plus a plain-language character
guess from the spectrum; the guess is labelled as such, and the call-site
context (the "Where it plays" column) is the certain identification. The
per-byte record semantics are still open (§12 item 3). First 8 record
bytes are from ROM `$FCAE2 + index*22`.

Audio capture method (`.scratch018/sfx/`): a 68k harness hooked at the
attract loop `0x35C` starts silent song 0 via `$173BC` (driver upload),
calls `$17586(i, $FFFF)`, then waits 360 VBlank frames calling `$EB772`
once per frame — the tempo clock the SFX voice needs, since `$0B22` only
services a voice when the tempo byte `$00E6` advances. One ROM per SFX
(`rom_sfxNN.gen`, checksums fixed); BlastEm `SDL_AUDIODRIVER=disk`,
~60 s emulated per capture, audio in `sfxNN.wav` (NOT committed).
Harness: `harness_sfx.s`, `build_sfx.py`, `capture_sfx.py`,
`analyze_sfx.py`, `run_one.py`. All onsets are ~4.4 s emulated (boot +
song-0 start + `$17586` call); durations are the sounding window.

| SFX | Sites | Record (first 8 B) | Where it plays (context) | Audio (harness capture) |
|---|---|---|---|---|
| 32 | 10 | `01 0c 0a 80 0a 7f 09 80` | The ubiquitous action sound. 7 sites in the big combat routine `FUN_0003e2d4` (`$3E2D4–$42E33`), plus command 50 (`FUN_0002619c`, character move/place — reads struct `+0x06`/`+0x0C`/`+0x0E`), the XP/resource routine `FUN_0002dcce`, and combat `FUN_0003a62e`. Most-used SFX; a general action/confirm/hit sound used for movement and combat actions. | 3.5 s (4.4–7.9 s), fundamental ~110–162 Hz, swells to a late peak (6.4 s). [live] A low, swelling thud/boom — character is a guess from the spectrum. |
| 1 | 7 | `08 09 30 f0 28 ff 00 00` | Intro/story (`FUN_00015012`), the song-11 routine `FUN_00017b88` (3 sites), `FUN_00024984`, and the XP routine `FUN_0002dcce`. A transition/UI sound. | 3.6 s (4.4–8.0 s), fundamental 272 Hz with harmonics at 740/806/1116 Hz. [live] A bright multi-tone chime — character is a guess. |
| 20 | 7 | `00 1c 14 c0 00 00 00 00` | The location-change/arrival chime. 4 sites in the world tick `FUN_0002155e`, each right after the song picker `$32D0E` → `$173BC` (i.e. right after the map song switches on entering a new location) — twice in a row at `0x21A84`/`0x21A94` (a doubled chime) — plus the main loop `FUN_0000d28e` and combat `FUN_0003e2d4`. Short (4 non-zero record bytes). | 2.8 s (4.4–7.2 s), fundamental ~120–126 Hz (tight, single low tone), clean decay. [live] A deep, low bell/chime — the arrival context is certain by call site; "bell" is a guess from the spectrum. |
| 15 | 6 | `18 2c 28 05 28 fb 28 05` | XP routine `FUN_0002dcce`, combat `FUN_0003e2d4` (2 sites), and the spell routines `FUN_00038fb8` / `FUN_00039172` / `FUN_000393fa` (`$38xxx–$39xxx` spell area). A spell/XP sound. | 9.6 s (4.4–14.0 s) — the longest table SFX captured — fundamental 384–482 Hz, peak mid-way (7.2 s). [live] A long, sustained mid-range shimmer — character is a guess. |
| 19 | 5 | `14 0c 14 c0 00 00 00 00` | XP routine, `FUN_00032284`, combat `FUN_0003a62e` / `FUN_0003d9f8` / `FUN_0003e2d4`. A combat/XP sound. Short (4 non-zero bytes). | 1.3 s (4.4–5.7 s), bright (296/560/988/1030 Hz). [live] A short, sharp high zap/ping — character is a guess. |
| 21 | 5 | `14 0c 14 c0 14 40 14 c0` | Combat: `FUN_0003d9f8` and `FUN_0003e2d4` (4 sites). A combat sound; the record repeats (`14 c0` twice), a longer effect. | 3.4 s (4.4–7.8 s), spectrum identical to SFX 19 (296/560/988/1030 Hz). [live] The same bright zap as 19, extended/repeated — the spectral identity is measured; the "same sound" reading follows from it and the repeated record. |
| 33 | 4 | `05 0c ff 00 00 00 00 00` | Combat: `FUN_0003d9f8` and `FUN_0003e2d4` (3 sites). A combat sound; very short (3 non-zero bytes). | 10.6 s (4.5–15.1 s) — the longest captured — fundamental 260–602 Hz, builds to a late peak (12.5 s). [live] A long, swelling effect, despite the 3-byte record — character is a guess. The record length does not predict the sounding length. |

Also captured for the burst investigation (§7.5). SFX 94 is burst 1 (see
§7.5); the others are ruled out as the burst source by spectrum and
lagged cross-correlation (0.03–0.07, no match) — except that the earlier
0.03–0.07 figure for SFX 94 was a window/alignment artefact, superseded
by the §7.5 spectral match:

| SFX | Sites | Audio (harness capture) |
|---|---|---|
| 17 | 2 (intro picture loop `0x015A44`, main loop `0x00D606`) | 6.6 s (4.4–11.0 s), fundamental 1818/3638 Hz — the highest-pitched SFX captured, a high whistle/sparkle (guess). |
| 91 | 5 (pointer SFX, `$1394`) | 4.4 s (4.4–8.8 s), fundamental 146–294 Hz, a mid-range tone (guess); plus a single ~0.1 s low blip at ~26.2 s emulated (102–108 Hz), a delayed pulse in the pointer data of unknown origin. |
| 92 | 1 (pointer SFX) | 1.2 s (4.4–5.6 s), fundamental 108–432 Hz, a short low blip (guess); plus the same ~26 s delayed pulse as 91/95. |
| 94 | 1 (pointer SFX, `$4504`) | 4.1 s (4.4–8.5 s), fundamental 230–252 Hz, a mid-low tone (guess). **This is burst 1 (§7.5)** — the attract/title sound, called from `FUN_0123b0` at `$0129DC`; it is also the ~37.6–41.6 s event in every SFX-harness capture. |
| 95 | 3 (pointer SFX, `$9A60`) | 3.5 s (4.4–7.9 s), fundamental ~106–136 Hz, a low tone (guess); plus the same ~26 s delayed pulse as 91/92. |

## 9. Boot sequence for sound [static + live]

1. Reset (`$200`): TMSS, VDP setup, checksum, save check, display ON. **No
   driver upload, no sound tick.** Interrupts masked (`SR=$2700`).
2. Attract loop (`0x35C`): VBlank-spin on `$C00004` bit 3, title animation.
   Z80 RAM holds no driver **[live]**; `$FF0010`/`$FF0220`/`$FF0234` do not
   advance (the VBlank handler never runs while interrupts are masked).
3. Attract exit → `0x1200`: RAM clear, `MANX` magic at `$FF000C+4`,
   `jsr $EB806` (driver upload, `0x1260`), `SR=$2000` (level-6 VBlank
   interrupts on), `jmp $D25C`.
4. `$D25C`: `$11E06` (song 0 via `$173BC` at `0x11F2C`), `$14FB6` (song 1),
   `$1B5D6` (new-game init), `$32D0E` → `$173BC` (song 2 or 17), then the
   `$D28E` main loop. From here the VBlank handler calls `$EB772` every
   frame and the watchdog (`0x21608`) replays the current song when it ends.

## 10. Live verification (BlastEm)

Two runs, both with the original ROM unless noted:

**Run 1 — original ROM, debugger breakpoints** (`.scratch018/live018.py`):
broke at the first `$EB88A` (song start) and at `$EB772` (sound tick).
- Boot song is index 0: `$FF012E=0`, `$FF022C=$0ED0E8`, `$FF0230=$0ED5E8`.
- Tempo accumulator `$FF0234`: `$2100 → $2200` across two consecutive
  `$EB772` hits (`+$100`/frame, NTSC); frame counter `$FF0220`: `33 → 34`.
- **Negative result that matters:** direct debugger reads of Z80 RAM
  (`p/x $A00000` etc.) return stale/garbage values (`0x5858`, `0x4E`,
  `0xB0`, tempo not incrementing) — the debugger reads the 68k bus without
  requesting the Z80 bus, so Z80 RAM must be read through the bus discipline
  (or a harness), never directly from the debugger. All Z80 RAM claims in
  this document come from the harness in run 2, not from debugger reads.

**Run 2 — snapshot harness** (`.scratch018/harness018.s` v2, `test018.gen`,
`.scratch018/run018.py`): hooked at the attract loop `0x35C`
(`jsr $FD0CC.l`, 6 bytes replacing `move.w $C00004,d1`, return `0x362`),
ran once, `rts` exit. Results (27 of 28 slots match prediction; see §12
for the one systematic exception, which is itself a finding):

| Slot | Value | Expect | Result |
|---|---|---|---|
| Z80 `$0000`/`$0002`/`$0004` pre-song | `0xE141` | `0x21FF`/`0xF9C3`/`0x7D01` | **driver absent** (see §9 step 2) |
| Z80 `$00DA` pre-song | `0x3A` | `0x53` ('S') | **driver absent** |
| Z80 `$00E6` pre-song | `0x3A` | `0x8F` | **driver absent** (and `$00E6`'s true init is `0x00`, §2.4) |
| Z80 `$000B`/`$000A` pre-song | `0xC0`/`0x3A` | `0x00` | **driver absent** (uninitialised RAM) |
| Z80 `$000A` post-song | `0x00` | `0x00` | ✅ |
| Z80 `$000B` post-song | `0x0D` | `0x0D` | ✅ |
| Z80 `$000C` post-song | `0x00` | `0x00` | ✅ |
| Z80 `$00DA` post-song | `0x16` | `0x16` | ✅ |
| Z80 `$1600`/`$1602`/`$1604` post-song | `0x00C1`/`0x0678`/`0xC106` | same | ✅ song 0's bytes streamed |
| `$FF022C` / `$FF0230` | `$0ED0E8` / `$0ED5E8` | same | ✅ |
| `$FF012E` / `$FF021E` | `0` / `$FF16` | same | ✅ |
| Z80 `$000B` / `$00DA` 30 frames later | `0x0D` / `0x16` | same | ✅ song still playing, chunk 0 |
| `$FF012E` 30 frames later | `0` | 0 | ✅ |
| `$FF0220` / `$FF0234` / `$FF0010` 30 frames later | `0` / `0` / `0` | advancing | ❌ — **expected in the attract context**: the VBlank handler does not run there (§9 step 2), so no tick advanced the counters. The tempo advance itself was verified in run 1 (game context). |

Harness lessons (also worth recording for future harnesses): (a) saving SR
inside a `bsr`'d helper makes `rts` pop the SR value as the return address —
the v1 harness froze BlastEm at `$DFFFFE` for exactly this reason; SR
save/restore belongs in the caller, like the game's `$EB92A` callers do.
(b) 68k word reads from the 8-bit Z80 RAM area return `(byte0, byte0)` in
BlastEm — read bytes and assemble words. (c) A bus request needs a short
settle delay before the first read, or the read returns stale bus data.

## 11. Tooling

- **Ghidra 11.4.2 headless Z80 analysis works.** The tooling gap in the issue
  is closed for disassembly: `tools/ghidra/ghidra_11.4.2_PUBLIC/support/analyzeHeadless`
  with `-processor z80:LE:16:default` (lowercase `z80` — the language ID is
  case-sensitive; `-processor Z80` and `-language` both fail), `-loader
  BinaryLoader -loader-baseAddr 0x0`, project directory must pre-exist.
  The driver blob (`.scratch018/driver.bin`, ROM `0xEBB6E–0xED0E4`) imports as
  a raw binary at base 0; a linear disassembly post-script
  (`.scratch018/DumpZ80.py`) dumped 1067 instructions
  (`.scratch018/z80_listing.txt`). Ghidra project in
  `.scratch018/ghidra-proj/` (not committed).
- **Capstone has no Z80 backend** — Ghidra is the Z80 disassembler for this
  project. The 68000 side was done with Capstone 5.0.9 (`tools/.venv`).
- **vasm was not needed.** `tools/install_vasm.sh` builds a Z80 assembler
  (`vasmz80_oldstyle`) but no Z80 test code was assembled for this issue —
  the 68k harness sufficed. The script remains the path if a Z80 harness is
  ever needed.
- **BlastEm debugger limits (established here):** direct `p/x` reads of Z80
  RAM (`$A00000–$A01FFF`) are unreliable (no bus request); 68k RAM reads are
  fine. Z80 state must be snapshotted to 68k RAM by a harness and read back
  from there.

## 12. Open items

1. **Track→index mapping — DONE (ROM-only), 2026-11-10.** Mapped in §7.4
   using only the ROM (Dayset's call: no MP3s — "we have ROM with all the
   music and sfx in it"). Method: code context (location table §7.3,
   `$32D0E` picker, all `$173BC`/`$173EC` call sites) + parsed song streams
   + one BlastEm audio capture per song via a dispatch-table patch
   (§7.5). Result: 17 names → 17 songs (1–7, 9–17, 20); song 0 is silent,
   song 8 is an unnamed sting, 18/19 are no-ops. Certain: song 0 (silent),
   song 2 (Enchanters), 18/19. Strong: song 1 (Main theme), song 8
   (unnamed sting). The rest are guesses by character/context — a live
   playthrough that drives the game to each named place would upgrade them,
   and the class/place assignments in particular rest on audio character
   (the location-id → city-name mapping is not recoverable from the ROM).
   The MP3 path is closed by Dayset's call and is not to be revived.
2. **`0x0E0000–0x0EB771` identity.** The L011 "song/SFX data" label is
   disproven (songs are at `$ED0E8+`, SFX at `$FCAE2`). What that range
   actually holds is still unknown.
3. **SFX record byte semantics.** The 22-byte `$FCAE2` records' per-byte
   meaning (beyond bytes 0/1/3, which `$0A04` reads) needs the FM voice
   routines (`$067B`/`$0558`/`$0515`/`$052E`/`$09E0`/`$09ED`/`$09FA`) traced
   to the per-byte level. Same for the song `$8X`/`$9X` parameter bytes'
   musical meaning and the `$079E` (`$00DB`) path.
4. **Z80 `$000B=$12` purpose** (`$EB986`/`$EB9A0`). Both routines are dead
   code — no callers anywhere in the ROM — so the `$12` write is unreachable
   and its intended purpose cannot be determined from the shipped game. (An
   earlier draft of this document listed it as an open live question; the
   re-check against the listing showed the routines are uncalled.)
5. **Z80 `$00E4` / `$0967`.** The song player calls `$0967` when `$00E4` is
   nonzero; that routine was not traced.
6. **The `$00E7` running-status path** (§6): the exact stream shape that
   triggers a re-dispatch of the last event byte is not pinned down.
7. **Leader `+0x06` semantics** (`$32D0E`): the field that selects song 17
   vs song 2 is read but its meaning (character type? role?) is not
   established.
8. **Z80 `$00E6` advance, direct observation.** Verified on the 68k side
   (`$FF0234 += $100`/frame, run 1) and by the `$EB772` code path, but not
   read back from Z80 RAM in the game context — the snapshot harness ran in
   the attract context, where the VBlank handler (and hence the tick) does
   not run. A game-context harness (e.g. hooked at `$EB772`'s call site
   `0x12F2`) could close this.
9. **PSG — CONFIRMED USED, 2026-11-10.** The earlier "no PSG writes were
   found / unconfirmed" is wrong. `$0967` writes to the PSG port `$7F11`
   (values `$81`, `$00`, `$A1`, `$00`); it is called from the song-player
   loop `$08F8` when `$00E4` is nonzero, and `$00E4` is set by `$070D`
   (the pointer-SFX data path). So the PSG IS used — for pointer-SFX
   (indices 90–96), not for the table songs. The PSG's musical role
   (which pointer-SFX use it, and what the `$81`/`$A1` writes do) is still
   open, but the "does the game use the PSG at all" question is closed:
   yes.
10. **`$EB93E` is unreachable in practice.** The non-`$FFFF` parameter branch
    in `$17586` is never taken — all 98 call sites pass `$FFFF` — so every
    pointer-SFX in the game goes through `$EB968` (`$000A=$FF`). `$EB93E`
    itself is only reachable via that dead branch. (An earlier draft of this
    document listed `$EB9EE` as having no callers; the re-check found 4 —
    see §3.1 — so that claim was corrected here, not carried forward.)
11. **SFX audio capture — DONE, 2026-11-10.** The 7 most-used table SFX
    (32, 1, 20, 15, 19, 21, 33) plus SFX 17 and pointer SFX 91/92/94/95
    were captured as audio (§8.4) with a 68k harness
    (`.scratch018/sfx/harness_sfx.s`: `$35C` hook, `$173BC` song-0 start,
    `$17586(i, $FFFF)`, 360-frame wait calling `$EB772` once per frame as
    the tempo clock). Durations and fundamentals are measured; the
    plain-language character per SFX is a spectral guess, labelled as
    such. Two findings worth keeping: SFX 21's spectrum is identical to
    SFX 19's (the same bright zap, extended — consistent with its repeated
    record), and SFX 33 sounds for 10.6 s despite a 3-byte record, so
    record length does not predict sounding length. Pointer SFX 91/92/95
    each carry a single ~0.1 s low delayed pulse at ~26 s emulated, of
    unknown origin. Captures: `.scratch018/sfx/sfxNN.wav` (NOT committed).
12. **The two non-dispatch bursts — BOTH SOLVED, 2026-11-10.** Burst 1
    (~24.4–28.4 s emulated in a song-0 capture: 2.7 s + ~0.4 s gap +
    0.8 s, ~250 Hz) is **SFX 94** (pointer SFX, data `$4504`, called
    from `FUN_0123b0` at `$0129DC`): a BlastEm breakpoint on `$17586`
    logs exactly two calls in 99 s emulated — SFX 94 at 17.2 s, SFX 1
    at 60.4 s — with audio events at 17.3 s and 60.4 s in the same run,
    and the SFX 94 harness capture shares burst 1's spectral peaks
    (193/232/260–263/318/490 Hz) and band ratio (0.96). It is also the
    ~37.6–41.6 s event in every SFX-harness capture. Burst 2
    (~67.6–71.1 s, ~3.5 s continuous) is **SFX 1** [live, NOP test]:
    a test ROM with the SFX 1 call at `$0150EC` NOP'd (`jsr
    $17586(pc)` → `NOP NOP`, checksums fixed) removes burst 2
    entirely while burst 1 is sample-identical (corr 1.000) — the
    SFX 1 call is the necessary and sufficient cause. The earlier
    "burst 2 is not SFX 1" (spectrum/correlation mismatch) is
    superseded: SFX 1 is deterministic within a context (a fresh
    harness capture reproduces the old peaks exactly), but renders
    with different pitches in the cinematic (song 1 playing) context
    than in the silent harness — context-dependent voicing. Burst 2
    and the harness SFX 1 share some low peaks and have nearly
    identical band energies, but differ in mid/high peaks with ~0
    waveform correlation. Ruled out as burst sources: a direct
    `$EB88A` call (all 19 sites are inside the `$173EC` dispatch),
    song 0's hidden note data (parser takes 686 s to reach the `$FC
    $80` seek; a test ROM with the 248 B zeroed still plays the
    event), the 31 uncaptured table SFX (`$17586` is the only SFX
    path, and the breakpoint log is exhaustive), and the
    variable-index `$17586` at `0x01837E` (never fires in the
    attract/cinematic context). **Mechanism — root cause found
    [live], pitch translation [open] (2026-11-10):** SFX 1's note
    `$09` is allocated a different FM voice by song context: the
    `$FD` voice-table row for channel E=`$0E` (`$0143–$0147`) holds
    `$09` at index 0 when silent (`09 FF FF FF FF`) but at index 2
    when song 1 plays (`FF FF 09 FF FF`); via the `$EB` map that is
    **FM channel 0 vs FM channel 2**. The SFX's frequency state is
    identical in both contexts (slot freq `$0930` at 60 frames,
    `$0C2C` at 1 frame; channel-struct freq `$043C`; `$00A6`
    `$120C`), so the base-frequency hypothesis is ruled out (the
    install-time base is `$0C3C`, note 9, in both — SFX 1's own note
    byte sets it). PSG is ruled out [static] (all `$7F11` writes are
    in `$0967–$09AA`, song loop only; SFX 1 is FM-only). Still
    [open]: how ch 2 vs ch 0 moves the heard peaks (282–612 Hz →
    112–254 Hz) — candidates: the song's notes on ch 2 overwriting
    the SFX's frequency registers, or a per-channel operator
    difference; a YM2612 write trace for SFX 1 in both contexts
    would settle it. Also [open]: 88 data steps (~1.5 s) vs ~3.6 s
    audible. See §7.5.

## Appendix: files

- This document: `docs/sound.md`
- Z80 listing: `.scratch018/z80_listing.txt` (1067 instructions, Ghidra Z80)
- Driver blob: `.scratch018/driver.bin` (ROM `0xEBB6E–0xED0E4`)
- Harness: `.scratch018/harness018.s` (v2), test ROM `.scratch018/test018.gen`
  (original ROM + harness, checksums fixed; original untouched)
- Drivers: `.scratch018/live018.py` (original-ROM breakpoint run),
  `.scratch018/run018.py` (harness run), outputs `live018_out.txt` /
  `run018_out.txt`
- Ghidra project: `.scratch018/ghidra-proj/` (headless Z80, not committed)
- Song-mapping addendum (2026-11-10, ROM-only): `.scratch018/parse_songs.py`
  (stream parser + fingerprints), `.scratch018/dump_melodies.py` (per-channel
  note sequences), `.scratch018/build_song_table.py` (dispatch-table patch —
  the method used), `.scratch018/build_song_harness.py` (abandoned `$D28E`
  jsr-hook approach, kept for the record), `.scratch018/capture_all_songs.py`
  (BlastEm `SDL_AUDIODRIVER=disk` batch capture),
  `.scratch018/analyze_songs.py` (numpy FFT + onset-autocorrelation
  character analysis). Per-song audio: `.scratch018/songs/songNN.wav`
  (44.1 kHz, 16-bit, stereo; NN = 00–17, 20; ~159 s emulated each; NOT
  committed). Per-song patched ROMs: `.scratch018/songs/rom_songNN.gen`
  (dispatch table patched to song NN; NOT committed). Capture log:
  `.scratch018/songs/capture.log`.
- SFX/burst follow-up (2026-11-10): `.scratch018/sfx/harness_sfx.s`
  (68k harness: `$35C` hook, `$173BC` song-0 start, `$17586(i, $FFFF)`,
  360-frame wait calling `$EB772` per frame),
  `.scratch018/sfx/build_sfx.py` (per-SFX ROM builder),
  `.scratch018/sfx/capture_sfx.py` (BlastEm batch capture),
  `.scratch018/sfx/run_one.py` (single-ROM capture),
  `.scratch018/sfx/analyze_sfx.py` (per-100 ms envelope + spectrum).
- Burst debugger follow-up (2026-11-10): `.scratch018/burst_log.py`
  (breakpoint on `$17586`, first run), `.scratch018/burst_log2.py`
  (breakpoint on `$17586` + same-run audio for ratio calibration —
  **burst 1 = SFX 94**), `.scratch018/burst_log3.py` (breakpoint on
  `$173EC` — no song start at burst 2's time),
  `.scratch018/songs/capture_song00b.py` (fresh song-0 capture,
  `song00b.wav`, ratio 2.058), `.scratch018/correlate_bursts.py`,
  `.scratch018/correlate_bursts2.py`, `.scratch018/correlate_bursts3.py`,
  `.scratch018/compare_sfx32.py`, `.scratch018/check_sfx1_psg.py`
  (segment spectra + correlations). Logs: `.scratch018/burst_log_out.txt`,
  `.scratch018/burst_log2_out.txt`, `.scratch018/burst_log3_out.txt`;
  audio: `.scratch018/raw_burstlog.raw`, `.scratch018/raw_burstlog3.raw`
  (NOT committed).
- Burst 2 NOP test (2026-11-10, **burst 2 = SFX 1**):
  `.scratch018/rom_nosfx1.gen` (song-0 ROM with the SFX 1 call at
  `$0150EC` NOP'd, checksums fixed; original untouched),
  `.scratch018/capture_rom.py` (plain-run capture, any ROM),
  `.scratch018/songs/song00_nosfx1.wav` (patched run — burst 2 gone,
  burst 1 sample-identical), `.scratch018/burst2_compare.py` (RMS /
  spectra / correlation vs `song00b.wav`),
  `.scratch018/burst2_analyze.py` (RMS envelope + sliding correlation
  vs song 1), `.scratch018/burst2_bg.py` (background artifact analysis),
  `.scratch018/sfx/sfx01_fresh1.wav` (fresh SFX 1 harness re-capture —
  reproduces the old peaks exactly, so SFX 1 is deterministic in
  context). Audio NOT committed.
  Per-SFX audio: `.scratch018/sfx/sfxNN.wav` (NN = 01, 15, 17, 19, 20,
  21, 32, 33, 91, 92, 94, 95; ~60 s emulated each; NOT committed).
  Per-SFX ROMs: `.scratch018/sfx/rom_sfxNN.gen` (NOT committed).
  Burst test ROM: `.scratch018/sfx/rom_testA_zeronote.gen` (song 0's
  248 B note-data region zeroed; the 37–42 s event survives — Test A).
