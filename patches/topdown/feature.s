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
;   $01B9E8  jsr dma_upload (room DMA) -> jsr td_dma (original view only)
;   $001352  joypad_queue_pop body -> jsr td_pad (A+B+C = switch views)
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
TD_TF		equ 22		; overworld on the dragon (orig attract flight 22.0)
TD_TS		equ 19		; boat / ship (orig over open sea 17-19)
TD_SLOT0	equ 68		; first sprite slot for blobs (game uses <= 67)
TD_NSLOT	equ 12		; our sprite slots (2 HUD box + figures)
TD_NFIG		equ 10		; figure sprites max
TD_BOXT		equ 802		; HUD box: 12 solid parchment tiles (bank offset)
TD_VC		equ 84		; screen line the leader is centred on
TD_NFC		equ 25		; figure images cached in VRAM (4x4 tiles each)
TD_SHL		equ 3		; extra cell columns left (shear: 42 px at line 0)
TD_SHR		equ 8		; extra cell columns right (shear: 69 px at line 223)
TD_NROW		equ 16		; cell rows drawn (the whole ring)
TD_BTAB		equ $C000	; static Plane B table (HUD band), bank tiles $600-$67F
TD_BROW		equ 20		; first window row of the HUD band
TD_FCB		equ 273		; first cache tile, relative to TD_BASE

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
TD_CANX		equ TD+$2E	; may extract one figure image this update
TD_STAMP	equ TD+$30	; figure-cache LRU clock
TD_OFF		equ TD+$32	; 1 = the original isometric view (A+B+C toggles)
TD_REQ		equ TD+$34	; view switch requested by td_pad
TD_PADC		equ TD+$36	; A+B+C held (switch latched until release)
TD_ANIMFR	equ TD+$38	; frame the last water toggle started
TD_ANIMI	equ TD+$3A	; water quadrant tiles still to toggle
TD_LAY		equ TD+$3C	; our VDP registers (R4/R11/R17/R18) are installed
TD_LIST		equ TD+$40	; TD_NSLOT x (px.w, py.w, tile.w, kind.w) = 96 B
TD_CHR		equ TD+$A0	; 56 x 10: lx, ly (target cell), fpx, fpy (from px), t0
TD_ROW		equ TD+$2E0	; 36-word window row buffer
TD_FC		equ TD+$328	; TD_NFC x (key.w, stamp.w): figure image cache
TD_UPTXT	equ TD+$328+4*TD_NFC	; window rows above the band hold text
TD_BAND		equ TD_UPTXT+2	; HUD band mode active
TD_YMAX		equ TD_UPTXT+4	; sprites below this cell top are culled
TD_MSG		equ TD_UPTXT+6	; other text in the HUD rows (a message)
TD_HASBOX	equ TD_UPTXT+8	; the HUD box holds moved HUD words
TD_BOX		equ TD_UPTXT+10	; draw the HUD box backdrop sprites
TD_BUSY		equ TD_UPTXT+12	; main thread is inside our code
TD_END		equ TD_UPTXT+14

NOPOS		equ $8000

;=======================================================================
; td_tick — replaces the room render in redraw_check. Syncs the view
; with the game, then waits out the rest of the tick, updating the
; picture once per frame.
;=======================================================================
td_tick:
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.s	.on
	tst.w	TD_REQ			; A+B+C: switch views
	beq.s	.noreq
	clr.w	TD_REQ
	eori.w	#1,TD_OFF
	beq.s	.toon
	addq.w	#1,TD_BUSY
	bsr.w	td_restore
	subq.w	#1,TD_BUSY
	bra.s	.noreq
.toon:	clr.w	TD_VALID		; reinstall from scratch
	clr.w	TD_TILES
.noreq:	tst.w	TD_OFF
	beq.s	.on
	jsr	($011DE8).l		; original view: the displaced code
	move.w	$FF0E90,-(a7)		; (clear the decode buffer, render
	move.w	$FF0E8E,-(a7)		; the 10x10 window)
	jsr	($01BA4E).l
	addq.w	#4,a7
	movem.l	(a7)+,d0-d7/a0-a6
	rts
.on:	moveq	#TD_T2,d0
	cmpi.w	#1,MODE
	bne.s	.per
	moveq	#TD_T1,d0
	move.w	LEADER,d1		; travel mode (char +6): dragon 4 and
	mulu.w	#$34,d1			; boat 2 / ship 3 use the original's pace
	lea	CHARS,a0
	move.w	6(a0,d1.l),d1
	cmpi.w	#4,d1
	bne.s	.sea
	moveq	#TD_TF,d0
.sea:	subq.w	#2,d1			; boat (2) or ship (3): sea pace
	cmpi.w	#1,d1
	bhi.s	.per
	moveq	#TD_TS,d0
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
	addq.w	#1,TD_BUSY
	bsr.w	td_sync			; right after an update, so the
	subq.w	#1,TD_BUSY
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
	bsr.w	td_poll_vb
	tst.w	$FF00AC
	rts

td_poll_turn:
	bsr.w	td_poll_vb
	jmp	($0226BC).l		; combat_turn_run (returns to the caller)

