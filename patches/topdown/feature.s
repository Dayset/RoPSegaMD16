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
; A+B+C cycles original -> top-down -> smooth iso (#252: the game's own
; iso render, run only on a camera step and resumable across ticks, tiled
; into a pool on Plane B at global positions, hardware-scrolled behind a
; fixed parchment frame; see "SMOOTH ISO VIEW" below) -> original.
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
; RAM: $FFDC00-$FFE55F (+ iso pool tables $FFD2EA-$FFDA07) (free in play: the attract buffer ends at
; $FFDBEA, the stack low-water mark seen on the playtest routes is
; $FFE972; the boot RAM clear resets it).

	org ORGVAL

; ---- tuning ----------------------------------------------------------
TD_T1		equ 26		; frames per world tick, overworld (orig avg 26.5)
TD_T2		equ 17		; frames per world tick, rooms (orig 17.0)
TD_TF		equ 22		; overworld on the dragon (orig attract flight 22.0)
TD_TS		equ 19		; boat / ship (orig over open sea 17-19)
TD_TB		equ 22		; big (32x32) rooms (orig room 156: 22)
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
TD_TMP		equ TD_UPTXT+14	; cell being drawn is raised (height > 0)
TD_BTOP		equ TD_UPTXT+16	; first plane tile row of the HUD band
TD_GSPON	equ TD_UPTXT+18	; game sprites above the band get priority
TD_RAISED	equ TD_UPTXT+20	; 64 B: ring cell (cy&15, cx&31) is raised
TD_GSP		equ TD_RAISED+64	; 80 words: tile word we gave priority to
TD_WROW		equ TD_GSP+160	; 40-word window row buffer
TD_ROWB		equ TD_WROW+80	; 64-word plane row buffer
TD_ISO		equ TD_ROWB+128	; smooth iso view (with TD_OFF = 0)
TD_IREQ		equ TD_ISO+2	; iso render requested
TD_REND		equ TD_ISO+4	; inside our map_chunk_pos call (no figures)
TD_ICX		equ TD_ISO+6	; camera cell of the plane picture ($8000 none)
TD_ICY		equ TD_ISO+8
TD_IOX		equ TD_ISO+10	; global tile column / row of bitmap tile (0,0)
TD_IOY		equ TD_ISO+12
TD_INX		equ TD_ISO+14	; the same for the render in progress
TD_INY		equ TD_ISO+16
TD_IGEN		equ TD_ISO+18	; render generation (tile pool ages)
TD_IGX		equ TD_ISO+20	; camera: global pixel at screen (0,0)
TD_IGY		equ TD_ISO+22
TD_NFCV		equ TD_ISO+24	; figure cache slots in use
TD_MAIN		equ TD_ISO+26	; this update may call the game (main thread)
TD_TLIFT	equ TD_ISO+28	; lift of the char being listed (iso)
TD_UNFR		equ TD_ISO+30	; td_iso_winfix: remove the frame instead
TD_ICAM		equ TD_ISO+32	; camera glide (lx, ly, fpx, fpy, t0) = 10 B
TD_CLK		equ TD_ISO+42	; 4 x 56 words: lift cell x, y, lift, last image key
TD_XF		equ TD_CLK+448	; the blob list is already in iso screen form
TD_INWF		equ TD_XF+2	; inside td_iso_winfix
TD_ISOU		equ TD_INWF+2	; iso chosen (A+B+C); TD_ISO = in effect
TD_IRS		equ TD_ISOU+2	; iso render state: 0 idle, 1 render, 2 commit
TD_IROW		equ TD_ISOU+4	; next map_chunk_pos row (render) / bitmap row (commit)
TD_IRX		equ TD_ISOU+6	; camera cell of the render in progress
TD_IRY		equ TD_ISOU+8
TD_ISH		equ TD_ISOU+10	; its X-table shift
TD_IBAIL	equ TD_ISOU+12	; map_chunk_pos stopped early (tick time up)
TD_INOB		equ TD_ISOU+14	; no time limit (first picture)
TD_WFC		equ TD_ISOU+16	; iso tick counter (window scan cadence)
TD_CMX		equ TD_ISOU+18	; iso camera (1/TI_CU cell)
TI_CU		equ 112		; camera units per cell (8 = 1 px across)
TI_CMAX		equ 8		; camera move cap per frame and axis (<= 2 px)
TD_CMY		equ TD_ISOU+20
TD_ICFR		equ TD_ISOU+22	; frame of its last update
TD_NAMES	equ TD_ISOU+24	; 64-word plane row buffer
TD_NBUF		equ TD_NAMES+128	; 36-word name buffer (one bitmap row)
TD_ILIN		equ TD_NBUF+72	; the render in progress is linear (fast streams)
TD_TT		equ TD_ILIN+2	; 32 B: the tile being committed, contiguous
TD_OLD		equ TD_TT+32	; 128 words: the plane row's names, twice
TD_VMASK	equ TD_OLD+256	; long: plane rows known to be all void
TD_IPH		equ TD_VMASK+4	; terrain phase ($FF0092) of the plane picture
TD_IRPH		equ TD_IPH+2	; ... of the render in progress
TD_PCX		equ TD_IRPH+2	; camera cell seen last (prediction)
TD_PCY		equ TD_PCX+2
TD_DX		equ TD_PCY+2	; its last step (-1..1 per axis)
TD_DY		equ TD_DX+2
TD_MVFR		equ TD_DY+2	; frame of that step
TD_IST		equ TD_MVFR+2	; frame the render in progress started
TD_ILAT		equ TD_IST+2	; frames the last picture took (start to plane)
TD_ICOL		equ TD_ILAT+2	; render stopped inside a row: its next column
TD_ICOLR	equ TD_ICOL+2	; ... pending for the resumed row
TD_PSLOT	equ TD_ICOLR+2	; pool slots in use (rooms lend 128 to figures)
TD_PSL24	equ TD_PSLOT+2	; TD_PSLOT - 24 (probe window start range)
TD_PEND		equ TD_PSL24+2	; bank offset past the pool's last slot
TD_LF0		equ TD_PEND+2	; 56 words: a char's lift at the start of its slide
TD_LFD		equ TD_LF0+112	; 56 words: its lift drawn last
TD_LFT		equ TD_LFD+112	; 56 words: the slide start (t0) TD_LF0 belongs to
TD_CGX		equ TD_LFT+112	; game camera cell seen last (camera glide)
TD_CGY		equ TD_CGX+2
TD_CFX		equ TD_CGY+2	; camera at that step (glide start)
TD_CFY		equ TD_CFX+2
TD_CT0		equ TD_CFY+2	; frame of that step
TD_IHLD		equ TD_CT0+2	; finished render held back (ti_hold)
TD_IHF		equ TD_IHLD+2	; frame the hold began
TD_MSEEN	equ TD_IHF+2	; frame td_tick's wait saw last
TD_END2		equ TD_MSEEN+2
TD_END		equ TD_END2

