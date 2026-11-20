; camdelay.s — one-step camera delay for the B-zoom room walk (mode 2).
;
; Base: rop-interp.rom (MD5 309d87c5a97cdbc5c2066f11a2f98399) — flat
; checkerboard (mode 2), feet fix, subcell template override, pacing gate
; (1 cell / 4 ticks), interpolation slide (room-relative, in hero_track).
; One fix only: make the slide VISIBLE on screen.
;
; DIAGNOSIS (probe v2/v3/v4 + static read + Dayset's loop-walk playtest):
; - The interp slide is room-relative: the figure's drawn cell interpolates
;   old -> new over phases 0-3. But the camera (ram $FF0E8E/$FF0E90) tracks
;   the figure's committed cell EXACTLY (probe v2: cam == Buc's cell at
;   most commits; the hunt live-proved cam == Buc's cell every row).
;   So each new cell's screen position is the centre, and the figure's
;   on-screen position = centre + slide_offset, which oscillates in
;   [-step, -step/4] and jumps back to -step at the next commit. Net
;   on-screen progress over a full step cycle is ZERO. The figure never
;   travels across the screen; it shuffles ~10 px behind the centre and
;   then the room jumps. That reads as "no subcell movement" / "standing
;   then teleporting" — exactly Dayset's playtest on the interp ROM.
; - Dayset's loop-walk playtest confirms the split: Buc CAN walk in all
;   directions (the loop works), but the world shift is still jumpy.
;   The remaining jumpiness is the world/camera shift (the integer-cell
;   camera jumping a whole cell at each commit), NOT the figure's slide.
; - The cutscene lag is a separate, confirmed mechanism: Buc's cutscene
;   record has +10 == 1 (probe v3/v4: rec10 = 1), so the record does NOT
;   step in combat_move_unit during a script and waits for the record
;   stepper at phase 2, while the camera moves at phase 0. The world
;   jumps first, then Buc catches up (2 phases). This fix does NOT touch
;   the cutscene (gated off while a script runs).
; - Speed: the interp hook adds ~100 instructions per hero_track call
;   (negligible vs an ~9-frame render). The walk is slow because the
;   pacing gate commits 1 cell / 4 ticks (~36 frames/cell on the flat
;   ROM vs ~22 on the original). The "even slower" feel is the gradual
;   slide making the slow pace visible. Restoring original walk speed
;   needs a pacing change — a separate decision (Dayset's call).
;
; WHAT THIS HOOK DOES:
; - Hooks the two step-mode camera writes in leader_spawn ($01C21A):
;   $01C2D8 (move.w d0,$FF0E8E, cam X) and $01C300 (move.w d0,$FF0E90,
;   cam Y). Mode 6 (absolute set, teleports) is NOT hooked and snaps
;   immediately. Only step modes (0-3, 5) are delayed.
; - Gate: delay ONLY when no event script runs ($FF0110 == 0) AND the
;   world/room mode is 2 (room / B-zoom view). Cutscene ($FF0110 != 0)
;   and overworld (mode 1) update the camera immediately, exactly as
;   before. A script starting, or leaving mode 2, clears any pending
;   camera so no stale cell is ever applied.
; - Delay: one step. When leader_spawn computes a new camera (cell N+1)
;   during a walk, the hook does NOT write it. Instead it stores it as
;   the pending camera (PEND_X/PEND_Y) and leaves $FF0E8E/$FF0E90 at the
;   old cell (N). On the NEXT step-mode camera write (the next commit,
;   4 ticks later), the hook FIRST writes the pending camera (cell N+1)
;   to $FF0E8E/$FF0E90, THEN stores the new camera (cell N+2) as pending.
;   So the camera is always one step behind the figure's committed cell.
; - Effect: at a commit the figure is drawn at the screen centre (its
;   slide offset -step cancels the one-step cell offset), then it slides
;   smoothly toward centre+step over phases 1-3 while the room stays
;   still. At the next commit the camera jumps one cell (the room
;   scrolls) and the figure is back at centre. The slide IS visible on
;   screen. The room still jumps once per cell at the commit — fully
;   smoothing the world shift needs a fractional (smooth-scrolling)
;   camera, which is the big rework (scroll-and-patch), NOT this fix.
; - Cell rate is unchanged (1 cell / 4 ticks, the pacing gate). Speed is
;   not worse than the pacing ROM.
; - Edge case: if the player stops walking mid-step, the last step's
;   camera stays pending (never applied) and the figure sits ~14 px
;   off-centre until the next step, when it corrects. Harmless.
; - Registers: uses only d0 (the new camera value, an input) and absolute
;   addressing; no other register is touched, no stack use. Exits with
;   rts (jsr hook), never jmp.
;
; Blob at $FDE00 (0xFF padding in the base ROM; above the runtime
; checksum range $000000-$FD07B, so it does not affect the runtime sum,
; but the hook-site changes at $01C2D8/$01C300 do, and the header
; checksum covers the whole ROM — both are fixed by checksum.py fix-all).
; RAM used: $FFD010-$FFD014 (PEND_X/PEND_Y/PEND_VALID). Adjacent to the
; interp RAM ($FFD000-$FFD00E, proven safe); well below the feet-fix
; list ($FFD800+). No collision with the subcell latch, pacing blob,
; interp blob, or the probe state/log regions.

        org     $FDE00

; --- RAM state ---
PEND_X   equ     $FFD010  ; pending camera X (one step behind)
PEND_Y   equ     $FFD012  ; pending camera Y
PEND_VALID equ   $FFD014  ; 1 = a pending camera is stored

; --- game addresses ---
MODE     equ     $FF00AE  ; world/room mode flag (1 = overworld, 2 = room)
SCRIPT   equ     $FF0110  ; $FF0110 != 0 while an event script runs
CAMX     equ     $FF0E8E  ; camera X (cell)
CAMY     equ     $FF0E90  ; camera Y (cell)

; --- hook at $01C2D8: step-mode camera X write (d0 = new cam X) ---
camdelay_x:
        tst.w   SCRIPT
        bne     .immediate
        cmpi.w  #2,MODE
        bne     .immediate
        ; delay: apply the pending X (if any), store the new X as pending
        tst.w   PEND_VALID
        beq     .storex
        move.w  PEND_X,CAMX
.storex:
        move.w  d0,PEND_X
        rts
.immediate:
        ; no delay: clear any stale pending camera, write immediately
        clr.w   PEND_VALID
        move.w  d0,CAMX
        rts

; --- hook at $01C300: step-mode camera Y write (d0 = new cam Y) ---
camdelay_y:
        tst.w   SCRIPT
        bne     .immediate
        cmpi.w  #2,MODE
        bne     .immediate
        ; delay: apply the pending Y (if any), store the new Y as pending
        tst.w   PEND_VALID
        beq     .storey
        move.w  PEND_Y,CAMY
.storey:
        move.w  d0,PEND_Y
        move.w  #1,PEND_VALID
        rts
.immediate:
        ; no delay: clear any stale pending camera, write immediately
        clr.w   PEND_VALID
        move.w  d0,CAMY
        rts