; td_poll_pgc — map_grid_place_chars per-character loop head
; ($0246C0: move.w d7,d0 / muls.w #$34,d0): update the picture if a new
; frame started, then the displaced instructions.
td_poll_pgc:
	bsr.w	td_poll_vb
	move.w	d7,d0
	muls.w	#$34,d0
	rts

; td_vint — VBlank handler ($00127A: addq.l #1,frame counter). When the
; main thread was interrupted inside one of the long game routines that
; never touch the VDP (and not inside our own code), update the picture
; right here (no streaming, no image extraction), so long ticks do not
; hold the picture. Elsewhere the main-thread polls do it.
td_vint:
	addq.l	#1,$FF0010
	cmpi.w	#$7D7D,TD_MAGIC		; cheap exits first (game timing)
	bne.s	.q
	tst.w	TD_BUSY
	bne.s	.q
	tst.w	TD_VALID
	beq.s	.q
	movem.l	d0-d7/a0-a6,-(a7)
	move.l	66(a7),d0		; interrupted PC (regs 60, return 4, SR 2)
	lea	td_vwl(pc),a0
.l:	move.l	(a0)+,d1
	beq.s	.out
	move.l	(a0)+,d2
	cmp.l	d1,d0
	bcs.s	.l
	cmp.l	d2,d0
	bcc.s	.l
	bsr.w	td_frame_ns
.out:	movem.l	(a7)+,d0-d7/a0-a6
.q:	rts
td_vwl:	; [start, end) of game routines with no VDP access of their own
	dc.l	$00DD5C,$00DE02		; sys_lzss_decompress
	dc.l	$01C176,$01C802		; map_chunk_cache_read, leader_spawn
	dc.l	$01C802,$01C83E		; map_chunk_load_buf
	dc.l	$01C83E,$01D9BA		; location_divide, move_cost_calc
	dc.l	$02103E,$0210D8		; map_grid_clear
	dc.l	$02155E,$021FE6		; world_tick
	dc.l	$0226BC,$0231D8		; combat_turn_run
	dc.l	$024676,$024916		; map_grid_place_chars
	dc.l	0

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
	tst.w	TD_OFF
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
; td_dma — redraw_check's room DMA ($01B9E8, jsr dma_upload): only in
; the original view.
;=======================================================================
td_dma:
	tst.w	TD_OFF
	beq.s	.skip
	jmp	($00DA04).l		; dma_upload, returns to redraw_check
.skip:	rts

;=======================================================================
; td_pad — joypad_queue_pop ($001352, after its `moveq #0,d0`): the
; whole pop, then A+B+C pressed together requests a view switch and is
; hidden from the game. Returns to the pop's caller.
;=======================================================================
td_pad:
	addq.w	#4,a7			; we return to the pop's caller
	moveq	#0,d1
	move.w	#$2700,sr
	move.b	$FF001B,d1
	lea	$FF001C,a0
	cmp.b	$FF001A,d1
	beq.s	.empty
	move.b	(a0,d1.w),d0
	move.b	d0,$FF002C
	addq.b	#1,d1
	andi.b	#$F,d1
	move.b	d1,$FF001B
	bra.s	.got
.empty:	move.b	$FF002C,d0
.got:	move.w	#$2000,sr
	move.b	d0,d1
	andi.b	#$70,d1
	cmpi.b	#$70,d1
	bne.s	.pass
	tst.b	TD_PADC
	bne.s	.mask
	st	TD_PADC
	move.w	#1,TD_REQ
.mask:	andi.b	#$8F,d0			; strip A, B, C
	rts
.pass:	clr.b	TD_PADC
	rts

;=======================================================================
; td_restore — back to the original view: unhook our sprites, zero the
; scroll, and let the game redraw its scene (window identity map +
; parchment, world_map_redraw). Its next ticks render and upload the
; room bitmap as before.
;=======================================================================
td_restore:
	clr.w	TD_VALID
	clr.w	TD_TILES
	bsr.w	td_unlay
	moveq	#23,d1			; empty the HUD box (rows 23-25,
.hb:	move.w	d1,d0			; cols 22-29): the game redraws the
	lsl.w	#7,d0			; HUD in its own place
	add.w	#$1000+22*2,d0
	bsr.w	td_vwrite
	moveq	#8-1,d0
.hc:	move.w	FONTBLK,VDP_DATA
	dbra	d0,.hc
	addq.w	#1,d1
	cmpi.w	#26,d1
	bcs.s	.hb
	clr.w	TD_HASBOX
	clr.w	TD_BOX
	cmpi.w	#$2400,SPRBASE
	bne.s	.scr
	move.w	SPRBASE,d0		; sprite 0 -> the game's first sprite
	addq.w	#2,d0
	bsr.w	td_vread
	andi.w	#$FF80,d0
	or.w	TD_GHEAD,d0
	move.w	d0,d1
	move.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vwrite
	move.w	d1,VDP_DATA
.scr:	clr.l	-(a7)			; vdp_set_scroll(0,0,0,0)
	clr.l	-(a7)
	jsr	($00DC16).l
	addq.w	#8,a7
	jsr	($0162FE).l		; world_map_redraw
	rts

;=======================================================================
; td_sync — (re)install the view when the scene changed under us.
;=======================================================================
td_sync:
	tst.w	TD_OFF
	bne.w	.out
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
	move.w	#1,TD_BUSY		; we are inside td_sync
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
	bsr.w	td_hud
	tst.w	TD_VALID
	beq.s	.redraw
	bsr.w	td_plane_check
	tst.w	d0
	beq.s	.out
.redraw:
	move.w	#1,TD_CANX
	bsr.w	td_chars
	bsr.w	td_camera
	move.w	d0,TD_CAMX
	move.w	d1,TD_CAMY
	asr.w	#4,d0
	asr.w	#4,d1
	move.w	d0,TD_CX0
	move.w	d1,TD_CY0
	bsr.w	td_draw_all
	bsr.w	td_layers
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
	bra.s	td_fwrap
td_frame_ns:
	moveq	#0,d1
td_fwrap:
	addq.w	#1,TD_BUSY
	bsr.s	td_frame_go
	subq.w	#1,TD_BUSY
	rts
td_frame_go:
	move.w	FRAME,TD_LASTFR
	tst.w	TD_VALID
	beq.w	.bad
	cmpi.w	#$2400,SPRBASE
	bne.w	.bad
	movea.l	GRIDPTR,a0
	cmpa.l	TD_GRID,a0
	bne.w	.bad
	move.w	MODE,d0
	cmp.w	TD_MODE,d0
	bne.w	.bad
	move.w	LOC,d0
	cmp.w	TD_LOC,d0
	bne.w	.bad
	move.w	d1,-(a7)
	bsr.w	td_plane_check		; another screen owns the plane?
	move.w	(a7)+,d1
	tst.w	d0
	bne.w	.bad
	move.w	#$8F02,VDP_CTRL
	; menu open ($FF00AC): the world pauses under the game's own panels;
	; blobs are taken off so they never sit on top of a panel
	tst.w	$FF00AC
	beq.s	.world
	clr.w	TD_NB
	bsr.w	td_sprites
	bsr.w	td_layers
	bsr.w	td_scroll
	rts
.bad:	bra.w	td_unlay
.world:
	move.w	d1,TD_CANX		; image extraction: game calls allowed?
	move.w	d1,-(a7)
	bsr.w	td_chars
	bsr.w	td_camera
	move.w	(a7)+,d2
	bne.s	.cam
	move.w	TD_CX0,d3		; no streaming: stay inside what is drawn
	lsl.w	#4,d3			; (x: CX0*16-6 .. +60, y: CY0*16 .. +32)
	subq.w	#6,d3
	cmp.w	d3,d0
	bge.s	.c1
	move.w	d3,d0
.c1:	add.w	#66,d3
	cmp.w	d3,d0
	ble.s	.c2
	move.w	d3,d0
.c2:	move.w	TD_CY0,d3
	lsl.w	#4,d3
	cmp.w	d3,d1
	bge.s	.c3
	move.w	d3,d1
.c3:	add.w	#32,d3
	cmp.w	d3,d1
	ble.s	.cam
	move.w	d3,d1
.cam:	move.w	d0,TD_CAMX
	move.w	d1,TD_CAMY
	bsr.w	td_layers
	bsr.w	td_scroll		; vblank-critical first
	bsr.w	td_sprites
	bsr.w	td_anim
	tst.w	d2
	beq.s	.out
	subq.w	#1,TD_BUSY		; streaming may load a chunk (~1 frame):
	bsr.w	td_stream		; VBlank may update meanwhile (cell
	addq.w	#1,TD_BUSY		; writes are masked)
.out:
	rts

;=======================================================================
; td_scroll — full-screen scroll of planes A and B to the camera.
;=======================================================================
td_scroll:	; per-line H-scroll: world row wy is shifted by floor(wy/2)
	; - floor((camY+TD_VC)/2) px (shear, rigid under scrolling);
	; Plane B static in band mode. V-scroll first: it must land before
	; the first visible line.
	movem.l	d2-d3,-(a7)
	lea	VDP_DATA,a0
	move.w	TD_CAMY,d0
	swap	d0
	move.w	TD_CAMY,d0
	tst.w	TD_BAND
	beq.s	.v
	clr.w	d0
.v:	move.l	#$40000010,VDP_CTRL	; VSRAM write 0
	move.l	d0,(a0)
	move.w	TD_CAMX,d0		; d0 = A.hi : B.lo, d1 = step per pair
	sub.w	#TD_VC/2,d0
	neg.w	d0
	andi.w	#$3FF,d0
	move.l	#$10000,d1
	tst.w	TD_BAND
	bne.s	.b
	move.w	d0,d2			; full window: Plane B is the map too
	add.w	#$400,d2		; (no borrow into A over 112 steps)
	swap	d0
	move.w	d2,d0
	moveq	#1,d2
	add.l	d2,d1
	bra.s	.go
.b:	swap	d0
	clr.w	d0
.go:	move.l	#$60000000,VDP_CTRL	; VRAM write $2000 (H-scroll table)
	btst	#0,TD_CAMY+1		; odd row at line 0: it ends a pair
	beq.s	.p
	move.l	d0,(a0)
	sub.l	d1,d0
.p:	moveq	#224/2-1,d2
.l:	move.l	d0,(a0)
	move.l	d0,(a0)
	sub.l	d1,d0
	dbra	d2,.l
	movem.l	(a7)+,d2-d3
	rts

;=======================================================================
; td_layers — band mode: window only on rows TD_BROW.. (the HUD), map on
; Plane A above it, Plane B = static parchment table behind the HUD.
; Full mode (menu open, or text above the band): the game's own window
; over the whole screen, map on Plane B. Per-line H-scroll in both.
;=======================================================================
td_layers:
	move.w	#1,TD_LAY
	move.w	#$8B03,VDP_CTRL		; H-scroll per line
	tst.w	$FF00AC
	bne.s	.full
	tst.w	TD_UPTXT
	bne.s	.full
	tst.w	TD_MSG			; a message: parchment strip
	beq.s	.full
	cmpi.w	#$38E,TD_BASE		; table position assumes this bank
	bne.s	.full
	clr.w	TD_BOX
	move.w	#$8400+TD_BTAB/$2000,VDP_CTRL
	move.w	#$9100,VDP_CTRL
	move.w	#$9280+TD_BROW,VDP_CTRL
	move.w	#1,TD_BAND
	move.w	#TD_BROW*8-16,TD_YMAX
	rts
.full:	move.w	#$8400,VDP_CTRL		; compact HUD: the game's window over
	move.w	#$9180,VDP_CTRL		; the whole screen, map on Plane B
	move.w	#$9200,VDP_CTRL
	clr.w	TD_BAND
	move.w	#224,TD_YMAX
	move.w	TD_HASBOX,TD_BOX
	rts

; td_unlay — back to the game's layout G registers (view invalid).
td_unlay:
	tst.w	TD_LAY
	beq.s	.out
	clr.w	TD_LAY
	clr.w	TD_BAND
	move.w	#$8400,VDP_CTRL
	move.w	#$8B00,VDP_CTRL
	move.w	#$9180,VDP_CTRL
	move.w	#$9200,VDP_CTRL
.out:	rts

; td_vctl — replaces the port write of vdp_ctrl_write ($D9E6, d0 = word;
; returns to its caller). A layout install (an R2 write) first drops our
; registers, so no other screen inherits them.
td_vctl:
	tst.w	TD_LAY
	beq.s	.go
	move.w	d1,-(a7)
	move.w	d0,d1
	andi.w	#$FF00,d1
	cmpi.w	#$8200,d1
	bne.s	.no
	bsr.s	td_unlay
.no:	move.w	(a7)+,d1
.go:	move.w	d0,VDP_CTRL
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
	addq.w	#1,TD_STAMP
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
.pos:	bsr.w	td_slidepos		; d5/d6 = position, d4 = elapsed
	bsr.w	td_figure		; d0 = figure tile word, or -1
	tst.w	d0
	bmi.s	.blob
	cmpi.w	#TD_NFIG,TD_NB
	bcc.w	.lchk
	move.w	d5,(a2)+
	move.w	d6,(a2)+
	move.w	d0,(a2)+
	move.w	#1,(a2)+		; kind 1: 32x32 figure
	addq.w	#1,TD_NB
	bra.s	.lchk
.blob:	; no image yet: a 16x16 blob (yellow = the leader's figure)
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
.add:
	cmpi.w	#TD_NFIG,TD_NB
	bcc.s	.lchk
	move.w	d5,(a2)+
	move.w	d6,(a2)+
	lsl.w	#2,d1			; tile: base+257+variant*4, pal 0
	add.w	TD_BASE,d1
	add.w	#257,d1
	move.w	d1,(a2)+
	clr.w	(a2)+			; kind 0: 16x16 blob
	addq.w	#1,TD_NB
.lchk:	; the leader's figure: char == leader, or a type-4 redirect to it
	cmp.w	LEADER,d7
	beq.s	.isl
	move.w	(a3),d0
	andi.w	#$F,d0
	cmpi.w	#4,d0
	bne.s	.next
	moveq	#0,d0
	move.b	$27(a3),d0
	cmp.w	LEADER,d0
	bne.s	.next
.isl:	move.w	d5,TD_LEADX
	move.w	d6,TD_LEADY
	move.w	#1,TD_LEADOK
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
; td_figure — the char's figure image as a sprite tile word (d0), or -1.
; a3 = char, a4 = slide state, d4 = elapsed (from td_slidepos).
; The image is the one the game itself would draw: record template
; (+2 + +4) at the animation phase geom+$A, giving an $E358 stream
; (record +0 + group offset) and a mirror param. While the figure slides
; between cells, its facing's 4 walk frames (offsets 0,6,1,7 or
; 8,14,9,15 — the poses of walk templates 36-39) are stepped through,
; one per quarter of the slide.
;=======================================================================
td_figure:
	movem.l	d1-d7/a0-a2,-(a7)
	move.w	4(a3),d0		; record
	mulu.w	#12,d0
	lea	RECS,a1
	adda.w	d0,a1
	move.w	2(a1),d0		; template
	add.w	4(a1),d0
	cmpi.w	#56,d0
	bcc.s	.none
	mulu.w	#36,d0
	movea.l	GRIDPTR,a0
	move.w	$A(a0),d1		; phase 0..3
	andi.w	#3,d1
	lsl.w	#3,d1
	add.w	d1,d0
	lea	($0197B0).l,a0
	adda.w	d0,a0
	move.w	(a0),d2			; image offset
	move.w	2(a0),d3		; mirror param
	cmp.w	TD_PERIOD,d4		; sliding?
	bcc.s	.key
	move.w	(a4),d0
	lsl.w	#4,d0
	cmp.w	4(a4),d0
	bne.s	.walk
	move.w	2(a4),d0
	lsl.w	#4,d0
	cmp.w	6(a4),d0
	beq.s	.key
.walk:	move.w	d2,d0			; facing poses only (0,1,6,7 / 8,9,14,15)
	andi.w	#6,d0
	beq.s	.w1
	cmpi.w	#6,d0
	bne.s	.key
.w1:	moveq	#0,d0			; walk frame = elapsed * 4 / T
	move.w	d4,d0
	lsl.w	#2,d0
	divu.w	TD_PERIOD,d0
	andi.w	#3,d0
	andi.w	#8,d2
	lea	td_walk(pc),a0
	add.b	(a0,d0.w),d2
.key:	add.w	(a1),d2			; stream = record +0 + offset
	tst.w	d3
	beq.s	.k1
	ori.w	#$8000,d2		; key bit 15 = mirror
.k1:	move.w	d2,d0
	bsr.s	td_img
	bra.s	.out
.none:	moveq	#-1,d0
.out:	movem.l	(a7)+,d1-d7/a0-a2
	rts

td_walk:
	dc.b	0,6,1,7

;=======================================================================
; td_img — figure image cache. d0 = key (stream | mirror<<15) -> d0 =
; tile word of its 4x4-tile copy in VRAM, or -1 (not cached and no
; extraction allowed now). One extraction per update at most
; (TD_CANX); the least recently used slot is replaced.
;=======================================================================
td_img:
	lea	TD_FC,a0
	moveq	#TD_NFC-1,d1
	moveq	#0,d2			; slot
.f:	cmp.w	(a0),d0
	beq.s	.hit
	addq.l	#4,a0
	addq.w	#1,d2
	dbra	d1,.f
	tst.w	TD_CANX			; miss
	beq.s	.no
	clr.w	TD_CANX
	lea	TD_FC,a0		; least recently used slot
	moveq	#TD_NFC-1,d1
	moveq	#0,d3			; candidate slot
	moveq	#-1,d2			; best stamp so far (unsigned max)
	moveq	#0,d4			; best slot
.l:	cmp.w	2(a0),d2
	bls.s	.l1
	move.w	2(a0),d2
	move.w	d3,d4
.l1:	addq.l	#4,a0
	addq.w	#1,d3
	dbra	d1,.l
	move.w	d4,d2
	bsr.w	td_extract		; d0 = key, d2 = slot
	move.w	d2,d1
	lsl.w	#2,d1
	lea	TD_FC,a0
	adda.w	d1,a0
	move.w	d0,(a0)
.hit:	move.w	TD_STAMP,2(a0)
	move.w	d2,d0			; tile word
	bra.w	td_slot
.no:	moveq	#-1,d0
	rts

;=======================================================================
; td_extract — draw one $E358 image alone into the decode buffer (at
; x=192, y=16: buffer tiles rows 2-5, cols 16-19, where every figure
; image fits) and copy those 16 tiles, column by column (sprite tile
; order), to cache slot d2. d0 = key. Preserves d0, d2.
;=======================================================================
; td_slot: d0 = cache slot -> d0 = first tile. Slots 0-21 sit before the
; static Plane B table (bank tiles $600-$67F), 22-25 after it.
td_slot:
	lsl.w	#4,d0
	cmpi.w	#22*16,d0
	bcs.s	.a
	add.w	#754-TD_FCB-22*16,d0
.a:	add.w	TD_BASE,d0
	add.w	#TD_FCB,d0
	rts

td_extract:
	movem.l	d0-d7/a0-a6,-(a7)
	move.w	d0,d7
	moveq	#5-1,d1			; clear rows 2..6, cols 16..19
	lea	DECBUF+(2*36+16)*32,a0
.cr:	moveq	#32-1,d0
	movea.l	a0,a1
.cl:	clr.l	(a1)+
	dbra	d0,.cl
	lea	36*32(a0),a0
	dbra	d1,.cr
	moveq	#0,d0			; variant (mirror)
	tst.w	d7
	bpl.s	.v
	moveq	#1,d0
.v:	move.w	d0,-(a7)
	move.w	#16,-(a7)		; y
	move.w	#64+128,-(a7)		; x (buffer pixel 128 = tile col 16)
	move.w	d7,d0
	andi.w	#$7FFF,d0
	move.w	d0,-(a7)		; stream
	jsr	($00E358).l
	addq.w	#8,a7
	move.w	10(a7),d0		; saved d2 = slot -> VRAM address
	bsr.w	td_slot
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	DECBUF+(2*36+16)*32,a0
	moveq	#4-1,d1			; columns
.cc:	movea.l	a0,a1
	moveq	#4-1,d2			; rows
.cr2:	moveq	#8-1,d3
	movea.l	a1,a2
.cw:	move.l	(a2)+,VDP_DATA
	dbra	d3,.cw
	lea	36*32(a1),a1
	dbra	d2,.cr2
	lea	32(a0),a0
	dbra	d1,.cc
	movem.l	(a7)+,d0-d7/a0-a6
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
; td_sprites — write the list (figures 32x32, blobs 16x16) to sprite
; slots TD_SLOT0.., nearest first (larger y = in front), and link them
; in at the head of the game's chain: sprite 0 (the game's dummy head)
; -> ours -> the game's first sprite. menu_format rewrites sprite 0
; every main-loop pass; td_menufmt re-links right after it.
;=======================================================================
td_sprites:
	movem.l	d2-d7/a2-a3,-(a7)
	move.w	SPRBASE,d0		; sprite 0's link: the game's first
	addq.w	#2,d0			; sprite, unless it points at us
	bsr.w	td_vread
	move.w	d0,d5			; sprite 0 word 1
	andi.w	#$7F,d0
	cmpi.w	#TD_SLOT0,d0
	bcc.s	.ours
	move.w	d0,TD_GHEAD
.ours:	; insertion sort, y descending (8-byte entries)
	move.w	TD_NB,d7
	moveq	#1,d6
.so:	cmp.w	d7,d6
	bcc.s	.sorted
	move.w	d6,d4
.si:	move.w	d4,d0
	lsl.w	#3,d0
	lea	TD_LIST,a2
	adda.w	d0,a2			; entry i
	move.w	2(a2),d0
	cmp.w	-8+2(a2),d0
	ble.s	.sn
	move.l	(a2),d0			; swap with entry i-1
	move.l	-8(a2),(a2)
	move.l	d0,-8(a2)
	move.l	4(a2),d0
	move.l	-8+4(a2),4(a2)
	move.l	d0,-8+4(a2)
	subq.w	#1,d4
	bne.s	.si
.sn:	addq.w	#1,d6
	bra.s	.so
.sorted:
	moveq	#0,d6			; sprites written
	tst.w	TD_BOX			; HUD box backdrop first (on top)
	beq.s	.nobox
	moveq	#0,d2
.bx:	moveq	#TD_SLOT0,d0
	add.w	d6,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	bsr.w	td_vwrite
	move.w	#184+128,VDP_DATA	; rows 23-25
	move.w	d6,d0
	add.w	#TD_SLOT0+1+$0E00,d0	; 32x24, link to the next
	move.w	d0,VDP_DATA
	move.w	TD_BASE,d0
	add.w	#TD_BOXT+$2000,d0	; palette 1, low priority
	move.w	d0,VDP_DATA
	move.w	d2,d0
	lsl.w	#5,d0
	add.w	#172+128,d0		; columns 22-29 (4 px margin)
	move.w	d0,VDP_DATA
	movea.w	#$0E00,a0
	addq.w	#1,d6
	addq.w	#1,d2
	cmpi.w	#2,d2
	bcs.s	.bx
.nobox:	move.w	TD_CAMY,d0		; shear reference: the leader's line
	add.w	#TD_VC,d0
	asr.w	#1,d0
	movea.w	d0,a1
	lea	TD_LIST,a2
	bra.w	.cond
.spr:	move.w	(a2)+,d2		; px
	move.w	(a2)+,d3		; py
	move.w	(a2)+,d4		; tile word
	move.w	(a2)+,d1		; kind
	sub.w	TD_CAMX,d2
	sub.w	TD_CAMY,d3
	cmp.w	TD_YMAX,d3		; below the HUD band
	bge.w	.cond
	move.w	d3,d0			; shear of the cell's centre row
	add.w	TD_CAMY,d0
	addq.w	#8,d0
	asr.w	#1,d0
	sub.w	a1,d0
	sub.w	d0,d2
	move.w	#$0500,a3		; 16x16
	tst.w	d1
	beq.s	.k0
	subq.w	#8,d2			; 32x32 figure, feet on the cell
	sub.w	#16,d3
	move.w	#$0F00,a3
.k0:	cmpi.w	#-32,d2
	ble.s	.cond
	cmpi.w	#320,d2
	bge.s	.cond
	cmpi.w	#-32,d3
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
	move.w	d6,d0			; size | link -> next slot (last fixed below)
	add.w	#TD_SLOT0+1,d0
	add.w	a3,d0
	move.w	d0,VDP_DATA
	move.w	d4,VDP_DATA		; tile, pal 0
	add.w	#128,d2
	move.w	d2,VDP_DATA		; X
	movea.w	a3,a0			; size of the last sprite written
	addq.w	#1,d6
.cond:	dbra	d7,.spr
	move.w	TD_GHEAD,d2
	tst.w	d6
	beq.s	.none
	moveq	#TD_SLOT0-1,d0		; last sprite -> game's first sprite
	add.w	d6,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vwrite
	move.w	a0,d0			; its size
	or.w	d2,d0
	move.w	d0,VDP_DATA
	moveq	#TD_SLOT0,d2		; sprite 0 -> first of ours
.none:	andi.w	#$FF80,d5
	or.w	d2,d5
	move.w	SPRBASE,d0
	addq.w	#2,d0
	bsr.w	td_vwrite
	move.w	d5,VDP_DATA
	movem.l	(a7)+,d2-d7/a2-a3
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
; td_anim — water shimmer: every 32 frames swap colours 2 and 4 (mid and
; light blue) inside the water map tiles: read and remap 20 quadrant tiles
; per frame into a RAM buffer, then write all 80 in one frame (no
; half-swapped water). Every cell showing water animates; no name-table writes.
;=======================================================================
TD_NWT		equ 20
TD_WPER		equ 32		; frames per shimmer step
TD_WBUF		equ $FF4BC0	; 2,560 B: unused rows 10-12 of the room bitmap
td_anim:
	movem.l	d2-d5/a2-a3,-(a7)
	move.w	TD_ANIMI,d2
	bmi.w	.flip			; all read: write them in one frame
	bne.s	.run
	move.w	FRAME,d0
	sub.w	TD_ANIMFR,d0
	cmpi.w	#TD_WPER,d0
	bcs.w	.out
	move.w	FRAME,TD_ANIMFR
	moveq	#TD_NWT*4,d2
.run:	lea	td_swap(pc),a3
	moveq	#20-1,d4
.t:	moveq	#TD_NWT*4,d3
	sub.w	d2,d3			; quadrant index
	move.w	d3,d0
	lsl.w	#5,d0
	lea	TD_WBUF,a2
	adda.w	d0,a2			; its slot in the buffer
	move.w	d3,d0
	lsr.w	#2,d0
	lea	td_wtl(pc),a0
	moveq	#0,d1
	move.b	(a0,d0.w),d1
	lsl.w	#2,d1
	andi.w	#3,d3
	add.w	d3,d1
	add.w	TD_BASE,d1
	lsl.w	#5,d1
	move.w	d1,d0			; tile's VRAM address
	bsr.w	td_vcmd
	move.l	d0,VDP_CTRL
	moveq	#16-1,d1
.rd:	move.w	VDP_DATA,d0
	moveq	#0,d5
	move.b	d0,d5
	move.b	(a3,d5.w),d0
	ror.w	#8,d0
	move.b	d0,d5
	move.b	(a3,d5.w),d0
	ror.w	#8,d0
	move.w	d0,(a2)+
	dbra	d1,.rd
	subq.w	#1,d2
	dbeq	d4,.t
	tst.w	d2
	bne.s	.out
	moveq	#-1,d2			; next frame: write
	bra.s	.out
.flip:	lea	TD_WBUF,a2		; 20 map tiles x 4 quadrants, 128 bytes each
	lea	td_wtl(pc),a3
	moveq	#TD_NWT-1,d4
.mt:	moveq	#0,d0
	move.b	(a3)+,d0
	lsl.w	#2,d0
	add.w	TD_BASE,d0
	lsl.w	#5,d0
	bsr.w	td_vwrite
	moveq	#32-1,d1
.w:	move.l	(a2)+,VDP_DATA
	dbra	d1,.w
	dbra	d4,.mt
	moveq	#0,d2
.out:	move.w	d2,TD_ANIMI
	movem.l	(a7)+,d2-d5/a2-a3
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
	add.w	#20+TD_SHR,d6
	bsr.w	td_draw_col
	bra.s	.xr
.xl:	cmp.w	TD_CX0,d4
	bge.s	.yd
	subq.w	#1,TD_CX0
	move.w	TD_CX0,d6
	subq.w	#TD_SHL,d6
	bsr.w	td_draw_col
	bra.s	.xl
.yd:	cmp.w	TD_CY0,d5
	ble.s	.yu
	addq.w	#1,TD_CY0
	move.w	TD_CY0,d7
	add.w	#TD_NROW-1,d7
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
	moveq	#TD_NROW-1,d4
.r:	bsr.s	td_draw_row
	addq.w	#1,d7
	dbra	d4,.r
	movem.l	(a7)+,d4-d7
	rts

td_draw_row:				; row d7, columns cx0-TD_SHL..cx0+20+TD_SHR
	movem.l	d5-d6,-(a7)
	move.w	TD_CX0,d6
	subq.w	#TD_SHL,d6
	moveq	#21+TD_SHL+TD_SHR-1,d5
.c:	bsr.s	td_draw_cell
	addq.w	#1,d6
	dbra	d5,.c
	movem.l	(a7)+,d5-d6
	rts

td_draw_col:				; column d6, rows cy0..cy0+TD_NROW-1
	movem.l	d5/d7,-(a7)
	move.w	TD_CY0,d7
	moveq	#TD_NROW-1,d5
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
	move.w	sr,-(a7)		; no VBlank update between address
	ori.w	#$0700,sr		; and data
	move.l	d3,VDP_CTRL
	move.l	d0,VDP_DATA
	addi.l	#$00800000,d3		; next tile row (+128 bytes)
	move.l	d3,VDP_CTRL
	move.l	d1,VDP_DATA
	move.w	(a7)+,sr
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
	clr.w	TD_UPTXT
	clr.w	TD_MSG
	clr.w	TD_HASBOX
	moveq	#0,d6			; row
.row:	bsr.w	td_poll_vb		; a scan takes ~1 frame: keep updating
	move.w	d6,d0			; read 36 words of row d6, cols 2..37
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
	sub.w	FONTBLK,d1
	andi.w	#$7FF,d1		; a blank, any attributes
	beq.w	.nx
	move.w	d0,d1
	andi.w	#$F800,d1		; no palette / priority / flips
	bne.s	.txt
	sub.w	BANKBASE,d0
	cmpi.w	#828,d0
	bcc.s	.txt
	move.w	d4,d0			; fix this cell
	add.w	d0,d0
	add.w	d5,d0
	bsr.w	td_vwrite
	move.w	FONTBLK,VDP_DATA
	bra.s	.nx
.txt:	cmpi.w	#TD_BROW,d6		; text above the HUD rows
	bcc.s	.band
	move.w	#1,TD_UPTXT
	bra.s	.nx
.band:	move.w	d4,d0			; screen column
	addq.w	#2,d0
	cmpi.w	#32,d0			; portrait
	bcs.s	.b1
	cmpi.w	#37,d0
	bls.s	.nx
.b1:	cmpi.w	#23,d6			; HUD box (rows 23-25, cols 22-29)
	bcs.s	.b2
	cmpi.w	#22,d0
	bcs.s	.b2
	cmpi.w	#29,d0
	bhi.s	.b2
	move.w	#1,TD_HASBOX
	bra.s	.nx
.b2:	move.w	d6,d1			; the game's own HUD place for this row
	sub.w	#TD_BROW,d1
	add.w	d1,d1
	lea	td_hsrc(pc),a0
	adda.w	d1,a0
	cmp.b	(a0)+,d0
	bcs.s	.msg
	cmp.b	(a0),d0
	bls.s	.nx
.msg:	move.w	#1,TD_MSG
.nx:	addq.w	#1,d4
	cmpi.w	#36,d4
	bcs.w	.col
	addq.w	#1,d6
	cmpi.w	#26,d6
	bcs.w	.row
	movem.l	(a7)+,d2-d6/a2
	rts

td_hsrc:	; columns of the game's HUD words, rows 20-25 (lo, hi)
	dc.b	6,9, 7,13, 10,13, 11,16, 14,16, 15,18

;=======================================================================
; td_hud — once per tick: move the HUD words the game (re)drew into the
; box left of the portrait and blank them where the game put them.
; Labels GOLD / TIME are dropped ($ and AM/PM say it). Not while a
; message is in the HUD rows (its words would be mistaken for HUD).
;=======================================================================
td_hud:
	tst.w	TD_MSG
	bne.w	.out
	movem.l	d2-d7/a2-a3,-(a7)
	lea	td_hseg(pc),a3
.seg:	moveq	#0,d2
	move.b	(a3)+,d2		; source row (0 = end)
	beq.w	.done
	moveq	#0,d3
	move.b	(a3)+,d3		; source column
	moveq	#0,d4
	move.b	(a3)+,d4		; length
	moveq	#0,d5
	move.b	(a3)+,d5		; dest row (0 = blank only)
	moveq	#0,d6
	move.b	(a3)+,d6		; dest column
	addq.w	#1,a3
	bsr.w	.addr
	move.w	d0,d7			; source address
	bsr.w	td_vcmd
	move.l	d0,VDP_CTRL
	lea	TD_ROW,a2
	move.w	d4,d0
	subq.w	#1,d0
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d0,.rd
	lea	TD_ROW,a2		; anything there?
	move.w	d4,d0
	subq.w	#1,d0
.ck:	move.w	(a2)+,d1
	sub.w	FONTBLK,d1
	andi.w	#$7FF,d1
	bne.s	.mv
	dbra	d0,.ck
	bra.s	.seg
.mv:	tst.w	d5
	beq.s	.blank
	move.w	d5,d2			; copy into the box
	move.w	d6,d3
	bsr.s	.addr
	bsr.w	td_vwrite
	lea	TD_ROW,a2
	move.w	d4,d0
	subq.w	#1,d0
.wr:	move.w	(a2)+,VDP_DATA
	dbra	d0,.wr
	move.w	#1,TD_HASBOX
.blank:	move.w	d7,d0			; blank the source
	bsr.w	td_vwrite
	move.w	d4,d0
	subq.w	#1,d0
.bl:	move.w	FONTBLK,VDP_DATA
	dbra	d0,.bl
	bra.w	.seg
.done:	movem.l	(a7)+,d2-d7/a2-a3
.out:	rts
.addr:	move.w	d2,d0			; d0 = $1000 + row*128 + col*2
	lsl.w	#7,d0
	move.w	d3,d1
	add.w	d1,d1
	add.w	d1,d0
	add.w	#$1000,d0
	rts

td_hseg:	; src row, src col, len, dest row (0 = blank only), dest col, pad
	dc.b	21,7,7, 23,22,0		; gold
	dc.b	23,11,6, 24,22,0	; time
	dc.b	24,14,3, 25,22,0	; F/W
	dc.b	25,15,4, 25,25,0	; food / water bars
	dc.b	20,6,4, 0,0,0		; GOLD
	dc.b	22,10,4, 0,0,0		; TIME
	dc.b	0
	even

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
	bne.s	.bad
	cmpi.w	#$38E,TD_BASE
	bne.s	.out
	move.w	#TD_BTAB+TD_BROW*128,d0	; band table, first band cell
	bsr.w	td_vread
	move.w	TD_BASE,d1
	add.w	#256+$2000,d1
	cmp.w	d1,d0
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
	cmpi.w	#$38E,TD_BASE		; static Plane B table: transparent
	bne.s	.nob			; above the band, parchment in it
	move.w	#TD_BTAB,d0
	bsr.w	td_vwrite
	move.w	#64*TD_BROW-1,d0
.bt:	move.w	FONTBLK,VDP_DATA
	dbra	d0,.bt
	move.w	TD_BASE,d1
	add.w	#256+$2000,d1
	move.w	#64*(32-TD_BROW)-1,d0
.bb:	move.w	d1,VDP_DATA
	dbra	d0,.bb
.nob:	move.w	TD_BASE,d0		; HUD box: 12 solid parchment tiles
	add.w	#TD_BOXT,d0
	lsl.w	#5,d0
	bsr.w	td_vwrite
	moveq	#12*8-1,d0
.bx:	move.l	#$CCCCCCCC,VDP_DATA
	dbra	d0,.bx
	move.w	#1,TD_TILES
	lea	TD_FC,a0		; figure cache empty (key $FFFF)
	moveq	#TD_NFC-1,d0
.fc:	move.l	#$FFFF0000,(a0)+
	dbra	d0,.fc
	movem.l	(a7)+,d2-d7/a2-a4
	rts

;=======================================================================
; Data (generated: pixel-double table, blank + blob tiles).
;=======================================================================
td_wtl:	; water map tiles (contain colours 1/2)
	dc.b 9,10,11,12,13,14,15,17,18,19,21,22,23,34,37,38,39,45,46,61
	even
td_swap:	; byte with nibbles 2<->4 swapped
	dc.b $00,$01,$04,$03,$02,$05,$06,$07,$08,$09,$0A,$0B,$0C,$0D,$0E,$0F
	dc.b $10,$11,$14,$13,$12,$15,$16,$17,$18,$19,$1A,$1B,$1C,$1D,$1E,$1F
	dc.b $40,$41,$44,$43,$42,$45,$46,$47,$48,$49,$4A,$4B,$4C,$4D,$4E,$4F
	dc.b $30,$31,$34,$33,$32,$35,$36,$37,$38,$39,$3A,$3B,$3C,$3D,$3E,$3F
	dc.b $20,$21,$24,$23,$22,$25,$26,$27,$28,$29,$2A,$2B,$2C,$2D,$2E,$2F
	dc.b $50,$51,$54,$53,$52,$55,$56,$57,$58,$59,$5A,$5B,$5C,$5D,$5E,$5F
	dc.b $60,$61,$64,$63,$62,$65,$66,$67,$68,$69,$6A,$6B,$6C,$6D,$6E,$6F
	dc.b $70,$71,$74,$73,$72,$75,$76,$77,$78,$79,$7A,$7B,$7C,$7D,$7E,$7F
	dc.b $80,$81,$84,$83,$82,$85,$86,$87,$88,$89,$8A,$8B,$8C,$8D,$8E,$8F
	dc.b $90,$91,$94,$93,$92,$95,$96,$97,$98,$99,$9A,$9B,$9C,$9D,$9E,$9F
	dc.b $A0,$A1,$A4,$A3,$A2,$A5,$A6,$A7,$A8,$A9,$AA,$AB,$AC,$AD,$AE,$AF
	dc.b $B0,$B1,$B4,$B3,$B2,$B5,$B6,$B7,$B8,$B9,$BA,$BB,$BC,$BD,$BE,$BF
	dc.b $C0,$C1,$C4,$C3,$C2,$C5,$C6,$C7,$C8,$C9,$CA,$CB,$CC,$CD,$CE,$CF
	dc.b $D0,$D1,$D4,$D3,$D2,$D5,$D6,$D7,$D8,$D9,$DA,$DB,$DC,$DD,$DE,$DF
	dc.b $E0,$E1,$E4,$E3,$E2,$E5,$E6,$E7,$E8,$E9,$EA,$EB,$EC,$ED,$EE,$EF
	dc.b $F0,$F1,$F4,$F3,$F2,$F5,$F6,$F7,$F8,$F9,$FA,$FB,$FC,$FD,$FE,$FF
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
