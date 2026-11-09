# Music-off patch — Rings of Power (Mega Drive)

Makes the in-game Music menu's **"Quiet"** choice actually silence the music,
and keeps it silent across location/screen changes.

## The bug (player report, 2026-11-09)

> «Пожалуйста сделайте патч\рабочую_Опцию для отключения музыки. Если музыку
> отключить в игре то при смене локации\экрана она автоматом включается.
> При продолжительной игре очень раздражает.»
>
> "Please make a patch / a working option to turn off the music. If you turn
> the music off in the game, when the location/screen changes it automatically
> turns back on. Very irritating in long sessions."

## Cause (verified by disassembly + debugger)

All addresses are 68000 ROM offsets (= file offsets). RAM variables are
`$FFxxxx`.

### The sound engine has no working "music off"

- `$FF021E` is the sound-on flag: `1` = sound on, `0` = off. The music
  streamer `$EBA00` does nothing while it is `0`, and streams 255-byte
  chunks of the current song to the Z80 while it is `1` (the streamer loops
  the song data itself: source `$FF0224` wraps to song start `$FF022C` at
  song end `$FF0230`).
- `$EB7C8` (stop-sound: clears `$FF021E`, resets the Z80) is **dead code in
  the original ROM — it has zero callers** (byte search for
  `jsr $EB7C8.l` finds nothing; no `bsr`/`jsr (pc)` reference either). The
  game never turns sound off by itself.
- `$FF012E` is the current-song index (word; `0xFFFF` = "no song yet" at
  boot). `$EB88A` (start-song, arg = song data pointer) unconditionally
  sets `$FF021E = 1` at `0xEB8D8` and writes `$0D` to the Z80 request byte
  `$A0000B`. It is only called from the 19 dispatch blocks inside `$173EC`.
- `$173BC` (request-song) plays the requested index whenever it differs from
  `$FF012E`, and replays it when the status check `$EB9C4` returns 0.
  `$EB9C4` returns 0 iff `$FF021E == 0` or the Z80 request byte is 0.
  There is **no music-off flag anywhere in this path** — a location change
  always (re)starts its song.
- The per-frame watchdog at `0x21608–0x2161E` (inside `$2155E`, every 8
  frames) does `jsr $EB9C4; tst.w d0; bne skip; jsr $173EC($FF012E)` — it
  restarts the current song whenever the driver reports done. This is the
  song-loop mechanism, and it also defeats any off-state within 8 frames.

### "Quiet" is song index 18 — and it is a no-op

- The Music menu's song list (ROM text at `0xCD208`) is Quiet plus 18 songs
  (Rings, Wilds, Seas, TnFinD, Death, Quest, Victry, Combat, House, Inside,
  Castle, Guilds, Sorcer, Knight, Archer, Necro, Conjur), indices 0–17.
  The entries carry their song index as a prefix byte; "Quiet" carries
  index `18` (`0x12`).
- `$173EC` (dispatch) accepts indices `< 21` and jumps through a table at
  `0x17546`. Table word #18 is `$0002`, which jumps to `0x17582`
  (`unlk a6; rts`) — a clean no-op. So choosing Quiet plays nothing **but
  does not stop the music already streaming** (the streamer keeps feeding
  the old song, `$FF021E` stays `1`). The music only stops when the current
  song ends and the watchdog re-requests index 18 (also a no-op) — which is
  why the player perceives "off works, then a location change turns it back
  on": the location change calls `$173BC` with a different index, and
  `$173BC` plays it unconditionally.
- Location changes reach `$173BC` from 15 call sites (all scene/location
  code, hardcoded or location-table songs) and `$173EC` directly from 17
  sites. The Music menu itself calls neither `$173BC` nor `$173EC` with a
  variable index (all 15 + 17 sites pass hardcoded or location-derived
  indices); the menu's selection path lives in the text/menu system and was
  not traced end-to-end (see "Not proven").

### Net effect

There is no persistent "music off" state in the original game. "Quiet" is
a no-op dispatch entry, the stop routine is dead code, and every song
request (location change, watchdog) restarts music. The patch makes index
18 a real "stop the music" command and makes it sticky.

## The patch

Two 6-byte hooks + two trampolines in the unused `0xFF` padding at the end
of the ROM (`0xFD0CC–0xFFFFF`, 12,084 bytes; outside the runtime checksum's
summed range). No game code is moved and no song is sacrificed. SFX code is
not touched at all.

### Hook A — `$173BC` gate (location changes can't restart music)

At `0x173C0`, replace `move.w $FF012E,d0` (`30 39 00 FF 01 2E`) with
`jsr $FD0CC.l` (`4E B9 00 0F D0 CC`).

Trampoline A at `0xFD0CC` (32 bytes):

