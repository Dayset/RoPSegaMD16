# D-crash fix build — crash fix + BOTH secondaries (INCREMENTAL)

Dayset picked the scope in the main chat: crash fix + BOTH secondaries,
in one build (explicit pick waives the one-fix rule for this round only).
Build NOTHING beyond these three changes. Nothing lands on main —
test ROMs stay in this worktree.

Diagnosis: `.scratch-big-rework-full/d-crash/REPORT.md` (§§1, 5–8).
Broken ROMs: C MD5 `385fa655a5a060ac6b66de8b9de795dd`,
D MD5 `208371be216d3182303c3af64cbc9eab` (final `rop-big-rework-full.rom`
is a copy of the broken D).
Original ROM MD5 `30c18fdbe2183f64702ae9f1a45d63f9`.

## 0. Ground facts + pre-build findings (2026-11-20)

### The three changes
1. **Crash fix** (d-crash §8): insert `addq.w #4,sp` at the start of
   `.sh_run` (skip_hero, $FE610) and `.sp_run` (skip_promote, $FE632),
   before the displaced prologue. One word ($584F) in each wrapper.
   The skip paths already have it — untouched.
2. **Secondary 1** (d-crash §7): move the install-camera state off
   $FF00C0 (installCamY) and $FF00BC (installCamX) to free RAM
   $FFD320/$FFD322 (see verification below).
3. **Secondary 2** (d-crash §1 H5 + §7): fix the D governor's NPC
   sentinel — destination NPCs must bypass the phase gate and move
   every tick, as the original does; wandering NPCs stay gated
   (phase gate + 16-tick NPC divisor gate).

### Pre-build finding A — H5 has a SECOND landmine (found while reading
### the original loop; NOT in the d-crash report)
The original NPC loop (`disasm/src/rop.s` $022B2E–$022B64, lead-verified
from ROM bytes):
```
$022B2E: cmpi.w #$4,-$E(a6)      ; heading < 4? (-$E(a6) = heading, from $FF02BE+char*$34)
$022B34: bcc.b $022B64            ; heading >= 4 -> skip
$022B36: move.w d4,d0
$022B38: muls.w #$34,d0
$022B3C: lea.l $FF02B8,a0         ; dest array
$022B42: cmpi.w #$ff,(a0,d0.l)   ; dest == $FF (wandering)?
$022B48: bne.b $022B56            ; dest != $FF -> MOVE directly (bypass phase gate)
$022B4A: movea.l $FFA7FC,a0       ; GRIDBASE
$022B50: tst.w $A(a0)             ; grid+$A phase
$022B54: bne.b $022B64            ; phase != 0 -> skip   (HOOK SITE in broken D)
$022B56: move.w -$E(a6),-(a7)
$022B5A: move.w d4,-(a7)
$022B5C: jsr combat_move_unit
$022B62: addq.w #$4,a7
$022B64: bra.w $022F34
```
The broken D hook is a 6-byte `jmp gov_npc` at $022B54, overwriting
$022B54–$022B59 — INCLUDING $022B56, the target of the original
dest-test branch at $022B48. So in the broken D ROM, the FIRST
destination NPC with a walk heading branches to $022B56, which is
the middle of the `jmp` instruction (bytes `00 0F E7 FA ...` =
`ori.b #$E7,d7` then a line-F trap) — a second, independent PC=0
crash, masked until now because the skip-hook crash fires first (on
the first room decode, before any NPC move). The d-crash report
verified gov_npc's own targets but did not check the pre-hook branch
target. The ONLY branch to $022B56 in the ROM is the one at $022B48
(grep for L022B36/L022B3C/L022B48/L022B54/L022B56/L022B5A: only
`bne.b L022B56 ; $022B48` and the `L022B56:` label itself).
**Fix:** move H5 to $022B36 (displacing `move.w d4,d0` + `muls.w
#$34,d0`, exactly 6 bytes). gov_npc then owns the whole decision:
re-execute the displaced offset computation, dest test FIRST
(`cmpi.w #$FF` — the original sentinel is $00FF, not $FFFF),
destination NPC → move path, wandering NPC → phase gate + GOV_NPC
gate. The original decision code at $022B3C–$022B53 becomes dead
(no branch enters it — the only entry was fall-through from $022B34,
now diverted by the jmp; verified by the grep above). The original
`move.w -$E(a6),-(a7)` at $022B56 stays intact; gov_npc's move path
re-executes it and jmps $022B5A, as the current code does. The heading
check at $022B2E–$022B34 runs before the hook site and is preserved.

