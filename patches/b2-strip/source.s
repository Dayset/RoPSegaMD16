; source.s -- big-rework-full phase B2: Scheme B improved gate
; (fallback per the B2 brief: literal strip streaming, DESIGN 7.3, is
; unbuildable for the 36x23 image -- see
; .scratch-big-rework-full/b2-strip/REPORT.md section 3 and
; sim_strip.py: a strip decoded alone into a cleared buffer is
; 2.7-88.8% wrong vs the full render (per-nibble overlap composite),
; and repack+strip is 6.5-16.5% wrong (render order + height-stack
; status changes). R1 verifies the full re-decode re-centre is
; flicker-free, so Scheme B is acceptable.)
;
; Base: rop-big-rework-full-b1.rom (MD5 49530033f2f191d938e9f0ec3f86e845).
; The B1 blob is kept except vbl_entry. The ONE change in B2: the
; VBlank scroll follows the CAMERA, not the D-pad. Fix2's gate is
; seamless only once the pad-driven scroll has caught up to the
; camera move, but the scroll is pad-driven while the camera is
; game-driven, so catch-up is not guaranteed: cutscene/scripted
; moves (pad not held) stall the gate until dx grows past 1 cell
; and it fires the jumpy ">1 cell" branch mid-cutscene; a short
; tap / direction change leaves the picture frozen with a blank
; strip ("patch on the left") until the pad is held again.
; B2: each VBlank the hook computes the scroll target from
; (camera - installCam) -- target hAcc = clamp(-(dx-dy),-1,+1)*224,
; target vAcc = clamp((dx+dy),-1,+1)*128, the same formulas the
; gate uses for its expected values -- and steps the accumulators
; toward it at the existing rates (16/16 px horiz, 9/16 px vert
; per frame, ~14-15 fr per cell). Catch-up is now guaranteed
; within ~15 frames of ANY camera move (walked, scripted, or
; snapped), with no pad input, and the scroll self-corrects to 0
; whenever the camera returns to the install camera. The gate
; itself is UNCHANGED: exactly-1-cell + caught-up -> seamless
; re-install; >1 cell (teleport / mode-6 cut) -> immediate
; re-install, which is a cut, not a slide. The pad still walks
; Buc (which moves the camera, which moves the scroll); the PoC's
; "slide the picture without walking" demo goes away -- the full
; rework's scroll is camera-driven (DESIGN 5.3), and the 3-cell
; dead zone still gates when the camera moves.
; Cost per cell step stays the fix2 full re-decode (~16 fr).
;
; Four trampolines in one blob at $FD900 (0xFF padding past the
; runtime checksum's summed range $000000-$FD07B):
;   vbl_entry    -- VBlank hook ($1272): camera-target scroll (B2 NEW).
;   redraw_entry -- redraw_check hook ($1B918): Plane B install +
;                   camera-aware re-decode gate (fix2/B1, unchanged).
;   scene_entry  -- world_map_draw hook ($12C20): reset install
;                   state (B1, unchanged).
;   mapclose_entry -- world_map_redraw hook ($16302): reset install
;                   state on map close (B1, unchanged).
; State: dead RAM $FF00A0-$FF00C0, as B1 (magic $9C07, armed,
; installed, hAcc, vAcc, lastH, lastV, lastLoc, installCamX
; $FF00BC, installCamY $FF00C0; $FFFF = none yet). $FF00A4 NOT
; used (game tests it at $1CF3C).
; A jsr hook MUST exit with rts/jmp-on, never a plain jmp that
; leaks the return address. The VBlank hook is a jmp hook and
; resumes with jmp $127A; the jsr hooks discard their return
; (addq #4,sp) and re-execute the displaced prologue before
; jumping on.
;
; Assemble: vasmm68k_mot -m68000 -Fbin -o source.bin -L source.lst source.s
; (vasm Motorola syntax; entry offsets read from the listing, never
; hardcoded. The redraw/scene/mapclose entries must assemble
; byte-identical to the B1 blob -- build.py checks that.)

	org 0

; ------------------------------------------------------------------
; vbl_entry: VBlank hook. Replicates the replaced instruction
; (move.w #$0,$FF0016) then, if armed in room 156, steps the
; scroll accumulators toward the CAMERA target and writes the
; Plane B scroll via $DC16 only when it changed. Resets the
; install state when the location changes; disarms and restores
; scroll 0 when leaving room 156. Clobbers d0-d5/a0-a1
; (saved/restored).
vbl_entry:
	move.w #0,$FF0016		; replicate the replaced handler instr
	movem.l d0-d5/a0-a1,-(sp)
	cmpi.w #$9C07,$FF00A0
	beq .vok
	; init state
	move.w #$9C07,$FF00A0
	clr.w $FF00A2
	clr.w $FF00A6
	clr.w $FF00A8
	clr.w $FF00AA
	clr.w $FF00B0
	clr.w $FF00B2
	move.w #$FFFF,$FF00B4
	move.w #$FFFF,$FF00BC		; installCamX = none yet
	move.w #$FFFF,$FF00C0		; installCamY = none yet
	bra .vdone
.vok:
	; validate armed/installed in {0,1}
	move.w $FF00A2,d0
	cmpi.w #1,d0
	bls .vaok
	bra .vreset
.vaok:
	move.w $FF00A6,d0
	cmpi.w #1,d0
	bls .viok
	bra .vreset
.viok:
	; validate accumulator ranges
	move.w $FF00A8,d0
	cmpi.w #224,d0
	bgt .vreset
	cmpi.w #-224,d0
	blt .vreset
	move.w $FF00AA,d0
	cmpi.w #128,d0
	bgt .vreset
	cmpi.w #-128,d0
	blt .vreset
	bra .vmain
.vreset:
	clr.w $FF00A2
	clr.w $FF00A6
	clr.w $FF00A8
	clr.w $FF00AA
	clr.w $FF00B0
	clr.w $FF00B2
	move.w #$FFFF,$FF00BC
	move.w #$FFFF,$FF00C0
	bra .vdone
.vmain:
	; location change resets the install state (any door/teleport/
	; save-load into another location reinstalls on next decode)
	move.w $FF0E98,d0
	cmp.w $FF00B4,d0
	beq .vloc_ok
	move.w d0,$FF00B4
	clr.w $FF00A6
	clr.w $FF00A2
	clr.w $FF00A8
	clr.w $FF00AA
	move.w #$FFFF,$FF00BC
	move.w #$FFFF,$FF00C0
.vloc_ok:
	move.w $FF0E98,d0
	cmpi.w #156,d0
	bne .vnotroom
	tst.w $FF00A2
	beq .vdone
	; ---- B2: camera-target scroll ----
	; dx = camX - installCamX (d0), dy = camY - installCamY (d1).
	; installCam $FFFF means "none yet": target scroll 0.
	move.w $FF00BC,d2
	cmpi.w #$FFFF,d2
	beq .vtgt0
	move.w $FF00C0,d2
	cmpi.w #$FFFF,d2
	beq .vtgt0
	move.w $FF0E8E,d0
	sub.w $FF00BC,d0		; d0 = dx
	move.w $FF0E90,d1
	sub.w $FF00C0,d1		; d1 = dy
	; target hAcc in d2 = clamp(-(dx-dy),-1,+1)*224
	move.w d0,d2
	sub.w d1,d2			; d2 = dx-dy
	neg.w d2			; d2 = -(dx-dy)
	tst.w d2
	beq .th0
	bpl .thpos
	move.w #-224,d2
	bra .thhave
.thpos:
	move.w #224,d2
	bra .thhave
.th0:
	clr.w d2
.thhave:
	; target vAcc in d3 = clamp(dx+dy,-1,+1)*128
	move.w d0,d3
	add.w d1,d3			; d3 = dx+dy
	tst.w d3
	beq .tv0
	bpl .tvpos
	move.w #-128,d3
	bra .tvhave
.tvpos:
	move.w #128,d3
	bra .tvhave
.tv0:
	clr.w d3
	bra .tvhave
.vtgt0:
	clr.w d2
	clr.w d3
.tvhave:
	; step hAcc (d4) toward d2 by 16/frame, not past the target
	move.w $FF00A8,d4
	cmp.w d2,d4
	beq .vh_done
	blt .vh_up
	subi.w #16,d4
	cmp.w d2,d4
	bge .vh_set
	move.w d2,d4
	bra .vh_set
.vh_up:
	addi.w #16,d4
	cmp.w d2,d4
	ble .vh_set
	move.w d2,d4
.vh_set:
	move.w d4,$FF00A8
.vh_done:
	; step vAcc (d5) toward d3 by 9/frame, not past the target
	move.w $FF00AA,d5
	cmp.w d3,d5
	beq .vv_done
	blt .vv_up
	subi.w #9,d5
	cmp.w d3,d5
	bge .vv_set
	move.w d3,d5
	bra .vv_set
.vv_up:
	addi.w #9,d5
	cmp.w d3,d5
	ble .vv_set
	move.w d3,d5
.vv_set:
	move.w d5,$FF00AA
.vv_done:
	; hScroll = hAcc>>4, vScroll = vAcc>>4
	move.w d4,d0
	asr.w #4,d0
	move.w d5,d1
	asr.w #4,d1
	; write only when changed
	cmp.w $FF00B0,d0
	bne .vwrite
	cmp.w $FF00B2,d1
	bne .vwrite
	bra .vdone
.vwrite:
	move.w d0,$FF00B0
	move.w d1,$FF00B2
	bra .vscroll
.vnotroom:
	; outside room 156: disarm, keep `installed` (the overworld
	; keeps its clean Plane B install; it reinstalls per scene),
	; restore scroll 0 once if needed
	clr.w $FF00A2
	clr.w $FF00A8
	clr.w $FF00AA
	move.w $FF00B0,d0
	or.w $FF00B2,d0
	beq .vdone
	clr.w $FF00B0
	clr.w $FF00B2
	moveq #0,d0
	moveq #0,d1
	; fall through to .vscroll with (hScroll,vScroll) = (0,0)
.vscroll:
	; $DC16(a=0, b=vScroll, c=0, d=hScroll): push d, c, b, a
	move.w d0,-(sp)
	clr.w -(sp)
	move.w d1,-(sp)
	clr.w -(sp)
	jsr $DC16
	addq.w #8,sp
.vdone:
	movem.l (sp)+,d0-d5/a0-a1
	jmp $00127A			; resume the VBlank handler

; ------------------------------------------------------------------
; redraw_entry: redraw_check hook (B1, UNCHANGED in B2 -- transcribed
; to vasm syntax; must assemble byte-identical to the B1 blob).
; Entered via jsr: discard the return, run the gate/install logic,
; re-execute the displaced prologue (link a6,#-2 ; tst.w $FF009C)
; and jump to $1B922. The body's own rts then returns to
; redraw_check's caller.
redraw_entry:
	addq.w #4,sp
	movem.l d0-d7/a0-a6,-(sp)
	cmpi.w #$9C07,$FF00A0
	beq .rok
	; init state (same as VBlank hook)
	move.w #$9C07,$FF00A0
	clr.w $FF00A2
	clr.w $FF00A6
	clr.w $FF00A8
	clr.w $FF00AA
	clr.w $FF00B0
	clr.w $FF00B2
	move.w #$FFFF,$FF00B4
	move.w #$FFFF,$FF00BC
	move.w #$FFFF,$FF00C0
	bra .rdone
.rok:
	move.w $FF00A2,d0
	cmpi.w #1,d0
	bls .raok
	bra .rreset
.raok:
	move.w $FF00A6,d0
	cmpi.w #1,d0
	bls .riok
	bra .rreset
.riok:
	; installed? then gate (room 156 only)
	tst.w $FF00A6
	bne .rgate
	; not installed: transition only when a room decode is pending
	tst.w $FF0098
	beq .rdone
	; no scene tiles yet (should not happen in main_loop): retry later
	move.w $FF8674,d0
	beq .rdone
	; ---- transition: install the Plane B layout ----
	move.w #$8407,-(sp)		; R4 = $07: Plane B $E000 (B1)
	jsr $D9E2			; vdp_ctrl_write
	addq.w #2,sp
	move.w #$9001,-(sp)		; R16 = $01: planes 64x32
	jsr $D9E2
	addq.w #2,sp
	; fill Plane B name table ($E000, 64x32) with blank tile $7FF
	move.w #$07FF,-(sp)		; tile
	move.w #32,-(sp)		; rows
	move.w #64,-(sp)		; cols
	clr.w -(sp)			; y0
	clr.w -(sp)			; x0
	move.w #$40,-(sp)		; stride
	pea.l $0000E000			; dest: Plane B $E000 (B1)
	jsr $11A1A			; gfx_tilemap_fill
	adda.w #16,sp
	; draw the room name table into Plane B $E000
	move.w $FF8674,-(sp)		; base
	move.w #23,-(sp)		; rows
	move.w #36,-(sp)		; cols
	clr.w -(sp)			; y0
	move.w #2,-(sp)			; x0
	move.w #$40,-(sp)		; stride
	pea.l $0000E000			; dest: Plane B $E000 (B1)
	jsr $11820			; gfx_tilemap_draw
	adda.w #16,sp
	; blank the window room rect (rows 0-22, cols 2-37) with $7FF
	move.w #$07FF,-(sp)		; tile
	move.w #23,-(sp)		; rows
	move.w #36,-(sp)		; cols
	clr.w -(sp)			; y0
	move.w #2,-(sp)			; x0
	move.w #$40,-(sp)		; stride
	pea.l $00001000			; dest
	jsr $11A1A			; gfx_tilemap_fill
	adda.w #16,sp
	move.w #1,$FF00A6		; installed
	move.w #1,$FF00A2		; armed (scroll; VBlank gates on 156)
	clr.w $FF00A8
	clr.w $FF00AA
	; record the install camera (fix2): the gate compares against it
	move.w $FF0E8E,$FF00BC		; installCamX = camera X
	move.w $FF0E90,$FF00C0		; installCamY = camera Y
	bra .rdone
.rgate:
	; installed: camera-aware re-decode gate, room 156 only (fix2).
	; d0 = dx = camX - installCamX, d1 = dy = camY - installCamY.
	move.w $FF0E98,d0
	cmpi.w #156,d0
	bne .rdone
	move.w $FF0E8E,d0
	sub.w $FF00BC,d0		; d0 = dx
	move.w $FF0E90,d1
	sub.w $FF00C0,d1		; d1 = dy
	tst.w d0
	bne .gdxnz
	tst.w d1
	beq .gsuppress			; dx==0 and dy==0: camera unmoved
.gdxnz:
	; adx = |dx| in d2, ady = |dy| in d3
	move.w d0,d2
	bpl .gdxp
	neg.w d2
.gdxp:
	move.w d1,d3
	bpl .gdyp
	neg.w d3
.gdyp:
	; >1 cell away on either axis: reinstall now (1-cell jump;
	; teleport / fast move / scroll lagged)
	cmpi.w #1,d2
	bgt .greinstall
	cmpi.w #1,d3
	bgt .greinstall
	; exactly 1 cell away: reinstall only once the scroll has
	; caught up to the move, else suppress and wait.
	; Expected accumulators: hExp = -(dx-dy)*224, vExp = (dx+dy)*128.
	move.w d0,d4
	sub.w d1,d4			; d4 = dx - dy
	neg.w d4			; d4 = -(dx-dy)
	tst.w d4
	beq .gh0
	bpl .ghpos
	move.w #-224,d4		; hExp = -224
	bra .ghhave
.ghpos:
	move.w #224,d4			; hExp = +224
	bra .ghhave
.gh0:
	clr.w d4			; hExp = 0
.ghhave:
	cmp.w $FF00A8,d4
	bne .gsuppress			; hAcc != hExp: scroll still sliding
	move.w d0,d5
	add.w d1,d5			; d5 = dx + dy
	tst.w d5
	beq .gv0
	bpl .gvpos
	move.w #-128,d5		; vExp = -128
	bra .gvhave
.gvpos:
	move.w #128,d5			; vExp = +128
	bra .gvhave
.gv0:
	clr.w d5			; vExp = 0
.gvhave:
	cmp.w $FF00AA,d5
	bne .gsuppress			; vAcc != vExp: scroll still sliding
	; scroll caught up: the new image at scroll 0 is exactly the
	; old image at the scroll extreme -> seamless reinstall
	bra .greinstall
.gsuppress:
	clr.w $FF0098
	bra .rdone
.greinstall:
	; update the install camera to the current camera
	move.w $FF0E8E,$FF00BC
	move.w $FF0E90,$FF00C0
	; reset the scroll to (0,0) now (VDP + state) so the body's
	; fresh decode shows unshifted
	clr.w $FF00A8
	clr.w $FF00AA
	clr.w $FF00B0
	clr.w $FF00B2
	clr.w -(sp)			; $DC16(a=0, b=0, c=0, d=0)
	clr.w -(sp)
	clr.w -(sp)
	clr.w -(sp)
	jsr $DC16
	addq.w #8,sp
	; fall through to .rdone WITHOUT clearing $FF0098: the body
	; runs its decode+DMA for the new camera.
	bra .rdone
.rreset:
	clr.w $FF00A2
	clr.w $FF00A6
	clr.w $FF00A8
	clr.w $FF00AA
	clr.w $FF00B0
	clr.w $FF00B2
	move.w #$FFFF,$FF00BC
	move.w #$FFFF,$FF00C0
	bra .rdone
.rdone:
	movem.l (sp)+,d0-d7/a0-a6
	link a6,#-2
	move.w $FF009C,d0		; tst.w $FF009C (re-executed prologue)
	tst.w d0
	jmp $1B922

; ------------------------------------------------------------------
; scene_entry: world_map_draw hook (B1, UNCHANGED in B2).
; Entered via jsr: discard the return, reset the install state,
; re-execute the displaced prologue (link a6,#-4 ; pea.l $0CCAD8)
; and jump to $12C2A. Uses no registers, so nothing is saved.
scene_entry:
	addq.w #4,sp
	clr.w $FF00A6			; installed
	clr.w $FF00A2			; armed
	clr.w $FF00A8			; hAcc
	clr.w $FF00AA			; vAcc
	move.w #$FFFF,$FF00BC		; installCamX = none yet
	move.w #$FFFF,$FF00C0		; installCamY = none yet
	link a6,#-4
	pea.l $000CCAD8
	jmp $012C2A

; ------------------------------------------------------------------
; mapclose_entry: world_map_redraw hook (B1, UNCHANGED in B2).
; Entered via jsr at $16302 (displacing `jsr wait_vblank.l`):
; discard the return, reset the install state, re-execute the
; displaced `jsr wait_vblank` and jump to $16308. The body's own
; rts then returns to the map-close block's caller ($170A2).
mapclose_entry:
	addq.w #4,sp
	clr.w $FF00A6			; installed
	clr.w $FF00A2			; armed
	clr.w $FF00A8			; hAcc
	clr.w $FF00AA			; vAcc
	move.w #$FFFF,$FF00BC		; installCamX = none yet
	move.w #$FFFF,$FF00C0		; installCamY = none yet
	jsr $1386A			; wait_vblank (re-executed)
	jmp $016308
