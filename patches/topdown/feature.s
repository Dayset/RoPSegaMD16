; topdown feature.s — top-down smooth-scrolling test view on the original
; engine (issue #249). Game logic, input, menus, messages, map data and
; RAM are the original's; only the world picture is replaced:
;
;   * the world is drawn top-down on Plane A/B (name table $0000, 64x32
;     tiles) as 16x16 blocks, one per map cell, using the game's own map
;     tileset (record 10 + descriptor table $1AE98, the tiles the map
;     screen uses) pixel-doubled to 2x2 tiles at load time;
;   * characters with a map-draw record are 16x16 sprite "blobs"
;     (yellow = the party leader's figure, white = everyone else);
;   * every frame the camera, the hardware scroll and the blob positions
;     are recomputed: blobs slide from their previous cell to their new
;     cell over one game tick, the camera follows the leader's blob, and
;     the plane is a ring buffer that gets one new column/row of cells
;     when the camera crosses a cell edge (Landstalker/Sonic streaming);
;   * the room render (clear 26 KB + 10x10 terrain decode + 26 KB DMA
;     during active display, ~20 frames/tick) is removed; the main loop
;     is frame-locked instead: each world tick takes exactly TD_T1
;     frames in the overworld and TD_T2 in rooms (the original's
;     measured average pace), and the waiting time is spent updating the
;     picture once per frame.
;
; The window plane keeps the HUD, messages and menus exactly as the game
; draws them; the room-bitmap cells of the window are pointed at the
; transparent font blank so the world shows through.
;
; Hooks (hooks.csv):
;   $01B958  jsr clear_decode_buffer        -> jsr td_tick (+ bra past
;            the map_chunk_pos call, bytes hook at $01B95E)
;   $01B9D0  move.w #$33C0,-(a7) (room DMA) -> bra $01B9F2 (DMA skipped,
;            $FF0098 still cleared by the instruction before)
;   $01B97E  jsr menu_format -> jsr td_menufmt (menu_format waits for
;            a VBlank and rewrites the HUD sprites; update right after)
;   $00D2BE  tst.w $FF00AC (main loop head) -> jsr td_poll_head
;   $00D97E  jsr combat_turn_run -> jsr td_poll_turn
;   $013876  move.w $FF0016,d0 (wait_vblank's loop) -> jsr td_wv
;   $0118A6  jsr vdp_data_write (gfx_tilemap_draw) -> jsr td_vdw
;   $01191A  jsr vdp_data_write (gfx_tilemap_fill_seq) -> jsr td_vdw
;   $0227FC  move.w d4,d0 / muls.w #$34,d0 (combat_turn_run char loop
;            head) -> jsr td_poll (one picture update per new frame
;            while the per-character logic runs)
;
; RAM: $FFDC00-$FFDF17 (free in play: the attract buffer ends at
; $FFDBEA, the stack low-water mark seen on the playtest routes is
; $FFE972; the boot RAM clear resets it).

	org ORGVAL

; ---- tuning ----------------------------------------------------------
TD_T1		equ 26		; frames per world tick, overworld (orig avg 26.5)
TD_T2		equ 17		; frames per world tick, rooms (orig 17.0)
TD_SLOT0	equ 68		; first sprite slot for blobs (game uses <= 67)
TD_NSLOT	equ 12		; blob sprites max
TD_VC		equ 84		; screen line the leader is centred on

; ---- game addresses --------------------------------------------------
FRAME		equ $FF0012	; low word of the VBlank counter
MODE		equ $FF00AE	; 1 overworld, 2 room
LOC		equ $FF0E98	; location ($FFFF = overworld)
LEADER		equ $FF02B2	; party leader char index
CHARS		equ $FF02B4	; 56 x $34 char structs
RECS		equ $FFB0CC	; 56 x 12 map-draw records
GRIDPTR		equ $FFA7FC	; -> geometry struct (+0 W, +2 H)
BANKBASE	equ $FF8674	; room bitmap tile base ($38E)
FONTBLK		equ $FF8640	; transparent font blank tile
SPRBASE		equ $FF8644	; sprite table base ($2400 in layout G)
VDP_DATA	equ $C00000
VDP_CTRL	equ $C00004
CELLREAD	equ $01C176	; map_chunk_cache_read(x, y) -> d0 = ptr to word
MAPDECODE	equ $01383C	; map_decode(rec) -> d0 = $FF1EC0
DMAUP		equ $00DA04	; dma_upload(src.l, dest.l, words.w)
DESC		equ $01AE98	; 512-word map tile descriptors
DECBUF		equ $FF1EC0	; decode buffer (free while top-down runs)

; ---- state -----------------------------------------------------------
TD		equ $FFDC00
TD_MAGIC	equ TD+$00	; $7D7D when initialised
TD_VALID	equ TD+$02	; plane content valid
TD_TILES	equ TD+$04	; tiles uploaded
TD_LASTFR	equ TD+$06	; frame of the last picture update
TD_TICKFR	equ TD+$08	; frame the last tick ended
TD_MODE		equ TD+$0A
TD_LOC		equ TD+$0C
TD_CAMX		equ TD+$0E	; camera: world pixel at screen (0,0)
TD_CAMY		equ TD+$10
TD_CX0		equ TD+$12	; first drawn cell column / row
TD_CY0		equ TD+$14
TD_PERIOD	equ TD+$16	; current tick period (frames)
TD_BASE		equ TD+$18	; VRAM tile index of our tiles
TD_W		equ TD+$1A	; map size in cells
TD_H		equ TD+$1C
TD_GRID		equ TD+$1E	; long: geometry struct pointer
TD_MAPSENT	equ TD+$22	; expected word inside map tile 128
TD_NB		equ TD+$24	; blobs in the list
TD_LEADOK	equ TD+$26	; leader position valid
TD_LEADX	equ TD+$28	; leader world pixel
TD_LEADY	equ TD+$2A
TD_GHEAD	equ TD+$2C	; game's first sprite (sprite 0's own link)
TD_LIST		equ TD+$40	; TD_NSLOT x (px.w, py.w, var.w) = 72 B
TD_CHR		equ TD+$90	; 56 x 10: lx, ly (target cell), fpx, fpy (from px), t0
TD_ROW		equ TD+$2D0	; 36-word window row buffer
TD_END		equ TD+$318

