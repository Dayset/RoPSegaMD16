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
  code region); SFX records live at **`$FCAE2`** (69 records × 22 bytes).
  What `0x0E0000–0x0EB771` actually is remains open (§12) — it is not music.
- **The 68000 streams song data to the Z80** through a 1 KB ring buffer at Z80
  `$1600–$1A00`, refilling 256-byte chunks whenever the Z80's chunk byte at
  `$00DA` changes. The song player on the Z80 is a blocking loop: while a song
  plays, the Z80 does nothing else except service SFX commands once per tempo
  tick.
- **19 playable songs** (indices 0–17 and 20) plus two silent indices (18, 19).
  Index 18 is the music menu's "Quiet". Index 20 is a 10-byte one-shot arrival
  jingle that shares its tail with song 2.
- **69 SFX records** (indices 0–68) in a 22-byte table at `$FCAE2`, delivered as
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
are other location fields). For location ids 0–63 the nibbles are mostly 2
(the map theme), with 4, 3, 5, 9, 10, 11, 12, 13 for specific ids (see
`.scratch018` notes: ids 12, 20, 35–37, 39, 58–63 → 4; 32–34, 40–41, 48, 53,
55–56 → 10; 43, 45, 49, 50 → 9; 45 → 5; 46 → 12; 47, 50 → 13; 52 → 3;
54 → 11). If the arrival-type argument (`$8(a6)`) is 3, the handler instead
plays song 20 directly via `$173EC` (the arrival jingle) **and** writes the
table song into `$FF012E`, so the watchdog loops the location song after the
jingle ends. Otherwise it plays the table song via `$173BC`.

### 7.4 The 17 named tracks [open mapping]

The rings-of-power.ru soundtrack page lists 17 named tracks: Main theme
(Rings theme), Wizards, Knights, Archers, Sorceresses, Necromancers,
Enchanters (also the map theme), Battle, Castle, Death, Nexus, Quest, At sea,
Someone's home, Tavern, Victory, On the street. (A commenter also names
"Guilds", which is not in the list.) The ROM has 19 playable song slots, so
at least two songs have no fan-site name. **No track→index mapping is
established by the bytes.** Plausible anchors only: song 2 is the map theme
("Enchanters" — it is the default/location song almost everywhere); the six
class names (Wizards/Knights/Archers/Sorceresses/Necromancers/Enchanters)
suggest six class/location themes among the slots; song 8 (stream 256 B,
content ends at offset ~103) and song 20 (6 parsed bytes) are too short to
be full tracks (jingles/stings). The `$32D0E` picker (song 17 vs 2, by leader
`+0x06`) is the one place a character-linked theme is selected in code. Identifying tracks by ear against
the fan-site MP3s is the remaining work (§12).

## 8. The SFX map [static]

### 8.1 Table SFX: `$FCAE2`, 22-byte records, indices 0–89

The table region holds 62 slots (indices 0–61, `$FCAE2–$FD036`); only indices
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

1. **Track→index mapping.** The 17 fan-site track names (§7.4) are not
   mapped to song indices by any bytes in the ROM. Next step: identify by
   ear against the fan-site MP3s (only the main theme is downloaded locally,
   `docs/research/rings-of-power-ru/Rings-main-theme.mp3`, 102 s), or by
   driving the game to each location/situation and noting the song. Song 2
   = map theme ("Enchanters") is the only anchored guess.
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
9. **PSG.** The driver as traced writes only YM2612 registers (`$4000–$4003`
   via `$01B4`/`$01BA`/`$04B7`/`$04BD`). No PSG (`$7F11`) writes were found
   in the disassembled code — whether the game ever uses the PSG is
   unconfirmed (the `$01C0`/`$01E1` DAC setup suggests PCM-ish SFX via the
   YM DAC, `$2B=$80`).
10. **`$EB93E` is unreachable in practice.** The non-`$FFFF` parameter branch
    in `$17586` is never taken — all 98 call sites pass `$FFFF` — so every
    pointer-SFX in the game goes through `$EB968` (`$000A=$FF`). `$EB93E`
    itself is only reachable via that dead branch. (An earlier draft of this
    document listed `$EB9EE` as having no callers; the re-check found 4 —
    see §3.1 — so that claim was corrected here, not carried forward.)

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