### Pre-build finding B — install-camera new home verified free
- $FFD320/$FFD322: ZERO refs in `disasm/symbols/*.csv` and
  `disasm/src/rop.s` (grep `ffd32`/`ffd33`: nothing); no ram_refs
  rows for $FFD3xx. C source's highest actual $FFD use is $FFD1AA
  ($FFD2FF is only a region-end comment); D source uses
  $FFD300–$FFD31F (governor state; last used word GOV_RUN $FFD30C,
  $FFD30E–$FFD31F reserved padding). $FFD320/$FFD322 are the first
  free words past the governor state.
- $FF00BC: no symbol and no refs anywhere in the CSVs (unclaimed
  RAM) — but it sits 4 bytes before the save field, and B2's "dead
  RAM $FF00A0–$FF00C0" claim is already proven wrong for $FF00C0,
  so BOTH move, per the task. $FF00C0 = `ram_save_field_00c0`
  (ram.csv, 19 refs: entity_spawn, npc_attitude_apply,
  save_serialise, save_deserialise, world_camp) — the persistent
  merchant-attitude table, confirmed.
- New names: ICAM_X = $FFD320, ICAM_Y = $FFD322. All absolute-long
  encodings, so every use stays the same instruction length — the
  relocation changes NO blob sizes.

### Pre-build finding C — C-blob growth shifts the tail (consequence
### of the two inserted words)
C listing offsets (broken C): vbl +0, redraw +0x642, skip_hero
+0x1210 ($FE610), skip_promote +0x1232 ($FE632), scene_entry +0x1256
($FE656), mapclose_entry +0x1290 ($FE690); blob 4806 bytes,
$FD400–$FE6C5. The two inserted words (+2 in skip_hero, +2 in
skip_promote) shift skip_promote → $FE634, scene_entry → $FE65A,
mapclose_entry → $FE694; the C blob grows to 4810 bytes
($FD400–$FE6C9). Consequences, all handled in the fix builds:
- D blob base moves $FE6C6 → $FE6CA (new `patches/d-governor-fix/
  build.py` BLOB_BASE + C_BLOB_LEN = 4810).
- D source `C_SCENE equ $FE656` → $FE65A (and the build.py
  `C_SCENE_TARGET`, the `jmp $FE656` tail-call assertion, and the
  C-hook `expect()` calls for scene $FE656→$FE65A, mapclose
  $FE690→$FE694, promote $FE632→$FE634; hero $FE610 unchanged).
- The D build's `BASE_MD5` becomes the fixed C ROM's MD5 (filled
  after the C build); its BASE becomes the fixed C ROM file.
- Fixed intermediates get distinct names so the broken ROMs stay
  on disk for the diff audit: `rop-big-rework-full-c-fix.rom`,
  `rop-big-rework-full-d-fix.rom`; the final is a copy of the fixed
  D as `rop-big-rework-full.rom` (same naming as before).
- The C build reads entry offsets from the listing, so its hook
  patching follows the shifts automatically; the scene/mapclose
  instruction streams are unchanged, so `check_entries.py` (B2
  comparison) still applies.