NOPOS		equ $8000

;=======================================================================
; td_tick — replaces the room render in redraw_check. Syncs the view
; with the game, then waits out the rest of the tick, updating the
; picture once per frame.
;=======================================================================
td_tick:
	movem.l	d0-d7/a0-a6,-(a7)
	moveq	#TD_T2,d0
	cmpi.w	#1,MODE
	bne.s	.per
	moveq	#TD_T1,d0
.per:
	move.w	d0,TD_PERIOD
	moveq	#0,d7			; synced yet?
.wait:
	move.w	FRAME,d0
	cmp.w	TD_LASTFR,d0
	beq.s	.wait			; once per frame:
	move.w	VDP_CTRL,d1
	btst	#3,d1
	beq.s	.late
	bsr.w	td_frame		; in VBlank: update the picture
	bra.s	.upd
.late:	move.w	d0,TD_LASTFR		; past VBlank: skip (no tearing)
.upd:	tst.w	d7
	bne.s	.chk
	bsr.w	td_sync			; right after an update, so the
	moveq	#1,d7			; sync work never straddles a VBlank
.chk:	move.w	FRAME,d0
	move.w	d0,d1
	sub.w	TD_TICKFR,d1		; frames since the last tick ended
	cmp.w	TD_PERIOD,d1
	bcs.s	.wait			; < period: keep waiting
	move.w	d0,TD_TICKFR		; game logic starts near the top of
	movem.l	(a7)+,d0-d7/a0-a6	; a frame, right after an update
	rts

;=======================================================================
; td_poll — combat_turn_run char-loop head: picture update if a new
; frame started, then the two displaced instructions.
;=======================================================================
td_poll:
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.skip
	move.w	FRAME,d0
	cmp.w	TD_LASTFR,d0
	beq.s	.skip
	move.w	VDP_CTRL,d0		; only inside VBlank (no mid-frame
	btst	#3,d0			; scroll change = no tearing); a later
	beq.s	.skip			; poll in this VBlank or the next does it
	bsr.w	td_frame
.skip:
	movem.l	(a7)+,d0-d7/a0-a6
	move.w	d4,d0
	muls.w	#$34,d0
	rts

;=======================================================================
; td_menufmt — redraw_check's menu_format call. menu_format waits for a
; VBlank and then rewrites the HUD sprites, sprite 0's link included
; (which unhooks our blobs). Update right behind it, in that VBlank.
;=======================================================================
td_menufmt:
	jsr	($0138A8).l		; menu_format
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.skip
	tst.w	TD_VALID
	beq.s	.skip
	move.w	FRAME,d0
	cmp.w	TD_LASTFR,d0
	beq.s	.relink
	move.w	VDP_CTRL,d0		; still in VBlank: full update
	btst	#3,d0
	beq.s	.relink
	bsr.w	td_frame
	bra.s	.skip
.relink:				; mid-frame: only re-hook the blobs
	cmpi.w	#$2400,SPRBASE		; (same positions; scroll untouched,
	bne.s	.skip			; so no tear)
	bsr.w	td_sprites
.skip:	movem.l	(a7)+,d0-d7/a0-a6
	rts

;=======================================================================
; td_poll_head — main loop head ($00D2BE): poll, then the displaced
; `tst.w $FF00AC` (its flags survive the rts).
; td_poll_turn — main loop `jsr combat_turn_run`: poll, then the call.
;=======================================================================
td_poll_head:
	bsr.s	td_poll_vb
	tst.w	$FF00AC
	rts

td_poll_turn:
	bsr.s	td_poll_vb
	jmp	($0226BC).l		; combat_turn_run (returns to the caller)

td_poll_vb:
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.skip
	move.w	FRAME,d0
	cmp.w	TD_LASTFR,d0
	beq.s	.skip
	move.w	VDP_CTRL,d0
	btst	#3,d0
	beq.s	.skip
	bsr.w	td_frame
.skip:	movem.l	(a7)+,d0-d7/a0-a6
	rts

;=======================================================================
; td_wv — wait_vblank's wait loop ($013876: move.w $FF0016,d0). Wait as
; the original does, then a no-streaming update in that VBlank (game
; routines that wait for a VBlank — messages, menus, the HUD sprite
; update — no longer freeze the picture). Returns d0 = 0 / Z set so
; the original `bne` falls through to `unlk; rts`.
;=======================================================================
td_wv:
.w:	tst.w	$FF0016
	bne.s	.w
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.skip
	move.w	FRAME,d0
	cmp.w	TD_LASTFR,d0
	beq.s	.skip
	bsr.w	td_frame_ns
.skip:	movem.l	(a7)+,d0-d7/a0-a6
	moveq	#0,d0
	rts

;=======================================================================
; td_vdw — vdp_data_write (same stack argument) for the name-table word
; writes of gfx_tilemap_draw ($0118A6) and gfx_tilemap_fill_seq
; ($01191A). While the top-down view owns the room bank, a word that
; points into the room bitmap (bank tile, no flags) is written as the
; transparent font blank instead, so the game's own redraws of the
; room area (scene setup, menu/panel close, message band) never show
; our tiles through the window.
;=======================================================================
td_vdw:
	move.w	4(a7),d0
	bsr.s	td_filt
	move.w	d0,VDP_DATA
	rts

