; source.s -- big-rework-full phase D: tick governor + chunk loading.
;
; Base: rop-big-rework-full-c-fix.rom (MD5 535288396024b3892d89d74b980436ac).
; Blob at $FE6CA (free 0xFF padding to the end of the ROM, 6454 bytes).
; Six hook sites (all 6-byte replacements, base bytes asserted first):
;   H1 $00D2E0 jsr world_tick      -> jsr gov_world_tick
;   H2 $00D97E jsr combat_turn_run -> jsr gov_combat_turn
;   H3 $0228CC cmpi.w #$4,-$E(a6)  -> jsr gov_path_a (pace v2 + leader heading)
;   H4 $022778 jsr sys_event_run   -> jsr gov_sys_event (16-tick gate)
;   H5 $022B36 move.w d4,d0 + muls.w #$34,d0 -> jmp gov_npc (NPC gate;
;        dest test first, $00FF sentinel; the old H5 at $022B54 is a
;        landmine -- the $022B48 bne.b $022B56 branches into it)
;   H6 $12C20  jsr $FE65A (C scene_entry) -> jsr gov_scene (chains to it)
;
; Governor (DESIGN §5.5): the world tick runs once per GOV_K VBlanks
; (default 5, 12 Hz), counted off the frame counter $FF0010 (which
; increments once per VBlank at $127A; no VBlank hook needed). The
; leader's cell commits once per 4 ticks (phase gate, turn check
; first), so 1 cell / 4 ticks ~= 20-24 fr/cell ~= original ~22 fr/cell.
; NPCs/scripts run once per GOV_NPCDIV phase-0 ticks (default 4,
; i.e. every 16th governor-tick ~= 80-96 fr ~= original ~88 fr).
; K and the divisor live in RAM so the walk-pace decision (Dayset's)
; is a one-word change later; built at the ORIGINAL pace by default.
;
; Chunk loading (DESIGN §7.2): the data-chunk load is unchanged
; (map_chunk_cache_read + 4-slot cache); doors are the transition.
; The one concrete gap found by code reading is fixed here: sprite
; slots are NOT invalidated on a location change (a stale slot whose
; recIdx coincides with a new room's figure keeps its old pattern
; and TARGET until round-robin re-decodes it). H6 clears the sprite
; magic on scene setup, so sprite_init drops all slots and the
; figures pop in freshly decoded instead of showing stale ones.
; Install camera / scroll across a transition are already handled
; (C VBlank location-change reset + scene_entry); data-chunk
; boundaries need no image-layer event (§7.1).
;
; RAM used: $FFD300-$FFD31F (no refs in rop.s; sprite state ends
; $FFD2FF; B2 state is $FF00A0-$FF00C0, untouched).
; Registers: every jsr entry saves what it uses (movem FIRST) and
; restores before rts; the jmp entry (gov_npc) saves/restores around
; its tests and preserves d4/a6/the stack. gov_scene tail-calls C's
; scene_entry, which never returns (it jmps into world_map_draw).
;
; Assemble: vasmm68k_mot -m68000 -Fbin -o source.bin -L source.lst source.s

        org     0

; --- game addresses ---
WORLD_TICK equ   $02155E  ; world_tick (phase counter, shimmer)
COMBAT_TURN equ  $0226BC  ; combat_turn_run (movement + script dispatch)
SYS_EVENT equ    $02D56A  ; sys_event_run (event-script engine)
FRAME   equ     $FF0010  ; frame counter (long, +1 per VBlank at $127A)
GRIDBASE equ    $FFA7FC  ; ram_map_grid_base (pointer); +$A = grid+$A phase
LEADER  equ     $FF02B2  ; ram_party_leader (char index)
HEADARR equ     $FF02BE  ; heading array: HEADARR + char*$34 (char 1 = $FF02F2)
DESTARR equ     $FF02B8  ; per-char dest array: $FFFF = wandering NPC
C_SCENE equ     $FE65A   ; C's scene_entry (world_map_draw hook; never returns)

; --- governor state ($FFD300-$FFD31F) ---
GOV_MAGIC  equ $FFD300  ; word $9C07 once initialised
GOV_K      equ $FFD302  ; word: VBlanks per tick (default 5)
GOV_NPCDIV equ $FFD304  ; word: phase-0 ticks per NPC/script step (default 4)
GOV_NPC    equ $FFD306  ; word: phase-0 counter 0..GOV_NPCDIV-1 (init DIV-1)
GOV_LAST   equ $FFD308  ; long: $FF0010 at the last tick
GOV_RUN    equ $FFD30C  ; word: 1 = this iteration's tick ran
SPR_MAGIC  equ $FFD000  ; C sprite magic (cleared by gov_scene)

; ------------------------------------------------------------------
; gov_world_tick (H1): main-loop tick gate. Entered via jsr at $00D2E0
; (displacing `jsr world_tick.l`). Runs world_tick once per GOV_K
; VBlanks; otherwise skips it. After a run, if the new grid+$A == 0
; (a phase-0 tick) bumps GOV_NPC = (GOV_NPC+1) mod GOV_NPCDIV.
gov_world_tick:
        movem.l d0-d1/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .wt_ok
        bsr     gov_init
.wt_ok:
        move.l  FRAME,d0
        sub.l   GOV_LAST,d0
        move.w  GOV_K,d1
        ext.l   d1
        cmp.l   d1,d0
        blt     .wt_skip
        move.l  FRAME,GOV_LAST
        move.w  #1,GOV_RUN
        movem.l (sp)+,d0-d1/a0
        jsr     WORLD_TICK
        movem.l d0/a0,-(sp)
        movea.l GRIDBASE,a0
        tst.w   $A(a0)
        bne     .wt_done
        move.w  GOV_NPC,d0
        addq.w  #1,d0
        cmp.w   GOV_NPCDIV,d0
        blt     .wt_set
        clr.w   d0
.wt_set:
        move.w  d0,GOV_NPC
.wt_done:
        movem.l (sp)+,d0/a0
        rts
.wt_skip:
        clr.w   GOV_RUN
        movem.l (sp)+,d0-d1/a0
        rts

; ------------------------------------------------------------------
; gov_combat_turn (H2): runs combat_turn_run only on a governor-tick
; (GOV_RUN set by gov_world_tick earlier in the same iteration).
; Entered via jsr at $00D97E (displacing `jsr combat_turn_run.l`).
gov_combat_turn:
        movem.l d0/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .ct_ok
        bsr     gov_init
.ct_ok:
        tst.w   GOV_RUN
        beq     .ct_skip
        clr.w   GOV_RUN
        movem.l (sp)+,d0/a0
        jsr     COMBAT_TURN
        rts
.ct_skip:
        movem.l (sp)+,d0/a0
        rts

; ------------------------------------------------------------------
; gov_path_a (H3): leader step gate (pace.s v2, leader-heading
; version). Entered via jsr at $0228CC (displacing
; `cmpi.w #$4,-$E(a6)`). A popped direction differing from the
; leader's heading goes through immediately (face turns in one
; press); the same direction goes through only on phase 0 (1 cell
; per 4 ticks). The dir==4 stop sentinel takes the allow path and
; Path A's beq skips exactly as before.
gov_path_a:
        movem.l d0-d1/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .pa_ok
        bsr     gov_init