```
FD0CC: move.w $FF012E,d0        ; replicate replaced instruction
FD0D2: cmpi.w #$12,d0           ; Quiet active? ($FF012E == 18)
FD0D6: bne.w  $FD0EA            ; no  -> normal return to $173C6
FD0DA: cmpi.w #$12,8(a6)        ; requested == 18?
FD0E0: beq.w  $FD0EA            ; yes -> normal (re-pick Quiet)
FD0E4: move.l #$173D6,(a7)      ; no  -> return to $173BC's exit instead
FD0EA: rts                      ; (unlk a6; rts) — song request skipped
```

So while Quiet is active, any `$173BC` request for a different song (i.e.
every location change) returns without playing and without overwriting
`$FF012E`. When Quiet is not active the hook is a transparent pass-through.

### Hook B — `$173EC` intercept (Quiet actually stops the music)

At `0x173F4`, replace `ext.l d0; bra.w $17570`
(`48 C0 60 00 01 78`) with `jsr $FD0F0.l` (`4E B9 00 0F D0 F0`).

Trampoline B at `0xFD0F0` (72 bytes). The `jsr` pushed a return address
(`0x173FA`); every exit discards it with `addq.w #4,sp` and jumps to a
`$173EC`-internal address, so the stack is exactly as `$173EC` left it
after `link a6,#0`:

```
FD0F0: ext.l  d0                ; replicate replaced instruction
FD0F2: cmpi.w #$12,d0           ; Quiet requested?
FD0F6: beq.w  $FD116            ; yes -> STOP
FD0FA: cmpi.w #$12,$FF012E      ; Quiet active?
FD102: beq.w  $FD10E            ; yes -> BLOCK (return, no play)
FD106: addq.w #4,sp
FD108: jmp    $17570.l          ; normal dispatch (jump table)
FD10E: addq.w #4,sp             ; BLOCK
FD110: jmp    $17582.l          ; unlk a6; rts
FD116: move.w #$12,$FF012E      ; STOP: mark Quiet active first
FD11E: jsr    $EB9C4.l          ; is music actually playing?
FD124: tst.w  d0
FD126: beq.w  $FD10E            ; no  -> just return (no Z80 reset)
FD12A: jsr    $EB7C8.l          ; yes -> stop it (the dead routine)
FD130: addq.w #4,sp
FD132: jmp    $17582.l          ; unlk a6; rts
```

Notes on the design:

- The STOP path checks `$EB9C4` (which reads the Z80 request byte
  `$A0000B`) instead of only `$FF021E`, so an SFX that set `$FF021E = 1`
  does not trigger a spurious Z80 reset — a reset would truncate a playing
  SFX. `$EB7C8` runs only when music is actually playing.
- The watchdog's restart (`$173EC($FF012E)`) is harmless under Quiet: with
  `$FF012E == 18` it takes the STOP path, `$EB9C4` returns 0 (nothing
  playing), and it returns without resetting anything.
- Direct `$173EC` callers (scene songs, watchdog) are covered by Hook B, so
  a location change that bypasses `$173BC` is blocked the same way.

### Checksums

The patch changes bytes inside the runtime checksum's summed range
(`0x000000–0xFD07B`), so both checksums were re-fixed with
`tools/checksum.py fix-all`:

- Header checksum at `0x18E`: `0x8B9F` → `0xD94C`
- Runtime checksum immediate at `0xFD098`: `0x8F33608C` → `0x52C1FFAB`

The trampolines themselves sit at `0xFD0CC+`, outside the runtime sum
range, so they do not affect the runtime value.

## Files

- `rings-of-power-music-off.ips` — IPS patch (180 bytes, 11 records).
  Apply to a clean copy of the original ROM
  (`Rings of Power (USA, Europe).gen`, MD5
  `30c18fdbe2183f64702ae9f1a45d63f9`) with any IPS patcher (e.g. Lunar IPS,
  Floating IPS). It produces the patched ROM; no full ROM is shipped here.
  Round-trip verified: applying the IPS to the original reproduces the
  patched ROM byte-for-byte.
- `changed-bytes.txt` — the full list of changed bytes with addresses
  (original → patched), for review without applying the IPS.

## How to use

1. Apply `rings-of-power-music-off.ips` to a copy of the original ROM.
2. In the game, open the Music menu and choose **Quiet**.
3. The music stops (immediately, not at the end of the current song) and
   stays off across location/screen changes and sound effects.
4. To get music back, reset the console (or remove the patch). See
   "Limits" — there is no in-game way to turn music back on once Quiet is
   chosen.

## Limits (read before using)

- **One-way off switch.** Once Quiet is chosen, music stays off until the
  console is reset. Picking another song from the Music menu while Quiet is
  active is ignored (the request is blocked by the patch). This is a
  deliberate consequence of the game's architecture: there is no separate
  music on/off flag, and at the patched choke point (`$173EC`) a menu song
  pick is indistinguishable from a location-change song request, so the
  patch cannot allow one while blocking the other. Reset restores normal
  music (the title/attract starts song 0 as before).