## 1. C source edits (DONE 2026-11-20)
- `patches/c-sprites-fix/` (copies of the C patch dir; originals untouched).
- `source.s`: `addq.w #4,sp` inserted at `.sh_run` and `.sp_run`
  (before the displaced prologue); the stale header comment
  ("the routine's own rts returns to its caller") corrected to state
  the discard rule and name the D-crash bug; the skip_hero/
  skip_promote comment corrected the same way.
- Install camera relocated: `ICAM_X equ $FFD320`, `ICAM_Y equ
  $FFD322` defined; all $FF00BC/$FF00C0 uses replaced (sed, then
  verified: ZERO $FF00BC/$FF00C0 refs remain in the source).
- `check_entries.py`: the B2 scene/mapclose comparison now allows
  exactly the icam relocation (the two `move #$FFFF` resets
  $FF00BC/$FF00C0 → $FFD320/$FFD322, at most one per entry) — the
  first build run failed on this check with ONLY those two
  replacements showing, which confirmed the relocation was complete
  and nothing else had drifted.

## 2. C rebuild + verification (DONE 2026-11-20)
- Build: `python3 patches/c-sprites-fix/build.py` — exit 0.
  Blob 4810 bytes at $FD400 ($FD400–$FE6C9); entries: vbl +0,
  redraw +0x642, skip_hero +0x1210 ($FE610), skip_promote +0x1234
  ($FE634), scene +0x125A ($FE65A), mapclose +0x1294 ($FE694) — all
  exactly as predicted in §0.
- Checksums verify: header 0xB756, runtime 0x54512C6C
  (`checksum.py verify-all` OK).
- IPS round-trip exact (360 records, 6237 bytes):
  B2 + `rings-of-power-big-rework-full-c-fix.ips` == fixed C ROM.
- Diff audit vs broken C (42 runs, 220 bytes — every byte
  accounted for): header checksum (2 B); scene hook target
  $FE656→$FE65A (1 B); mapclose $FE690→$FE694 (1 B); promote
  $FE632→$FE634 (1 B); runtime checksum immediate (2 B); 16×
  `00bc→d320` + 16× `00c0→d322` (install-camera relocation);
  the two inserted `584f` words + the resulting +4 shift of
  scene_entry/mapclose_entry code.
- Blob scan: `00ff00bc`/`00ff00c0` count 0; `00ffd320`/`00ffd322`
  count 16 each.
- Wrapper disassembly (capstone): skip_hero run path at $FE626
  is `addq.w #4,a7; link a6,#0; move.l a3,-(sp); jmp $231DE`;
  skip_promote run path at $FE64A is `addq.w #4,a7; link a6,#0;
  movem.l d4-d5/a3,-(sp); jmp $23442`. Both exactly as specified.
- **Fixed C MD5 (v2, with the register-restore fix): `535288396024b3892d89d74b980436ac`**
  (header $B752, runtime $54512C6C). Broken C untouched
  (MD5 `385fa655a5a060ac6b66de8b9de795dd` re-verified).
  Original ROM untouched (MD5 re-verified by the build).
- Diff audit vs broken C (v2): 43 runs, 274 bytes — the same 42 runs
  as v1 plus one 54-byte run at $0FDCC0–$0FDCF5 (the `.rdone`
  block): the `movem.l (sp)+,d0-d7/a0-a6` (`4cdf7fff`) moved from
  the tail to before `link a6,#-2`, and the tail is now `bsr.s
  decode_figures; rts` (the `bsr` at $0FDCF4 targets $FDCF8).
  Every byte accounted for; header checksum $B756→$B752.

## 2b. SECOND BUG — the fixed C still froze (diagnosed 2026-11-20)
- The v1 fixed C (MD5 `2a05…`) froze idle at ~1.0 s, same
  $DFFFFE message. The skip-hook fix was correct but incomplete:
  a second, independent bug remained.
