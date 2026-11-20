; source.s -- big-rework-full phase C: figures as sprites with
; per-frame interpolation.
;
; Base: rop-big-rework-full-b2.rom (MD5 ec7bcffe9c45fd851a6752dec5bcf788).
; The B2 blob is replaced wholesale: one contiguous blob at $FD400
; (4806 bytes, to $FE6C6), covering the 0xFF padding $FD400-$FD8FF
; plus B2's old blob region $FD900-$FDE30 plus the padding $FDE30-
; $FE6C6. The original ROM is 0xFF from $FDE30 to the end of the
; 1 MB ROM, so the blob may extend past $FE000; build.py asserts
; the padding before overwriting.
;
; What C does (see .scratch-big-rework-full/c-sprites/REPORT.md section 2):
; - The install draws TERRAIN ONLY: hero_track ($0231D8) and
;   map_promote_record ($02343A) are hooked; during the body's terrain
;   decode (redraw_entry, when installed) they return immediately,
;   so no figure is ever baked into the Plane B image. Kinds 2/3
;   (static/animated scenery) are NOT hooked and stay baked.
; - After the body returns, redraw_entry decodes up to K=3 figures
;   (the leader at window (5,5) always + 2 round-robin) by calling
;   the game's own hero_track / map_promote_record into the decode
;   buffer $FF1EC0 (the DMA upload has already finished -- dma_upload
;   polls the VDP busy bit -- so the buffer is free), scans the bbox,
;   and repack-copies the tiles into the VRAM pattern cache with a
;   sub-tile alignment shift (sx in {0,2,4,6}, sy in 0..7), so every
;   figure occupies at most 4x4 aligned tiles (20 with the feet row).
; - Every VBlank, the sprite updater steps each figure's CUR toward
;   its TARGET (clamped +-32/16 px horiz, +-18/16 vert per frame),
;   computes the screen position from CUR + installCam + scroll, and
;   writes the 12 figure sprites (8 bodies + 3 feet) + repairs the
;   chain through sprite 22. Figures hide when off-screen, when the
;   menu ($FF00AC) or dialog ($FF0114) is open, or when their pattern
;   is empty. No teleport ever: CUR only moves by the clamp.
;
; Sprite X/Y are stored +128 (Genesis convention; menu sprites at
; screen 150-201 confirm it). Hide = Y raw 0. Sprite word1 =
; (height<<10)|(width<<8)|link. Pattern word = tile index (palette
; 0, priority 0 -- figures index the same CRAM palette 0 as terrain).
;
; B2's camera-driven scroll + Scheme B gate are UNCHANGED (only
; re-assembled). scene_entry / mapclose_entry are B2's code and must
; assemble to the identical instruction stream (build.py checks).
; redraw_entry changes: it now WRAPS the body (jsr $1B922, body
; returns to the blob) instead of jumping to it, so the figure
; decode can run after the DMA.
;
; A jsr hook MUST exit with rts, never a plain jmp that leaks the
; return address. A hook that jmps ON into the hooked function MUST
; discard the hook jsr's return address FIRST (addq.w #4,sp) --
; otherwise the function's own rts returns to the hook site instead
; of the caller and the body re-executes with a corrupted frame
; (this was the D-crash bug: skip_hero/skip_promote ran without the
; discard and the stack collapsed to PC=0). The skip entries below
; discard the return on BOTH paths: the skip path discards and rts
; to the caller; the run path discards, re-executes the displaced
; prologue, and jmps on, so the function's rts returns to its caller.
; The VBlank hook is a jmp hook and resumes with jmp $127A.
;
; Assemble: vasmm68k_mot -m68000 -Fbin -o source.bin -L source.lst source.s
; (vasm Motorola syntax; entry offsets read from the listing, never
; hardcoded.)

	org 0

; --- sprite state ($FFD000-$FFD2FF; B2's $FF00A0-$FF00B2 scroll state
;     still used; install camera moved OFF $FF00BC/$FF00C0 -- $FF00C0
;     is the game's persistent merchant-attitude table (d-crash §7) --
;     to $FFD320/$FFD322, free RAM past the D governor state) ---
ICAM_X		equ	$FFD320	; word: install camera X ($FFFF = none yet)
ICAM_Y		equ	$FFD322	; word: install camera Y ($FFFF = none yet)
SPR_MAGIC	equ	$FFD000	; word $9C07 once initialised
SPR_RR		equ	$FFD002	; word: round-robin cursor (scan-list index)
SPR_SUPP	equ	$FFD004	; word: 1 = gate suppressed this tick
SPR_PEND	equ	$FFD006	; word: 1 = $FF0098 was set at redraw entry
SPR_SCRPTR	equ	$FFD008	; long: scratch pointer (cache_read arg, ignored)
SPR_SLOTS	equ	$FFD010	; 9 x 28-byte pattern slots (252 bytes)
SPR_SCAN_N	equ	$FFD10C	; word: figures found by the scan (<= 12)
SPR_SKIP	equ	$FFD10E	; word: 1 = skip figure draws (body decode)
SPR_SCAN	equ	$FFD110	; 12 x 6-byte scan entries: recIdx.w, r.w, c.w, kind.w
SPR_FEET	equ	$FFD158	; 3 x 4 bytes: ownerSlot.w, lru.w
SPR_LIVE	equ	$FFD164	; 12 bytes: sprite numbers in chain order, $FF terminated
SPR_VIS		equ	$FFD170	; 9 words: per-slot visible flag (body sprites)
; decode scratch ($FFD182+)
DEC_R		equ	$FFD182	; word: window row of the figure being decoded
DEC_C		equ	$FFD184	; word: window col
DEC_ARG		equ	$FFD186	; word: figure arg
DEC_D0B		equ	$FFD188	; word: d0b of the figure's cell
DEC_D1B		equ	$FFD18A	; word: d1b of the figure's cell
DEC_KIND	equ	$FFD18C	; word: draw-record kind (0/1)
DEC_REC		equ	$FFD18E	; word: draw-record index
REG_ROW0	equ	$FFD190	; word: clear/scan region first buffer row
REG_ROW1	equ	$FFD192	; word: clear/scan region last buffer row
REG_COL0	equ	$FFD194	; word: clear/scan region first buffer col
REG_COL1	equ	$FFD196	; word: clear/scan region last buffer col
BBOX_MIN	equ	$FFD198	; word: min buffer byte offset written ($FFFF = empty)
BBOX_MAX	equ	$FFD19A	; word: max buffer byte offset written
DEC_TX0		equ	$FFD19C	; word: aligned tile origin col
DEC_TY0		equ	$FFD19E	; word: aligned tile origin row
DEC_SX		equ	$FFD1A0	; word: sub-tile x shift (0,2,4,6)
DEC_SY		equ	$FFD1A2	; word: sub-tile y shift (0..7)
DEC_COLS	equ	$FFD1A4	; word: aligned tile cols (<= 4)
DEC_ROWS	equ	$FFD1A6	; word: aligned tile rows (<= 5)
DEC_TILE	equ	$FFD1A8	; word: body slot base tile index
DEC_FEET	equ	$FFD1AA	; word: feet quad index ($FFFF = none)
SLOT_SZ		equ	28
; slot struct: +0 recIdx ($FFFF empty), +2 state (0 empty, 1 live, 3 live+leader),
; +4 CURx, +6 CURy, +8 TGTx, +10 TGTy, +12 ax, +14 ay, +16 cols, +18 rows,
; +20 feetQuad ($FFFF none), +22 lastSeen, +24 scrX, +26 scrY
SLOT_REC	equ	0
SLOT_ST		equ	2
SLOT_CURX	equ	4
SLOT_CURY	equ	6
SLOT_TGTX	equ	8
SLOT_TGTY	equ	10
SLOT_AX		equ	12
SLOT_AY		equ	14
SLOT_COLS	equ	16
SLOT_ROWS	equ	18
SLOT_FEET	equ	20
SLOT_SEEN	equ	22
SLOT_SCRX	equ	24
SLOT_SCRY	equ	26