- **Sound effects are untouched and keep working.** The patch does not
  modify any SFX code (`$EBB04`/`$EBBFE`/`$EBB08`/`$17586`/`$EBAF4`/
  `$EBAFA`). An SFX sets `$FF021E = 1`, but the music streamer stays idle
  because the driver's request byte `$A0000B` is 0 after a stop (only
  `$EB88A` sets it to `$0D`), so SFX do not resume the music. SFX
  audibility while Quiet is active was not directly heard headlessly (see
  "Not proven") — the claim rests on the code reading above.
- **The patch does not add a menu option.** It repairs the existing
  "Quiet" entry. No text, graphics, or menu layout was changed.
- **Emulator only.** Tested in BlastEm, not on real hardware.

## What was tested (verified)

- **Checksums:** `tools/checksum.py verify-all` on the patched ROM:
  header `0xD94C` OK, runtime `0x52C1FFAB` OK.
- **Boot (BlastEm 0.6.3.4 headless, Xvfb + dummy audio):** the patched ROM
  boots, passes its own runtime checksum, reaches the dispatcher/main loop,
  and keeps running (exit 124 = still running at the 30 s and 60 s
  timeouts). No hang at `0xFD0CA` (the checksum-fail address). The
  branch-target address log covers a superset of the original ROM's
  addresses (nothing the original reaches is missing).
- **Normal music still starts (BlastEm debugger, `-d`, PTY-driven):**
  breakpoints at `FD0CC`, `FD0F0`, `EB88A` all hit with correct backtraces
  for the title/attract song start: `$D260 → $11E06 → $173BC(0)` →
  Hook A → Hook B → dispatch block 0 (`0x17400`) → `$EB88A` (song 0
  starts). The normal path is unchanged when Quiet is not active.
- **The stop path runs (address log, full-speed runs):** in the patched
  attract, trampoline B's STOP entry (`FD116`), BLOCK entry (`FD10E`) and
  stop-sound (`$EB7C8`) all execute — i.e. an index-18 ("no music") request
  was made while music was playing and the patch stopped it. The exact
  scene issuing that 18 request was not traced to a backtrace (the debugger
  runs too slowly to reach it in a reasonable session); by elimination from
  the call graph, the only variable source of an index-18 `$173EC` request
  is `$FFBB6F` via `0x20646` (the watchdog can only repeat an 18 that is
  already current).
- **No audible regression in the attract (BlastEm `-y`, YM-2612 WAV):**
  the attract is silent in both the original and the patched ROM (all six
  channels are a constant DC value, byte-identical files). The patch does
  not introduce audible music or noise.
- **IPS round-trip:** applying the IPS to the original reproduces the
  patched ROM byte-for-byte. The original ROM is untouched
  (MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).

## What was NOT proven

- **The menu UI path was not driven.** No buttons were pressed headlessly,
  so the Music-menu selection of "Quiet" was not observed end-to-end. What
  is proven is the `$173EC` level: a request for index 18 stops the music
  (STOP path) and is remembered (`$FF012E = 18`). The menu handler itself
  lives in the text/menu system (issue #004's domain) and was not traced.
- **A real location change after Quiet was not played through.** The
  suppression is proven at the `$173BC`/`$173EC` level (both hooks block
  song starts while `$FF012E == 18`), but no one walked through a door /
  changed screens with Quiet active in the emulator.
- **SFX audibility while Quiet is active was not heard.** Headless runs use
  dummy audio. The SFX code is untouched and the flag analysis above shows
  SFX cannot resume music, but no SFX was listened to with Quiet on.
- **Real hardware was not tested.** BlastEm only.
- **The `$EB88A` address-log anomaly.** In the address logs, `$EB88A`
  appears in the patched runs but not in the original runs. The debugger
  proved this is a logging artifact, not a patch effect: on the original
  ROM, `$173BC(0)` → `$EB88A` (song 0 starts) with `$FF012E = 0xFFFF`
  ("no song yet") at the call — the original does start music; the `-l`
  log simply failed to record `$EB88A` in those runs. Do not read the
  address-log difference as "the patch starts a song".

## Confidence labels

- **Verified:** flag addresses and meanings (`$FF021E`, `$FF012E`,
  `$A0000B`); `$EB7C8` dead code (0 callers); dispatch table word #18 =
  `$0002` → no-op; watchdog restart at `0x21608`; `$173BC` unconditional
  play on location change; hook bytes and trampoline disassembly
  (Capstone); checksums; boot/no-crash; normal song start through the
  patch (debugger backtraces); IPS round-trip.
- **Likely:** the attract's index-18 request comes from `$FFBB6F` via
  `0x20646` (only variable source; backtrace not captured).
- **Unknown / not proven:** the menu UI path to `$173EC(18)`; a real
  gameplay location change with Quiet active; SFX audibility with Quiet on;
  real-hardware behaviour.