- Bisection (four diagnostic variants, all built from source in
  `patches/c-diag-*/`, repro idle 70 s each):
  - `c-diag-nodecode` (decode_figures disabled) — FROZE.
    Decode/repack/scan/clear is not the bug.
  - `c-diag-nosprite` (sprite_update disabled) — FROZE.
    Sprite update is not the bug.
  - `c-diag-novbl` (vbl_entry reduced to a pass-through: no
    init/scroll/sprite_update) — FROZE. The VBlank handler is
    exonerated; the crash is in the main-loop / redraw-body path.
  - `c-diag-jmpbody` (redraw_entry reverted to B2's `jmp $1B922`
    tail-call, no jsr-wrap, no decode) — CLEAN 70 s.
  - `c-diag-regrestore` (jsr-wrap kept, but the saved registers
    restored BEFORE calling the body) — CLEAN 70 s.
- Root cause: C's `redraw_entry` saved the registers at entry,
  ran the gate/install (clobbering d0–d7/a0–a6), then called the
  redraw body via `jsr` with the clobbered registers still live,
  restoring them only after the body returned. The game's redraw
  body must see redraw_check's registers (as B2 restores them
  before its `jmp` to the body). With clobbered registers the body
  takes a bad jump in its decode/DMA path at ~1 s (Buc's first
  cutscene step, the first redraw after the install) and the CPU
  reaches PC=0; the zero-vector exception loop then collapses SP
  to $DFFFFE. (The exact clobbered register is not pinned; the
  bisection is conclusive — restore-before-body is clean,
  restore-after-body freezes. B2 was immune because it restores
  before the jump.)
- Supporting evidence: B2 runs clean idle 70 s (same scroll/gate/
  install), so the bug is C-only. A breakpoint sample of the v1
  fixed C showed a7 flat ~$FFEB90 for 67 VBlanks, then collapsing
  ~17.7 KB/VBlank from VBlank 68 (the PC=0 cascade); the first
  PC=0 hit (t=1.0 s) had SP=$FFEBBE with a VBlank interrupt frame
  [SR=$2004][PC=$1B9FA] on the stack (interrupt fired in the body
  just after the DMA upload at $1B9E8).