.pa_ok:
        move.w  -$E(a6),d0
        move.w  LEADER,d1
        muls.w  #$34,d1
        lea.l   HEADARR,a0
        move.w  (a0,d1.l),d1
        andi.w  #3,d1
        cmp.w   d1,d0
        bne     .pa_allow
        movea.l GRIDBASE,a0
        tst.w   $A(a0)
        bne     .pa_skip
.pa_allow:
        movem.l (sp)+,d0-d1/a0
        cmpi.w  #$4,-$E(a6)
        rts
.pa_skip:
        movem.l (sp)+,d0-d1/a0
        addq.l  #4,sp
        jmp     $022960

; ------------------------------------------------------------------
; gov_sys_event (H4): script-step gate. Entered via jsr at $022778
; (displacing `jsr sys_event_run.l`). Runs the script step only when
; GOV_NPC==0 (every 4th phase-0 tick = every 16th governor-tick).
; GOV_NPC advances only on phase-0 ticks, so GOV_NPC==0 always
; coincides with one (no deadlock from counter misalignment).
gov_sys_event:
        movem.l d0/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .se_ok
        bsr     gov_init
.se_ok:
        tst.w   GOV_NPC
        bne     .se_skip
        movem.l (sp)+,d0/a0
        jsr     SYS_EVENT
        rts
.se_skip:
        movem.l (sp)+,d0/a0
        rts

; ------------------------------------------------------------------
; gov_npc (H5): NPC step gate. Entered via jmp at $022B36
; (displacing `move.w d4,d0` + `muls.w #$34,d0`, 6 bytes, which
; gov_npc re-executes to index the dest array). The dest test
; comes FIRST, with the ORIGINAL sentinel $00FF (not $FFFF):
; a destination NPC (dest != $00FF) bypasses every gate and moves
; at the original pace; only wandering NPCs (dest == $00FF) take
; the phase gate (1 step per 4 ticks) plus the GOV_NPC divisor
; gate (every 16th governor-tick). Allow: re-execute the displaced
; move and jmp $022B5A. Skip: jmp $022B64 (the loop's next-char
; exit). Preserves d4/a6/the stack. (The old H5 at $022B54 is
; dead: the $022B48 bne.b $022B56 branched into its jmp.)
gov_npc:
        movem.l d0-d1/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .np_ok
        bsr     gov_init
.np_ok:
        move.w  d4,d0
        muls.w  #$34,d0
        lea.l   DESTARR,a0
        cmpi.w  #$FF,(a0,d0.l)
        bne     .np_move
        movea.l GRIDBASE,a0
        tst.w   $A(a0)
        bne     .np_skip
        tst.w   GOV_NPC
        bne     .np_skip
.np_move:
        movem.l (sp)+,d0-d1/a0
        move.w  -$E(a6),-(a7)
        jmp     $022B5A
.np_skip:
        movem.l (sp)+,d0-d1/a0
        jmp     $022B64

; ------------------------------------------------------------------
; gov_scene (H6): scene-setup chain. Entered via jsr at $12C20
; (displacing `jsr $FE65A`, C's scene_entry). Clears the sprite
; magic so sprite_init drops all (possibly stale) figure slots on
; the next decode/update, then tail-calls C's scene_entry, which
; never returns (it jmps into world_map_draw at $012C2A after
; discarding the jsr return).
gov_scene:
        movem.l d0/a0,-(sp)
        cmpi.w  #$9C07,GOV_MAGIC
        beq     .sc_ok
        bsr     gov_init
.sc_ok:
        movem.l (sp)+,d0/a0
        clr.w   SPR_MAGIC
        jmp     C_SCENE

; ------------------------------------------------------------------
; gov_init: initialise the governor state. Called once (bsr) from any
; entry whose magic check fails. Uses d0/a0 only (callers save them).
gov_init:
        move.w  #5,GOV_K
        move.w  #4,GOV_NPCDIV
        move.w  GOV_NPCDIV,d0
        subq.w  #1,d0
        move.w  d0,GOV_NPC
        clr.l   GOV_LAST
        clr.w   GOV_RUN
        move.w  #$9C07,GOV_MAGIC
        rts