td_filt:				; d0 = word -> d0 = word to write
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.keep
	tst.w	TD_TILES
	beq.s	.keep
	cmpi.w	#$2400,SPRBASE
	bne.s	.keep
	move.w	d1,-(a7)
	move.w	d0,d1
	andi.w	#$F800,d1		; no palette / priority / flips
	bne.s	.k1
	move.w	d0,d1
	sub.w	BANKBASE,d1
	cmpi.w	#828,d1
	bcc.s	.k1
	move.w	FONTBLK,d0
.k1:	move.w	(a7)+,d1
.keep:	rts

;=======================================================================
; td_sync — (re)install the view when the scene changed under us.
;=======================================================================
td_sync:
	move.w	MODE,d0
	cmpi.w	#1,d0
	beq.s	.mok
	cmpi.w	#2,d0
	bne.w	.out
.mok:
	cmpi.w	#$2400,SPRBASE		; game layout G only
	bne.w	.out
	cmpi.w	#$7D7D,TD_MAGIC
	beq.s	.inited
	lea	TD,a0
	move.w	#(TD_END-TD)/2-1,d1
.clr:	clr.w	(a0)+
	dbra	d1,.clr
	move.w	#$7D7D,TD_MAGIC
	move.w	FRAME,TD_TICKFR
	move.w	#TD_T2,TD_PERIOD
	bsr.w	td_chr_reset
.inited:
	move.w	#$8F02,VDP_CTRL		; auto-increment 2
	move.w	#$9001,VDP_CTRL		; planes 64x32 (A/B table $0000)
	move.w	BANKBASE,d0
	cmp.w	TD_BASE,d0
	beq.s	.bok
	move.w	d0,TD_BASE
	clr.w	TD_TILES
	clr.w	TD_VALID
.bok:
	movea.l	GRIDPTR,a0
	cmpa.l	TD_GRID,a0
	bne.s	.newmap
	move.w	MODE,d0
	cmp.w	TD_MODE,d0
	bne.s	.newmap
	move.w	LOC,d0
	cmp.w	TD_LOC,d0
	beq.s	.same
.newmap:
	move.l	a0,TD_GRID
	move.w	(a0),TD_W
	move.w	2(a0),TD_H
	move.w	MODE,TD_MODE
	move.w	LOC,TD_LOC
	clr.w	TD_VALID
	bsr.w	td_chr_reset
.same:
	bsr.w	td_tiles_check		; reload tiles if overwritten
	tst.w	TD_TILES
	bne.s	.tok
	bsr.w	td_tiles_load
	clr.w	TD_VALID
.tok:
	bsr.w	td_winfix		; window only; the plane is checked next
	tst.w	TD_VALID
	beq.s	.redraw
	bsr.w	td_plane_check
	tst.w	d0
	beq.s	.out
.redraw:
	bsr.w	td_chars
	bsr.w	td_camera
	move.w	d0,TD_CAMX
	move.w	d1,TD_CAMY
	asr.w	#4,d0
	asr.w	#4,d1
	move.w	d0,TD_CX0
	move.w	d1,TD_CY0
	bsr.w	td_draw_all
	bsr.w	td_scroll
	move.w	#1,TD_VALID
.out:
	rts

;=======================================================================
; td_frame — one picture update: blobs, camera, scroll, streaming.
; td_frame_ns — the same without streaming (no game calls): used from
; inside wait_vblank, where the caller may hold game state; the camera
; is then clamped to the cells already in the plane.
;=======================================================================
td_frame:
	moveq	#1,d1
	bra.s	td_frame_go
td_frame_ns:
	moveq	#0,d1
td_frame_go:
	move.w	FRAME,TD_LASTFR
	tst.w	TD_VALID
	beq.w	.out
	cmpi.w	#$2400,SPRBASE
	bne.w	.out
	movea.l	GRIDPTR,a0
	cmpa.l	TD_GRID,a0
	bne.w	.out
	move.w	MODE,d0
	cmp.w	TD_MODE,d0
	bne.w	.out
	move.w	LOC,d0
	cmp.w	TD_LOC,d0
	bne.w	.out
	move.w	d1,-(a7)
	bsr.w	td_plane_check		; another screen owns the plane?
	move.w	(a7)+,d1
	tst.w	d0
	bne.w	.out
	move.w	#$8F02,VDP_CTRL
	; menu open ($FF00AC): the world pauses under the game's own panels;
	; blobs are taken off so they never sit on top of a panel
	tst.w	$FF00AC
	beq.s	.world
	clr.w	TD_NB
	bsr.w	td_sprites
	rts
.world:
	move.w	d1,-(a7)
	bsr.w	td_chars
	bsr.w	td_camera
	move.w	(a7)+,d2
	bne.s	.cam
	move.w	TD_CX0,d3		; no streaming: stay inside the plane
	lsl.w	#4,d3
	cmp.w	d3,d0
	bge.s	.c1
	move.w	d3,d0
.c1:	add.w	#16,d3
	cmp.w	d3,d0
	ble.s	.c2
	move.w	d3,d0
.c2:	move.w	TD_CY0,d3
	lsl.w	#4,d3
	cmp.w	d3,d1
	bge.s	.c3
	move.w	d3,d1
.c3:	add.w	#16,d3
	cmp.w	d3,d1
	ble.s	.cam
	move.w	d3,d1
.cam:	move.w	d0,TD_CAMX
	move.w	d1,TD_CAMY
	bsr.w	td_scroll		; vblank-critical first
	bsr.w	td_sprites
	tst.w	d2
	beq.s	.out
	bsr.w	td_stream
.out:
	rts

;=======================================================================
; td_scroll — full-screen scroll of planes A and B to the camera.
;=======================================================================
td_scroll:
	move.w	TD_CAMX,d0
	neg.w	d0
	andi.w	#$3FF,d0
	move.w	d0,d1
	swap	d0
	move.w	d1,d0
	move.l	#$60000000,VDP_CTRL	; VRAM write $2000 (H-scroll table)
	move.l	d0,VDP_DATA
	move.w	TD_CAMY,d0
	andi.w	#$3FF,d0
	move.w	d0,d1
	swap	d0
	move.w	d1,d0
	move.l	#$40000010,VDP_CTRL	; VSRAM write 0
	move.l	d0,VDP_DATA
	rts