- Fix (applied to `patches/c-sprites-fix/source.s`, §2 v2): in
  `.rdone`, `movem.l (sp)+,d0-d7/a0-a6` moved to BEFORE `link
  a6,#-2` (B2's order); the tail is now just `rts` after the
  decode. The jsr-wrap and decode_figures are kept. Blob stays
  4810 bytes; all entries at the same offsets.

## 3. C idle repro ≥60 s (PASSED 2026-11-20)
- `repro.py rop-big-rework-full-c-fix.rom c_fix_v2 70` (idle from
  Dayset's save): **no freeze in 70 s**. Screenshot
  `c_fix_v2.png`. The v2 fixed C (MD5 `535288396024b3892d89d74b980436ac`)
  passes the repro that failed on v1.
- (Diagnostic ROMs also ran: `c-diag-jmpbody` and
  `c-diag-regrestore` clean 70 s; `c-diag-nodecode`,
  `c-diag-nosprite`, `c-diag-novbl` froze — see §2b.)
## 4. D source edits (DONE 2026-11-20)
- `patches/d-governor-fix/` (copies of the D patch dir; originals untouched).
- Base re-pointed: `rop-big-rework-full-c-fix.rom` (the v2 fixed C,
  MD5 `535288396024b3892d89d74b980436ac`); output
  `rop-big-rework-full-d-fix.rom` + `rings-of-power-big-rework-full-d-fix.ips`.
- Blob base $FE6C6→$FE6CA (fixed C blob is 4810 bytes);
  C_BLOB_LEN 4810; C blob read from `patches/c-sprites-fix/source.bin`
  and asserted byte-identical to the fixed C ROM.
- C_SCENE $FE656→$FE65A (source equ, build.py `C_SCENE_TARGET`,
  `jmp $FE656` assertion → `jmp $FE65A`, and the `expect()` hooks:
  scene $12C20 jsr $FE65A, mapclose $16302 jsr $FE694, promote
  $02343A jsr $FE634; hero $FE610 and vbl/redraw unchanged).
- SECONDARY 2 + H5 landmine fix: H5 moved $022B54→$022B36
  (displacing `move.w d4,d0` + `muls.w #$34,d0`, expected bytes
  `3004 c1fc 0034` — asserted by the build, matched). gov_npc
  restructured: dest test FIRST with `cmpi.w #$FF` (the original
  $00FF sentinel, not $FFFF); destination NPCs (dest != $00FF)
  bypass every gate and move at the original pace; wandering NPCs
  (dest == $00FF) take the phase gate + the GOV_NPC 16-tick
  divisor gate. Move path re-executes `move.w -$E(a6),-(a7)` +
  `jmp $022B5A`; skip path `jmp $022B64`. The old H5's landmine
  (the $022B48 `bne.b $022B56` branching into the middle of its
  6-byte jmp) is dead: gov_npc never returns to $022B3C–$022B54.
- gov_npc disassembly (capstone, $FE7FE): movem save; magic check;
  `move.w d4,d0; muls.w #$34,d0; lea $FF02B8; cmpi.w #$FF,(a0,d0.l);
  bne $FE836` (destination → move); `movea GRIDBASE; tst.w $A(a0);
  bne $FE844; tst.w $FFD306; bne $FE844` (wandering gates);
  `movem restore; move.w -$E(a6),-(a7); jmp $022B5A` (move);
  `movem restore; jmp $022B64` (skip). Exactly as specified.

## 5. D rebuild + verification (DONE 2026-11-20)
- Build: `python3 patches/d-governor-fix/build.py` — exit 0.
  Blob 472 bytes at $FE6CA–$FE8A1; entries: world_tick $FE6CA,
  combat_turn $FE74A, path_a $FE77C, sys_event $FE7D2, npc $FE7FE,
  scene $FE84E, init $FE86E.
- Hooks patched (base bytes asserted first): H1 $D2E0 → $FE6CA,
  H2 $D97E → $FE74A, H3 $228CC → $FE77C, H4 $22778 → $FE7D2,
  H5 $22B36 (`3004c1fc0034`) → $FE7FE, H6 $12C20 → $FE84E.
- C blob verified byte-identical to the fixed C ROM
  ($FD400–$FE6C9, 4810 bytes); C hooks asserted unchanged.
- Checksums verify: header 0xAC11, runtime 0xA20FF3DE
  (`checksum.py verify-all` OK).
- IPS round-trip exact (48 records, 710 bytes):
  fixed C + `rings-of-power-big-rework-full-d-fix.ips` == fixed D ROM.
- **Fixed D MD5: `a2569bc0c7d93342b8cb1f2d426fbdfe`**
  (header $AC11, runtime $A20FF3DE). Broken D untouched
  (MD5 `208371be216d3182303c3af64cbc9eab` re-verified).
  Original ROM untouched (MD5 re-verified by the build).

## 6. D idle repro ≥60 s + final designation (DONE 2026-11-20)
- `repro.py rop-big-rework-full-d-fix.rom d_fix 70` (idle from
  Dayset's save): **no freeze in 70 s**. Screenshot `d_fix.png`.
- Final designated: `rop-big-rework-full.rom` is a copy of the
  fixed D (MD5 `a2569bc0c7d93342b8cb1f2d426fbdfe`; checksums
  re-verified on the final file: header $AC11, runtime
  $A20FF3DE). The broken final (`208371be…`) is superseded but
  kept on disk as `rop-big-rework-full-d.rom` for reference.
- Scope respected: exactly the three changes (crash fix +
  both secondaries) plus the second-bug register-restore fix
  that the crash fix required; nothing else landed. Nothing
  pushed to main; test ROMs stay in the worktree.