; --- game addresses used by the blob ---
VDP_DATA	equ	$C00000	; VDP data port (vdp_data_write writes one word here)
VDP_SETADDR	equ	$00DC60	; vdp_set_write_addr (long arg: VRAM byte address)
VDP_DATAWR	equ	$00D9EE	; vdp_data_write (word arg)
CACHE_READ	equ	$01C176	; map_chunk_cache_read (x, y, ptr) -> d0 = $FF0248
HERO_TRACK	equ	$0231D8	; hero_track (recPtr, d0b, d1b, arg)
PROMOTE		equ	$02343A	; map_promote_record (recPtr, d0b, d1b, arg)
REDRAW_BODY	equ	$01B922	; redraw_check body (after its prologue)
WAIT_VBLANK	equ	$01386A	; wait_vblank

; ------------------------------------------------------------------
; vbl_entry: VBlank hook. B2's camera-target scroll, UNCHANGED,
; plus the sprite update at .vdone (guarded by installed==1).
; Replicates the replaced instruction (move.w #$0,$FF0016),
; saves/restores d0-d5/a0-a1, resumes with jmp $127A.
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
	move.w #$FFFF,ICAM_X		; installCamX = none yet
	move.w #$FFFF,ICAM_Y		; installCamY = none yet
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
	move.w #$FFFF,ICAM_X
	move.w #$FFFF,ICAM_Y
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
	move.w #$FFFF,ICAM_X
	move.w #$FFFF,ICAM_Y
.vloc_ok:
	move.w $FF0E98,d0
	cmpi.w #156,d0
	bne .vnotroom
	tst.w $FF00A2
	beq .vdone
	; ---- B2: camera-target scroll ----
	; dx = camX - installCamX (d0), dy = camY - installCamY (d1).
	; installCam $FFFF means "none yet": target scroll 0.
	move.w ICAM_X,d2
	cmpi.w #$FFFF,d2
	beq .vtgt0
	move.w ICAM_Y,d2
	cmpi.w #$FFFF,d2
	beq .vtgt0
	move.w $FF0E8E,d0
	sub.w ICAM_X,d0		; d0 = dx
	move.w $FF0E90,d1
	sub.w ICAM_Y,d1		; d1 = dy
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
	; ---- C: sprite update (installed only; any location) ----
	tst.w $FF00A6
	beq .vskip_upd
	bsr sprite_update
.vskip_upd:
	movem.l (sp)+,d0-d5/a0-a1
	jmp $00127A			; resume the VBlank handler

; ------------------------------------------------------------------
; sprite_init: clear the sprite state (slots, feet pool, cursors)
; and set the magic. Called once, from sprite_update and from
; decode_figures (whichever runs first). Clobbers d0/a0.
sprite_init:
	move.w #$9C07,SPR_MAGIC
	clr.w SPR_RR
	clr.w SPR_SUPP
	clr.w SPR_PEND
	clr.w SPR_SKIP
	lea SPR_SLOTS,a0
	move.w #8,d0			; 9 slots
.si_clr:
	move.w #$FFFF,SLOT_REC(a0)
	clr.w SLOT_ST(a0)
	clr.l SLOT_CURX(a0)		; CURx + CURy
	clr.l SLOT_TGTX(a0)		; TGTx + TGTy
	clr.l SLOT_AX(a0)		; ax + ay
	clr.l SLOT_COLS(a0)		; cols + rows
	clr.w SLOT_FEET(a0)
	clr.w SLOT_SEEN(a0)
	clr.l SLOT_SCRX(a0)		; scrX + scrY
	lea SLOT_SZ(a0),a0
	dbra d0,.si_clr
	lea SPR_FEET,a0
	move.w #2,d0			; 3 quads
.si_clrf:
	move.w #$FFFF,(a0)+		; owner = none
	clr.w (a0)+			; lru
	dbra d0,.si_clrf
	rts

; ------------------------------------------------------------------
; interp_step: step *CUR toward *TGT by at most +step per call.
; a0 = &CUR (word), a1 = &TGT (word), d0 = +step (word).
; Clobbers d0-d1 only.
interp_step:
	move.w (a1),d1
	sub.w (a0),d1			; d1 = TGT - CUR
	beq .is_done
	bpl .is_pos
	neg.w d0			; d0 = -step
	cmp.w d0,d1			; diff vs -step
	bge .is_snap		; -step <= diff < 0: snap to target
	move.w (a0),d1
	add.w d0,d1			; CUR - step
	move.w d1,(a0)
	bra .is_done
.is_pos:
	cmp.w d0,d1			; diff vs +step
	ble .is_snap		; 0 < diff <= step: snap
	move.w (a0),d1
	add.w d0,d1			; CUR + step
	move.w d1,(a0)
	bra .is_done
.is_snap:
	move.w (a1),(a0)
.is_done:
	rts

; ------------------------------------------------------------------
; slot_sprite: d0 = pattern slot index (0..7) -> d0 = sprite number
; (68,69,70,72,73,74,75,76 -- slot 71 belongs to the game).
; Clobbers d0 only.
slot_sprite:
	addi.w #68,d0
	cmpi.w #71,d0
	blt .ss_done
	addq.w #1,d0
.ss_done:
	rts

; ------------------------------------------------------------------
; slot_tile: d0 = pattern slot index -> d0 = base tile index.
; Slot 0 -> $6F0; slots 1..8 -> $780+(i-1)*16. Clobbers d0 only.
slot_tile:
	tst.w d0
	beq .st_zero
	subq.w #1,d0
	asl.w #4,d0			; (i-1)*16
	addi.w #$780,d0
	rts
.st_zero:
	move.w #$6F0,d0
	rts

; ------------------------------------------------------------------
; find_link: d0 = sprite number -> d0 = link (the next sprite in
; the LIVEVEC chain order, or 23 if it is last / not in the list).
; Preserves d1-d7/a1-a6; clobbers d0/a0.
find_link:
	move.w d1,-(sp)
	lea SPR_LIVE,a0
.fl_scan:
	move.b (a0)+,d1
	cmpi.b #$FF,d1
	beq .fl_none
	cmp.b d0,d1
	bne .fl_scan
	move.b (a0),d1
	cmpi.b #$FF,d1
	beq .fl_none
	moveq #0,d0
	move.b d1,d0
	move.w (sp)+,d1
	rts
.fl_none:
	move.w #23,d0
	move.w (sp)+,d1
	rts

; ------------------------------------------------------------------
; write_sprite: write 4 words to a sprite's VRAM entry.
; d0 = sprite number, d1 = w0 (Y), d2 = w1 (size/link),
; d3 = w2 (pattern), d4 = w3 (X). Clobbers d0-d4/a0 (saves d5).
write_sprite:
	movem.l d5,-(sp)
	move.w d0,d5
	asl.w #3,d5
	add.w $FF8644,d5		; d5 = VRAM byte address
	moveq #0,d0
	move.w d5,d0
	move.l d0,-(sp)
	jsr VDP_SETADDR
	addq.w #4,sp
	move.w d1,-(sp)
	jsr VDP_DATAWR
	addq.w #2,sp
	move.w d2,-(sp)
	jsr VDP_DATAWR
	addq.w #2,sp
	move.w d3,-(sp)
	jsr VDP_DATAWR
	addq.w #2,sp
	move.w d4,-(sp)
	jsr VDP_DATAWR
	addq.w #2,sp
	movem.l (sp)+,d5
	rts

; ------------------------------------------------------------------
; write_sprite_w1: write word 1 (size/link) of a sprite's VRAM
; entry only (the game's sprite 22 keeps its Y/pattern/X).
; d0 = sprite number, d1 = word1. Clobbers d0-d1/a0 (saves d5).
write_sprite_w1:
	movem.l d5,-(sp)
	move.w d0,d5
	asl.w #3,d5
	add.w $FF8644,d5
	addq.w #2,d5			; word 1
	moveq #0,d0
	move.w d5,d0
	move.l d0,-(sp)
	jsr VDP_SETADDR
	addq.w #4,sp
	move.w d1,-(sp)
	jsr VDP_DATAWR
	addq.w #2,sp
	movem.l (sp)+,d5
	rts

; ------------------------------------------------------------------
; sprite_update: per-VBlank figure sprite positions. Called from
; vbl_entry when installed==1 (any location). Steps CUR toward
; TARGET, computes the screen position, hides off-screen /
; menu / dialog figures, writes the 12 figure sprites and
; repairs the chain through sprite 22. Saves/restores all regs.
sprite_update:
	movem.l d0-d7/a0-a6,-(sp)
	cmpi.w #$9C07,SPR_MAGIC
	beq .su_init_ok
	bsr sprite_init
.su_init_ok:
	; hide-all if menu open ($FF00AC) or dialog active ($FF0114)
	move.w $FF00AC,d6
	or.w $FF0114,d6		; d6 != 0 -> hide all
	; camera terms: d4 = 14*(icx-icy), d5 = 8*(icx+icy)
	move.w ICAM_X,d0
	sub.w ICAM_Y,d0		; d0 = icx-icy
	move.w d0,d4
	asl.w #4,d4
	move.w d0,d1
	asl.w #1,d1
	sub.w d1,d4			; d4 = 14*(icx-icy)
	move.w ICAM_X,d0
	add.w ICAM_Y,d0		; d0 = icx+icy
	asl.w #3,d0
	move.w d0,d5			; d5 = 8*(icx+icy)
	move.w $FF00B0,d2		; hScroll
	move.w $FF00B2,d3		; vScroll
	; ---- per-slot interpolation + screen position ----
	lea SPR_SLOTS,a6
	lea SPR_VIS,a4
	moveq #0,d7			; i = 0..8
.su_loop:
	move.w SLOT_ST(a6),d0
	beq .su_next		; empty slot: not visible
	; interpolate CUR toward TARGET (clamped per frame)
	lea SLOT_CURX(a6),a0
	lea SLOT_TGTX(a6),a1
	move.w #32,d0
	bsr interp_step
	lea SLOT_CURY(a6),a0
	lea SLOT_TGTY(a6),a1
	move.w #18,d0
	bsr interp_step
	; scrX = 212 + (CURx>>4) - d4 + ax + hScroll
	move.w SLOT_CURX(a6),d0
	asr.w #4,d0
	addi.w #212,d0
	sub.w d4,d0
	add.w SLOT_AX(a6),d0
	add.w d2,d0
	move.w d0,SLOT_SCRX(a6)
	; scrY = 98 + (CURy>>4) - d5 + ay - vScroll
	move.w SLOT_CURY(a6),d0
	asr.w #4,d0
	addi.w #98,d0
	sub.w d5,d0
	add.w SLOT_AY(a6),d0
	sub.w d3,d0
	move.w d0,SLOT_SCRY(a6)
	; visible = rows!=0 AND on-screen AND !hideAll
	move.w #0,(a4)
	tst.w d6
	bne .su_next
	tst.w SLOT_ROWS(a6)
	beq .su_next
	move.w SLOT_SCRX(a6),d0
	cmpi.w #-32,d0
	blt .su_next
	cmpi.w #320,d0
	bgt .su_next
	move.w SLOT_SCRY(a6),d0
	cmpi.w #-32,d0
	blt .su_next
	cmpi.w #224,d0
	bgt .su_next
	move.w #1,(a4)
.su_next:
	lea SLOT_SZ(a6),a6
	addq.w #2,a4
	addq.w #1,d7
	cmpi.w #9,d7
	blt .su_loop
	; ---- build the chain order (LIVEVEC): bodies, then feet ----
	lea SPR_LIVE,a5
	moveq #0,d7			; i = 0..7 (body sprites)
	lea SPR_VIS,a4
.su_lv:
	tst.w (a4)+
	beq .su_lv_next
	move.w d7,d0
	bsr slot_sprite
	move.b d0,(a5)+
.su_lv_next:
	addq.w #1,d7
	cmpi.w #8,d7
	blt .su_lv
	; feet quads 0..2: visible iff the owner slot is visible,
	; has 5 rows, and owns this quad
	moveq #0,d7			; q = 0..2
	lea SPR_FEET,a4
.su_lvf:
	move.w (a4),d0		; owner slot
	cmpi.w #$FFFF,d0
	beq .su_lvf_next
	lea SPR_VIS,a0
	move.w d0,d1
	asl.w #1,d1
	adda.w d1,a0
	tst.w (a0)
	beq .su_lvf_next
	lea SPR_SLOTS,a0
	move.w (a4),d1
	muls.w #SLOT_SZ,d1
	adda.w d1,a0
	cmpi.w #5,SLOT_ROWS(a0)
	bne .su_lvf_next
	cmp.w SLOT_FEET(a0),d7
	bne .su_lvf_next
	move.w d7,d0
	addi.w #77,d0
	move.b d0,(a5)+
.su_lvf_next:
	addq.w #4,a4
	addq.w #1,d7
	cmpi.w #3,d7
	blt .su_lvf
	move.b #$FF,(a5)		; terminate
	; ---- write the body sprites ----
	moveq #0,d7			; i = 0..7
	lea SPR_VIS,a4
.su_wr:
	move.w d7,d0
	bsr slot_sprite		; d0 = sprite number
	move.w d0,d6			; d6 = spr
	bsr find_link		; d0 = link
	move.w d0,d2
	ori.w #$0F00,d2		; d2 = w1 (size 3,3 + link)
	tst.w (a4)
	beq .su_wr_hidden
	lea SPR_SLOTS,a0
	move.w d7,d1
	muls.w #SLOT_SZ,d1
	adda.w d1,a0
	move.w SLOT_SCRY(a0),d1
	addi.w #128,d1		; d1 = w0 (Y raw)
	move.w SLOT_SCRX(a0),d4
	addi.w #128,d4		; d4 = w3 (X raw)
	move.w d7,d0
	bsr slot_tile		; d0 = base tile
	move.w d0,d3			; d3 = w2 (pattern)
	move.w d6,d0			; d0 = spr
	bsr write_sprite
	bra .su_wr_next
.su_wr_hidden:
	moveq #0,d1
	moveq #0,d3
	moveq #0,d4
	move.w d6,d0
	bsr write_sprite
.su_wr_next:
	addq.w #2,a4
	addq.w #1,d7
	cmpi.w #8,d7
	blt .su_wr
	; ---- write the feet sprites ----
	moveq #0,d7			; q = 0..2
	lea SPR_FEET,a4
.su_wrf:
	move.w (a4),d0		; owner slot
	cmpi.w #$FFFF,d0
	beq .su_wrf_hidden
	lea SPR_SLOTS,a0
	move.w d0,d1
	muls.w #SLOT_SZ,d1
	adda.w d1,a0
	lea SPR_VIS,a1
	move.w (a4),d1
	asl.w #1,d1
	adda.w d1,a1
	tst.w (a1)
	beq .su_wrf_hidden
	cmpi.w #5,SLOT_ROWS(a0)
	bne .su_wrf_hidden
	cmp.w SLOT_FEET(a0),d7
	bne .su_wrf_hidden
	; visible: w0 = scrY+32+128, w1 = $0300|link, w2 = quad tile,
	; w3 = scrX+128
	move.w d7,d0
	addi.w #77,d0
	move.w d0,d6			; d6 = spr
	move.w SLOT_SCRY(a0),d1
	addi.w #160,d1		; d1 = w0
	move.w SLOT_SCRX(a0),d4
	addi.w #128,d4		; d4 = w3
	move.w d7,d3
	addi.w #$6E4,d3		; d3 = w2 (quad tile)
	move.w d6,d0
	bsr find_link		; d0 = link (preserves d1-d4)
	move.w d0,d2
	ori.w #$0300,d2		; d2 = w1 (size 3,0 + link)
	move.w d6,d0
	bsr write_sprite
	bra .su_wrf_next
.su_wrf_hidden:
	move.w d7,d0
	addi.w #77,d0
	move.w d0,d6
	bsr find_link
	move.w d0,d2
	ori.w #$0300,d2
	moveq #0,d1
	moveq #0,d3
	moveq #0,d4
	move.w d6,d0
	bsr write_sprite
.su_wrf_next:
	addq.w #4,a4
	addq.w #1,d7
	cmpi.w #3,d7
	blt .su_wrf
	; ---- repair the chain: sprite 22's word1 -> first live, else 23 ----
	lea SPR_LIVE,a0
	move.b (a0),d0
	cmpi.b #$FF,d0
	beq .su_22none
	moveq #0,d1
	move.b d0,d1
	bra .su_22have
.su_22none:
	move.w #23,d1
.su_22have:
	ori.w #$0F00,d1		; size 3,3 + link
	move.w #22,d0
	bsr write_sprite_w1
	movem.l (sp)+,d0-d7/a0-a6
	rts

; ------------------------------------------------------------------
; redraw_entry: redraw_check hook (B2's gate/install, plus C's
; jsr-wrap and figure decode). Entered via jsr: discard the return,
; run the gate/install logic, re-execute the displaced prologue
; (link a6,#-2 ; tst.w $FF009C), call the body with jsr $1B922
; (it returns here -- the DMA upload has finished by then), then
; decode up to K=3 figures, restore the regs and rts to the main
; loop. The skip flag is set around the body call (when installed)
; so the body's terrain decode draws no figures.
redraw_entry:
	addq.w #4,sp
	movem.l d0-d7/a0-a6,-(sp)
	; snapshot: was a room decode pending? (the body and the gate
	; both clear $FF0098, so this must be read before either runs)
	move.w $FF0098,SPR_PEND
	clr.w SPR_SUPP
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
	move.w #$FFFF,ICAM_X
	move.w #$FFFF,ICAM_Y
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
	move.w $FF0E8E,ICAM_X		; installCamX = camera X
	move.w $FF0E90,ICAM_Y		; installCamY = camera Y
	bra .rdone
.rgate:
	; installed: camera-aware re-decode gate, room 156 only (fix2).
	; d0 = dx = camX - installCamX, d1 = dy = camY - installCamY.
	move.w $FF0E98,d0
	cmpi.w #156,d0
	bne .rdone
	move.w $FF0E8E,d0
	sub.w ICAM_X,d0		; d0 = dx
	move.w $FF0E90,d1
	sub.w ICAM_Y,d1		; d1 = dy
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
	move.w #1,SPR_SUPP		; C: the body will not decode
	clr.w $FF0098
	bra .rdone
.greinstall:
	; update the install camera to the current camera
	move.w $FF0E8E,ICAM_X
	move.w $FF0E90,ICAM_Y
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
	move.w #$FFFF,ICAM_X
	move.w #$FFFF,ICAM_Y
	bra .rdone
.rdone:
	; set the skip flag while the body decodes (installed only):
	; the body's terrain decode must not draw figures.
	tst.w $FF00A6
	beq .rnoskip
	move.w #1,SPR_SKIP
.rnoskip:
	; SECOND-BUG FIX (2026-11-20): restore redraw_check's registers
	; BEFORE calling the body (B2's order). The body must see the
	; caller's registers, not the gate/install's clobbered values --
	; running it clobbered sent the CPU to PC=0 at ~1 s (Buc's first
	; step) via a bad jump in the decode/DMA path. The jsr-wrap is
	; kept so decode_figures still runs after the body returns.
	movem.l (sp)+,d0-d7/a0-a6	; restore BEFORE the body
	link a6,#-2			; re-executed prologue
	move.w $FF009C,d0		; tst.w $FF009C (re-executed prologue)
	tst.w d0
	jsr REDRAW_BODY		; the body (returns here; DMA done)
	clr.w SPR_SKIP		; figures may draw again
	; figure decode, iff the body decoded this tick: a decode was
	; pending on entry, the gate did not suppress, and we are
	; installed (installCam valid).
	tst.w SPR_PEND
	beq .rnodecode
	tst.w SPR_SUPP
	bne .rnodecode
	tst.w $FF00A6
	beq .rnodecode
	bsr decode_figures
.rnodecode:
	rts				; to redraw_check's caller (main loop)

; ------------------------------------------------------------------
; decode_figures: scan the byte maps for kind 0/1 figures, decode
; up to K=3 (the leader at (5,5) always + 2 round-robin), and
; update the pattern slots. Called from redraw_entry after the
; body returns (the DMA has finished; $FF1EC0 is free).
; Saves/restores all regs.
; Subroutine convention in this section: a routine may clobber
; d0-d3/a0-a1 freely; anything else it uses, it saves itself.
decode_figures:
	movem.l d0-d7/a0-a6,-(sp)
	cmpi.w #$9C07,SPR_MAGIC
	beq .df_init_ok
	bsr sprite_init
.df_init_ok:
	; --- scan: (5,5) first (the leader), then all cells ---
	clr.w SPR_SCAN_N
	lea SPR_SCAN,a5			; list cursor
	moveq #5,d6
	moveq #5,d7
	bsr scan_cell
	clr.w d6				; r = 0
.df_r:
	clr.w d7				; c = 0
.df_c:
	cmp.w #5,d6
	bne .df_do
	cmp.w #5,d7
	beq .df_next			; (5,5) already done
.df_do:
	bsr scan_cell
.df_next:
	addq.w #1,d7
	cmpi.w #10,d7
	blt .df_c
	addq.w #1,d6
	cmpi.w #10,d6
	blt .df_r
	; --- free slots whose recIdx is not in the scan list ---
	bsr free_stale_slots
	; --- decode the leader first (scan[0] if it is (5,5)) ---
	move.w #0,d6				; decoded count
	move.w SPR_SCAN_N,d0
	beq .df_done			; no figures at all
	lea SPR_SCAN,a0
	cmpi.w #5,2(a0)			; scan[0].r == 5?
	bne .df_rr
	cmpi.w #5,4(a0)			; scan[0].c == 5?
	bne .df_rr
	bsr decode_one			; a0 = scan[0]
	addq.w #1,d6
	move.w #$FFFE,SPR_SCAN		; mark scan[0] decoded
.df_rr:
	; --- round-robin: more, starting at SPR_RR, one full pass ---
	cmpi.w #3,d6
	bge .df_done
	move.w SPR_SCAN_N,d5		; nFig
	move.w SPR_RR,d7			; idx
	cmp.w d5,d7
	blt .df_rr_ok
	clr.w d7				; cursor past the end: restart
.df_rr_ok:
	clr.w d4				; examined count
.df_rr_loop:
	cmp.w #3,d6
	bge .df_rr_done
	cmp.w d4,d5
	bge .df_rr_done			; examined all
	lea SPR_SCAN,a0
	move.w d7,d0
	muls.w #6,d0
	adda.w d0,a0
	addq.w #1,d7			; idx++
	cmp.w d5,d7
	blt .df_rr_nwrap
	clr.w d7				; wrap
.df_rr_nwrap:
	addq.w #1,d4			; examined++
	cmpi.w #$FFFE,(a0)
	beq .df_rr_loop			; already decoded
	bsr decode_one
	addq.w #1,d6
	move.w #$FFFE,(a0)			; mark decoded
	bra .df_rr_loop
.df_rr_done:
	move.w d7,SPR_RR			; next start index
.df_done:
	movem.l (sp)+,d0-d7/a0-a6
	rts

; ------------------------------------------------------------------
; scan_cell: look up the draw record mapped at window cell (r,c)
; and append it to the scan list if it is a kind 0/1 figure.
; in: d6 = r, d7 = c (words 0..9); a5 = list cursor (advanced on
; append). Preserves d6/d7/a5; clobbers d0-d3/a0-a1.
scan_cell:
	move.w SPR_SCAN_N,d0
	cmpi.w #12,d0
	bge .sc_ret			; list full
	; byte-map index = (r+1)*32 + (c+1)
	move.w d6,d0
	addq.w #1,d0
	asl.w #5,d0
	move.w d7,d1
	addq.w #1,d1
	add.w d1,d0
	lea $FFB76C,a0
	move.b (a0,d0.l),d1		; site 1, read first
	cmpi.b #$FF,d1
	bne .sc_have
	lea $FFB36C,a0
	move.b (a0,d0.l),d1		; site 2
	cmpi.b #$FF,d1
	beq .sc_ret
.sc_have:
	moveq #0,d2
	move.b d1,d2			; recIdx
	; kind = word at $FFB0CC + recIdx*12 + $A
	move.w d2,d3
	asl.w #3,d3
	move.w d2,d0
	asl.w #2,d0
	add.w d0,d3			; d3 = recIdx*12
	lea $FFB0CC,a0
	adda.w d3,a0
	move.w $A(a0),d1		; kind
	cmpi.w #1,d1
	bgt .sc_ret			; kinds 2/3 stay baked in the terrain
	; append: recIdx.w, r.w, c.w, kind.w
	move.w d2,(a5)+
	move.w d6,(a5)+
	move.w d7,(a5)+
	move.w d1,(a5)+
	addq.w #1,SPR_SCAN_N
.sc_ret:
	rts

; ------------------------------------------------------------------
; free_stale_slots: free every live slot whose recIdx is not in
; the current scan list (the figure left the install). Clobbers
; d0-d3/a0-a1 only.
free_stale_slots:
	lea SPR_SLOTS,a0		; slot pointer
	moveq #0,d2			; i = 0..8
.fs_loop:
	tst.w SLOT_ST(a0)
	beq .fs_next
	move.w SLOT_REC(a0),d0		; recIdx to find
	lea SPR_SCAN,a1
	move.w SPR_SCAN_N,d1
	beq .fs_free		; empty scan: free
.fs_scan:
	cmp.w (a1),d0
	beq .fs_next		; still present: keep
	lea 6(a1),a1
	subq.w #1,d1
	bne .fs_scan
.fs_free:
	move.w #$FFFF,SLOT_REC(a0)
	clr.w SLOT_ST(a0)
	bsr slot_release_feet		; a0 = slot
.fs_next:
	lea SLOT_SZ(a0),a0
	addq.w #1,d2
	cmpi.w #9,d2
	blt .fs_loop
	rts

; ------------------------------------------------------------------
; slot_release_feet: release a slot's feet quad, if any.
; in: a0 = slot pointer. Clobbers d0/a1 only.
slot_release_feet:
	move.w SLOT_FEET(a0),d0
	cmpi.w #$FFFF,d0
	beq .srf_done
	lea SPR_FEET,a1
	asl.w #2,d0			; q*4
	adda.w d0,a1
	move.w #$FFFF,(a1)		; owner = none
	move.w #$FFFF,SLOT_FEET(a0)
.srf_done:
	rts

; ------------------------------------------------------------------
; feet_alloc: allocate a feet quad for a slot. Returns d0 = quad
; index (0..2). Evicts the least-recently-used quad if all 3 are
; in use (the evicted owner loses its feet until its next decode).
; in: a0 = slot pointer (the new owner). Clobbers d0-d3/a0-a1.
; NOTE: the caller sets SLOT_FEET itself after this returns.
feet_alloc:
	; free quad?
	lea SPR_FEET,a0
	moveq #0,d0			; q = 0..2
.fa_free:
	cmpi.w #$FFFF,(a0)
	beq .fa_have
	lea 4(a0),a0
	addq.w #1,d0
	cmpi.w #3,d0
	blt .fa_free
	; none free: evict the quad with the largest lru (oldest)
	lea SPR_FEET,a0
	move.w 2(a0),d1		; lru[0]
	moveq #0,d0			; best q = 0
	move.w 6(a0),d2		; lru[1]
	cmp.w d1,d2
	bls .fa_cmp2
	move.w d2,d1
	moveq #1,d0
.fa_cmp2:
	move.w 10(a0),d2		; lru[2]
	cmp.w d1,d2
	bls .fa_have
	move.w d2,d1
	moveq #2,d0
.fa_have:
	; d0 = quad; clear its old owner (if any) and set lru = now
	lea SPR_FEET,a1
	move.w d0,d1
	asl.w #2,d1
	adda.w d1,a1
	move.w (a1),d2		; old owner slot
	cmpi.w #$FFFF,d2
	beq .fa_noowner
	lea SPR_SLOTS,a0
	muls.w #SLOT_SZ,d2
	adda.w d2,a0
	move.w #$FFFF,SLOT_FEET(a0)	; old owner loses its feet
.fa_noowner:
	move.w $FF0010,2(a1)		; lru = frame counter low word
	rts

; ------------------------------------------------------------------
; slot_alloc: find the slot for recIdx (d0), or allocate one
; (evicting the oldest non-leader slot if none is free).
; in: d0 = recIdx, d1 = isLeader (0/1). Returns a0 = slot pointer,
; d0 = 1 if the slot is newly assigned (snap CUR), 0 if it was
; already this figure's slot. Preserves d4-d7.
slot_alloc:
	movem.l d4-d7,-(sp)
	move.w d0,d6			; recIdx
	move.w d1,d7			; isLeader
	; search by recIdx
	lea SPR_SLOTS,a0
	moveq #0,d2
.sa_find:
	tst.w SLOT_ST(a0)
	beq .sa_next
	cmp.w SLOT_REC(a0),d6
	beq .sa_have_old
.sa_next:
	lea SLOT_SZ(a0),a0
	addq.w #1,d2
	cmpi.w #9,d2
	blt .sa_find
	; not found: find a free slot
	lea SPR_SLOTS,a0
	moveq #0,d2
.sa_free:
	tst.w SLOT_ST(a0)
	beq .sa_have_new
	lea SLOT_SZ(a0),a0
	addq.w #1,d2
	cmpi.w #9,d2
	blt .sa_free
	; none free: evict the oldest non-leader slot (max now-lastSeen)
	move.w $FF0010,d4		; now (low word)
	clr.w d5			; best age = 0
	moveq #-1,d3			; best index = -1
	lea SPR_SLOTS,a0
	moveq #0,d2
.sa_ev:
	cmpi.w #3,SLOT_ST(a0)
	beq .sa_ev_next		; never evict the leader
	tst.w SLOT_ST(a0)
	beq .sa_ev_next		; empty (cannot happen here)
	move.w d4,d0
	sub.w SLOT_SEEN(a0),d0		; age = now - lastSeen
	cmp.w d5,d0
	bls .sa_ev_next		; not older (unsigned)
	move.w d0,d5
	move.w d2,d3
.sa_ev_next:
	lea SLOT_SZ(a0),a0
	addq.w #1,d2
	cmpi.w #9,d2
	blt .sa_ev
	cmpi.w #-1,d3
	bne .sa_ev_have
	; all ages 0 (all decoded this same frame): take the first
	; non-leader live slot; last resort is slot 0.
	lea SPR_SLOTS,a0
	moveq #0,d2
.sa_ev_fb:
	cmpi.w #3,SLOT_ST(a0)
	beq .sa_ev_fbnext
	tst.w SLOT_ST(a0)
	bne .sa_ev_fbhave
.sa_ev_fbnext:
	lea SLOT_SZ(a0),a0
	addq.w #1,d2
	cmpi.w #9,d2
	blt .sa_ev_fb
	moveq #0,d2			; last resort: slot 0
.sa_ev_fbhave:
	move.w d2,d3
.sa_ev_have:
	lea SPR_SLOTS,a0
	move.w d3,d0
	muls.w #SLOT_SZ,d0
	adda.w d0,a0
	bsr slot_release_feet		; release its feet quad
	bra .sa_have_new
.sa_have_old:
	moveq #0,d0			; existing slot: no snap
	bra .sa_set
.sa_have_new:
	moveq #1,d0			; newly assigned: snap CUR
.sa_set:
	move.w d6,SLOT_REC(a0)
	tst.w d7
	beq .sa_plain
	move.w #3,SLOT_ST(a0)		; live + leader
	bra .sa_done
.sa_plain:
	move.w #1,SLOT_ST(a0)		; live
.sa_done:
	movem.l (sp)+,d4-d7
	rts

; ------------------------------------------------------------------
; decode_one: decode one figure and update its pattern slot.
; in: a0 = scan entry (recIdx.w, r.w, c.w, kind.w).
; Preserves d4-d7 (the round-robin state); clobbers d0-d3/a0-a3.
decode_one:
	movem.l d4-d7,-(sp)
	move.w (a0),DEC_REC		; recIdx
	move.w 2(a0),DEC_R		; r
	move.w 4(a0),DEC_C		; c
	move.w 6(a0),DEC_KIND		; kind
	move.w DEC_R,d6
	move.w DEC_C,d7
	; d0b = 196 - 14c + 14r ; d1b = 18 + 8(r+c)
	move.w d6,d0
	asl.w #4,d0
	move.w d6,d1
	asl.w #1,d1
	sub.w d1,d0			; d0 = 14r
	move.w d7,d1
	asl.w #4,d1
	move.w d7,d2
	asl.w #1,d2
	sub.w d2,d1			; d1 = 14c
	move.w #196,d2
	sub.w d1,d2
	add.w d0,d2			; d2 = d0b
	move.w d6,d0
	add.w d7,d0			; r+c
	asl.w #3,d0
	addi.w #18,d0			; d0 = d1b
	move.w d2,DEC_D0B
	move.w d0,DEC_D1B
	; mx = icx-5+r, my = icy-5+c
	move.w ICAM_X,d0
	add.w d6,d0
	subq.w #5,d0			; mx
	move.w ICAM_Y,d1
	add.w d7,d1
	subq.w #5,d1			; my
	; cellw = *map_chunk_cache_read(mx, my)
	pea.l $FFD008			; scratch pointer (routine ignores it)
	move.w d1,-(sp)
	move.w d0,-(sp)
	jsr CACHE_READ
	addq.w #8,sp
	movea.l d0,a1
	move.w (a1),d3			; cellw
	; tile = cellw & $1FF; rec5 = $5EDC4[tile*2]
	move.w d3,d0
	andi.w #$1FF,d0
	asl.w #1,d0
	lea $5EDC4,a1
	move.w (a1,d0.l),d0		; rec5
	; height = (cellw>>13)&7
	move.w d3,d1
	lsr.w #8,d1
	lsr.w #5,d1
	andi.w #7,d1			; height
	; arg = -(7*(height + rec5>>7&1) + 4*(rec5>>8&1))
	move.w d0,d2
	lsr.w #7,d2
	andi.w #1,d2
	add.w d2,d1			; height+bit7
	muls.w #7,d1
	move.w d0,d2
	lsr.w #8,d2
	andi.w #1,d2
	asl.w #2,d2			; 4*bit8
	add.w d2,d1
	neg.w d1			; d1 = arg
	move.w d1,DEC_ARG
	; --- clear the decode region ---
	bsr clear_region		; d1=arg, d6=r, d7=c
	; --- call the figure routine ---
	; recPtr = $FFB0CC + recIdx*12
	move.w DEC_REC,d0
	move.w d0,d2
	asl.w #3,d0
	asl.w #2,d2
	add.w d2,d0			; recIdx*12
	lea $FFB0CC,a1
	adda.w d0,a1
	; push (arg, d1b, d0b, recPtr)
	move.w DEC_ARG,-(sp)
	move.w DEC_D1B,-(sp)
	move.w DEC_D0B,-(sp)
	move.l a1,-(sp)
	tst.w DEC_KIND
	beq .do_hero
	jsr PROMOTE
	bra .do_called
.do_hero:
	jsr HERO_TRACK
.do_called:
	adda.w #10,sp
	; --- scan the bbox of what the routine wrote ---
	bsr scan_bbox
	; --- aligned tile origin / sub-tile shifts / span ---
	move.w BBOX_MIN,d0
	cmpi.w #$FFFF,d0
	bne .do_have
	; empty decode: rows = 0 (VBlank hides the sprite); the
	; TARGET is still updated below.
	clr.w DEC_COLS
	clr.w DEC_ROWS
	bra .do_slot
.do_have:
	; minx = BBOX_MIN % 1152 ; miny = BBOX_MIN / 1152
	; (divide by 1152 = 1024+128; use divu)
	moveq #0,d0
	move.w BBOX_MIN,d0
	move.w #1152,d1
	divu.w d1,d0			; d0 = (minx<<16)|miny
	move.w d0,d1			; miny
	swap d0
	move.w d0,d2			; minx
	; tx0 = minx//8, sx = minx%8; ty0 = miny//8, sy = miny%8
	move.w d2,d0
	lsr.w #3,d0			; tx0
	move.w d0,DEC_TX0
	move.w d2,d0
	andi.w #7,d0			; sx (0,2,4,6: minx always even)
	move.w d0,DEC_SX
	move.w d1,d0
	lsr.w #3,d0			; ty0
	move.w d0,DEC_TY0
	move.w d1,d0
	andi.w #7,d0			; sy
	move.w d0,DEC_SY
	; cols = maxx//8 - tx0 + 1 ; rows = maxy//8 - ty0 + 1
	moveq #0,d0
	move.w BBOX_MAX,d0
	move.w #1152,d1
	divu.w d1,d0
	move.w d0,d1			; maxy
	swap d0
	move.w d0,d2			; maxx
	lsr.w #3,d2
	sub.w DEC_TX0,d2
	addq.w #1,d2
	move.w d2,DEC_COLS		; <= 4
	lsr.w #3,d1
	sub.w DEC_TY0,d1
	addq.w #1,d1
	move.w d1,DEC_ROWS		; <= 5
.do_slot:
	; --- slot assignment ---
	; isLeader = (r == 5 && c == 5)
	moveq #0,d1			; isLeader = 0
	cmp.w #5,DEC_R
	bne .do_alloc
	cmp.w #5,DEC_C
	bne .do_alloc
	moveq #1,d1
.do_alloc:
	move.w DEC_REC,d0
	bsr slot_alloc			; a0 = slot, d0 = 1 if newly assigned
	movea.l a0,a3			; keep the slot pointer in a3
	move.w d0,d5			; snap flag (d0 is clobbered below)
	; TARGET = (224*mx - 224*my, 128*mx + 128*my)
	move.w ICAM_X,d0
	add.w DEC_R,d0
	subq.w #5,d0			; mx
	move.w ICAM_Y,d1
	add.w DEC_C,d1
	subq.w #5,d1			; my
	move.w d0,d2
	sub.w d1,d2			; mx - my
	muls.w #224,d2			; TGTx
	move.w d0,d3
	add.w d1,d3			; mx + my
	muls.w #128,d3			; TGTy
	; snap CUR if the slot is new, or the TARGET jumped > 1 cell
	; from the old TARGET (|dTGTx| > 448 or |dTGTy| > 256)
	tst.w d5				; snap flag from slot_alloc
	bne .do_snap
	; -- recompute: d0 = |TGTx - SLOT_TGTX| > 448?
	move.w d2,d0
	sub.w SLOT_TGTX(a3),d0
	bpl .do_dx
	neg.w d0
.do_dx:
	cmpi.w #448,d0
	bgt .do_snap
	move.w d3,d0
	sub.w SLOT_TGTY(a3),d0
	bpl .do_dy
	neg.w d0
.do_dy:
	cmpi.w #256,d0
	bgt .do_snap
	bra .do_nosnap
.do_snap:
	move.w d2,SLOT_CURX(a3)
	move.w d3,SLOT_CURY(a3)
.do_nosnap:
	move.w d2,SLOT_TGTX(a3)
	move.w d3,SLOT_TGTY(a3)
	; anchor = (tx0*8 - d0b, ty0*8 - d1b)
	move.w DEC_TX0,d0
	asl.w #3,d0
	sub.w DEC_D0B,d0
	move.w d0,SLOT_AX(a3)
	move.w DEC_TY0,d0
	asl.w #3,d0
	sub.w DEC_D1B,d0
	move.w d0,SLOT_AY(a3)
	move.w DEC_COLS,SLOT_COLS(a3)
	move.w DEC_ROWS,SLOT_ROWS(a3)
	move.w $FF0010,SLOT_SEEN(a3)
	; --- repack-copy to the VRAM cache (a3 = slot) ---
	; body base tile: slot 0 -> $6F0; slots 1..8 -> $780+(i-1)*16
	; (slot index = (a3 - SPR_SLOTS)/28)
	movea.l a3,a0
	suba.l #SPR_SLOTS,a0
	move.l a0,d0
	divu.w #SLOT_SZ,d0		; quotient (the index) in the low word
	move.w d0,d1			; index
	beq .do_tile0
	move.w #$780,d2
	subq.w #1,d1
	asl.w #4,d1			; (i-1)*16
	add.w d1,d2
	bra .do_tile
.do_tile0:
	move.w #$6F0,d2
.do_tile:
	move.w d2,DEC_TILE
	; feet: rows == 5 -> allocate a quad; else release
	cmpi.w #5,DEC_ROWS
	bne .do_nofeet
	movea.l a3,a0
	bsr feet_alloc			; d0 = quad
	move.w d0,DEC_FEET
	; set the quad's owner to this slot's index
	move.w d0,d1
	asl.w #2,d1
	lea SPR_FEET,a0
	adda.w d1,a0
	movea.l a3,a1
	suba.l #SPR_SLOTS,a1
	move.l a1,d2
	divu.w #SLOT_SZ,d2		; quotient (the index) in the low word
	move.w d2,(a0)			; owner = slot index
	move.w d0,SLOT_FEET(a3)
	bra .do_copy
.do_nofeet:
	movea.l a3,a0
	bsr slot_release_feet
	move.w #$FFFF,DEC_FEET
.do_copy:
	bsr repack_copy		; a3 = slot; reads DEC_* scratch
	movem.l (sp)+,d4-d7
	rts

; ------------------------------------------------------------------
; clear_region: zero the decode region in $FF1EC0 for the figure at
; (r,c) with arg. Stores the clipped bounds in REG_ROW0/1/COL0/1.
; in: d1 = arg, d6 = r, d7 = c. Clobbers d0-d3/a0-a1 only.
;   row0 = 8 + (arg>>3) + (r+c-10); rows = 9
;   col0 = 15 + (5*(r-c))/3 - 2; cols = 11
;   (arg is a multiple of 7 and <= 0, so arg>>3 is exact)
clear_region:
	movem.l d4-d5,-(sp)
	; row0 = 8 + (arg>>3) + (r+c-10)
	move.w d1,d0
	asr.w #3,d0			; arg>>3 (arithmetic: arg <= 0)
	addi.w #8,d0
	move.w d6,d2
	add.w d7,d2			; r+c
	subi.w #10,d2
	add.w d2,d0			; row0
	move.w d0,d4			; row0
	addq.w #8,d0			; row1 = row0+8
	move.w d0,d5			; row1
	; clip rows to [0..22]
	tst.w d4
	bpl .cr_r0ok
	clr.w d4
.cr_r0ok:
	cmpi.w #22,d5
	ble .cr_r1ok
	move.w #22,d5
.cr_r1ok:
	move.w d4,REG_ROW0
	move.w d5,REG_ROW1
	; col0 = 15 + (5*(r-c))/3 - 2
	move.w d6,d0
	sub.w d7,d0			; k = r-c
	muls.w #5,d0
	divs.w #3,d0			; (5k)/3, truncated toward zero
	addi.w #13,d0			; 15 - 2
	move.w d0,d4			; col0
	addi.w #10,d0			; col1 = col0+10
	move.w d0,d5			; col1
	; clip cols to [0..35]
	tst.w d4
	bpl .cr_c0ok
	clr.w d4
.cr_c0ok:
	cmpi.w #35,d5
	ble .cr_c1ok
	move.w #35,d5
.cr_c1ok:
	move.w d4,REG_COL0
	move.w d5,REG_COL1
	; clear rows [REG_ROW0..REG_ROW1], cols [REG_COL0..REG_COL1]
	move.w REG_ROW0,d0
.cr_row:
	; a0 = $FF1EC0 + row*1152 + col0*32
	move.w d0,d1
	muls.w #1152,d1			; row*1152
	move.w REG_COL0,d2
	asl.w #5,d2			; col0*32
	add.w d2,d1
	lea $FF1EC0,a0
	adda.w d1,a0
	; clear (col1-col0+1)*32 bytes = (col1-col0+1)*8 longwords
	move.w REG_COL1,d1
	sub.w REG_COL0,d1
	addq.w #1,d1
	asl.w #3,d1			; longwords
	subq.w #1,d1			; dbra count
.cr_col:
	clr.l (a0)+
	dbra d1,.cr_col
	addq.w #1,d0
	cmp.w REG_ROW1,d0
	ble .cr_row
	movem.l (sp)+,d4-d5
	rts

; ------------------------------------------------------------------
; scan_bbox: scan the clear region for nonzero bytes; store the
; min/max buffer byte offsets in BBOX_MIN/BBOX_MAX ($FFFF = empty).
; Clobbers d0-d3/a0-a1 only.
scan_bbox:
	movem.l d4-d7,-(sp)
	move.w #$FFFF,BBOX_MIN
	clr.w BBOX_MAX
	lea $FF1EC0,a0			; buffer base
	move.w REG_ROW0,d4		; row
.sb_row:
	; row byte offset = row*1152
	move.w d4,d0
	muls.w #1152,d0			; row*1152
	; a1 = buf + row*1152 + col0*32; d7 = byte offset of a1
	move.w REG_COL0,d1
	asl.w #5,d1
	add.w d1,d0
	move.w d0,d7			; byte offset
	lea (a0,d0.l),a1
	; longwords to scan = (col1-col0+1)*8
	move.w REG_COL1,d1
	sub.w REG_COL0,d1
	addq.w #1,d1
	asl.w #3,d1			; d1 = longword count
	subq.w #1,d1			; dbra count
.sb_lw:
	tst.l (a1)+
	beq .sb_next
	; nonzero longword at byte offset d7: scan its 4 bytes
	moveq #0,d2			; b = 0..3
.sb_byte:
	tst.b (a0,d7.l)
	beq .sb_bnext
	; nonzero byte at offset d7
	cmpi.w #$FFFF,BBOX_MIN
	bne .sb_max
	move.w d7,BBOX_MIN		; first: set both
.sb_max:
	move.w d7,BBOX_MAX		; monotonic: max grows
.sb_bnext:
	addq.w #1,d7
	addq.w #1,d2
	cmpi.w #4,d2
	blt .sb_byte
	bra .sb_lwdone
.sb_next:
	addq.w #4,d7
.sb_lwdone:
	dbra d1,.sb_lw
	addq.w #1,d4
	cmp.w REG_ROW1,d4
	ble .sb_row
	movem.l (sp)+,d4-d7
	rts

; ------------------------------------------------------------------
; repack_copy: copy the decoded figure from $FF1EC0 into the VRAM
; pattern cache, re-aligning by (sx,sy) into the slot's 16 body
; tiles (rows 0..3) and, if rows == 5, the feet quad (row 4).
; Tiles outside the bbox are zero-filled. Interrupts are masked
; for the whole sequence. in: a3 = slot; reads DEC_* scratch.
; Clobbers d0-d3/a0-a2 only (d4-d7 saved).
repack_copy:
	movem.l d4-d7,-(sp)
	move.w sr,-(sp)
	ori.w #$0700,sr			; mask interrupts
	; --- body: 16 tiles, tile-major (tc outer, tr inner) ---
	; set the VDP write address to the body slot's first tile
	move.w DEC_TILE,d0
	asl.w #5,d0			; tile*32 = VRAM byte address
	move.l d0,-(sp)
	jsr $DC60			; vdp_set_write_addr
	addq.w #4,sp
	moveq #0,d4			; tc = 0..3
.rc_tc:
	moveq #0,d5			; tr = 0..3
.rc_tr:
	; tile present? (tc < cols && tr < rows)
	cmp.w DEC_COLS,d4
	bge .rc_zero
	cmp.w DEC_ROWS,d5
	bge .rc_zero
	; write the 8 rows of tile (tc,tr)
	moveq #0,d6			; r = 0..7
.rc_row:
	; srcPxRow = ty0*8 + tr*8 + r + sy
	; srcTileRow = ty0 + tr + ((r+sy)>>3); srcRowInTile = (r+sy)&7
	move.w d6,d0
	add.w DEC_SY,d0		; r+sy
	move.w d0,d1
	andi.w #7,d1			; srcRowInTile
	move.w d0,d2
	lsr.w #3,d2			; (r+sy)>>3
	add.w DEC_TY0,d2
	add.w d5,d2			; srcTileRow
	; a0 = buf + (srcTileRow*36 + tx0+tc)*32 + srcRowInTile*4
	move.w d2,d0
	muls.w #36,d0
	add.w DEC_TX0,d0
	add.w d4,d0			; tile A
	asl.w #5,d0			; *32
	move.w d1,d2
	asl.w #2,d2			; srcRowInTile*4
	add.w d2,d0
	; past the buffer end? (a figure at the very bottom of the
	; window: the shift reads up to 7 px rows past the figure's
	; maxy. The threshold 26464 also covers tile B (+32).)
	cmpi.w #26464,d0
	bhs .rc_rz
	lea $FF1EC0,a0
	adda.w d0,a0
	move.l (a0),d0			; tile A row
	; a1 = tile B (tx0+tc+1), same row
	adda.w #32,a0
	move.l (a0),d1			; tile B row
	bra .rc_sh
.rc_rz:
	moveq #0,d0
	moveq #0,d1
.rc_sh:
	; apply the sx shift (d3 = sx>>1)
	move.w DEC_SX,d3
	lsr.w #1,d3			; 0..3
	beq .rc_w
	cmpi.w #1,d3
	beq .rc_s1
	cmpi.w #2,d3
	beq .rc_s2
	; case 3: out = (d0<<24) | (d1>>8)
	lsl.l #8,d0
	lsl.l #8,d0
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	or.l d2,d0
	bra .rc_w
.rc_s1:
	; out = (d0<<8) | (d1>>24)
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	lsr.l #8,d2
	lsr.l #8,d2
	or.l d2,d0
	bra .rc_w
.rc_s2:
	; out = (d0<<16) | (d1>>16)
	lsl.l #8,d0
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	lsr.l #8,d2
	or.l d2,d0
.rc_w:
	; write the 4 bytes high word first
	swap d0
	move.w d0,$C00000
	swap d0
	move.w d0,$C00000
	addq.w #1,d6
	cmpi.w #8,d6
	blt .rc_row
	bra .rc_next
.rc_zero:
	; zero-fill one tile (8 rows x 2 words)
	moveq #0,d0
	moveq #0,d6
.rc_zrow:
	move.w d0,$C00000
	move.w d0,$C00000
	addq.w #1,d6
	cmpi.w #8,d6
	blt .rc_zrow
.rc_next:
	addq.w #1,d5
	cmpi.w #4,d5
	blt .rc_tr
	addq.w #1,d4
	cmpi.w #4,d4
	blt .rc_tc
	; --- feet: 4 tiles (row 4), or all-zero if rows < 5 ---
	cmpi.w #$FFFF,DEC_FEET
	beq .rc_done			; no quad: nothing to write
	move.w DEC_FEET,d0
	asl.w #2,d0			; quad*4
	addi.w #$6E4,d0		; feet quad base tile
	asl.w #5,d0			; VRAM byte address
	move.l d0,-(sp)
	jsr $DC60
	addq.w #4,sp
	moveq #0,d4			; tc = 0..3
.rc_ftc:
	cmpi.w #5,DEC_ROWS
	bne .rc_fzero
	cmp.w DEC_COLS,d4
	bge .rc_fzero
	; write the 8 rows of feet tile (tc, tr=4)
	moveq #0,d6			; r = 0..7
.rc_frow:
	move.w d6,d0
	add.w DEC_SY,d0		; r+sy
	move.w d0,d1
	andi.w #7,d1			; srcRowInTile
	move.w d0,d2
	lsr.w #3,d2			; (r+sy)>>3
	add.w DEC_TY0,d2
	addq.w #4,d2			; srcTileRow = ty0+4+(...)
	; a0 = buf + (srcTileRow*36 + tx0+tc)*32 + srcRowInTile*4
	move.w d2,d0
	muls.w #36,d0
	add.w DEC_TX0,d0
	add.w d4,d0
	asl.w #5,d0
	move.w d1,d2
	asl.w #2,d2
	add.w d2,d0
	cmpi.w #26464,d0		; past the buffer end? (see body loop)
	bhs .rc_frz
	lea $FF1EC0,a0
	adda.w d0,a0
	move.l (a0),d0
	adda.w #32,a0
	move.l (a0),d1
	bra .rc_fsh
.rc_frz:
	moveq #0,d0
	moveq #0,d1
.rc_fsh:
	move.w DEC_SX,d3
	lsr.w #1,d3
	beq .rc_fw
	cmpi.w #1,d3
	beq .rc_fs1
	cmpi.w #2,d3
	beq .rc_fs2
	lsl.l #8,d0
	lsl.l #8,d0
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	or.l d2,d0
	bra .rc_fw
.rc_fs1:
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	lsr.l #8,d2
	lsr.l #8,d2
	or.l d2,d0
	bra .rc_fw
.rc_fs2:
	lsl.l #8,d0
	lsl.l #8,d0
	move.l d1,d2
	lsr.l #8,d2
	lsr.l #8,d2
	or.l d2,d0
.rc_fw:
	swap d0
	move.w d0,$C00000
	swap d0
	move.w d0,$C00000
	addq.w #1,d6
	cmpi.w #8,d6
	blt .rc_frow
	bra .rc_fnext
.rc_fzero:
	moveq #0,d0
	moveq #0,d6
.rc_fzrow:
	move.w d0,$C00000
	move.w d0,$C00000
	addq.w #1,d6
	cmpi.w #8,d6
	blt .rc_fzrow
.rc_fnext:
	addq.w #1,d4
	cmpi.w #4,d4
	blt .rc_ftc
.rc_done:
	move.w (sp)+,sr			; unmask interrupts
	movem.l (sp)+,d4-d7
	rts

; ------------------------------------------------------------------
; skip_hero / skip_promote: figure-draw skip hooks. Entered via jsr
; from the first bytes of hero_track ($0231D8) / map_promote_record
; ($02343A). If the skip flag is set (and the sprite state is
; initialised), discard the hook's return and rts to the figure
; routine's caller as if the routine returned immediately; else
; discard the hook's return FIRST, then re-execute the displaced
; prologue and jmp to the routine +6/+8 (the routine's own rts then
; returns to its caller). The stack stays balanced on both paths.
; (The run path WITHOUT the discard was the D-crash bug: the
; routine's rts returned to the hook site, the body re-ran with a
; corrupted frame, and the CPU reached PC=0.)
skip_hero:
	cmpi.w #$9C07,SPR_MAGIC
	bne .sh_run
	tst.w SPR_SKIP
	beq .sh_run
	; skip: discard the jsr return, return to the figure caller
	addq.w #4,sp
	rts
.sh_run:
	addq.w #4,sp			; D-CRASH FIX: discard hook jsr return
					; (without this, hero_track's rts returns
					; to the hook site and the body re-runs)
	link a6,#0			; displaced prologue
	move.l a3,-(sp)			; displaced prologue
	jmp $0231DE			; hero_track + 6
skip_promote:
	cmpi.w #$9C07,SPR_MAGIC
	bne .sp_run
	tst.w SPR_SKIP
	beq .sp_run
	addq.w #4,sp
	rts
.sp_run:
	addq.w #4,sp			; D-CRASH FIX: discard hook jsr return
					; (without this, promote's rts returns
					; to the hook site and the body re-runs)
	link a6,#0			; displaced prologue
	movem.l d4-d5/a3,-(sp)		; displaced prologue
	jmp $023442			; map_promote_record + 8

; ------------------------------------------------------------------
; scene_entry: world_map_draw hook (B1, UNCHANGED in B2/C).
; Entered via jsr: discard the return, reset the install state,
; re-execute the displaced prologue (link a6,#-4 ; pea.l $0CCAD8)
; and jump to $12C2A. Uses no registers, so nothing is saved.
scene_entry:
	addq.w #4,sp
	clr.w $FF00A6			; installed
	clr.w $FF00A2			; armed
	clr.w $FF00A8			; hAcc
	clr.w $FF00AA			; vAcc
	move.w #$FFFF,ICAM_X		; installCamX = none yet
	move.w #$FFFF,ICAM_Y		; installCamY = none yet
	link a6,#-4
	pea.l $000CCAD8
	jmp $012C2A

; ------------------------------------------------------------------
; mapclose_entry: world_map_redraw hook (B1, UNCHANGED in B2/C).
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
	move.w #$FFFF,ICAM_X		; installCamX = none yet
	move.w #$FFFF,ICAM_Y		; installCamY = none yet
	jsr $1386A			; wait_vblank (re-executed)
	jmp $016308