;=======================================================================
; td_chr_reset — forget every char's slide state.
;=======================================================================
td_chr_reset:
	lea	TD_CHR,a0
	moveq	#56-1,d1
.r:	move.w	#NOPOS,(a0)
	lea	10(a0),a0
	dbra	d1,.r
	rts

;=======================================================================
; td_chars — walk the 56 chars; update slide state; build the blob
; list (world pixel positions) and the leader position.
;=======================================================================
td_chars:
	movem.l	d2-d7/a2-a4,-(a7)
	clr.w	TD_NB
	clr.w	TD_LEADOK
	lea	CHARS,a3
	lea	TD_CHR,a4
	lea	TD_LIST,a2
	moveq	#0,d7			; char index
.loop:
	move.w	(a3),d0
	andi.w	#$F,d0
	beq.w	.gone
	move.w	4(a3),d0		; map-draw record
	cmpi.w	#56,d0
	bcc.w	.gone
	mulu.w	#12,d0
	lea	RECS,a0
	cmpi.w	#$270F,(a0,d0.w)
	beq.w	.gone
	move.w	$C(a3),d2		; cell x
	move.w	$E(a3),d3		; cell y
	cmpi.w	#NOPOS,(a4)
	bne.s	.known
	move.w	d2,(a4)			; first sighting: no slide
	move.w	d3,2(a4)
	move.w	d2,d0
	lsl.w	#4,d0
	move.w	d0,4(a4)
	move.w	d3,d0
	lsl.w	#4,d0
	move.w	d0,6(a4)
	move.w	FRAME,d0
	sub.w	#64,d0
	move.w	d0,8(a4)
	bra.s	.pos
.known:
	cmp.w	(a4),d2
	bne.s	.moved
	cmp.w	2(a4),d3
	beq.s	.pos
.moved:	; new target: slide on from where the figure is drawn now (no
	; jump when a step lands before the previous slide finished);
	; jumps of more than 2 cells snap
	bsr.w	td_slidepos		; d5/d6 = current drawn position
	move.w	d2,d0
	sub.w	(a4),d0
	bpl.s	.ax
	neg.w	d0
.ax:	move.w	d3,d1
	sub.w	2(a4),d1
	bpl.s	.ay
	neg.w	d1
.ay:	cmpi.w	#2,d0
	bgt.s	.snap
	cmpi.w	#2,d1
	bgt.s	.snap
	move.w	d5,4(a4)
	move.w	d6,6(a4)
	bra.s	.start
.snap:	move.w	d2,d0
	lsl.w	#4,d0
	move.w	d0,4(a4)
	move.w	d3,d0
	lsl.w	#4,d0
	move.w	d0,6(a4)
.start:	move.w	d2,(a4)
	move.w	d3,2(a4)
	move.w	FRAME,8(a4)
.pos:	bsr.w	td_slidepos
	; leader figure: char == leader, or a type-4 redirect to the leader
	moveq	#1,d1			; variant 1 (white)
	cmp.w	LEADER,d7
	beq.s	.lead
	move.w	(a3),d0
	andi.w	#$F,d0
	cmpi.w	#4,d0
	bne.s	.add
	moveq	#0,d0
	move.b	$27(a3),d0
	cmp.w	LEADER,d0
	bne.s	.add
.lead:	moveq	#0,d1			; variant 0 (yellow)
	move.w	d5,TD_LEADX
	move.w	d6,TD_LEADY
	move.w	#1,TD_LEADOK
.add:
	cmpi.w	#TD_NSLOT,TD_NB
	bcc.s	.next
	move.w	d5,(a2)+
	move.w	d6,(a2)+
	move.w	d1,(a2)+
	addq.w	#1,TD_NB
	bra.s	.next
.gone:
	move.w	#NOPOS,(a4)
.next:
	lea	$34(a3),a3
	lea	10(a4),a4
	addq.w	#1,d7
	cmpi.w	#56,d7
	bcs.w	.loop
	movem.l	(a7)+,d2-d7/a2-a4
	rts

;=======================================================================
; td_slidepos — a4 = slide state (lx, ly target cell; fpx, fpy from
; pixel; t0). -> d5/d6 = drawn world pixel now. Uses d0, d4.
;=======================================================================
td_slidepos:
	move.w	FRAME,d4		; elapsed = min(now - t0, T)
	sub.w	8(a4),d4
	bmi.s	.full
	cmp.w	TD_PERIOD,d4
	bls.s	.el
.full:	move.w	TD_PERIOD,d4
.el:	move.w	4(a4),d5		; x: fpx + (lx*16 - fpx) * el / T
	move.w	(a4),d0
	lsl.w	#4,d0
	sub.w	d5,d0
	beq.s	.y
	muls.w	d4,d0
	divs.w	TD_PERIOD,d0
	add.w	d0,d5
.y:	move.w	6(a4),d6
	move.w	2(a4),d0
	lsl.w	#4,d0
	sub.w	d6,d0
	beq.s	.out
	muls.w	d4,d0
	divs.w	TD_PERIOD,d0
	add.w	d0,d6
.out:	rts