TI_NSLOT	equ 639		; iso tile pool slots (hash table, 24-slot probe)
TI_PHASH	equ $FFD2EA	; pool hashes (words) + ages (bytes): in the
TI_PGEN		equ TI_PHASH+2*TI_NSLOT	; attract buffer, unused in play
TI_POOLB	equ 401		; bank offset of pool slots 256-638 (401-783)
TI_EDGE		equ 784		; bank offset of the frame edge tiles (44)
TI_NFC		equ 8		; figure images cached in iso (tiles 273-400) ...
TI_NFCR		equ 16		; ... in rooms: 8 more in the pool's last 128
TI_NSLOTR	equ TI_NSLOT-128	; tiles (rooms: <= ~460 distinct per render)
TI_CX		equ 162		; hole centre and half sizes (screen px)
TI_CY		equ 98
TI_HW		equ 112
TI_HH		equ 64
XTAB		equ $FFAE7A	; map_chunk_pos X table (10 x 10 words)
CLEARBUF	equ $011DE8	; clear_decode_buffer
CHUNKPOS	equ $01BA4E	; map_chunk_pos(cx, cy): the 10 x 10 iso render
DESC2		equ $05EDC4	; iso cell descriptors (word per tile)
ISOFAST		equ $100000	; fast terrain streams (2 MB ROM, tools/iso_fast_streams.py)
TI_LMAX		equ 160		; linear render: lines drawn (rows 20-22 are never
				; committed; their 3,456 B hold td_extract's save)
TI_XSAVE	equ DECBUF+TI_LMAX*144	; 640 B
E358		equ $00E358	; map_terrain_tile_lookup
MASKT		equ $0433C0	; its byte -> keep-mask table

TD_BANDL	equ 152		; first screen line of the HUD band (untinted)
TD_NBAND	equ 13		; plane tile rows treated as band (lines 145..255)
TD_WBROW	equ 18		; window rows from here: blanks with priority
				; (line 144: covers the band row's top part)

NOPOS		equ $8000

;=======================================================================
; td_tick — replaces the room render in redraw_check. Syncs the view
; with the game, then waits out the rest of the tick, updating the
; picture once per frame.
;=======================================================================
td_tick:
	movem.l	d0-d7/a0-a6,-(a7)
	cmpi.w	#$7D7D,TD_MAGIC
	bne.w	.on
	tst.w	TD_REQ			; A+B+C: original -> top-down ->
	beq.s	.noreq			; smooth iso -> original
	clr.w	TD_REQ
	tst.w	TD_OFF
	bne.s	.toon
	tst.w	TD_ISOU
	bne.s	.toorg
	move.w	#1,TD_ISOU		; top-down -> iso (switched below)
	bra.s	.noreq
.toorg:	clr.w	TD_ISOU			; iso -> original
	addq.w	#1,TD_BUSY
	tst.w	TD_ISO
	beq.s	.o1
	bsr.w	td_iso_off
.o1:	bsr.w	td_restore
	move.w	#1,TD_OFF
	subq.w	#1,TD_BUSY
	bra.s	.noreq
.toon:	clr.w	TD_OFF			; original -> top-down
	clr.w	TD_ISOU
	clr.w	TD_ISO
	clr.w	TD_VALID		; reinstall from scratch
	clr.w	TD_TILES
.noreq:	tst.w	TD_OFF			; iso in effect = chosen, and not the
	bne.s	.noiso			; combat arena (grid $FFB0BC, drawn
	moveq	#0,d0			; zoomed by the game: the top-down
	tst.w	TD_ISOU			; picture stands in there)
	beq.s	.wi
	cmpi.l	#$FFB0BC,GRIDPTR
	beq.s	.wi
	moveq	#1,d0
.wi:	cmp.w	TD_ISO,d0
	beq.s	.noiso
	addq.w	#1,TD_BUSY
	tst.w	d0
	bne.s	.ion
	bsr.w	td_iso_off		; iso -> top-down
	bra.s	.ire
.ion:	bsr.w	td_restore		; top-down -> iso: the game's own scene
	move.w	#1,TD_ISO		; and HUD first, then install
.ire:	subq.w	#1,TD_BUSY
.noiso:	tst.w	TD_OFF
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
	beq.s	.ow
	movea.l	GRIDPTR,a0		; rooms: 32x32 ones at the original's
	cmpi.w	#32,(a0)		; slower pace (their render was slower)
	bcs.s	.per
	moveq	#TD_TB,d0
	bra.s	.per
.ow:
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
ti_tw0:
.wait:
	move.w	FRAME,d0		; once per frame (seen here, not by
	cmp.w	TD_MSEEN,d0		; TD_LASTFR: td_vint updates the picture
	beq.s	.wait			; itself while this loop waits, and the
	move.w	d0,TD_MSEEN		; loop then saw a new frame only when
	cmp.w	TD_LASTFR,d0		; the VBlank fell between two of its
	beq.s	.upd			; instructions: ticks ran 0-8 late, #289)
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
	tst.w	TD_ISO			; iso: render / commit what this tick
	beq.s	.chk			; has time for (VBlank keeps the glide
	bsr.w	td_iso_render		; going meanwhile)
.chk:	move.w	FRAME,d0
	move.w	d0,d1
	sub.w	TD_TICKFR,d1		; frames since the last tick ended
	cmp.w	TD_PERIOD,d1
	bcs.s	.wait			; < period: keep waiting
	move.w	d0,TD_TICKFR		; game logic starts near the top of
ti_tw1:
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
	cmpi.l	#ti_tw0,d0		; td_tick's wait (main thread idle, no
	bcs.s	.lst			; VDP sequence open): the full update
	cmpi.l	#ti_tw1,d0		; here, in VBlank, not late
	bcc.s	.lst
	bsr.w	td_frame
	bra.s	.out
.lst:	tst.w	TD_INWF			; iso window scan's helpers (also used
	beq.s	.l0			; from td_filt: only during the scan)
	cmpi.l	#ti_blankish,d0
	bcs.s	.l0
	cmpi.l	#ti_rows,d0
	bcs.s	.ns
.l0:	lea	td_vwl(pc),a0
.l:	move.l	(a0)+,d1
	beq.s	.out
	move.l	(a0)+,d2
	cmp.l	d1,d0
	bcs.s	.l
	cmp.l	d2,d0
	bcc.s	.l
.ns:	bsr.w	td_frame_ns
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
	dc.l	$00E358,$01107A		; map_terrain_tile_lookup (iso render)
	dc.l	ti_clear,ti_fend	; its fast form (ti_fast) + our clear
	dc.l	ISOFAST,ISOFAST+$100000	; the fast form's stubs (2 MB ROM)
	dc.l	$011DE8,$011E06		; clear_decode_buffer
	dc.l	$01BA4E,$01C0EC		; map_chunk_pos
	dc.l	$0232AC,$02343A		; map_tile_at_offset, map_animated_tile
	dc.l	ti_cstart,ti_cend	; td_iso_commit (VDP writes masked)
	dc.l	td_iso_winfix,ti_wend	; its window scan (likewise)
	dc.l	$03A062,$03A4A2		; spell target / effect arithmetic
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
	tst.w	TD_ISO			; iso: the frame word of that window
	beq.s	.k1			; cell (identity map: col 2 + t mod 36,
	movem.l	d2/a0,-(a7)		; row t / 36)
	andi.l	#$FFFF,d1
	divu.w	#36,d1
	move.w	d1,d2			; row
	swap	d1
	addq.w	#2,d1			; column
	bsr.w	ti_frameword
	movem.l	(a7)+,d2/a0
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
	bsr.w	td_gsp			; (GSPON is off): give back priorities
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
	tst.w	TD_ISO
	bne.w	td_isync
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
	bsr.w	td_bandtop
	move.w	d0,TD_BTOP
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
	move.w	d1,TD_MAIN
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
	tst.w	TD_IRS			; (while the decode buffer holds an iso
	beq.s	.cx			; render in progress only if it is linear:
	tst.w	TD_ILIN			; td_extract saves and restores its
	bne.s	.cx			; corner then, #270)
	clr.w	TD_CANX
.cx:
	tst.w	TD_ISO
	bne.w	td_iframe
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
	bsr.w	td_band
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
td_scroll:
	tst.w	TD_ISO
	bne.w	td_iso_scroll
	; per-line H-scroll: world row wy is shifted by floor(wy/2)
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
	tst.w	TD_ISO
	bne.w	td_ilayers
	move.w	#1,TD_LAY
	move.w	#$8B03,VDP_CTRL		; H-scroll per line
	move.w	#$8C89,VDP_CTRL		; H40 + shadow/highlight (height tint)
	moveq	#0,d0			; game sprites get priority only
	tst.w	$FF00AC			; with no menu and no upper text
	bne.s	.g
	tst.w	TD_UPTXT
	bne.s	.g
	moveq	#1,d0
.g:	move.w	d0,TD_GSPON
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
	clr.w	TD_GSPON
	move.w	#$8400,VDP_CTRL
	move.w	#$8B00,VDP_CTRL
	move.w	#$8C81,VDP_CTRL		; shadow/highlight off
	move.w	#$8700,VDP_CTRL		; backdrop colour 0 (iso: parchment)
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
; td_band — keep the HUD band untinted while the camera scrolls: plane
; tile rows under screen lines TD_BANDL.. (and the off-screen rows below)
; carry no priority bit, so the low-priority HUD sprites (portrait frame,
; HUD box, message scroll) stay on top and the window's high blanks keep
; them unshadowed. Rows that enter the band lose the bit; rows that leave
; it get it back from the raised bitmap.
;=======================================================================
td_bandtop:				; -> d0 = first band tile row (0-31)
	move.w	TD_CAMY,d0
	add.w	#TD_BANDL,d0
	asr.w	#3,d0
	andi.w	#31,d0
	rts

td_band:
	movem.l	d2-d6/a2,-(a7)
	bsr.s	td_bandtop
	move.w	TD_BTOP,d5		; old band
	cmp.w	d5,d0
	beq.s	.out
	move.w	d0,TD_BTOP
	move.w	d0,d6			; new band
	moveq	#31,d4			; tile row
.r:	move.w	d4,d0
	sub.w	d5,d0
	andi.w	#31,d0
	cmpi.w	#TD_NBAND,d0
	scs	d1			; in the old band
	move.w	d4,d0
	sub.w	d6,d0
	andi.w	#31,d0
	cmpi.w	#TD_NBAND,d0
	scs	d2			; in the new band
	cmp.b	d1,d2
	beq.s	.n
	bsr.s	td_rowfix
.n:	dbra	d4,.r
.out:	movem.l	(a7)+,d2-d6/a2
	rts

td_rowfix:				; d4 = tile row, d2.b = $FF: clear, 0: restore
	move.w	d4,d0
	lsl.w	#7,d0
	move.w	d0,d3			; row address
	bsr.w	td_vcmd
	move.l	d0,VDP_CTRL
	lea	TD_ROWB,a0
	moveq	#64-1,d1
.rd:	move.w	VDP_DATA,(a0)+
	dbra	d1,.rd
	lea	TD_ROWB,a0
	moveq	#64-1,d1
.cl:	andi.w	#$7FFF,(a0)+
	dbra	d1,.cl
	tst.b	d2
	bne.s	.wr
	move.w	d4,d0			; raised bits of cell row (r>>1)&15
	lsr.w	#1,d0
	lsl.w	#2,d0
	lea	TD_RAISED,a2
	adda.w	d0,a2
	lea	TD_ROWB,a0
	moveq	#0,d1			; cell column 0..31
.st:	move.w	d1,d0
	lsr.w	#3,d0
	btst	d1,(a2,d0.w)
	beq.s	.sn
	ori.w	#$8000,(a0)
	ori.w	#$8000,2(a0)
.sn:	addq.w	#4,a0
	addq.w	#1,d1
	cmpi.w	#32,d1
	bcs.s	.st
.wr:	move.w	d3,d0
	bsr.w	td_vwrite
	lea	TD_ROWB,a0
	moveq	#32-1,d1
.w:	move.l	(a0)+,VDP_DATA
	dbra	d1,.w
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
	lea	TD_CLK,a0		; lift cache, last images: nothing known
	moveq	#56-1,d1
.l:	move.w	#NOPOS,(a0)
	move.w	#NOPOS,336(a0)
	addq.l	#2,a0
	dbra	d1,.l
	rts

;=======================================================================
; td_chars — walk the 56 chars; update slide state; build the blob
; list (world pixel positions) and the leader position.
;=======================================================================
td_chars:
	movem.l	d2-d7/a2-a4,-(a7)
	addq.w	#1,TD_STAMP
	clr.w	TD_NB
	clr.w	TD_XF
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
	clr.w	TD_TLIFT
	tst.w	TD_ISO
	beq.s	.fig
	bsr.w	td_ilift		; iso: lift of its target cell
.fig:	bsr.w	td_figure		; d0 = figure tile word, or -1
	tst.w	d0
	bmi.s	.blob
	cmpi.w	#TD_NFIG,TD_NB
	bcc.w	.lchk
	move.w	d5,(a2)+
	move.w	d6,(a2)+
	move.w	d0,(a2)+
	move.w	TD_TLIFT,d0		; kind 1: 32x32 figure (lift << 8)
	lsl.w	#8,d0
	addq.w	#1,d0
	move.w	d0,(a2)+
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
	move.w	TD_TLIFT,d0		; kind 0: 16x16 blob (lift << 8)
	lsl.w	#8,d0
	move.w	d0,(a2)+
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
	bcc.w	.none
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
.k1:	move.w	d2,d6			; key (td_img uses d2)
	move.w	d2,d0
	bsr.s	td_img
	move.w	d7,d1			; this char's last image key
	add.w	d1,d1
	lea	TD_CLK+336,a0
	adda.w	d1,a0
	tst.w	d0
	bmi.s	.old
	move.w	d6,(a0)			; cached: remember it
	bra.s	.out
.old:	move.w	(a0),d0			; not cached yet: its last image if it
	cmpi.w	#NOPOS,d0		; is still in the cache (no blob)
	beq.s	.none
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
	move.w	TD_NFCV,d1
	subq.w	#1,d1
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
	move.w	TD_NFCV,d1
	subq.w	#1,d1
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
	tst.w	TD_ISO
	beq.s	.td
	cmpi.w	#TI_NFC*16,d0		; iso: slots 8+ in the tiles the pool
	bcs.s	.a			; lends in rooms (TD_PEND on)
	sub.w	#TI_NFC*16+TD_FCB,d0
	add.w	TD_PEND,d0
	bra.s	.a
.td:	cmpi.w	#22*16,d0
	bcs.s	.a
	add.w	#754-TD_FCB-22*16,d0
.a:	add.w	TD_BASE,d0
	add.w	#TD_FCB,d0
	rts

td_extract:
	movem.l	d0-d7/a0-a6,-(a7)
	bsr.w	ti_xswap		; a render in progress: save its corner
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
	bsr.s	ti_xswap		; ... and put it back
	movem.l	(a7)+,d0-d7/a0-a6
	rts

ti_xswap:	; iso linear render in progress: swap td_extract's 640 bytes
	; (tiled rows 2-6, cols 16-19) with TI_XSAVE (bitmap lines 160+,
	; never drawn or committed). Called before and after: a swap twice
	; restores both. (2 MB only: the linear render needs the fast streams.)
	ifd	SIZE2M
	tst.w	TD_IRS
	beq.s	.x
	tst.w	TD_ILIN
	beq.s	.x
	movem.l	d0-d2/a0-a1,-(a7)
	lea	DECBUF+(2*36+16)*32,a0
	lea	TI_XSAVE,a1
	moveq	#5-1,d1
.r:	moveq	#32-1,d0
.l:	move.l	(a0),d2
	move.l	(a1),(a0)+
	move.l	d2,(a1)+
	dbra	d0,.l
	lea	36*32-128(a0),a0
	dbra	d1,.r
	movem.l	(a7)+,d0-d2/a0-a1
.x:
	endif
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
.ours:	tst.w	TD_ISO			; iso: screen x + depth key
	beq.s	.srt
	bsr.w	ti_spr_xform
.srt:	; insertion sort, y descending (8-byte entries)
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
.nobox:	lea	TD_LIST,a2
	tst.w	TD_ISO
	bne.w	.icond
	move.w	TD_CAMY,d0		; shear reference: the leader's line
	add.w	#TD_VC,d0
	asr.w	#1,d0
	movea.w	d0,a1
	lea	TD_LIST,a2
	bra.w	.cond
.spr:	move.w	(a2)+,d2		; px
	move.w	(a2)+,d3		; py
	move.w	(a2)+,d4		; tile word
	move.w	(a2)+,d1		; kind
	andi.w	#$FF,d1
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
	move.w	d3,d0			; above the HUD band: priority, so raised
	add.w	#16,d0			; (priority) cells never hide it; in the
	cmpa.w	#$0500,a3		; band: low, under the HUD
	beq.s	.pb
	add.w	#16,d0
.pb:	cmpi.w	#TD_BANDL+8,d0
	bgt.s	.pw
	ori.w	#$8000,d4
.pw:
.put:	moveq	#TD_SLOT0,d0		; VRAM address of slot TD_SLOT0+d6
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
.cond:	tst.w	TD_ISO
	bne.s	.icond
	dbra	d7,.spr
	bra.s	.endl
.ispr:	move.w	(a2)+,d2		; iso entry: screen x ($8000 = culled),
	move.w	(a2)+,d3		; depth y (global), tile, lift << 8 | kind
	move.w	(a2)+,d4
	move.w	(a2)+,d1
	cmpi.w	#$8000,d2
	beq.s	.icond
	move.w	d1,d0
	lsr.w	#8,d0
	sub.w	d0,d3			; top = depth y - 8 - lift - camera
	subq.w	#8,d3
	sub.w	TD_IGY,d3
	movea.w	#$0F00,a3		; 32x32
	tst.b	d1
	bne.s	.ik
	addq.w	#8,d2			; blob: 16x16 in the middle
	addq.w	#8,d3
	movea.w	#$0500,a3
.ik:	cmpi.w	#-32,d2
	ble.s	.icond
	cmpi.w	#320,d2
	bge.s	.icond
	cmpi.w	#-32,d3
	ble.s	.icond
	cmpi.w	#224,d3
	blt.w	.put
.icond:	dbra	d7,.ispr
.endl:	move.w	TD_GHEAD,d2
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
	bsr.s	td_gsp
	movem.l	(a7)+,d2-d7/a2-a3
	rts

;=======================================================================
; td_gsp — the game's own sprites above the HUD band (pad icon) are low
; priority: give them the priority bit while no menu / upper text is up
; (raised map cells would hide them, height-0 cells would shadow them);
; otherwise put back the words we changed (only if still ours).
;=======================================================================
td_gsp:
	movem.l	d2-d5/a2,-(a7)
	lea	TD_GSP,a2
	tst.w	TD_GSPON
	bne.s	.on
	moveq	#80-1,d5
	moveq	#0,d4
.rv:	move.w	(a2),d3
	beq.s	.rn
	clr.w	(a2)
	move.w	d4,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	addq.w	#4,d0
	move.w	d0,d2
	bsr.w	td_vread
	cmp.w	d3,d0
	bne.s	.rn
	move.w	d2,d0
	bsr.w	td_vwrite
	andi.w	#$7FFF,d3
	move.w	d3,VDP_DATA
.rn:	addq.l	#2,a2
	addq.w	#1,d4
	dbra	d5,.rv
	bra.s	.out
.on:	move.w	TD_GHEAD,d4		; walk the game's chain
	moveq	#80-1,d5
.w:	andi.w	#$7F,d4
	beq.s	.out
	cmpi.w	#TD_SLOT0,d4
	bcc.s	.out
	move.w	d4,d0
	lsl.w	#3,d0
	add.w	SPRBASE,d0
	move.w	d0,d2			; entry address
	bsr.w	td_vread		; y + 128
	move.w	d0,d3
	move.w	d2,d0
	addq.w	#2,d0
	bsr.w	td_vread		; size | link
	move.w	d0,-(a7)
	lsr.w	#8,d0			; height in cells - 1
	andi.w	#3,d0
	addq.w	#1,d0
	lsl.w	#3,d0
	add.w	d0,d3			; bottom + 128
	cmpi.w	#TD_BANDL+128,d3
	bgt.s	.nx
	move.w	d2,d0
	addq.w	#4,d0
	bsr.w	td_vread		; tile word
	tst.w	d0
	bmi.s	.nx
	ori.w	#$8000,d0
	move.w	d0,d3
	move.w	d4,d1
	add.w	d1,d1
	move.w	d3,(a2,d1.w)
	move.w	d2,d0
	addq.w	#4,d0
	bsr.w	td_vwrite
	move.w	d3,VDP_DATA
.nx:	move.w	(a7)+,d4
	dbra	d5,.w
.out:	movem.l	(a7)+,d2-d5/a2
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
TD_SWAPT	equ DECBUF+13*1152	; 256 B shimmer swap table (built at load;
TD_DBLT		equ TD_SWAPT+256	; free rows of the decode buffer in
					; top-down) + 512 B pixel-double table
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
.run:	lea	TD_SWAPT,a3
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
	move.w	d2,d0			; height (bits 13-15) -> raised flag
	andi.w	#$E000,d0
	move.w	d0,TD_TMP
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
	move.w	#1,TD_TMP		; (never shadowed)
	move.w	TD_BASE,d0
	add.w	#256+$2000,d0		; palette 1
	move.w	d0,d1
	swap	d0
	move.w	d1,d0
	move.l	d0,d1
td_cell_put:	; d0 = TL:TR, d1 = BL:BR, TD_TMP = raised.
	; Height tint: a raised cell's tiles get the priority bit (not
	; shadowed), except in plane rows inside the HUD band. The raised
	; bitmap lets td_band restore the bit when a row leaves the band.
	move.w	d7,d2			; bit (cy&15)*32 + (cx&31)
	andi.w	#15,d2
	lsl.w	#5,d2
	move.w	d6,d3
	andi.w	#31,d3
	add.w	d3,d2
	move.w	d2,d3
	lsr.w	#3,d3
	lea	TD_RAISED,a0
	adda.w	d3,a0
	tst.w	TD_TMP
	beq.s	.lo
	bset	d2,(a0)
	move.w	d7,d2			; top tile row in the band?
	add.w	d2,d2
	sub.w	TD_BTOP,d2
	andi.w	#31,d2
	cmpi.w	#TD_NBAND,d2
	bcs.s	.t1
	ori.l	#$80008000,d0
.t1:	addq.w	#1,d2			; bottom tile row
	andi.w	#31,d2
	cmpi.w	#TD_NBAND,d2
	bcs.s	.ad
	ori.l	#$80008000,d1
	bra.s	.ad
.lo:	bclr	d2,(a0)
.ad:	; VRAM address: ((2cy & 31) * 64 + (2cx & 63)) * 2
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
	tst.w	TD_ISO
	bne.w	td_iso_pcheck
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
	moveq	#0,d2			; found: bit 0 upper text, 1 message,
	moveq	#0,d6			; 2 HUD box (committed at the end, so
					; updates during the scan see the last
					; tick's state); d6 = row
.row:	bsr.w	td_poll_vb		; a scan takes ~1 frame: keep updating
	move.w	d6,d0			; read the 40 visible words of row d6
	lsl.w	#7,d0
	add.w	#$1000,d0
	move.w	d0,d5			; row address
	andi.l	#$3FFF,d0
	swap	d0
	move.l	d0,VDP_CTRL
	lea	TD_WROW,a2
	moveq	#40-1,d1
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d1,.rd
	lea	TD_WROW,a2
	moveq	#0,d4			; column 0..39
.col:	move.w	(a2)+,d0
	move.w	d0,d1
	sub.w	FONTBLK,d1
	andi.w	#$7FF,d1		; a blank, any attributes
	bne.s	.nb
	cmpi.w	#TD_WBROW,d6		; HUD band: blanks with priority, so
	bcs.w	.nx			; the map under them is not shadowed
	tst.w	d0
	bmi.w	.nx
	move.w	FONTBLK,d1
	ori.w	#$8000,d1
	bra.s	.fix
.nb:	move.w	d0,d1
	andi.w	#$F800,d1		; no palette / priority / flips
	bne.s	.txt
	sub.w	BANKBASE,d0
	cmpi.w	#828,d0
	bcc.s	.txt
	move.w	FONTBLK,d1		; a room-bitmap word: blank it
	cmpi.w	#TD_WBROW,d6
	bcs.s	.fix
	ori.w	#$8000,d1
.fix:	move.w	d4,d0
	add.w	d0,d0
	add.w	d5,d0
	bsr.w	td_vwrite
	move.w	d1,VDP_DATA
	bra.s	.nx
.txt:	cmpi.w	#TD_BROW,d6		; text above the HUD rows
	bcc.s	.band
	bset	#0,d2
	bra.s	.nx
.band:	cmpi.w	#26,d6			; below the HUD rows: a message
	bcc.s	.msg
	move.w	d4,d0			; screen column
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
	bset	#2,d2
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
.msg:	bset	#1,d2
.nx:	addq.w	#1,d4
	cmpi.w	#40,d4
	bcs.w	.col
	addq.w	#1,d6
	cmpi.w	#28,d6
	bcs.w	.row
	moveq	#0,d0
	btst	#0,d2
	sne	d0
	move.w	d0,TD_UPTXT
	btst	#1,d2
	sne	d0
	move.w	d0,TD_MSG
	btst	#2,d2
	sne	d0
	move.w	d0,TD_HASBOX
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
.blank:	move.w	d7,d0			; blank the source (band blank:
	bsr.w	td_vwrite		; priority, not shadowed)
	move.w	FONTBLK,d1
	ori.w	#$8000,d1
	move.w	d4,d0
	subq.w	#1,d0
.bl:	move.w	d1,VDP_DATA
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
	cmpi.w	#$0DDE,d0
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
	lea	TD_SWAPT,a0		; build the swap and pixel-double
	lea	TD_DBLT,a1		; tables: byte b = (hi, lo) ->
	lea	td_nsw(pc),a2		; nsw[hi] nsw[lo], word hi hi lo lo
	moveq	#0,d0
.tb:	move.w	d0,d1
	lsr.w	#4,d1
	move.b	(a2,d1.w),d2
	lsl.b	#4,d2
	move.w	d0,d3
	andi.w	#15,d3
	or.b	(a2,d3.w),d2
	move.b	d2,(a0)+
	move.w	d1,d2			; hi * $1100 + lo * $0011
	lsl.w	#4,d2
	or.w	d1,d2
	lsl.w	#8,d2
	move.w	d3,d1
	lsl.w	#4,d1
	or.w	d3,d1
	or.w	d1,d2
	move.w	d2,(a1)+
	addq.w	#1,d0
	cmpi.w	#256,d0
	bcs.s	.tb
	lea	DECBUF,a3		; 64 source tiles
	lea	DECBUF+$800,a4		; 256 scaled tiles
	lea	TD_DBLT,a2
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
	movea.l	a4,a0			; blank + blobs
	movea.w	#4,a1
	bsr.w	td_blobs
	; DMA (256 + 17) tiles to VRAM
	move.w	#(256*32+TD_NGFX)/2,-(a7)
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
	move.w	#TD_NFC,TD_NFCV
	lea	TD_FC,a0		; figure cache empty (key $FFFF)
	moveq	#TD_NFC-1,d0
.fc:	move.l	#$FFFF0000,(a0)+
	dbra	d0,.fc
	movem.l	(a7)+,d2-d7/a2-a4
	rts

;=======================================================================
; SMOOTH ISO VIEW (#252). The game's own isometric render, run only when
; the camera cell changes and with no figures in it, lands on a global
; 8-px grid (X table shifted so every render aligns), is cut into tiles
; that are deduplicated into a pool (hash table, ages by render), and
; is written to Plane B at global tile positions. The camera glides
; between cells by hardware scroll; figures are the top-down's cached
; images as sprites. A fixed parchment frame in the window hides the
; render's edges (the hole is the camera's cells within +-4).
;=======================================================================

; td_iso_off — leave iso: frame off, top-down reinstalls from scratch.
td_iso_off:
	bsr.w	td_iso_cancel
	move.w	#1,TD_UNFR
	bsr.w	td_iso_winfix
	clr.w	TD_UNFR
	clr.w	TD_ISO
	clr.w	TD_VALID
	clr.w	TD_TILES
	bra.w	td_unlay

; td_isync — td_sync's tail in iso (td_sync branches here).
td_isync:
	bsr.w	td_iso_check
	tst.w	TD_TILES
	bne.s	.tok
	bsr.w	td_iso_load
.tok:	tst.w	TD_VALID		; window scan: on install, then every
	beq.s	.wf			; 4th tick (it costs ~2 frames; td_filt
	addq.w	#1,TD_WFC		; catches the game's room-bitmap words)
	move.w	TD_WFC,d0
	andi.w	#3,d0
	bne.s	.nwf
.wf:	subq.w	#1,TD_BUSY		; VBlank updates may run inside the
	bsr.w	td_iso_winfix		; scan (td_vwl)
	addq.w	#1,TD_BUSY
.nwf:
	tst.w	TD_VALID
	beq.w	.full
	bsr.w	td_iso_pcheck
	tst.w	d0
	bne.w	.full
	bsr.w	ti_target		; d6/d7 = the cell to show (one ahead
	tst.w	TD_IRS			; while walking)
	beq.s	.idle
	move.w	TD_IRX,d0		; a render in progress off the camera's
	move.w	TD_IRY,d1		; path (camera cell + 0..2 steps: a turn,
	move.w	$FF0E8E,d2		; a stop, a phase-only render) gives way
	move.w	$FF0E90,d3
	moveq	#3-1,d4
.r1:	cmp.w	d2,d0
	bne.s	.r2
	cmp.w	d3,d1
	beq.s	.onp
.r2:	add.w	TD_DX,d2
	add.w	TD_DY,d3
	dbra	d4,.r1
	bra.s	.drop
.onp:	tst.w	TD_IHLD			; on the path but held back (ti_hold)
	beq.s	.out			; and the camera stopped stepping:
	move.w	FRAME,d0		; the prediction missed, drop it
	sub.w	TD_MVFR,d0
	move.w	TD_PERIOD,d1
	add.w	d1,d1
	cmp.w	d1,d0
	bcs.s	.out
.drop:	bsr.w	td_iso_cancel
	bra.s	.mv
.idle:	cmp.w	TD_ICX,d6		; (td_tick renders it, after this)
	bne.s	.mv
	cmp.w	TD_ICY,d7
	bne.s	.mv
	move.w	$FF0092,d0		; standing still: the terrain phase
	cmp.w	TD_IPH,d0		; (water etc., toggled every tick)
	beq.s	.out			; changed: render it too (#266 item 3)
.mv:	move.w	#1,TD_IREQ
.out:	rts
.full:	bsr.w	td_iso_cancel		; (re)install: camera on the cell,
	bsr.w	ti_cfg
	clr.w	TD_VALID		; picture by td_tick's render
	move.w	#$8000,TD_PCX		; no prediction yet
	move.w	#1,TD_MAIN
	move.w	#1,TD_CANX
	bsr.w	td_chars
	move.w	#1,TD_IREQ
	rts

; td_iframe — td_frame_go's world update in iso.
td_iframe:
	bsr.w	td_chars
	bsr.w	td_iso_cam
	bsr.w	td_layers
	bsr.w	td_iso_scroll		; vblank-critical first
	bra.w	td_sprites

td_ilayers:
	move.w	#1,TD_LAY
	clr.w	TD_GSPON
	clr.w	TD_BAND
	clr.w	TD_BOX
	move.w	#TI_CY+TI_HH,TD_YMAX
	move.w	#$8B00,VDP_CTRL		; full-screen scroll
	move.w	#$8C81,VDP_CTRL		; no shadow/highlight
	move.w	#$871C,VDP_CTRL		; backdrop: parchment (pal 1 colour 12)
	move.w	#$8400,VDP_CTRL		; the game's window over the whole
	move.w	#$9180,VDP_CTRL		; screen, picture on Plane B
	move.w	#$9200,VDP_CTRL
	rts

td_iso_scroll:
	move.l	#$40000010,VDP_CTRL	; VSRAM 0: A, B
	move.w	TD_IGY,d0
	subq.w	#6,d0			; global row 6 = plane line 0
	move.w	d0,VDP_DATA
	move.w	d0,VDP_DATA
	move.l	#$60000000,VDP_CTRL	; H-scroll $2000: A, B
	move.w	TD_IGX,d0
	neg.w	d0
	move.w	d0,VDP_DATA
	move.w	d0,VDP_DATA
	rts

; td_iso_pcheck -> d0 != 0 if the plane no longer holds our picture
; (two cells of the last render: pool, void or edge tiles only).
td_iso_pcheck:
	movem.l	d2-d3,-(a7)
	moveq	#18,d2
	moveq	#11,d3
	bsr.s	.one
	moveq	#12,d2
	moveq	#8,d3
	bsr.s	.one
	moveq	#0,d0
	bra.s	.out
.bad:	addq.w	#4,a7
	moveq	#1,d0
.out:	movem.l	(a7)+,d2-d3
	rts
.one:	add.w	TD_IOY,d3
	andi.w	#31,d3
	lsl.w	#7,d3
	add.w	TD_IOX,d2
	andi.w	#63,d2
	add.w	d2,d2
	add.w	d3,d2
	move.w	d2,d0
	bsr.w	td_vread
	andi.w	#$7FF,d0
	sub.w	TD_BASE,d0
	cmpi.w	#TI_EDGE,d0		; pool, void, blobs or our figures
	bcc.s	.bad
	rts

; td_iso_cam — camera (TD_CMX/CMY, 1/TI_CU cell) -> TD_IGX / TD_IGY
; (global px at screen (0,0), the original's framing of that cell). Each
; step of the game camera is glided over one tick (TD_PERIOD frames), the
; leader figure's own slide timing, so the ground moves at the walking
; pace with no stop-go per cell. The camera stays within one cell of the
; picture on the plane (TD_ICX/ICY) and moves at most TI_CMAX per frame
; (catching up after being held).
td_iso_cam:
	movem.l	d2-d5,-(a7)
	move.w	FRAME,d0
	cmp.w	TD_ICFR,d0
	beq.w	.xy			; one move per frame
	move.w	d0,TD_ICFR
	move.w	$FF0E8E,d0		; a game camera step: glide from here
	move.w	$FF0E90,d1
	cmp.w	TD_CGX,d0
	bne.s	.ns
	cmp.w	TD_CGY,d1
	beq.s	.el
.ns:	move.w	d0,TD_CGX
	move.w	d1,TD_CGY
	move.w	TD_CMX,TD_CFX
	move.w	TD_CMY,TD_CFY
	move.w	FRAME,TD_CT0
.el:	move.w	FRAME,d4		; d4 = elapsed (0..T)
	sub.w	TD_CT0,d4
	bmi.s	.full
	cmp.w	TD_PERIOD,d4
	bls.s	.e1
.full:	move.w	TD_PERIOD,d4
.e1:	move.w	TD_CGX,d0
	move.w	TD_ICX,d1
	move.w	TD_CFX,d5
	lea	TD_CMX,a0
	bsr.s	.ax
	move.w	TD_CGY,d0
	move.w	TD_ICY,d1
	move.w	TD_CFY,d5
	lea	TD_CMY,a0
	bsr.s	.ax
.xy:	move.w	TD_CMX,d0
	sub.w	TD_CMY,d0
	asr.w	#3,d0			; 14 (x - y) / 112
	sub.w	#148,d0
	move.w	d0,TD_IGX
	moveq	#0,d0
	move.w	TD_CMX,d0
	moveq	#0,d1
	move.w	TD_CMY,d1
	add.l	d1,d0
	divu.w	#14,d0			; 8 (x + y) / 112
	sub.w	#98,d0
	move.w	d0,TD_IGY
	movem.l	(a7)+,d2-d5
	rts
.ax:	mulu.w	#TI_CU,d0		; d0 = game cell, d1 = picture cell,
	mulu.w	#TI_CU,d1		; d5 = glide start, d4 = elapsed
	move.w	d0,d2
	sub.w	(a0),d2			; more than 3 cells away: snap
	bpl.s	.a1
	neg.w	d2
.a1:	cmpi.w	#3*TI_CU,d2
	bls.s	.gl
	move.w	d0,(a0)
	rts
.gl:	sub.w	d5,d0			; want = start + (cell - start) el / T
	muls.w	d4,d0
	divs.w	TD_PERIOD,d0
	add.w	d5,d0
	move.w	d1,d2			; ... within one cell of the picture
	sub.w	#TI_CU,d2
	cmp.w	d2,d0
	bge.s	.c1
	move.w	d2,d0
.c1:	add.w	#2*TI_CU,d2
	cmp.w	d2,d0
	ble.s	.c2
	move.w	d2,d0
.c2:	sub.w	(a0),d0			; ... at most TI_CMAX per frame
	cmpi.w	#TI_CMAX,d0
	ble.s	.m1
	moveq	#TI_CMAX,d0
.m1:	cmpi.w	#-TI_CMAX,d0
	bge.s	.m2
	moveq	#-TI_CMAX,d0
.m2:	add.w	d0,(a0)
	rts

td_iso_glide:	; (the camera follows by itself)
	rts

td_iso_snap:				; camera on the picture's cell now
	move.w	TD_ICX,d0
	mulu.w	#TI_CU,d0
	move.w	d0,TD_CMX
	move.w	TD_ICY,d0
	mulu.w	#TI_CU,d0
	move.w	d0,TD_CMY
	move.w	FRAME,TD_ICFR
	rts

; td_ilift — iso lift (px) of the target cell of char d7 (slide record
; a4) -> TD_TLIFT: (height + desc bit 7) * 7 + desc bit 8 * 4, as
; map_chunk_pos passes it to hero_track. Cached per char; read from the
; map only when game calls are allowed (TD_MAIN).
td_ilift:
	movem.l	d0-d3/a0-a2,-(a7)
	move.w	d7,d1
	add.w	d1,d1
	lea	TD_CLK,a1
	adda.w	d1,a1			; +0 cell x, +112 cell y, +224 lift
	move.w	(a4),d2
	move.w	2(a4),d3
	cmp.w	(a1),d2
	bne.s	.new
	cmp.w	112(a1),d3
	beq.w	.have
.new:	tst.w	TD_MAIN
	beq.s	.have
	move.w	d2,(a1)
	move.w	d3,112(a1)
	move.l	a1,-(a7)
	move.w	d3,-(a7)
	move.w	d2,-(a7)
	jsr	(CELLREAD).l
	addq.w	#4,a7
	movea.l	(a7)+,a1
	movea.l	d0,a0
	move.w	(a0),d2			; cell word
	move.w	d2,d0
	andi.w	#$1FF,d0
	add.w	d0,d0
	lea	(DESC2).l,a0
	move.w	(a0,d0.w),d1		; descriptor
	rol.w	#3,d2
	andi.w	#7,d2			; height
	move.w	d1,d0
	lsr.w	#7,d0
	andi.w	#1,d0
	add.w	d0,d2
	mulu.w	#7,d2
	lsr.w	#8,d1
	andi.w	#1,d1
	lsl.w	#2,d1
	add.w	d1,d2
	move.w	d2,224(a1)
.have:	move.w	d7,d0			; lift = from + (to - from) * el / T
	add.w	d0,d0			; (d4 = elapsed, from td_slidepos)
	lea	TD_LFT,a0		; a new slide: from the lift drawn last,
	move.w	8(a4),d1		; unless the position snaps too
	cmp.w	(a0,d0.w),d1
	beq.s	.in
	move.w	d1,(a0,d0.w)
	lea	TD_LFD,a0
	move.w	(a0,d0.w),d1
	move.w	(a4),d3
	lsl.w	#4,d3
	cmp.w	4(a4),d3
	bne.s	.gl
	move.w	2(a4),d3
	lsl.w	#4,d3
	cmp.w	6(a4),d3
	bne.s	.gl
	move.w	224(a1),d1
.gl:	lea	TD_LF0,a0
	move.w	d1,(a0,d0.w)
.in:	lea	TD_LF0,a0
	move.w	(a0,d0.w),d1
	move.w	224(a1),d2
	sub.w	d1,d2
	muls.w	d4,d2
	divs.w	TD_PERIOD,d2
	add.w	d1,d2
	lea	TD_LFD,a0
	move.w	d2,(a0,d0.w)
	move.w	d2,TD_TLIFT
	movem.l	(a7)+,d0-d3/a0-a2
	rts

; ti_spr_xform — iso: the blob list (top-down cell pixels px, py) to
; (screen x of the sprite, global depth y = 8 (x + y)); figures whose
; cell face is outside the frame's hole are culled (x = $8000).
ti_spr_xform:
	tst.w	TD_XF			; once per list (td_menufmt re-links
	bne.w	ti_rts			; with the same list)
	move.w	#1,TD_XF
	movem.l	d2-d3/d7/a2,-(a7)
	lea	TD_LIST,a2
	move.w	TD_NB,d7
	bra.s	.c
.t:	move.w	(a2),d0
	move.w	2(a2),d1
	move.w	d0,d2
	sub.w	d1,d2
	muls.w	#7,d2
	asr.l	#3,d2			; global x = 14 (x - y)
	add.w	d1,d0
	asr.w	#1,d0			; global y = 8 (x + y)
	move.w	d0,2(a2)
	sub.w	TD_IGX,d2
	move.w	d2,(a2)
	add.w	#14-TI_CX,d2		; face centre in the hole?
	bpl.s	.a
	neg.w	d2
.a:	mulu.w	#TI_HH,d2
	addq.w	#8,d0
	sub.w	TD_IGY,d0
	sub.w	#TI_CY,d0
	bpl.s	.b
	neg.w	d0
.b:	mulu.w	#TI_HW,d0
	add.l	d2,d0
	cmpi.l	#TI_HW*TI_HH,d0
	bls.s	.n
	move.w	#$8000,(a2)
.n:	addq.w	#8,a2
.c:	dbra	d7,.t
	movem.l	(a7)+,d2-d3/d7/a2
	rts

; ti_fig_ht / ti_fig_pr / ti_spell — map_chunk_pos's figure draws and
; its spell-effect step: skipped while we render the terrain.
ti_fig_ht:
	tst.w	TD_REND
	bne.s	ti_rts
	jmp	($0231D8).l		; hero_track
ti_fig_pr:
	tst.w	TD_REND
	bne.s	ti_rts
	jmp	($02343A).l		; map_promote_record
ti_spell:
	tst.w	TD_REND
	bne.s	ti_rts
	jmp	($03D9F8).l		; spell_effect_step
ti_rts:	rts

;=======================================================================
; td_iso_render — terrain render of the game camera cell into the decode
; buffer, aligned to the global grid, then td_iso_commit. Runs with
; TD_BUSY clear: the VBlank handler keeps the picture gliding while the
; game's composite runs (td_vwl).
;=======================================================================
td_iso_render:
	movem.l	d2-d7/a2-a6,-(a7)
	clr.w	TD_INOB
	tst.w	TD_VALID		; first picture: all at once
	bne.s	.go
	move.w	#1,TD_INOB
.go:	tst.w	TD_IRS
	bne.w	.cont
	tst.w	TD_IREQ
	beq.w	.out
	clr.w	TD_IREQ
	bsr.w	ti_target		; start: the target cell, alignment shift
	move.w	FRAME,TD_IST
	clr.w	TD_IHLD
	move.w	d6,TD_IRX
	move.w	d7,TD_IRY
	move.w	$FF0092,TD_IRPH
	move.w	d6,d0			; bitmap x of a cell = 14 (X - Y) - Ox,
	sub.w	d7,d0			; Ox = 14 (cx - cy) - 132
	muls.w	#14,d0
	sub.w	#132,d0
	move.w	d0,d1			; shift the X table by e = Ox mod 8
	andi.w	#7,d1			; (taken in -4..2: images stay inside
	cmpi.w	#2,d1			; the 288-px bitmap), so the bitmap's
	bls.s	.e			; columns sit on global tile columns
	subq.w	#8,d1
.e:	move.w	d1,TD_ISH
	sub.w	d1,d0
	asr.w	#3,d0
	move.w	d0,TD_INX
	move.w	d6,d0			; bitmap y = 8 (X + Y) - Oy, Oy = 8 (cx
	add.w	d7,d0			; + cy) - 98 = 6 mod 8: global tile row
	sub.w	#13,d0			; of bitmap row 0 = cx + cy - 13
	move.w	d0,TD_INY
	move.w	TD_ISH,d5
	bsr.w	ti_xshift
	move.w	#1,TD_IRS
	clr.w	TD_IROW
	clr.w	TD_ICOLR
	clr.w	TD_ILIN			; fast streams present: draw linear
	ifd	SIZE2M
	cmpi.l	#$49534F46,ISOFAST	; ('ISOF', 2 MB ROM)
	bne.s	.cl
	move.w	#1,TD_ILIN
	endif
.cl:	bsr.w	ti_clear
.cont:	cmpi.w	#1,TD_IRS
	bne.s	.com
	bsr.w	ti_late			; no time left in this tick?
	bne.w	.out
	move.w	#1,TD_REND		; render rows TD_IROW.. (map_chunk_pos
	clr.w	TD_IBAIL		; stops between rows when the tick's
	move.w	TD_IRY,-(a7)		; time is up: ti_row)
	move.w	TD_IRX,-(a7)
	jsr	(CHUNKPOS).l
	addq.w	#4,a7
	clr.w	TD_REND
	tst.w	TD_IBAIL
	bne.w	.out			; resume next tick
	move.w	TD_ISH,d5
	neg.w	d5
	bsr.w	ti_xshift
	move.w	#2,TD_IRS
	clr.w	TD_IROW
	addq.w	#1,TD_IGEN
.com:	tst.w	TD_IROW			; before the first plane row: a
	bne.s	.cm			; picture ahead of the game camera
	bsr.w	ti_hold			; waits for it (ti_hold)
	bne.w	.out
.cm:	bsr.w	td_iso_commit		; rows TD_IROW.. while time is left
	cmpi.w	#23,TD_IROW
	bcs.w	.out
	clr.w	TD_IRS			; done: the plane shows the new picture
	move.w	TD_INX,TD_IOX
	move.w	TD_INY,TD_IOY
	move.w	TD_IRX,TD_ICX
	move.w	TD_IRY,TD_ICY
	move.w	TD_IRPH,TD_IPH
	move.w	FRAME,d0		; how long it took (lookahead)
	sub.w	TD_IST,d0
	move.w	d0,TD_ILAT
	tst.w	TD_VALID
	bne.s	.gl
	addq.w	#1,TD_BUSY		; first picture: show it
	bsr.w	td_iso_snap
	bsr.w	td_iso_cam
	bsr.w	td_layers
	bsr.w	td_iso_scroll
	move.w	#1,TD_VALID
	subq.w	#1,TD_BUSY
	bra.s	.out
.gl:	bsr.w	td_iso_glide		; glide to the new picture's cell
	bsr.w	ti_target		; the target moved on meanwhile: start
	cmp.w	TD_ICX,d6		; the next picture right away
	bne.s	.nx
	cmp.w	TD_ICY,d7
	beq.s	.out
.nx:	move.w	#1,TD_IREQ
	bra.w	.go
.out:	movem.l	(a7)+,d2-d7/a2-a6
	rts

ti_hold:	; -> d0 != 0: keep the finished render off the plane. A picture
	; is shown only within one cell (per axis) of the game camera:
	; the camera stays within a cell of the picture, so a picture two
	; steps ahead (lookahead, ti_target) shown when the leader stopped
	; pulled the view a cell forward and back (#289). Hold time does
	; not count as render latency (TD_ILAT).
	tst.w	TD_VALID
	beq.s	.go
	move.w	TD_IRX,d0
	sub.w	$FF0E8E,d0
	addq.w	#1,d0
	cmpi.w	#2,d0
	bhi.s	.hold
	move.w	TD_IRY,d0
	sub.w	$FF0E90,d0
	addq.w	#1,d0
	cmpi.w	#2,d0
	bhi.s	.hold
.go:	tst.w	TD_IHLD
	beq.s	.z
	move.w	FRAME,d0
	sub.w	TD_IHF,d0
	add.w	d0,TD_IST
	clr.w	TD_IHLD
.z:	moveq	#0,d0
	rts
.hold:	tst.w	TD_IHLD
	bne.s	.h1
	move.w	#1,TD_IHLD
	move.w	FRAME,TD_IHF
.h1:	moveq	#1,d0
	rts

ti_target:	; -> d6/d7 = the cell the next picture shows: the game camera
	; cell, one step further in the direction of its last step while it
	; keeps stepping (last step < 2 tick periods ago), so a picture is
	; ready when the camera gets there. Tracks the camera's steps.
	move.w	$FF0E8E,d6
	move.w	$FF0E90,d7
	cmp.w	TD_PCX,d6
	bne.s	.mv
	cmp.w	TD_PCY,d7
	beq.s	.st
.mv:	move.w	d6,d0
	sub.w	TD_PCX,d0
	move.w	d7,d1
	sub.w	TD_PCY,d1
	move.w	d6,TD_PCX
	move.w	d7,TD_PCY
	move.w	FRAME,TD_MVFR
	addq.w	#1,d0			; a jump (door, scene): no direction
	cmpi.w	#2,d0
	bhi.s	.j
	addq.w	#1,d1
	cmpi.w	#2,d1
	bhi.s	.j
	subq.w	#1,d0
	subq.w	#1,d1
	move.w	d0,TD_DX
	move.w	d1,TD_DY
	bra.s	.st
.j:	clr.w	TD_DX
	clr.w	TD_DY
.st:	move.w	FRAME,d0
	sub.w	TD_MVFR,d0
	move.w	TD_PERIOD,d1
	add.w	d1,d1
	cmp.w	d1,d0
	bcc.s	.x
	add.w	TD_DX,d6		; one step ahead; two when a picture
	add.w	TD_DY,d7		; takes longer than a tick (busy rooms)
	move.w	TD_ILAT,d0
	cmp.w	TD_PERIOD,d0
	bls.s	.x
	add.w	TD_DX,d6
	add.w	TD_DY,d7
.x:	rts

ti_xshift:	; add d5 to the 100 X-table words
	lea	XTAB,a0
	moveq	#100-1,d0
.x:	add.w	d5,(a0)+
	dbra	d0,.x
	rts

ti_clear:	; the 26,496-byte decode buffer to 0 (12 registers per store:
	; 0.5 frame, clear_decode_buffer takes 1.6)
	movem.l	d2-d7/a2-a6,-(a7)
	moveq	#0,d0
	moveq	#0,d1
	moveq	#0,d2
	moveq	#0,d3
	moveq	#0,d4
	moveq	#0,d5
	moveq	#0,d6
	moveq	#0,d7
	movea.l	d0,a1
	movea.l	d0,a2
	movea.l	d0,a3
	movea.l	d0,a4
	movea.l	d0,a6
	lea	DECBUF+26496,a5
	move.w	#26496/48-1,d0
	tst.w	TD_ILIN
	beq.s	.c
	lea	DECBUF+TI_LMAX*144,a5
	move.w	#TI_LMAX*144/48-1,d0
.c:	movem.l	d1-d7/a1-a4/a6,-(a5)
	dbra	d0,.c
	movem.l	(a7)+,d2-d7/a2-a6
	rts

;=======================================================================
; ti_e358 — entry of map_terrain_tile_lookup ($E358, jmp hook). While
; our iso render runs with the fast streams (TD_REND + TD_ILIN) the
; stream is drawn from its records into the LINEAR bitmap (144 bytes
; per line, no 8x8 tiles), otherwise the game's decoder runs as is.
; Records: tools/iso_fast_streams.py (exact against $E358 for all 944 x
; 2 streams; each record = one run of a line: h bytes with a
; transparent nibble, m opaque bytes, t masked bytes, drawn by stub P).
;=======================================================================
ti_e358:
	ifd	SIZE2M
	tst.w	TD_REND
	beq.s	.orig
	tst.w	TD_ILIN
	bne.s	ti_fast
	endif
.orig:	moveq	#0,d2			; the two instructions the hook replaced
	move.w	4(a7),d2
	jmp	(E358+6).l

	ifd	SIZE2M
ti_fast:
	movem.l	d4-d7/a2-a6,-(a7)	; args at 40(a7): stream, x, line, d3
	move.w	44(a7),d1		; line (d1)
	cmpi.w	#-21,d1			; as $E358: far above the top = nothing
	blt.w	.out
	lea	ISOFAST,a6
	move.w	40(a7),d2		; entry = stream * 2 + (d3 != 0)
	add.w	d2,d2
	tst.w	46(a7)
	beq.s	.a
	addq.w	#1,d2
.a:	lsl.w	#3,d2
	movem.l	12(a6,d2.w),a0/a1	; a0 = data, a1 = records (offsets)
	adda.l	a6,a0
	adda.l	a6,a1
	movea.l	4(a6),a2		; stubs
	adda.l	a6,a2
	move.l	8(a6),d7		; pattern lengths (clipped calls)
	add.l	a6,d7
	movem.w	(a1)+,d3/d4		; origin column - x/2, last line + 1
	move.w	42(a7),d0		; column of x = (x & $FFFE) / 2
	lsr.w	#1,d0
	add.w	d3,d0
	lea	DECBUF,a4		; a4 = bitmap + line * 144 + column
	adda.w	d0,a4
	move.w	d1,d3
	muls.w	#144,d3
	adda.l	d3,a4
	lea	MASKT,a3
	tst.w	d1
	bmi.s	.clip
	add.w	d1,d4
	cmpi.w	#TI_LMAX,d4
	bhi.s	.bot
	lea	.rec(pc),a6
.rec:	move.l	(a1)+,d0		; disp.w, stub offset.w
	bmi.s	.out
	swap	d0
	lea	(a4,d0.w),a5
	swap	d0
	jmp	(a2,d0.w)		; stub: draws, then jmp (a6)
.out:	movem.l	(a7)+,d4-d7/a2-a6
	rts
.bot:	move.w	#TI_LMAX,d7		; lines from TI_LMAX on are skipped:
	sub.w	d1,d7			; records come in line order, so stop at
	mulu.w	#144,d7			; the first disp >= (TI_LMAX - line) * 144
	lea	.br(pc),a6
.br:	move.l	(a1)+,d0
	bmi.s	.out
	swap	d0
	cmp.w	d7,d0
	bcc.s	.out
	lea	(a4,d0.w),a5
	swap	d0
	jmp	(a2,d0.w)
.clip:	lea	.cl(pc),a6		; lines outside 0..TI_LMAX-1 are skipped
.cl:	move.l	(a1)+,d0
	bmi.s	.out
	move.l	d0,d5
	swap	d5
	moveq	#0,d6
	move.w	d5,d6
	divu.w	#144,d6			; record line
	add.w	d1,d6
	cmpi.w	#TI_LMAX,d6
	bcc.s	.sk
	lea	(a4,d5.w),a5
	jmp	(a2,d0.w)
.sk:	moveq	#0,d5			; skip its data bytes
	move.w	d0,d5
	divu.w	#24,d5
	movea.l	d7,a5
	moveq	#0,d6
	move.b	(a5,d5.w),d6
	adda.w	d6,a0
	bra.s	.cl
	endif

;=======================================================================
; ti_ccr — map_chunk_pos's `jsr map_chunk_cache_read; addq #4,a7`
; ($01BA84). While our render runs: the same lookup with two divu
; instead of six divs and three C calls (cell (x, y) wrapped by the
; geometry W, H; chunk = (y'/E) * CPR + x'/E + base; word (y'%E) * E +
; x'%E of its buffer, loaded by map_chunk_load if not cached), copied
; to $FF0248 as the game does. Otherwise the game's routine.
;=======================================================================
ti_ccr:
	ifd	SIZE2M
	tst.w	TD_REND
	beq.w	.orig
	movem.l	d2-d3/a2,-(a7)		; args at 16(a7): x, y
	movea.l	GRIDPTR,a2		; +0 W, +2 H, +4 E, +6 chunks per row
	move.w	16(a7),d0
	add.w	(a2),d0
.mx:	cmp.w	(a2),d0
	blt.s	.my0
	sub.w	(a2),d0
	bra.s	.mx
.my0:	move.w	18(a7),d1
	add.w	2(a2),d1
.my:	cmp.w	2(a2),d1
	blt.s	.dv
	sub.w	2(a2),d1
	bra.s	.my
.dv:	andi.l	#$FFFF,d0		; x' % E : x' / E
	divu.w	4(a2),d0
	andi.l	#$FFFF,d1		; y' % E : y' / E
	divu.w	4(a2),d1
	move.w	d1,d2
	mulu.w	6(a2),d2
	add.w	d0,d2
	cmpi.w	#$FFFF,LOC
	beq.s	.b
	add.w	LOC,d2
	add.w	#$4D,d2
.b:	moveq	#0,d3
	move.w	d2,d3
	lsl.l	#2,d3
	lea	($FFA896).l,a0		; chunk buffer pointers
	move.l	(a0,d3.l),d3
	bne.s	.have
	movem.l	d0-d1,-(a7)
	move.w	d2,-(a7)
	jsr	($019692).l		; map_chunk_load
	addq.w	#2,a7
	movem.l	(a7)+,d0-d1
	moveq	#0,d3
	move.w	d2,d3
	lsl.l	#2,d3
	lea	($FFA896).l,a0
	move.l	(a0,d3.l),d3
.have:	swap	d0
	swap	d1
	mulu.w	4(a2),d1
	add.w	d0,d1
	add.w	d1,d1
	movea.l	d3,a0
	move.w	(a0,d1.w),($FF0248).l
	lea	($FF0248).l,a0
	move.l	a0,d0
	movem.l	(a7)+,d2-d3/a2
	move.l	(a7)+,(a7)		; drop the args (the replaced addq)
	rts
	endif
.orig:	move.l	4(a7),-(a7)
	jsr	($01C176).l		; map_chunk_cache_read
	addq.w	#4,a7
	move.l	(a7)+,(a7)
	rts
ti_fend:

ti_late:	; -> Z clear if this tick has < 1 frame left (and limits apply);
	; the render checks it per cell, the commit per row (< 0.5 frame)
	tst.w	TD_INOB
	bne.s	.no
	move.w	FRAME,d0
	sub.w	TD_TICKFR,d0
	addq.w	#1,d0
	cmp.w	TD_PERIOD,d0
	bcc.s	.yes
.no:	moveq	#0,d0
	rts
.yes:	moveq	#1,d0
	rts

; td_iso_cancel — drop a render in progress (scene change, view off).
td_iso_cancel:
	cmpi.w	#1,TD_IRS
	bne.s	.c
	move.w	TD_ISH,d5
	neg.w	d5
	bsr.w	ti_xshift
.c:	clr.w	TD_IRS
	clr.w	TD_IREQ
	clr.w	TD_REND
	clr.w	TD_ICOLR
	rts

; ti_mso — map_chunk_pos's `jsr map_scroll_offset` (+ the removed
; `addq #4,a7; moveq #0,d4`): row d4 starts at TD_IROW while we render.
ti_mso:
	move.l	4(a7),-(a7)
	jsr	($020D58).l		; map_scroll_offset
	addq.w	#4,a7
	moveq	#0,d4
	tst.w	TD_REND
	beq.s	.r
	move.w	TD_IROW,d4
.r:	movea.l	(a7)+,a0		; drop the caller's argument
	addq.w	#4,a7
	jmp	(a0)

; ti_cell — map_chunk_pos's cell head (`move.w d4,d0; add.w 8(a6),d0`,
; $01BA66): while we render, a resumed row starts at the saved column,
; and the render stops before a cell when the tick's time is up (unwind
; to the epilogue at $1C0E4; td_iso_render resumes at TD_IROW/TD_ICOL).
ti_cell:
	tst.w	TD_REND
	beq.s	.go
	tst.w	TD_ICOLR
	beq.s	.t
	move.w	TD_ICOL,d5
	clr.w	TD_ICOLR
.t:	bsr.w	ti_late
	beq.s	.go
	move.w	d4,TD_IROW
	move.w	d5,TD_ICOL
	move.w	#1,TD_ICOLR
	move.w	#1,TD_IBAIL
	addq.w	#4,a7			; drop our return: out of the cell loop
	jmp	($01C0E4).l
.go:	move.w	d4,d0
	add.w	8(a6),d0
	rts

; ti_row — map_chunk_pos's outer row step (`addq #1,d4; cmp #10,d4`):
; while we render, stop after a row when the tick's time is up (unwind
; to its epilogue at $1C0E4; td_iso_render resumes at TD_IROW).
ti_row:
	addq.w	#1,d4
	tst.w	TD_REND
	beq.s	.c
	move.w	d4,TD_IROW
	cmpi.w	#10,d4
	bcc.s	.c
	move.w	d0,-(a7)
	bsr.w	ti_late
	movem.w	(a7)+,d0		; (keeps the flags of ti_late)
	beq.s	.c
	move.w	#1,TD_IBAIL
	addq.w	#4,a7			; drop our return: out of the row loop
	jmp	($01C0E4).l		; (no spell step), back to td_iso_render
.c:	cmpi.w	#10,d4
	rts

;=======================================================================
; td_iso_commit — the bitmap to Plane B at global tile positions, rows
; TD_IROW.. while the tick has time. Only the columns that can show
; through the hole (ti_crow); each tile: blank -> void word, else a
; 16-bit hash -> pool slot (ti_pool); the rest of the plane row is void.
; The interrupt is masked only around VDP address/data sequences, so
; the VBlank glide keeps running (range listed in td_vwl).
;=======================================================================
ti_cstart:
td_iso_commit:
	movem.l	d2-d7/a2-a6,-(a7)
	moveq	#32,d2			; tile step and line stride: tiled
	movea.w	#4,a2
	ifd	SIZE2M
	tst.w	TD_ILIN
	beq.s	.lay
	moveq	#4,d2			; linear bitmap: 144-byte lines
	movea.w	#144,a2
	endif
.lay:	move.w	TD_IROW,d7		; bitmap row
.row:	cmpi.w	#23,d7
	bcc.w	.done
	bsr.w	ti_late
	bne.w	.done
	lea	ti_crow(pc),a0		; only the columns that can show
	move.w	d7,d0			; through the hole (ti_crow)
	add.w	d0,d0
	moveq	#0,d4
	move.b	(a0,d0.w),d4		; first column
	moveq	#0,d5
	move.b	1(a0,d0.w),d5
	sub.w	d4,d5
	addq.w	#1,d5			; count (0: none)
	ble.w	.vrow
	bsr.w	ti_oldrow		; a6 -> the plane's name at column 1
	move.w	d7,d0			; a3 = tile (row, first column)
	tst.w	TD_ILIN
	bne.s	.lin
	mulu.w	#36,d0
	add.w	d4,d0
	lsl.l	#5,d0
	bra.s	.ta
.lin:	mulu.w	#8*144,d0
	move.w	d4,d1
	add.w	d1,d1
	add.w	d1,d1
	add.w	d1,d0
.ta:	lea	DECBUF,a3
	adda.l	d0,a3
	lea	TD_NBUF,a4
	move.w	d5,d6
	subq.w	#1,d6
.til:	movea.l	a3,a0			; gather + hash the tile (into TD_TT)
	lea	TD_TT,a1
	moveq	#0,d0			; hash (0 only for a blank tile)
	rept	8
	move.l	(a0),d3
	adda.l	a2,a0
	move.l	d3,(a1)+
	rol.l	#5,d0
	eor.l	d3,d0
	endr
	tst.l	d0
	bne.s	.nb
	move.w	TD_BASE,d0		; blank: void (parchment)
	add.w	#256+$2000,d0
	bra.s	.put
.nb:	move.l	d0,d1			; fold to 16 bits
	swap	d1
	eor.w	d1,d0
	bsr.w	ti_reuse		; the same tile already at this place?
	beq.s	.put
	bsr.w	ti_pool
.put:	move.w	d0,(a4)+
	addq.l	#2,a6
	adda.w	d2,a3
	dbra	d6,.til
.vrow:	bsr.w	ti_rowput
	addq.w	#1,d7
	cmpi.w	#23,d7			; picture done: the 9 plane rows below it
	bcs.w	.row			; void too (under the HUD's text)
	moveq	#0,d5
.vr:	bsr.w	ti_rowput
	addq.w	#1,d7
	cmpi.w	#32,d7
	bcs.s	.vr
	moveq	#23,d7
.done:	move.w	d7,TD_IROW
	movem.l	(a7)+,d2-d7/a2-a6
	rts

ti_oldrow:	; TD_OLD <- plane row (INY + d7) & 31, twice (no wrap);
	; a6 -> its word at column (INX + d4) & 63
	lea	TD_OLD,a6
	move.w	TD_INY,d0
	add.w	d7,d0
	andi.w	#31,d0
	lsl.w	#7,d0
	bsr.w	td_vcmd
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
	moveq	#32-1,d1
.r:	move.l	VDP_DATA,d0
	move.l	d0,128(a6)
	move.l	d0,(a6)+
	dbra	d1,.r
	move.w	(a7)+,sr
	lea	TD_OLD,a6
	move.w	TD_INX,d0
	add.w	d4,d0
	andi.w	#63,d0
	add.w	d0,d0
	adda.w	d0,a6
	rts

ti_reuse:	; d0.w = hash; (a6) = the name now at this plane place. If it
	; is a pool slot holding this hash: Z set, d0 = that name, slot
	; marked in use by this render; else Z clear, d0 kept. RAM only (VRAM
	; reads stall in active display): a wrong match needs the place's
	; tile to change AND a 16-bit hash collision; a scene's first
	; picture (TD_INOB) always goes through ti_pool's VRAM check.
	tst.w	TD_INOB
	bne.s	.no
	move.w	(a6),d1
	sub.w	TD_BASE,d1
	cmpi.w	#256,d1
	bcs.s	.s
	cmpi.w	#TI_POOLB,d1
	bcs.s	.no
	cmp.w	TD_PEND,d1
	bcc.s	.no
	sub.w	#TI_POOLB-256,d1
.s:	move.l	a0,-(a7)
	lea	TI_PHASH,a0
	add.w	d1,d1
	cmp.w	(a0,d1.w),d0
	bne.s	.ne
	lsr.w	#1,d1
	lea	TI_PGEN,a0
	move.b	TD_IGEN+1,(a0,d1.w)	; in use by this render
	movea.l	(a7)+,a0
	move.w	(a6),d0
	cmp.w	d0,d0			; Z
	rts
.ne:	movea.l	(a7)+,a0
.no:	moveq	#1,d1			; Z clear
	rts

ti_pool:	; d0.w = hash, TD_TT = tile -> d0.w = name word. 24-slot window
	; from hash * (N - 24) / 65536 (no wrap): a hash match is checked against
	; the slot's tile in VRAM; a miss takes the window's oldest slot
	; not used by this render (age 1 = the previous render: last resort).
	movem.l	d1-d6/a0-a2,-(a7)
	move.w	d0,d4
	moveq	#0,d1
	move.w	d4,d1
	mulu.w	TD_PSL24,d1		; first slot = hash * (N - 24) / 65536
	swap	d1
	lea	TI_PHASH,a1
	move.w	d1,d0
	add.w	d0,d0
	lea	(a1,d0.w),a0
	moveq	#24-1,d2
.f:	cmp.w	(a0)+,d4
	dbeq	d2,.f
	bne.s	.miss
	move.l	a0,d1			; slot = (a0 - 2 - a1) / 2
	sub.l	a1,d1
	subq.l	#2,d1
	lsr.l	#1,d1
	bsr.w	ti_same
	beq.s	.hit
	subq.w	#1,d2			; another tile with this hash: go on
	bpl.s	.f
.miss:	lea	TI_PGEN,a2		; first slot in the window not used by
	move.w	TD_IGEN,d3		; this render or the previous one
	moveq	#0,d1
	move.w	d4,d1
	mulu.w	TD_PSL24,d1
	swap	d1
	lea	(a2,d1.w),a0
	moveq	#24-1,d2
.q:	move.b	d3,d6
	sub.b	(a0)+,d6
	cmpi.b	#2,d6
	dbcc	d2,.q
	bcs.s	.old
	move.l	a0,d1			; slot = a0 - 1 - TI_PGEN
	sub.l	a2,d1
	subq.w	#1,d1
	bra.s	.got
.old:	moveq	#-1,d5			; all recent: the oldest of them
	moveq	#0,d0			; its age
	moveq	#24-1,d2
	moveq	#0,d1
	move.w	d4,d1
	mulu.w	TD_PSL24,d1
	swap	d1
.a:	move.b	d3,d6
	sub.b	(a2,d1.w),d6
	cmp.b	d0,d6
	bls.s	.an
	move.b	d6,d0
	move.w	d1,d5
.an:	addq.w	#1,d1
	dbra	d2,.a
	tst.w	d5
	bmi.s	.full
	move.w	d5,d1
.got:	move.w	d1,d2
	add.w	d2,d2
	move.w	d4,(a1,d2.w)
	bsr.w	ti_upload
.hit:	lea	TI_PGEN,a2
	move.b	TD_IGEN+1,(a2,d1.w)	; in use by this render
	bsr.w	ti_stile
	bra.s	.out
.full:	move.w	TD_BASE,d0		; pool full: parchment
	add.w	#256+$2000,d0
.out:	movem.l	(a7)+,d1-d6/a0-a2
	rts

ti_same:	; slot d1's VRAM tile == the 32 bytes at TD_TT -> Z
	movem.l	d0/a0,-(a7)
	bsr.w	ti_stile
	lsl.w	#5,d0
	bsr.w	td_vcmd
	lea	TD_TT,a0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
	rept	8
	move.l	VDP_DATA,d0
	cmp.l	(a0)+,d0
	bne.w	.x
	endr
.x:	sne	d0			; $FF: different
	move.w	(a7)+,sr
	tst.b	d0			; Z: the same tile
	movem.l	(a7)+,d0/a0
	rts

ti_stile:	; d1 = slot -> d0 = tile index
	move.w	d1,d0
	cmpi.w	#256,d0
	bcs.s	.a
	add.w	#TI_POOLB-256,d0
.a:	add.w	TD_BASE,d0
	rts

ti_upload:	; slot d1 <- the 32 bytes at TD_TT
	bsr.s	ti_stile
	lsl.w	#5,d0
	bsr.w	td_vcmd
	ori.l	#$40000000,d0
	lea	TD_TT,a0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
	rept	8
	move.l	(a0)+,VDP_DATA
	endr
	move.w	(a7)+,sr
	rts

ti_rowput:	; plane row (INY + d7) & 31: void, with the d5 words built at
	; TD_NBUF placed at columns (INX + d4 + k) & 63. Only what differs
	; from the plane is written (VDP writes stall in active display):
	; a void row known void (TD_VMASK) not at all, a row with tiles word
	; by word against TD_OLD (ti_oldrow read it for this row).
	movem.l	d2-d3/a1,-(a7)
	lea	TD_NAMES,a0		; row: void, then the names at their
	move.w	TD_BASE,d2		; columns (wrapping at 64)
	add.w	#256+$2000,d2
	move.w	d2,d0
	swap	d2
	move.w	d0,d2
	moveq	#8-1,d0
.v:	move.l	d2,(a0)+
	move.l	d2,(a0)+
	move.l	d2,(a0)+
	move.l	d2,(a0)+
	dbra	d0,.v
	lea	-128(a0),a0
	lea	TD_NBUF,a1		; the names (TD_NBUF)
	move.w	TD_INX,d1
	add.w	d4,d1
	andi.w	#63,d1
	add.w	d1,d1
	move.w	d5,d0
	bra.s	.nc
.n:	move.w	(a1)+,(a0,d1.w)
	addq.w	#2,d1
	andi.w	#126,d1
.nc:	dbra	d0,.n
	move.w	TD_INY,d3
	add.w	d7,d3
	andi.w	#31,d3
	tst.w	d5
	bne.s	.diff
	move.l	TD_VMASK,d0		; all void: skip if it is already
	bset	d3,d0
	bne.s	.out
	move.l	d0,TD_VMASK
	lsl.w	#7,d3
	move.w	d3,d0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	bsr.w	td_vwrite
	moveq	#32-1,d0
.w:	move.l	(a0)+,VDP_DATA
	dbra	d0,.w
	move.w	(a7)+,sr
	bra.s	.out
.diff:	move.l	TD_VMASK,d0
	bclr	d3,d0
	move.l	d0,TD_VMASK
	lsl.w	#7,d3			; row's VRAM address
	lea	TD_OLD,a1
	moveq	#64,d2			; words left
.d:	subq.w	#1,d2
	bmi.s	.out
	cmpm.w	(a0)+,(a1)+
	beq.s	.d
	moveq	#63,d0			; a run of changed words from here
	sub.w	d2,d0
	add.w	d0,d0
	add.w	d3,d0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	bsr.w	td_vwrite
	move.w	-2(a0),VDP_DATA
.r:	subq.w	#1,d2
	bmi.s	.re
	cmpm.w	(a0)+,(a1)+
	beq.s	.re
	move.w	-2(a0),VDP_DATA
	bra.s	.r
.re:	move.w	(a7)+,sr
	tst.w	d2
	bpl.s	.d
.out:	movem.l	(a7)+,d2-d3/a1
	rts
ti_cend:

;=======================================================================
; ti_cfg — pool size and figure-cache slots for the scene (#270): rooms
; (<= ~460 distinct tiles per render, many figures) lend the pool's last
; 128 tiles to 8 more figure images; the overworld keeps the whole pool.
; On a change: pool and figure cache emptied, plane rows not known void.
;=======================================================================
ti_cfg:
	move.w	#TI_NSLOT,d0
	moveq	#TI_NFC,d1
	cmpi.w	#2,MODE
	bne.s	.c
	move.w	#TI_NSLOTR,d0
	moveq	#TI_NFCR,d1
.c:	cmp.w	TD_PSLOT,d0
	beq.s	.x
	move.w	d0,TD_PSLOT
	move.w	d1,TD_NFCV
	move.w	d0,d1
	sub.w	#24,d1
	move.w	d1,TD_PSL24
	add.w	#TI_POOLB-256,d0
	move.w	d0,TD_PEND
	lea	TI_PHASH,a0		; pool: every slot dead (age 0 vs
	move.w	#(TI_NSLOT*3+1)/2-1,d0	; render 2 on)
.h:	clr.w	(a0)+
	dbra	d0,.h
	move.w	#1,TD_IGEN
	lea	TD_FC,a0
	moveq	#TD_NFC-1,d0
.f:	move.l	#$FFFF0000,(a0)+
	dbra	d0,.f
	clr.l	TD_VMASK
.x:	rts

;=======================================================================
; Iso tiles: pool reset, void + blobs, frame edge tiles, figure cache.
;=======================================================================
td_iso_load:
	move.w	TD_BASE,d0		; void + blob tiles
	add.w	#256,d0
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	VDP_DATA,a0
	suba.l	a1,a1
	bsr.w	td_blobs
	move.w	TD_BASE,d0		; edge tiles: bit 1 -> colour 12
	add.w	#TI_EDGE,d0
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	ti_etil(pc),a0
	move.w	#TI_NEDGE*8-1,d1
.e:	move.b	(a0)+,d2
	moveq	#0,d0
	moveq	#8-1,d3
.b:	lsl.l	#4,d0
	add.b	d2,d2
	bcc.s	.z
	ori.b	#$C,d0
.z:	dbra	d3,.b
	move.l	d0,VDP_DATA
	dbra	d1,.e
	clr.w	TD_PSLOT		; pool size and figure slots by scene
	bsr.w	ti_cfg
	moveq	#0,d0			; plane: all void (no priority bits
	bsr.w	td_vwrite		; left over from the top-down's tint)
	move.w	TD_BASE,d0
	add.w	#256+$2000,d0
	move.w	#64*32-1,d1
.v:	move.w	d0,VDP_DATA
	dbra	d1,.v
	move.w	#1,TD_TILES
	clr.w	TD_VALID
	move.w	#$8000,TD_ICX
	moveq	#-1,d0
	move.l	d0,TD_VMASK		; every plane row void
	rts

td_iso_check:				; clears TD_TILES if overwritten
	tst.w	TD_TILES
	beq.s	.out
	move.w	TD_BASE,d0		; row 4 of blob tile 0
	add.w	#257,d0
	lsl.w	#5,d0
	add.w	#16,d0
	bsr.w	td_vread
	cmpi.w	#$0DDE,d0
	beq.s	.out
	clr.w	TD_TILES
.out:	rts

;=======================================================================
; td_iso_winfix — once per tick: every window cell that is blank, a
; room-bitmap word or a frame word gets the frame word of its place
; (TD_UNFR: the blank, to take the frame off).
;=======================================================================
td_iso_winfix:
	movem.l	d2-d6/a2,-(a7)
	move.w	#1,TD_INWF
	moveq	#0,d6			; row
.row:	tst.w	TD_UNFR
	bne.s	.r0
	bsr.w	td_poll_vb
.r0:	move.w	d6,d0
	lsl.w	#7,d0
	add.w	#$1000,d0
	move.w	d0,d5
	bsr.w	td_vcmd
	lea	TD_WROW,a2
	moveq	#40-1,d1
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d1,.rd
	move.w	(a7)+,sr
	lea	TD_WROW,a2
	moveq	#0,d4
.col:	move.w	(a2)+,d0
	bsr.w	ti_blankish
	bne.s	.nx
	move.w	FONTBLK,d0
	tst.w	TD_UNFR
	bne.s	.w
	move.w	d4,d1
	move.w	d6,d2
	bsr.w	ti_frameword
.w:	cmp.w	-2(a2),d0
	beq.s	.nx
	move.w	d0,d1
	move.w	d4,d0
	add.w	d0,d0
	add.w	d5,d0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	bsr.w	td_vwrite
	move.w	d1,VDP_DATA
	move.w	(a7)+,sr
.nx:	addq.w	#1,d4
	cmpi.w	#40,d4
	bcs.s	.col
	addq.w	#1,d6
	cmpi.w	#28,d6
	bcs.w	.row
	clr.w	TD_INWF
	movem.l	(a7)+,d2-d6/a2
	rts
ti_wend:

ti_blankish:	; d0 = window word -> Z set if it is ours to (re)write
	movem.l	d0-d1,-(a7)
	move.w	d0,d1
	sub.w	FONTBLK,d1
	andi.w	#$7FF,d1
	beq.s	.y
	move.w	d0,d1
	andi.w	#$F800,d1
	beq.s	.room
	cmpi.w	#$2000,d1		; palette 1, no flags: a frame word?
	bne.s	.n
	andi.w	#$7FF,d0
	sub.w	TD_BASE,d0
	cmpi.w	#256,d0
	beq.s	.y
	sub.w	#TI_EDGE,d0
	cmpi.w	#TI_NEDGE,d0
	bcs.s	.y
	bra.s	.n
.room:	sub.w	BANKBASE,d0
	cmpi.w	#828,d0
	bcs.s	.y
.n:	moveq	#1,d1
	bra.s	.o
.y:	moveq	#0,d1
.o:	movem.l	(a7)+,d0-d1
	rts

ti_frameword:	; d1 = column, d2 = row -> d0 = frame word (keeps d1-d2)
	movem.l	d1-d3/a0,-(a7)
	lea	ti_rows(pc),a0
	move.w	d2,d0
	add.w	d0,d0
	cmp.b	(a0,d0.w),d1		; first fully inside column
	bcs.s	.e
	cmp.b	1(a0,d0.w),d1		; last
	bhi.s	.e
	move.w	FONTBLK,d0		; inside the hole: transparent
	bra.s	.o
.e:	lea	ti_eoff(pc),a0
	moveq	#0,d3
	move.b	(a0,d2.w),d3
	moveq	#0,d0
	move.b	1(a0,d2.w),d0
	sub.w	d3,d0			; edge cells in this row
	lea	ti_ecel(pc),a0
	add.w	d3,d3
	adda.w	d3,a0
	bra.s	.lc
.l:	cmp.b	(a0),d1
	beq.s	.edge
	addq.w	#2,a0
.lc:	dbra	d0,.l
	move.w	TD_BASE,d0		; outside: parchment
	add.w	#256+$2000,d0
	bra.s	.o
.edge:	moveq	#0,d0
	move.b	1(a0),d0
	add.w	#TI_EDGE+$2000,d0
	add.w	TD_BASE,d0
.o:	movem.l	(a7)+,d1-d3/a0
	rts

; ti_frame data (tools/td_iso_frame.py)
TI_NEDGE	equ 44
ti_crow:	; per bitmap row: first, last column the commit writes
	dc.b	1,0, 18,18, 16,20, 14,21, 12,23, 11,25, 9,27, 7,28
	dc.b	5,30, 4,32, 2,34, 0,35, 0,35, 1,34, 3,33, 5,31
	dc.b	6,29, 8,27, 10,26, 12,24, 1,0, 1,0, 1,0
ti_rows:	; per window row: first, last fully inside column
	dc.b	1,0, 1,0, 1,0, 1,0, 1,0, 19,20, 18,22
	dc.b	16,24, 14,25, 12,27, 11,29, 9,31, 8,32, 10,30
	dc.b	11,28, 13,26, 15,25, 17,23, 18,21, 1,0, 1,0
	dc.b	1,0, 1,0, 1,0, 1,0, 1,0, 1,0, 1,0
ti_eoff:	; per window row: offset of its edge cells in ti_ecel (+ end)
	dc.b	0, 0, 0, 0, 0, 3, 8, 13, 18, 23
	dc.b	28, 33, 38, 42, 47, 52, 57, 62, 67, 72
	dc.b	72, 72, 72, 72, 72, 72, 72, 72, 72
ti_ecel:	; edge cells: column, tile id
	dc.b	19, 0, 20, 1, 21, 2, 17, 3, 18, 4, 21, 5, 22, 6, 23, 7
	dc.b	15, 8, 16, 9, 17, 10, 23, 11, 24, 12, 13, 13, 14, 14, 15, 15
	dc.b	25, 16, 26, 17, 12, 0, 13, 18, 26, 19, 27, 20, 28, 2, 10, 3
	dc.b	11, 4, 28, 5, 29, 6, 30, 7, 8, 8, 9, 9, 10, 10, 30, 11
	dc.b	31, 12, 6, 13, 7, 14, 8, 15, 32, 16, 33, 17, 6, 21, 7, 22
	dc.b	33, 23, 34, 24, 7, 25, 8, 26, 9, 27, 31, 28, 32, 29, 9, 30
	dc.b	10, 31, 29, 32, 30, 33, 31, 34, 11, 35, 12, 36, 27, 37, 28, 38
	dc.b	29, 39, 12, 40, 13, 41, 14, 22, 26, 42, 27, 43, 14, 25, 15, 26
	dc.b	16, 27, 24, 28, 25, 29, 16, 30, 17, 31, 22, 32, 23, 33, 24, 34
ti_etil:	; edge tiles, 1 bit per pixel (1 = parchment), 8 rows each
	dc.b	$FF, $FF, $FF, $FE, $FC, $F0, $C0, $00
	dc.b	$FF, $FF, $9F, $07, $03, $00, $00, $00
	dc.b	$FF, $FF, $FF, $FF, $FF, $FF, $3F, $0F
	dc.b	$FF, $FF, $FF, $FF, $FF, $FC, $F0, $C0
	dc.b	$FE, $F8, $E0, $80, $00, $00, $00, $00
	dc.b	$07, $01, $00, $00, $00, $00, $00, $00
	dc.b	$FF, $FF, $7F, $1F, $0F, $03, $00, $00
	dc.b	$FF, $FF, $FF, $FF, $FF, $FF, $FF, $3F
	dc.b	$FF, $FF, $FF, $FF, $FF, $FF, $FC, $F0
	dc.b	$FF, $FE, $F8, $E0, $C0, $00, $00, $00
	dc.b	$80, $00, $00, $00, $00, $00, $00, $00
	dc.b	$1F, $07, $01, $00, $00, $00, $00, $00
	dc.b	$FF, $FF, $FF, $7F, $3F, $0F, $03, $00
	dc.b	$FF, $FF, $FF, $FF, $FF, $FF, $FF, $FC
	dc.b	$FF, $FF, $FE, $F8, $F0, $C0, $00, $00
	dc.b	$E0, $80, $00, $00, $00, $00, $00, $00
	dc.b	$7F, $1F, $07, $01, $00, $00, $00, $00
	dc.b	$FF, $FF, $FF, $FF, $FF, $3F, $0F, $03
	dc.b	$F8, $E0, $80, $00, $00, $00, $00, $00
	dc.b	$01, $00, $00, $00, $00, $00, $00, $00
	dc.b	$FF, $7F, $1F, $07, $03, $00, $00, $00
	dc.b	$F8, $E0, $E0, $F8, $FC, $FF, $FF, $FF
	dc.b	$00, $00, $00, $00, $00, $00, $C0, $F0
	dc.b	$01, $00, $00, $01, $03, $0F, $3F, $FF
	dc.b	$FF, $7F, $7F, $FF, $FF, $FF, $FF, $FF
	dc.b	$F8, $FE, $FF, $FF, $FF, $FF, $FF, $FF
	dc.b	$00, $00, $80, $E0, $F0, $FC, $FF, $FF
	dc.b	$00, $00, $00, $00, $00, $00, $00, $C0
	dc.b	$00, $00, $00, $00, $00, $03, $0F, $3F
	dc.b	$01, $07, $1F, $7F, $FF, $FF, $FF, $FF
	dc.b	$E0, $F8, $FE, $FF, $FF, $FF, $FF, $FF
	dc.b	$00, $00, $00, $80, $C0, $F0, $FC, $FF
	dc.b	$00, $00, $00, $00, $00, $00, $03, $0F
	dc.b	$00, $01, $07, $1F, $3F, $FF, $FF, $FF
	dc.b	$7F, $FF, $FF, $FF, $FF, $FF, $FF, $FF
	dc.b	$80, $E0, $F8, $FE, $FF, $FF, $FF, $FF
	dc.b	$00, $00, $00, $00, $00, $C0, $F0, $FC
	dc.b	$00, $00, $00, $00, $00, $00, $00, $03
	dc.b	$00, $00, $01, $07, $0F, $3F, $FF, $FF
	dc.b	$1F, $7F, $FF, $FF, $FF, $FF, $FF, $FF
	dc.b	$FE, $FF, $FF, $FF, $FF, $FF, $FF, $FF
	dc.b	$00, $80, $E0, $F8, $FC, $FF, $FF, $FF
	dc.b	$00, $00, $00, $01, $03, $0F, $3F, $FF
	dc.b	$07, $1F, $7F, $FF, $FF, $FF, $FF, $FF
	even
; ti_frame data end

;=======================================================================
; Data (generated: pixel-double table, blank + blob tiles).
;=======================================================================
td_wtl:	; water map tiles (contain colours 1/2)
	dc.b 9,10,11,12,13,14,15,17,18,19,21,22,23,34,37,38,39,45,46,61
	even
td_nsw:	; nibble with 2 <-> 4 swapped (the shimmer's swap table is built
	; from this into TD_SWAPT at load)
	dc.b	0,1,4,3,2,5,6,7,8,9,10,11,12,13,14,15
TD_NGFX		equ 17*32
td_blobs:	; tile 0 void (solid colour 12 = parchment pink in palette 1),
	; then 4 blob variants x (TL,BL,TR,BR), built from one quadrant:
	; BL/BR bottom up, TR/BR mirrored, highlight (F) in TL only.
	; Longs to (a0), a0 += a1 after each (a1 = 0: a VDP data port).
	movem.l	d2-d7/a2-a3,-(a7)
	moveq	#8-1,d0
.v0:	move.l	#$CCCCCCCC,(a0)
	adda.l	a1,a0
	dbra	d0,.v0
	lea	td_bcol(pc),a2
	lea	td_blob(pc),a3
	moveq	#4-1,d7
.var:	moveq	#0,d6			; quadrant 0..3: TL, BL, TR, BR
.q:	moveq	#0,d5			; row
.r:	move.w	d5,d0
	btst	#0,d6
	beq.s	.t
	eori.w	#7,d0
.t:	lsl.w	#2,d0
	move.l	(a3,d0.w),d1
	moveq	#8-1,d4
.n:	btst	#1,d6
	bne.s	.m
	rol.l	#4,d1			; next pixel from the left
	move.b	d1,d3
	bra.s	.g
.m:	move.b	d1,d3			; ... from the right (mirror)
	ror.l	#4,d1
.g:	andi.w	#$F,d3
	cmpi.b	#$E,d3			; 0, D (outline) kept
	bcs.s	.p
	beq.s	.b
	tst.w	d6			; F: highlight in TL only
	bne.s	.b
	move.b	1(a2),d3
	bra.s	.p
.b:	move.b	(a2),d3			; E: body colour
.p:	lsl.l	#4,d2
	or.b	d3,d2
	dbra	d4,.n
	move.l	d2,(a0)
	adda.l	a1,a0
	addq.w	#1,d5
	cmpi.w	#8,d5
	bcs.s	.r
	addq.w	#1,d6
	cmpi.w	#4,d6
	bcs.s	.q
	addq.w	#2,a2
	dbra	d7,.var
	movem.l	(a7)+,d2-d7/a2-a3
	rts
td_bcol:	; per variant: body, highlight colour
	dc.b	$E,$F, $F,$B, $C,$F, $4,$F
td_blob:	; TL quadrant (body E, highlight F)
	dc.l $0000000D,$0000DDDD,$000DDEEE,$00DDEEEE,$0DDEEFFE,$0DEEFFEE,$0DEEEEEE,$DDEEEEEE