;=======================================================================
; td_camera -> d0 = camx, d1 = camy (world pixel at screen top-left).
; Axis that fits on screen: centred. Else: follow the leader's figure
; (or the game's camera cell), clamped to the map.
;=======================================================================
td_camera:
	movem.l	d2-d3,-(a7)
	tst.w	TD_LEADOK
	beq.s	.gcam
	move.w	TD_LEADX,d2
	move.w	TD_LEADY,d3
	bra.s	.have
.gcam:	move.w	$FF0E8E,d2		; game camera cell
	lsl.w	#4,d2
	move.w	$FF0E90,d3
	lsl.w	#4,d3
.have:
	; x
	move.w	TD_W,d1
	lsl.w	#4,d1			; map width px
	cmpi.w	#320,d1
	bgt.s	.fx
	sub.w	#320,d1
	asr.w	#1,d1
	move.w	d1,d0
	bra.s	.y
.fx:	move.w	d2,d0
	sub.w	#160-8,d0
	bpl.s	.x0
	moveq	#0,d0
.x0:	sub.w	#320,d1
	cmp.w	d1,d0
	ble.s	.y
	move.w	d1,d0
.y:	; y: the HUD covers the bottom ~56 px, so the play area centre
	; is y = TD_VC (leader figure centred there; small maps centred in
	; the top 2*TD_VC lines)
	move.w	TD_H,d1
	lsl.w	#4,d1
	cmpi.w	#224,d1
	bgt.s	.fy
	sub.w	#2*TD_VC,d1
	asr.w	#1,d1
	bra.s	.out
.fy:	move.w	d1,d2			; d2 = map height px
	move.w	d3,d1
	sub.w	#TD_VC-8,d1
	bpl.s	.y0
	moveq	#0,d1
.y0:	sub.w	#224,d2
	cmp.w	d2,d1
	ble.s	.out
	move.w	d2,d1
.out:	movem.l	(a7)+,d2-d3
	rts

;=======================================================================
; td_sprites — write the blob list to sprite slots TD_SLOT0.. and link
; them in at the head of the game's chain (sprite 0 is the game's dummy
; head; its link is redirected to our first slot and our last slot
; links on to the game's first sprite). menu_format rewrites sprite 0
; every main-loop pass; td_menufmt re-links right after it.
;=======================================================================
td_sprites:
	movem.l	d2-d7/a2,-(a7)
	; game's first sprite: sprite 0's link, unless it already points at us
	move.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vread
	move.w	d0,d5			; sprite 0 word 1
	andi.w	#$7F,d0
	cmpi.w	#TD_SLOT0,d0
	bcc.s	.ours
	move.w	d0,TD_GHEAD
.ours:
	lea	TD_LIST,a2
	move.w	TD_NB,d7
	moveq	#0,d6			; sprites written
	bra.w	.cond
.blob:
	move.w	(a2)+,d2		; px
	move.w	(a2)+,d3		; py
	move.w	(a2)+,d4		; variant
	sub.w	TD_CAMX,d2
	sub.w	TD_CAMY,d3
	cmpi.w	#-16,d2
	ble.s	.cond
	cmpi.w	#320,d2
	bge.s	.cond
	cmpi.w	#-16,d3
	ble.s	.cond
	cmpi.w	#224,d3
	bge.s	.cond
	moveq	#TD_SLOT0,d0		; VRAM address of slot TD_SLOT0+d6
	add.w	d6,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	bsr.w	td_vwrite
	add.w	#128,d3
	move.w	d3,VDP_DATA		; Y
	move.w	d6,d0			; link -> next slot (last fixed below)
	add.w	#TD_SLOT0+1,d0
	ori.w	#$0500,d0		; 2x2 cells
	move.w	d0,VDP_DATA
	move.w	TD_BASE,d0		; tile: base+257+variant*4, pal 0
	add.w	#257,d0
	lsl.w	#2,d4
	add.w	d4,d0
	move.w	d0,VDP_DATA
	add.w	#128,d2
	move.w	d2,VDP_DATA		; X
	addq.w	#1,d6
.cond:	dbra	d7,.blob
	move.w	TD_GHEAD,d2
	tst.w	d6
	beq.s	.none
	moveq	#TD_SLOT0-1,d0		; last blob -> game's first sprite
	add.w	d6,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vwrite
	move.w	d2,d0
	ori.w	#$0500,d0
	move.w	d0,VDP_DATA
	moveq	#TD_SLOT0,d2		; sprite 0 -> first blob
.none:	andi.w	#$FF80,d5
	or.w	d2,d5
	move.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vwrite
	move.w	d5,VDP_DATA
	movem.l	(a7)+,d2-d7/a2
	rts

;=======================================================================
; VRAM address helpers. d0.w = address ($0000-$FFFF).
; Command long = (addr & $3FFF | CD1-0 << 14) << 16 | addr >> 14.
;=======================================================================
td_vwrite:
	bsr.s	td_vcmd
	ori.l	#$40000000,d0
	move.l	d0,VDP_CTRL
	rts

td_vread:				; -> d0.w = VRAM word
	bsr.s	td_vcmd
	move.l	d0,VDP_CTRL
	move.w	VDP_DATA,d0
	rts

td_vcmd:
	andi.l	#$FFFF,d0
	lsl.l	#2,d0			; bits 14-15 -> 16-17
	lsr.w	#2,d0			; low word back to addr & $3FFF
	swap	d0
	rts

;=======================================================================
; td_stream — bring the ring buffer up to the camera.
;=======================================================================
td_stream:
	movem.l	d2-d7,-(a7)
	move.w	TD_CAMX,d4
	asr.w	#4,d4			; wanted cx0
	move.w	TD_CAMY,d5
	asr.w	#4,d5			; wanted cy0
	move.w	d4,d0
	sub.w	TD_CX0,d0
	bpl.s	.a1
	neg.w	d0
.a1:	cmpi.w	#3,d0
	bgt.w	.all
	move.w	d5,d0
	sub.w	TD_CY0,d0
	bpl.s	.a2
	neg.w	d0
.a2:	cmpi.w	#3,d0
	bgt.w	.all
.xr:	cmp.w	TD_CX0,d4
	ble.s	.xl
	addq.w	#1,TD_CX0
	move.w	TD_CX0,d6
	add.w	#20,d6
	bsr.w	td_draw_col
	bra.s	.xr
.xl:	cmp.w	TD_CX0,d4
	bge.s	.yd
	subq.w	#1,TD_CX0
	move.w	TD_CX0,d6
	bsr.w	td_draw_col
	bra.s	.xl
.yd:	cmp.w	TD_CY0,d5
	ble.s	.yu
	addq.w	#1,TD_CY0
	move.w	TD_CY0,d7
	add.w	#14,d7
	bsr.w	td_draw_row
	bra.s	.yd
.yu:	cmp.w	TD_CY0,d5
	bge.s	.out
	subq.w	#1,TD_CY0
	move.w	TD_CY0,d7
	bsr.w	td_draw_row
	bra.s	.yu
.all:	move.w	d4,TD_CX0
	move.w	d5,TD_CY0
	bsr.w	td_draw_all
.out:	movem.l	(a7)+,d2-d7
	rts

;=======================================================================
; Cell drawing. d6 = cell x, d7 = cell y (kept across game calls: the
; game's C code saves d4-d7/a3-a4 when it uses them).
;=======================================================================
td_draw_all:
	movem.l	d4-d7,-(a7)
	move.w	TD_CY0,d7
	moveq	#15-1,d4
.r:	bsr.s	td_draw_row
	addq.w	#1,d7
	dbra	d4,.r
	movem.l	(a7)+,d4-d7
	rts

td_draw_row:				; row d7, columns cx0..cx0+20
	movem.l	d5-d6,-(a7)
	move.w	TD_CX0,d6
	moveq	#21-1,d5
.c:	bsr.s	td_draw_cell
	addq.w	#1,d6
	dbra	d5,.c
	movem.l	(a7)+,d5-d6
	rts

td_draw_col:				; column d6, rows cy0..cy0+14
	movem.l	d5/d7,-(a7)
	move.w	TD_CY0,d7
	moveq	#15-1,d5
.c:	bsr.s	td_draw_cell
	addq.w	#1,d7
	dbra	d5,.c
	movem.l	(a7)+,d5/d7
	rts

td_draw_cell:
	; cell word or blank
	tst.w	d6
	bmi.w	td_cell_blank
	cmp.w	TD_W,d6
	bge.w	td_cell_blank
	tst.w	d7
	bmi.w	td_cell_blank
	cmp.w	TD_H,d7
	bge.w	td_cell_blank
	move.w	d7,-(a7)
	move.w	d6,-(a7)
	jsr	(CELLREAD).l
	addq.w	#4,a7
	movea.l	d0,a0
	move.w	(a0),d2			; cell word
	move.w	d2,d0
	andi.w	#$1FF,d0
	add.w	d0,d0
	lea	DESC,a0
	move.w	(a0,d0.w),d1		; descriptor
	btst	#12,d2
	bne.s	.hi
	move.w	d1,d3			; low variant
	lsr.w	#2,d3
	andi.w	#63,d3
	move.w	d1,d2
	andi.w	#3,d2			; flips: bit0 H, bit1 V
	bra.s	.mk
.hi:	move.w	d1,d3			; high variant
	lsr.w	#8,d3
	lsr.w	#2,d3
	andi.w	#63,d3
	move.w	d1,d2
	lsr.w	#8,d2
	andi.w	#3,d2
.mk:	lsl.w	#2,d3
	add.w	TD_BASE,d3		; quadrant-0 tile
	move.w	d2,d1
	lsl.w	#8,d1
	lsl.w	#3,d1			; flips -> $0800 / $1000
	or.w	d1,d3
	; quadrant at screen position p is tile p XOR flips
	move.w	d2,d0
	add.w	d3,d0
	swap	d0			; TL
	move.w	d2,d1
	eori.w	#1,d1
	add.w	d3,d1
	move.w	d1,d0			; TR
	move.w	d2,d1
	eori.w	#2,d1
	add.w	d3,d1
	swap	d1			; BL
	eori.w	#3,d2
	add.w	d3,d2
	move.w	d2,d1			; BR
	bra.s	td_cell_put
td_cell_blank:				; outside the map: parchment void
	move.w	TD_BASE,d0
	add.w	#256+$2000,d0		; palette 1
	move.w	d0,d1
	swap	d0
	move.w	d1,d0
	move.l	d0,d1
td_cell_put:	; VRAM address: ((2cy & 31) * 64 + (2cx & 63)) * 2
	move.w	d7,d2
	add.w	d2,d2
	andi.w	#31,d2
	lsl.w	#7,d2
	move.w	d6,d3
	add.w	d3,d3
	andi.w	#63,d3
	add.w	d3,d3
	add.w	d3,d2
	moveq	#0,d3
	move.w	d2,d3
	swap	d3
	ori.l	#$40000000,d3
	move.l	d3,VDP_CTRL
	move.l	d0,VDP_DATA
	addi.l	#$00800000,d3		; next tile row (+128 bytes)
	move.l	d3,VDP_CTRL
	move.l	d1,VDP_DATA
	rts

;=======================================================================
; td_plane_check -> d0 != 0 if the plane was overwritten (three cells of
; the visible area must hold one of our tiles).
;=======================================================================
td_plane_check:
	movem.l	d2-d3,-(a7)
	moveq	#0,d2
	moveq	#0,d3
	bsr.s	.one
	moveq	#10,d2
	moveq	#7,d3
	bsr.s	.one
	moveq	#20,d2
	moveq	#14,d3
	bsr.s	.one
	moveq	#0,d0
	bra.s	.out
.bad:	addq.w	#4,a7			; drop .one's return
	moveq	#1,d0
.out:	movem.l	(a7)+,d2-d3
	rts
.one:	add.w	TD_CY0,d3
	add.w	d3,d3
	andi.w	#31,d3
	lsl.w	#7,d3
	add.w	TD_CX0,d2
	add.w	d2,d2
	andi.w	#63,d2
	add.w	d2,d2
	add.w	d3,d2
	move.w	d2,d0
	bsr.w	td_vread
	andi.w	#$7FF,d0
	sub.w	TD_BASE,d0
	cmpi.w	#257,d0			; unsigned: 0..256 are ours
	bcc.s	.bad
	rts

;=======================================================================
; td_winfix — backstop for td_vdw: point every window cell that shows a
; room-bitmap tile at the transparent font blank.
;=======================================================================
td_winfix:
	movem.l	d2-d6/a2,-(a7)
	moveq	#0,d6			; row
.row:	move.w	d6,d0			; read 36 words of row d6, cols 2..37
	lsl.w	#7,d0
	add.w	#$1000+4,d0
	move.w	d0,d5			; row address
	andi.l	#$3FFF,d0
	swap	d0
	move.l	d0,VDP_CTRL
	lea	TD_ROW,a2
	moveq	#36-1,d1
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d1,.rd
	lea	TD_ROW,a2
	moveq	#0,d4			; column 0..35
.col:	move.w	(a2)+,d0
	move.w	d0,d1
	andi.w	#$F800,d1		; no palette / priority / flips
	bne.s	.nx
	sub.w	BANKBASE,d0
	cmpi.w	#828,d0
	bcc.s	.nx
	move.w	d4,d0			; fix this cell
	add.w	d0,d0
	add.w	d5,d0
	bsr.w	td_vwrite
	move.w	FONTBLK,VDP_DATA
.nx:	addq.w	#1,d4
	cmpi.w	#36,d4
	bcs.s	.col
	addq.w	#1,d6
	cmpi.w	#23,d6
	bcs.s	.row
	movem.l	(a7)+,d2-d6/a2
	rts

;=======================================================================
; Tiles. VRAM layout from TD_BASE: 256 map quadrant tiles (tile t ->
; t*4 + TL,TR,BL,BR), 1 void (solid), 4 blob variants x 4 (TL,BL,TR,BR).
;=======================================================================
td_tiles_check:				; clears TD_TILES if overwritten
	tst.w	TD_TILES
	beq.s	.out
	move.w	TD_BASE,d0		; row 4 of blob tile 0 (TL)
	add.w	#257,d0
	lsl.w	#5,d0
	add.w	#16,d0
	bsr.w	td_vread
	lea	td_gfx+32+16(pc),a0
	cmp.w	(a0),d0
	bne.s	.bad
	move.w	TD_BASE,d0		; a word inside map tile 128
	add.w	#128,d0
	lsl.w	#5,d0
	addq.w	#6,d0
	bsr.w	td_vread
	cmp.w	TD_MAPSENT,d0
	beq.s	.out
.bad:	clr.w	TD_TILES
.out:	rts

td_tiles_load:
	movem.l	d2-d7/a2-a4,-(a7)
	move.w	#10,-(a7)		; map tileset record
	jsr	(MAPDECODE).l
	addq.w	#2,a7
	lea	DECBUF,a3		; 64 source tiles
	lea	DECBUF+$800,a4		; 256 scaled tiles
	lea	td_dbl(pc),a2
	moveq	#64-1,d7
.tile:	moveq	#0,d6			; quadrant 0..3 (TL,TR,BL,BR)
.quad:	move.w	d6,d0			; source bytes: rows (q>>1)*4, cols (q&1)*2
	andi.w	#1,d0
	add.w	d0,d0
	move.w	d6,d1
	lsr.w	#1,d1
	lsl.w	#4,d1			; *4 rows *4 bytes
	add.w	d1,d0
	lea	(a3,d0.w),a0
	moveq	#4-1,d5
.row:	moveq	#0,d0
	move.b	(a0),d0
	add.w	d0,d0
	move.w	(a2,d0.w),d1
	swap	d1
	moveq	#0,d0
	move.b	1(a0),d0
	add.w	d0,d0
	move.w	(a2,d0.w),d1
	move.l	d1,(a4)+
	move.l	d1,(a4)+
	addq.w	#4,a0
	dbra	d5,.row
	addq.w	#1,d6
	cmpi.w	#4,d6
	bcs.s	.quad
	lea	32(a3),a3
	dbra	d7,.tile
	lea	td_gfx(pc),a0		; blank + blobs
	move.w	#(td_gfx_end-td_gfx)/4-1,d0
.cp:	move.l	(a0)+,(a4)+
	dbra	d0,.cp
	; DMA (256 + 17) tiles to VRAM
	move.w	#(256*32+td_gfx_end-td_gfx)/2,-(a7)
	moveq	#0,d0
	move.w	TD_BASE,d0
	lsl.l	#5,d0
	move.l	d0,-(a7)
	pea	DECBUF+$800
	jsr	(DMAUP).l
	lea	10(a7),a7
	move.w	#$8F02,VDP_CTRL
	; sentinel: word 3 of map tile 128 as uploaded
	lea	DECBUF+$800+128*32+6,a0
	move.w	(a0),TD_MAPSENT
	move.w	#1,TD_TILES
	movem.l	(a7)+,d2-d7/a2-a4
	rts

;=======================================================================
; Data (generated: pixel-double table, blank + blob tiles).
;=======================================================================
	even
td_dbl:	; byte (p0<<4|p1) -> word (p0 p0 p1 p1)
	dc.w $0000,$0011,$0022,$0033,$0044,$0055,$0066,$0077
	dc.w $0088,$0099,$00AA,$00BB,$00CC,$00DD,$00EE,$00FF
	dc.w $1100,$1111,$1122,$1133,$1144,$1155,$1166,$1177
	dc.w $1188,$1199,$11AA,$11BB,$11CC,$11DD,$11EE,$11FF
	dc.w $2200,$2211,$2222,$2233,$2244,$2255,$2266,$2277
	dc.w $2288,$2299,$22AA,$22BB,$22CC,$22DD,$22EE,$22FF
	dc.w $3300,$3311,$3322,$3333,$3344,$3355,$3366,$3377
	dc.w $3388,$3399,$33AA,$33BB,$33CC,$33DD,$33EE,$33FF
	dc.w $4400,$4411,$4422,$4433,$4444,$4455,$4466,$4477
	dc.w $4488,$4499,$44AA,$44BB,$44CC,$44DD,$44EE,$44FF
	dc.w $5500,$5511,$5522,$5533,$5544,$5555,$5566,$5577
	dc.w $5588,$5599,$55AA,$55BB,$55CC,$55DD,$55EE,$55FF
	dc.w $6600,$6611,$6622,$6633,$6644,$6655,$6666,$6677
	dc.w $6688,$6699,$66AA,$66BB,$66CC,$66DD,$66EE,$66FF
	dc.w $7700,$7711,$7722,$7733,$7744,$7755,$7766,$7777
	dc.w $7788,$7799,$77AA,$77BB,$77CC,$77DD,$77EE,$77FF
	dc.w $8800,$8811,$8822,$8833,$8844,$8855,$8866,$8877
	dc.w $8888,$8899,$88AA,$88BB,$88CC,$88DD,$88EE,$88FF
	dc.w $9900,$9911,$9922,$9933,$9944,$9955,$9966,$9977
	dc.w $9988,$9999,$99AA,$99BB,$99CC,$99DD,$99EE,$99FF
	dc.w $AA00,$AA11,$AA22,$AA33,$AA44,$AA55,$AA66,$AA77
	dc.w $AA88,$AA99,$AAAA,$AABB,$AACC,$AADD,$AAEE,$AAFF
	dc.w $BB00,$BB11,$BB22,$BB33,$BB44,$BB55,$BB66,$BB77
	dc.w $BB88,$BB99,$BBAA,$BBBB,$BBCC,$BBDD,$BBEE,$BBFF
	dc.w $CC00,$CC11,$CC22,$CC33,$CC44,$CC55,$CC66,$CC77
	dc.w $CC88,$CC99,$CCAA,$CCBB,$CCCC,$CCDD,$CCEE,$CCFF
	dc.w $DD00,$DD11,$DD22,$DD33,$DD44,$DD55,$DD66,$DD77
	dc.w $DD88,$DD99,$DDAA,$DDBB,$DDCC,$DDDD,$DDEE,$DDFF
	dc.w $EE00,$EE11,$EE22,$EE33,$EE44,$EE55,$EE66,$EE77
	dc.w $EE88,$EE99,$EEAA,$EEBB,$EECC,$EEDD,$EEEE,$EEFF
	dc.w $FF00,$FF11,$FF22,$FF33,$FF44,$FF55,$FF66,$FF77
	dc.w $FF88,$FF99,$FFAA,$FFBB,$FFCC,$FFDD,$FFEE,$FFFF
td_gfx:	; tile 0 void (solid colour 12 = parchment pink in palette 1),
	; then 4 blob variants x (TL,BL,TR,BR)
	dcb.l 8,$CCCCCCCC
	dc.l $0000000D,$0000DDDD,$000DDEEE,$00DDEEEE,$0DDEEFFE,$0DEEFFEE,$0DEEEEEE,$DDEEEEEE
	dc.l $DDEEEEEE,$0DEEEEEE,$0DEEEEEE,$0DDEEEEE,$00DDEEEE,$000DDEEE,$0000DDDD,$0000000D
	dc.l $D0000000,$DDDD0000,$EEEDD000,$EEEEDD00,$EEEEEDD0,$EEEEEED0,$EEEEEED0,$EEEEEEDD
	dc.l $EEEEEEDD,$EEEEEED0,$EEEEEED0,$EEEEEDD0,$EEEEDD00,$EEEDD000,$DDDD0000,$D0000000
	dc.l $0000000D,$0000DDDD,$000DDFFF,$00DDFFFF,$0DDFFBBF,$0DFFBBFF,$0DFFFFFF,$DDFFFFFF
	dc.l $DDFFFFFF,$0DFFFFFF,$0DFFFFFF,$0DDFFFFF,$00DDFFFF,$000DDFFF,$0000DDDD,$0000000D
	dc.l $D0000000,$DDDD0000,$FFFDD000,$FFFFDD00,$FFFFFDD0,$FFFFFFD0,$FFFFFFD0,$FFFFFFDD
	dc.l $FFFFFFDD,$FFFFFFD0,$FFFFFFD0,$FFFFFDD0,$FFFFDD00,$FFFDD000,$DDDD0000,$D0000000
	dc.l $0000000D,$0000DDDD,$000DDCCC,$00DDCCCC,$0DDCCFFC,$0DCCFFCC,$0DCCCCCC,$DDCCCCCC
	dc.l $DDCCCCCC,$0DCCCCCC,$0DCCCCCC,$0DDCCCCC,$00DDCCCC,$000DDCCC,$0000DDDD,$0000000D
	dc.l $D0000000,$DDDD0000,$CCCDD000,$CCCCDD00,$CCCCCDD0,$CCCCCCD0,$CCCCCCD0,$CCCCCCDD
	dc.l $CCCCCCDD,$CCCCCCD0,$CCCCCCD0,$CCCCCDD0,$CCCCDD00,$CCCDD000,$DDDD0000,$D0000000
	dc.l $0000000D,$0000DDDD,$000DD444,$00DD4444,$0DD44FF4,$0D44FF44,$0D444444,$DD444444
	dc.l $DD444444,$0D444444,$0D444444,$0DD44444,$00DD4444,$000DD444,$0000DDDD,$0000000D
	dc.l $D0000000,$DDDD0000,$444DD000,$4444DD00,$44444DD0,$444444D0,$444444D0,$444444DD
	dc.l $444444DD,$444444D0,$444444D0,$44444DD0,$4444DD00,$444DD000,$DDDD0000,$D0000000
td_gfx_end:
