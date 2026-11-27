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
	ifd	SIZE8M			; pre-drawn view: a quicker walk (#308)
TD_T1		equ 10		; frames per world tick, overworld (orig avg 26.5)
TD_T2		equ 8		; frames per world tick, rooms (orig 17.0)
	else
TD_T1		equ 26		; frames per world tick, overworld (orig avg 26.5)
TD_T2		equ 17		; frames per world tick, rooms (orig 17.0)
	endif
TD_TC		equ 2		; combat arena tick period (frames)
TD_TF		equ 22		; overworld on the dragon (orig attract flight 22.0)
TD_TS		equ 10		; boat / ship (orig over open sea 17-19)
	ifd	SIZE8M
TD_TB		equ 8		; big rooms: no render to wait for in the
	else			; pre-drawn view (and the grid search is fast)
TD_TB		equ 22		; big (32x32) rooms (orig room 156: 22)
	endif
TD_SLOT0	equ 68		; first sprite slot for blobs (game uses <= 67)
TD_NSLOT	equ 12		; our sprite slots (2 HUD box + figures)
TD_NFIG		equ 10		; figure sprites max
TD_BOXT		equ 802		; HUD box: 12 solid parchment tiles (bank offset)
TD_VC		equ 84		; screen line the leader is centred on
TD_NFC		equ 25		; figure images cached in VRAM (4x4 tiles each)
TA_W		equ 42		; window columns (wider ran out of VRAM slots: pink holes)
TA_H		equ 28		; window rows: 26 shown + 2 (TA_W x TA_H <= TA_N)
				; camera runs ahead of the loading, #308)
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
RECS		equ $FFFFB0CC	; 56 x 12 map-draw records
GRIDPTR		equ $FFFFA7FC	; -> geometry struct (+0 W, +2 H)
BANKBASE	equ $FFFF8674	; room bitmap tile base ($38E)
FONTBLK		equ $FFFF8640	; transparent font blank tile
SPRBASE		equ $FFFF8644	; sprite table base ($2400 in layout G)
VDP_DATA	equ $C00000
VDP_CTRL	equ $C00004
CELLREAD	equ $01C176	; map_chunk_cache_read(x, y) -> d0 = ptr to word
MAPDECODE	equ $01383C	; map_decode(rec) -> d0 = $FF1EC0
DMAUP		equ $00DA04	; dma_upload(src.l, dest.l, words.w)
DESC		equ $01AE98	; 512-word map tile descriptors
DECBUF		equ $FF1EC0	; decode buffer (free while top-down runs)

; ---- state -----------------------------------------------------------
TD		equ $FFFFDC00	; (RAM at $FF8000+ written sign-extended:
				; abs.w addressing, see patches/topdown/vasm-opt)
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
TD_TMP		equ TD_UPTXT+14	; (unused since #297)
TD_BTOP		equ TD_UPTXT+16	; first plane tile row of the HUD band
TD_GSPON	equ TD_UPTXT+18	; game sprites above the band get priority
TD_RAISED	equ TD_UPTXT+20	; 64 B (unused since #297)
MG_CACHE	equ TD_RAISED	; mg_find: 16 x (id, layer<<10|cell)
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
TD_EROW		equ TD_MSEEN+2	; 40 words: frame words of a window row
TD_VSUM		equ TD_EROW+80	; VERIFY283: bitmap sum, own loop
TD_VOK		equ TD_VSUM+4	; renders equal / different
TD_VBAD		equ TD_VOK+2
TD_VROW		equ TD_VBAD+2	; 23 longs: per-row sums, own loop
TD_VDIF		equ TD_VROW+92	; last mismatch: row mask (long), IRX, IRY
TI_WIN		equ TI_XSAVE+640	; 200 B: last picture's cell words [row*10+col]
				; (#278; decode buffer lines 164+: never drawn
				; by the linear render, the stack reaches
				; below TD_END while $E358 draws an overlay)
TI_WREC		equ TI_WIN+200	; 200 B: its record bytes (second grid, first)
TD_OVK		equ TI_WREC+200	; 56 words: char's occlusion decision, 0 = none yet
				; ($8000 | cell key, $4000 = needs an overlay)
TD_OVPX		equ TD_OVK+112	; overlay to build: cell x, y, figure lift, key
TD_OVPY		equ TD_OVPX+2
TD_OVPL		equ TD_OVPY+2
TD_OVPK		equ TD_OVPL+2	; (0 = none)
TD_OLOC		equ TD_OVPK+2	; location the cached overlays belong to
TD_OVDN		equ TD_OLOC+2	; an occlusion decided this update (one per)
TD_ARTOK	equ TD_OVDN+2	; rec 6's tiles are in VRAM: frame art on (#306)
	ifd	SIZE8M
TA_ON		equ TD_ARTOK+2	; $5A71: pre-drawn overworld in effect (#307)
TA_L		equ TA_ON+2	; loaded window: left column (global px / 8), $8000 none
TA_T		equ TA_L+2	; its top row (plane line / 8)
TA_HAND		equ TA_T+2	; next slot the allocator looks at
TA_B6		equ TA_HAND+2	; banks in mapper slots 6 / 7 (-1 unknown)
TA_B7		equ TA_B6+2
TA_GX		equ TA_B7+2	; camera before the window clamp
TA_GY		equ TA_GX+2
TA_A		equ TA_GY+2	; long: header of the area shown
TA_AR		equ TA_A+4	; 1 + its area number
TA_BAD		equ TA_AR+2	; the plane lost our tiles: fill it again
TA_LX		equ TA_BAD+2	; the leader's last step (-1..1 per axis)
TA_LY		equ TA_LX+2
TA_PH		equ TA_LY+2	; terrain phase drawn (0/1)
TA_PR		equ TA_PH+2	; phase sweep: next window row, -1 none
TA_SXY		equ TA_PR+2	; path correction: record x/y, blocked flag,
TA_SFL		equ TA_SXY+4	; side being tried, its direction
TA_TRY		equ TA_SFL+2
TA_PD		equ TA_TRY+2
TA_LS		equ TA_PD+2	; the side that worked last (1 or 3) first
TA_CTL		equ TA_LS+2	; leader controller on (#307 follow-up)
TA_OX		equ TA_CTL+2	; figure offset from the game's cell, 1/256 cell
TA_OY		equ TA_OX+2
TA_G0X		equ TA_OY+2	; the game's leader cell seen last
TA_G0Y		equ TA_G0X+2
TA_FACE		equ TA_G0Y+2	; facing 0-3 (N E S W)
TA_LH		equ TA_FACE+2	; direction held last (-1 none)
TA_CMT		equ TA_LH+2	; pad nibble to hand the game (a step), 0 none
TA_CF		equ TA_CMT+2	; frame the game took it (0: none pending)
TA_BLK		equ TA_CF+2	; the step was refused: back to the cell
TA_WPH		equ TA_BLK+2	; walk phase (1/256 cell travelled)
TA_MOV		equ TA_WPH+2	; moved this frame
TA_CFR		equ TA_MOV+2	; frame the controller last ran
TA_MISS		equ TA_CFR+2	; leader images shown late (count, a measure)
TA_NMENU	equ TA_MISS+32	; counts (a measure): updates by the menu path,
TA_NBAD		equ TA_NMENU+2	; by the bad path
TA_LP		equ TA_NBAD+2	; pad nibble of the direction held last
TA_TRN		equ TA_LP+2	; frame of a turn from standing (no step yet)
TA_LOST		equ TA_TRN+2	; the game decoded into DECBUF: tables gone
TA_WHO		equ TA_LOST+2	; the char the pad moves (ta_who)
TA_WFQ		equ TA_WHO+2	; ticks the window is cleaned every tick
TA_MSG0		equ TA_WFQ+2	; TD_MSG last tick
TA_LDB		equ TA_MSG0+2	; ta_look: the cell's depth byte, atlas row
TA_LROW		equ TA_LDB+2
TA_BLIFT	equ TA_LROW+2	; the leader's lift (td_chars)
TA_OVK		equ TA_BLIFT+2	; overlay key: column, row, depth, phase, area
TA_OVOK		equ TA_OVK+10	; overlay drawn (TA_OVT), at global TA_OVX/Y
TA_OVX		equ TA_OVOK+2
TA_OVY		equ TA_OVX+2
TA_WFF		equ TA_OVY+2	; frames the window is cleaned every 4th
TA_DFACE	equ TA_WFF+2	; the facing drawn: the way he moves (a
TA_POX		equ TA_DFACE+2	; corrected step goes sideways), TA_FACE
TA_POY		equ TA_POX+2	; standing
TA_LMF		equ TA_POY+2	; last frame he did not move
TA_CAP		equ TA_LMF+2
TA_DCAND	equ TA_CAP+2
TA_CDIR		equ TA_DCAND+2	; the step handed to the game: its direction
TA_SX		equ TA_CDIR+2	; the camera last shown (ta_clamp)
TA_PFP		equ TA_SX+4	; prefetch (ta_pfetch): progress, direction
TA_PFD		equ TA_PFP+2	; (1 right 2 left 3 down 4 up), the window
TA_PFL		equ TA_PFD+2	; it was for, the camera seen last
TA_PFT		equ TA_PFL+2
TA_PFGX		equ TA_PFT+2
TA_PFGY		equ TA_PFGX+2
TA_FPH		equ TA_PFGY+2	; figure animation phase held while he walks
TA_WSK		equ TA_FPH+2	; window scans: every other one while he walks
TA_CX		equ TA_WSK+2	; camera, 1/16 px (long): eased to the target
TA_CY		equ TA_CX+4
TA_RGX		equ TA_CY+4	; the camera's target before easing (tests)
TA_RGY		equ TA_RGX+2
TA_HELD		equ TA_RGY+2	; the camera held at the window's edge
TA_FARN		equ TA_HELD+2	; a far camera target seen (once: not yet)
TA_INV		equ TA_FARN+2	; ta_stream called by ta_vstream (VBlank)
TA_MSGT		equ TA_INV+2	; cb_msg: frame of the last combat message
TA_SY		equ TA_SX+2	; a new drawn facing, seen once (2 frames turn it)	; how far a step goes before the game takes it
TA_OVT		equ 1958	; its 16 tiles: TA_N's last 16 slots
OVBUF		equ DECBUF+21376	; 512 B scratch (past the slot tables)
TA_LT		equ TA_MISS+2	; 5 x (cell x, y, lift): the leader's cell and
				; its neighbours, read ahead (main loop)
TA_DZ		equ TI_CU	; camera: dead zone, lead, speed cap (units)
TA_LEAD		equ 2*TI_CU
TA_VMAX		equ 16
TA_CMTP		equ 16		; progress (1/256 cell) the step goes to the game
TA_TURN		equ 3		; frames a new facing is held before a step
TA_N		equ 1182	; tile slots (42 x 28 = 1176 cells: never short): bank 64-272, 401-827, rec 6's 436-873,
				; records 16-17's 1834-1973 (pad, gauges); 1974-2037:
				; figure images 8-11 (the leader's other facings)
TA_HUD		equ $9F0000	; their copy (restored on leaving)
TA_HEAD		equ DECBUF	; 512 words: hash bucket -> slot + 1
TA_SH		equ DECBUF+7552	; 2048 words: plane cell -> slot + 1, $FFFF blank
TA_ID		equ TA_SH+4096	; TA_N longs: slot -> tile id, -1 free
TA_NX		equ TA_ID+4*TA_N	; next slot + 1 in the bucket
TA_RC		equ TA_NX+2*TA_N	; cells of the loaded window using the slot
ATL		equ $210000	; tools/ow_atlas.py
FIGIMG		equ $8D0000	; tools/ow_atlas.py FIG
	endif
TD_END2		equ TD_VDIF+8
TD_ARN		equ TD_END2	; combat arena shown by the game itself
TD_RLAST	equ TD_ARN+2	; frame td_tick last handed back to the game
TD_RPER		equ TD_RLAST+2	; frames its ticks take (peak, slow decay)
TD_HB1		equ TD_RPER+2	; 32 B: a half-width tile doubled (ta_up)
TD_HB2		equ TD_HB1+32	; 32 B: the same for ta_occ
TD_DK		equ TD_HB2+32	; display dark (ta_dark): 1
TD_DKC		equ TD_DK+2	; the backdrop colour it saved
TD_END		equ TD_DKC+2

TI_NSLOT	equ 639		; iso tile pool slots (hash table, 24-slot probe)
TI_PHASH	equ $FFFFD2EA	; pool hashes (words) + ages (bytes): in the
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
XTAB		equ $FFFFAE7A	; map_chunk_pos X table (10 x 10 words)
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
	beq.w	.noreq			; smooth iso -> original
	clr.w	TD_REQ
	tst.w	TD_ARN			; (not in the arena)
	bne.w	.noreq
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; leaving the pre-drawn view: its plane
	bne.s	.na			; words off (they would show the next
	addq.w	#1,TD_BUSY		; view's tiles), records 16-17 and 6
	bsr.w	ta_pblank		; back
	bsr.w	ta_out
	subq.w	#1,TD_BUSY
.na:
	endif
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
.noreq:	cmpi.l	#$FFB0BC,GRIDPTR	; combat arena: the game's own
	bne.s	.narn			; (classic) arena and menus, any view
	tst.w	TD_OFF
	bne.s	.arn1
	addq.w	#1,TD_BUSY
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON
	bne.s	.a1
	bsr.w	ta_pblank
	bsr.w	ta_out
.a1:
	endif
	tst.w	TD_ISO
	beq.s	.a2
	bsr.w	td_iso_off
.a2:	bsr.w	td_restore
	move.w	#1,TD_OFF
	move.w	#1,TD_ARN
	subq.w	#1,TD_BUSY
	bra.s	.arn1
.narn:	tst.w	TD_ARN			; arena over: the chosen view back
	beq.s	.arn1			; from scratch
	clr.w	TD_ARN
	clr.w	TD_OFF
	clr.w	TD_ISO
	clr.w	TD_VALID
	clr.w	TD_TILES
.arn1:	tst.w	TD_OFF			; iso in effect = chosen, and not the
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
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; (combat: the pre-drawn view off; it
	bne.s	.nc			; comes back from scratch after)
	bsr.w	ta_out
.nc:
	endif
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
.on:	moveq	#TD_TC,d0		; combat arena: the game's own pace
	cmpi.l	#$FFB0BC,GRIDPTR	; (its moves are its animation; a
	beq.s	.per			; walking period made it crawl)
	moveq	#TD_T2,d0
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
	move.w	sr,-(a7)		; in VBlank: update the picture (no
	move.w	#$2700,sr		; VBlank handler between its VDP
	bsr.w	td_frame		; address and data words)
	move.w	(a7)+,sr
	bra.s	.upd
.late:	move.w	d0,TD_LASTFR		; past VBlank: skip (no tearing)
.upd:
	ifd	SIZE8M
	bsr.w	ta_stream		; pre-drawn overworld: every frame
	bsr.w	ta_pfetch		; (and tiles ahead, while it waits)
	endif
	tst.w	d7
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
	bcc.s	.tk
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn view: a step handed over
	bne.w	.wait			; is taken once half the period is
	tst.w	TA_CMT			; over (a tick the game's own work made
	beq.w	.wait			; late left the walk standing at the
	move.w	TD_PERIOD,d2		; cell's end, #308)
	lsr.w	#1,d2
	cmp.w	d2,d1
	bcs.w	.wait
	else
	bra.w	.wait
	endif
.tk:	move.w	d0,d1			; how long the game's ticks really take
	sub.w	TD_RLAST,d1		; (its own work in a busy room runs
	move.w	d0,TD_RLAST		; past the period: the walk is paced
	move.w	TD_PERIOD,d2		; to that, not left waiting, #308):
	move.w	d2,d3			; peak, decaying by a quarter of the
	add.w	d3,d3			; difference; ticks over 2 periods
	cmp.w	d3,d1			; (loads, menus) not counted, at most
	bhi.s	.tk1			; 1.5 periods
	lsr.w	#1,d3
	add.w	d2,d3
	cmp.w	d3,d1
	bls.s	.tkc
	move.w	d3,d1
.tkc:	move.w	TD_RPER,d2
	cmp.w	d2,d1
	bcs.s	.tkd
	cmpi.w	#2,MODE			; rooms: the peak at once (a long tick
	beq.s	.tk0			; there left the walk standing: stop
	sub.w	d2,d1			; and go, #308)
	addq.w	#1,d1
	lsr.w	#1,d1
	add.w	d2,d1
	bra.s	.tk0
.tkd:
	sub.w	d1,d2
	cmpi.w	#2,MODE			; (and in rooms down by a 16th only)
	bne.s	.tkq
	add.w	#15,d2
	lsr.w	#4,d2
	bra.s	.tkn
.tkq:	addq.w	#3,d2
	lsr.w	#2,d2
.tkn:	neg.w	d2
	add.w	TD_RPER,d2
	move.w	d2,d1
.tk0:	move.w	d1,TD_RPER
.tk1:
	move.w	d0,TD_TICKFR		; game logic starts near the top of
ti_tw1:
	movem.l	(a7)+,d0-d7/a0-a6	; a frame, right after an update
	rts

;=======================================================================
; mg_find — the game's grid search ($02103E, "map_grid_clear"): the
; first cell, row-major, of grid $FFB36C (layer 0) or $FFB76C (layer 1)
; holding byte (arg) -> (row, col, layer) at (ptr), d0 = -1; 0 if none.
; The compiled loop took a fifth of a busy room's tick (#308).
;=======================================================================
mg_find:
	ifd	HELDPC
	addq.w	#1,$FF7ECC
	endif
	move.w	4(a7),d0
	cmpi.w	#255,d0
	bhi.s	.no
	moveq	#15,d1			; where it was last found (a record
	and.w	d0,d1			; sits in one cell): checked there first
	lsl.w	#2,d1
	lea	MG_CACHE,a0
	adda.w	d1,a0
	cmp.w	(a0)+,d0
	bne.s	.sc
	move.w	(a0),d1			; layer << 10 | index
	andi.w	#2047,d1
	lea	$FFB36C,a1
	cmp.b	(a1,d1.w),d0
	bne.s	.sc
	move.w	d1,d0
	lsr.w	#8,d0
	lsr.w	#2,d0
	andi.w	#1023,d1
	movea.l	6(a7),a0
	move.w	d0,4(a0)
	move.w	d1,d0
	lsr.w	#5,d0
	move.w	d0,(a0)
	andi.w	#31,d1
	move.w	d1,2(a0)
	moveq	#-1,d0
	rts
.sc:	lea	$FFB36C,a0
	lea	$FFB76C,a1
	move.w	#1024-1,d1
.l:	cmp.b	(a0)+,d0
	beq.s	.f0
	cmp.b	(a1)+,d0
	beq.s	.f1
	dbra	d1,.l
.no:	moveq	#0,d0
	ifd	HELDPC
	addq.w	#1,$FF7ECE
	endif
	rts
.f1:	moveq	#1,d0
	bra.s	.f
.f0:	moveq	#0,d0
.f:	neg.w	d1			; index 1023 - d1
	add.w	#1023,d1
	move.l	d2,-(a7)		; remember it
	move.w	8(a7),d2
	andi.w	#15,d2
	lsl.w	#2,d2
	lea	MG_CACHE,a0
	adda.w	d2,a0
	move.w	8(a7),(a0)+
	move.w	d0,d2
	lsl.w	#8,d2
	lsl.w	#2,d2
	or.w	d1,d2
	move.w	d2,(a0)
	move.l	(a7)+,d2
	movea.l	6(a7),a0
	move.w	d0,4(a0)
	move.w	d1,d0
	lsr.w	#5,d0
	move.w	d0,(a0)
	andi.w	#31,d1
	move.w	d1,2(a0)
	moveq	#-1,d0
	rts
mg_fend:


;=======================================================================
; ta_bar — the pre-drawn view shows rows 1-26 (42 x 28 loaded cells fit
; the 1182 slots: no pink holes); window rows 0 and 27 are opaque bars,
; the bottom one with the time, gold, food and water as numbers
; (tiles 1942-1957: ta_glyphs, the font on a solid ground). #308
;=======================================================================
TA_GLY		equ 1942
TA_GW		equ $A000+TA_GLY	; priority, palette 1
TA_GBG		equ 13			; the bars' colour (palette 1)

ta_barrow:	; d6 = window row -> Z set if it is a bar (pre-drawn view)
	cmpi.w	#$5A71,TA_ON
	bne.s	.o
	tst.w	d6
	beq.s	.o
	cmpi.w	#27,d6
.o:	rts

ta_glc:	dc.b	"0123456789:$FW  "
	even

ta_glyphs:
	movem.l	d0-d5/a0-a2,-(a7)
	move.w	sr,-(a7)
	move.w	#$2700,sr
	lea	ta_glc(pc),a2
	moveq	#0,d5
.g:	moveq	#0,d0
	move.b	(a2,d5.w),d0
	sub.w	#32,d0
	add.w	FONTBLK,d0
	lsl.w	#5,d0
	bsr.w	td_vcmd
	move.l	d0,VDP_CTRL
	lea	TD_ROWB,a0
	moveq	#16-1,d1
.r:	move.w	VDP_DATA,(a0)+
	dbra	d1,.r
	lea	TD_ROWB,a0
	moveq	#32-1,d1
.p:	move.b	(a0),d2
	move.b	d2,d3
	andi.b	#$F0,d3
	bne.s	.p1
	ori.b	#TA_GBG<<4,d2
.p1:	move.b	d2,d3
	andi.b	#$0F,d3
	bne.s	.p2
	ori.b	#TA_GBG,d2
.p2:	move.b	d2,(a0)+
	dbra	d1,.p
	move.w	d5,d0
	add.w	#TA_GLY,d0
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	TD_ROWB,a0
	moveq	#16-1,d1
.w:	move.w	(a0)+,VDP_DATA
	dbra	d1,.w
	addq.w	#1,d5
	cmpi.w	#16,d5
	bcs.s	.g
	move.w	(a7)+,sr
	movem.l	(a7)+,d0-d5/a0-a2
	rts

ta_bar:
	cmpi.w	#$5A71,TA_ON
	bne.w	.o
	move.w	FRAME,d0
	andi.w	#7,d0
	bne.w	.o
	movem.l	d2-d4/a2,-(a7)
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	#$1000,d0		; top bar
	bsr.w	td_vwrite
	moveq	#40-1,d1
.t:	move.w	#TA_GW+15,VDP_DATA
	dbra	d1,.t
	tst.w	TD_MSG			; a message: the bottom rows are its
	bne.w	.x
	lea	TD_ROWB,a2
	moveq	#40-1,d1
.c:	move.w	#15,(a2)+
	dbra	d1,.c
	lea	TD_ROWB+2*2,a2		; time hh:mm (the game's clock: hour
	moveq	#0,d0			; (clock / 100 + 11) mod 24)
	move.w	$FF0E16,d0
	divu.w	#100,d0
	move.l	d0,d2
	swap	d2			; d2 = clock mod 100
	addi.w	#11,d0
	ext.l	d0
	divu.w	#24,d0
	swap	d0
	bsr.s	.two
	move.w	#10,(a2)+		; :
	move.w	d2,d0
	mulu.w	#3,d0
	divu.w	#5,d0
	bsr.s	.two
	lea	TD_ROWB+11*2,a2		; $ gold
	move.w	#11,(a2)+
	move.w	LEADER,d0
	mulu.w	#$34,d0
	lea	$FF02DE,a0
	move.w	(a0,d0.l),d0
	bsr.s	.num
	lea	TD_ROWB+21*2,a2		; F food
	move.w	#12,(a2)+
	move.w	$FFC364,d0
	bsr.s	.num
	lea	TD_ROWB+30*2,a2		; W water
	move.w	#13,(a2)+
	move.w	$FFC366,d0
	bsr.s	.num
	move.w	#$1000+27*128,d0
	bsr.w	td_vwrite
	lea	TD_ROWB,a2
	moveq	#40-1,d1
.wr:	move.w	(a2)+,d0
	add.w	#TA_GW,d0
	move.w	d0,VDP_DATA
	dbra	d1,.wr
.x:	move.w	(a7)+,sr
	movem.l	(a7)+,d2-d4/a2
.o:	rts
.two:	andi.l	#$FFFF,d0		; d0 < 100 -> two digits at (a2)+
	divu.w	#10,d0
	move.w	d0,(a2)+
	swap	d0
	move.w	d0,(a2)+
	rts
.num:	andi.l	#$FFFF,d0		; d0 -> its digits at (a2)+
	moveq	#0,d3
.n1:	divu.w	#10,d0
	swap	d0
	move.w	d0,-(a7)
	addq.w	#1,d3
	clr.w	d0
	swap	d0
	tst.w	d0
	bne.s	.n1
	subq.w	#1,d3
.n2:	move.w	(a7)+,(a2)+
	dbra	d3,.n2
	rts

; hp_gauge — the combat roster's HP / Power bars ($02736A jsr
; text_draw_gauge): the HP as a number in the bars' 4 cells instead (#308)
hp_gauge:
	tst.w	$16(a7)			; down: the game's own word
	beq.s	.up
	jmp	($011416).l
.up:	movem.l	d2-d4,-(a7)
	move.w	12+$C(a7),d0		; row * stride + column
	mulu.w	12+8(a7),d0
	add.w	12+$A(a7),d0
	add.w	d0,d0
	add.w	12+6(a7),d0		; + base
	move.w	FONTBLK,d4
	add.w	12+$18(a7),d4		; blank word, the bars' attribute
	moveq	#0,d1
	move.w	12+$E(a7),d1		; HP
	bpl.s	.p
	moveq	#0,d1
.p:	moveq	#0,d3			; its digits on the stack
.d:	divu.w	#10,d1
	swap	d1
	move.w	d1,-(a7)
	addq.w	#1,d3
	clr.w	d1
	swap	d1
	tst.w	d1
	bne.s	.d
	move.w	sr,d2
	move.w	#$2700,sr
	bsr.w	td_vwrite
	moveq	#4,d1
	sub.w	d3,d1
	subq.w	#1,d3
.w:	move.w	(a7)+,d0
	add.w	#16,d0			; '0' - ' '
	add.w	d4,d0
	move.w	d0,VDP_DATA
	dbra	d3,.w
	bra.s	.b1
.b:	move.w	d4,VDP_DATA
.b1:	dbra	d1,.b
	move.w	d2,sr
	movem.l	(a7)+,d2-d4
	rts

; cb_msg — text_event_message ($0275B0) in a combat arena: the last
; message stays a second at least (the next cast's came at once and
; replaced it: a cast with no damage told, #308)
CB_HOLD		equ 60
cb_msg:
	cmpi.l	#$FFB0BC,GRIDPTR
	bne.s	.go
.w:	move.w	FRAME,d0
	sub.w	TA_MSGT,d0
	cmpi.w	#CB_HOLD,d0
	bcc.s	.ok
	jsr	($01386A).l		; wait_vblank
	bra.s	.w
.ok:	move.w	FRAME,TA_MSGT
.go:	link.w	a6,#-$F0
	movem.l	d4-d7/a3-a4,-(a7)
	jmp	($0275B8).l

; s_beh — a character's behaviour switch ($022F22): everyone but the
; party and scripted moves (0 follow, 9 go/attack) stands still: no
; wandering (11, 13) and no chasing or fleeing the leader (5, 6) (#308)
s_beh:
	cmpi.l	#14,d0
	bcc.s	.x
	move.w	#$0800,d1
	btst	d0,d1
	bne.s	.x
	jmp	($022F2A).l
.x:	jmp	($022F34).l

; s52_find — the game's "n-th character at cell (x, y)" ($0258EE): the
; same answer with a pointer walk (the compiled one multiplied for each
; field of each of the 56, #308)
s52_find:
	movem.l	d2-d5,-(a7)
	movem.w	20(a7),d1-d3		; x, y, n
	lea	$FF02B4,a0
	moveq	#0,d0
	moveq	#56-1,d4
.l:	moveq	#15,d5
	and.b	1(a0),d5
	beq.s	.n
	cmp.w	$C(a0),d1
	bne.s	.n
	cmp.w	$E(a0),d2
	bne.s	.n
	tst.w	d3
	beq.s	.o
	subq.w	#1,d3
.n:	lea	$34(a0),a0
	addq.w	#1,d0
	dbra	d4,.l
	moveq	#-1,d0
.o:	movem.l	(a7)+,d2-d5
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
	ifd	HELDPC			; debug: where VBlank found the main
	move.l	6(a7),($FF7EC0).l	; thread (tools/md_held.py)
	move.w	$FF0012,($FF7EC4).l
	move.w	TD_BUSY,($FF7EC6).l
	move.w	TD_VALID,($FF7EC8).l
	movem.l	d0/a0-a1,-(a7)
	lea	22(a7),a0
	lea	($FF7E40).l,a1
	moveq	#24-1,d0
.hp:	move.l	(a0)+,(a1)+
	dbra	d0,.hp
	movem.l	(a7)+,d0/a0-a1
	endif
	cmpi.w	#$7D7D,TD_MAGIC		; cheap exits first (game timing)
	bne.w	.q
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
.l0:	bsr.s	td_vin
	beq.s	.ns
	ifd	SIZE2M
	lea	td_vhl(pc),a0		; a small VDP-free helper (C frame)
.h:	move.l	(a0)+,d1		; called from one of those routines:
	beq.s	.out			; its return address, 4(a6), decides
	move.l	(a0)+,d2		; (#289; not on its first instruction,
	cmp.l	d1,d0			; before its link)
	bls.s	.h
	cmp.l	d2,d0
	bcc.s	.h
	move.l	56(a7),d0		; interrupted a6 (even, in RAM)
	btst	#0,d0
	bne.s	.out
	cmpi.l	#$FF0000,d0
	bcs.s	.out
	movea.l	d0,a0
	move.l	4(a0),d0
	bsr.s	td_vin
	bne.s	.out
	bra.s	.ns
	endif
	bra.s	.out
.ns:	bsr.w	td_frame_ns
	ifd	SIZE8M
	bsr.w	ta_vstream
	endif
.out:	movem.l	(a7)+,d0-d7/a0-a6
.q:	rts
td_vin:	; d0 = PC -> Z set if inside a td_vwl range (uses d1-d2, a0)
	lea	td_vwl(pc),a0
.l:	move.l	(a0)+,d1
	beq.s	.no
	move.l	(a0)+,d2
	cmp.l	d1,d0
	bcs.s	.l
	cmp.l	d2,d0
	bcc.s	.l
	cmp.l	d0,d0
	rts
.no:	andi	#$FB,ccr
	rts
	ifd	SIZE2M
td_vhl:	; VDP-free helpers with a link frame (callers checked)
	dc.l	$012B82,$012BFC		; rand_next
	dc.l	$032FFA,$033136		; npc_find_best_char
	dc.l	$026076,$02619C		; npc_location_greet
	dc.l	$026B08,$026B58		; world_location_lookup
	dc.l	$020D9E,$020E7E		; map_scroll_adjust
	dc.l	0
	endif
td_vwl:	; [start, end) of game routines with no VDP access of their own
	dc.l	$00DD5C,$00DE02		; sys_lzss_decompress
	dc.l	$00DE8E,$00DF58		; mul32 .. math_udiv32 (register-call
					; arithmetic leaves, no VDP)
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
	dc.l	$00D98A,$00D996		; main_loop's 10,000-count delay loop
	dc.l	$01BA4E,$01C0EC		; map_chunk_pos
	dc.l	$0232AC,$02343A		; map_tile_at_offset, map_animated_tile
	dc.l	ti_cstart,ti_cend	; td_iso_commit (VDP writes masked)
	dc.l	td_iso_winfix,ti_wend	; its window scan (likewise)
	ifd	SIZE8M
	dc.l	ta_start,ta_end		; pre-drawn overworld (likewise)
	endif
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
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; (pre-drawn overworld: no frame)
	beq.s	.k1
	endif
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
	ifd	SIZE8M
	bsr.w	ta_padf			; the controller hands out the steps
	endif
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
	move.w	#1,TD_ISOU		; the full-screen pre-drawn view from the start
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
	beq.s	.bad
	cmpi.w	#$2400,SPRBASE
	bne.s	.bad
	movea.l	GRIDPTR,a0
	cmpa.l	TD_GRID,a0
	bne.s	.bad
	move.w	MODE,d0
	cmp.w	TD_MODE,d0
	bne.s	.bad
	move.w	LOC,d0
	cmp.w	TD_LOC,d0
	bne.s	.bad
	move.w	d1,-(a7)
	bsr.w	td_plane_check		; another screen owns the plane?
	move.w	(a7)+,d1
	tst.w	d0
	bne.s	.bad
	move.w	#$8F02,VDP_CTRL
	; menu open ($FF00AC): the world pauses under the game's own panels;
	; blobs are taken off so they never sit on top of a panel
	tst.w	$FF00AC
	beq.s	.world
	ifd	SIZE8M
	addq.w	#1,TA_NMENU
	endif
	clr.w	TD_NB
	bsr.w	td_sprites
	bsr.w	td_layers
	tst.w	TD_ISO			; (iso: its own scroll)
	bne.w	td_iso_scroll
	bsr.w	td_scroll
	rts
.bad:
	ifd	SIZE8M
	addq.w	#1,TA_NBAD
	endif
	bra.w	td_unlay
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
	bsr.s	td_scroll		; vblank-critical first
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

td_band:	; the band moved: redraw the rows that enter or leave it
	movem.l	d2-d7,-(a7)		; (td_tput sets the priority bit by TD_BTOP)
	bsr.s	td_bandtop
	move.w	TD_BTOP,d3		; old band
	cmp.w	d3,d0
	beq.s	.out
	move.w	d0,TD_BTOP
	move.w	d0,d7			; new band
	move.w	TD_CY0,d4
	add.w	d4,d4			; the ring's world tile rows
	moveq	#31,d2
.r:	move.w	d4,d0
	sub.w	d3,d0
	andi.w	#31,d0
	cmpi.w	#TD_NBAND,d0
	scs	d1			; in the old band
	move.w	d4,d0
	sub.w	d7,d0
	andi.w	#31,d0
	cmpi.w	#TD_NBAND,d0
	scs	d0			; in the new band
	cmp.b	d1,d0
	beq.s	.n
	bsr.w	td_trow
.n:	addq.w	#1,d4
	dbra	d2,.r
.out:	movem.l	(a7)+,d2-d7
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
	ifd	SIZE2M
	clr.w	TD_OVDN
	endif
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
.ay:	moveq	#2,d4			; (the dragon: 6, #308)
	cmpi.w	#TD_TF,TD_PERIOD
	bne.s	.az
	moveq	#6,d4
.az:	cmp.w	d4,d0
	bgt.s	.snap
	cmp.w	d4,d1
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
	ifd	SIZE8M
	bsr.w	ta_isldr		; the leader: where the controller has
	bne.s	.np			; him (cell + offset)
	move.w	d2,d5
	lsl.w	#4,d5
	move.w	TA_OX,d0
	asr.w	#4,d0
	add.w	d0,d5
	move.w	d3,d6
	lsl.w	#4,d6
	move.w	TA_OY,d0
	asr.w	#4,d0
	add.w	d0,d6
.np:
	endif
	bsr.w	td_ilift		; lift of its target cell
.fig:	bsr.w	td_figure		; d0 = figure tile word, or -1
	tst.w	d0
	bmi.s	.blob
	cmpi.w	#TD_NFIG,TD_NB
	bcc.s	.lchk
	move.w	d5,(a2)+
	move.w	d6,(a2)+
	move.w	d0,(a2)+
	move.w	TD_TLIFT,d0		; kind 1: 32x32 figure (lift << 8)
	lsl.w	#8,d0
	addq.w	#1,d0
	move.w	d0,(a2)+
	addq.w	#1,TD_NB
	ifd	SIZE2M
	tst.w	TD_ISO
	beq.s	.lchk
	bsr.w	ti_occl			; iso: terrain in front of it
	endif
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
	ifd	SIZE8M
	tst.w	TA_CTL			; (the controller's figure)
	beq.s	.lc0
	bsr.w	ta_isldr
	beq.s	.isl
	bra.s	.next
.lc0:
	endif
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
	ifd	SIZE8M
	move.w	TD_TLIFT,TA_BLIFT
	endif
	bra.s	.next
.gone:
	move.w	#NOPOS,(a4)
.next:
	lea	$34(a3),a3
	lea	10(a4),a4
	addq.w	#1,d7
	cmpi.w	#56,d7
	bcs.w	.loop
	ifd	SIZE8M
	bsr.w	ta_ovl			; the terrain in front of the leader
	endif
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
	cmpi.w	#2,10(a1)		; draw type 2 (an item: map_tile_at_
	bcs.s	.tp			; offset) or 3 (an animated object,
	moveq	#0,d2			; its first frame): the record's own
	moveq	#0,d3			; image, no template (a key, a scroll
	bra.w	.key			; showed a sack and a knife, #308)
.tp:	move.w	2(a1),d0		; template
	ifd	SIZE8M
	bsr.w	ta_isldr		; (the leader: the controller's facing)
	bne.s	.nf
	move.w	TA_DFACE,d0
.nf:
	endif
	add.w	4(a1),d0
	cmpi.w	#56,d0
	bcc.w	.none
	mulu.w	#36,d0
	movea.l	GRIDPTR,a0
	move.w	$A(a0),d1		; phase 0..3
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn view: only the leader
	bne.s	.ph1			; animates; everyone else holds the
	bsr.w	ta_isldr		; first frame of his pose and only
	beq.s	.ph1			; turns (fountains and fires too, #308)
	moveq	#0,d1
.ph1:
	endif
	andi.w	#3,d1
	lsl.w	#3,d1
	add.w	d1,d0
	lea	($0197B0).l,a0
	adda.w	d0,a0
	move.w	(a0),d2			; image offset
	move.w	2(a0),d3		; mirror param
	movea.l	a0,a2			; a template animated by the phase (the
	suba.w	d1,a2			; dragon's wings, a missile) is drawn as
	move.w	(a2),d0			; it is: no walk poses (its offsets 6/7
	cmp.w	8(a2),d0		; are the dragon's shadow, #308)
	bne.w	.key
	cmp.w	16(a2),d0
	bne.w	.key
	cmp.w	24(a2),d0
	bne.w	.key
	ifd	SIZE8M
	bsr.w	ta_isldr		; the leader walks while he moves
	bne.s	.nw
	tst.w	TA_MOV
	beq.s	.key
	move.w	d2,d0
	andi.w	#6,d0
	beq.s	.lw
	cmpi.w	#6,d0
	bne.s	.key
.lw:	move.w	TA_WPH,d0		; 4 frames a cell
	lsr.w	#6,d0
	bra.s	.wf
.nw:	cmpi.w	#$5A71,TA_ON		; (no walk poses for the others)
	beq.w	.key
	endif
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
.wf:	andi.w	#3,d0
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
.old:
	ifd	SIZE8M
	bsr.w	ta_isldr
	bne.s	.nm
	addq.w	#1,TA_MISS
.nm:
	endif
	move.w	(a0),d0			; not cached yet: its last image if it
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
	bsr.s	td_extract		; d0 = key, d2 = slot
	move.w	d2,d1
	lsl.w	#2,d1
	lea	TD_FC,a0
	adda.w	d1,a0
	move.w	d0,(a0)
.hit:	move.w	TD_STAMP,2(a0)
	move.w	d2,d0			; tile word
	bra.s	td_slot
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
	ifd	HELDPC
	addq.w	#1,$FF7ECA
	endif
	ifd	SIZE8M			; 8 MB+: the image pre-drawn in the ROM
	move.w	d0,d1			; (tools/ow_atlas.py figs, #308)
	andi.l	#$7FFF,d1
	add.l	d1,d1
	tst.w	d0
	bpl.s	.pv
	addq.l	#1,d1
.pv:	moveq	#9,d0
	lsl.l	d0,d1
	addi.l	#FIGIMG,d1
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	TA_B7,-(a7)
	bsr.w	ta_t7			; a0 = the image
	move.w	14(a7),d0		; saved d2 = slot -> VRAM address
	bsr.w	td_slot
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	VDP_DATA,a1
	moveq	#16-1,d1
.pc:	rept	8
	move.l	(a0)+,(a1)
	endr
	dbra	d1,.pc
	move.w	(a7)+,d2		; slot 7 back as it was
	bmi.s	.pb
	move.w	d2,TA_B7
	move.b	d2,$A130FF
.pb:	move.w	(a7)+,sr
	movem.l	(a7)+,d0-d7/a0-a6
	rts
	endif
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
	move.w	sr,-(a7)		; (a VBlank between address and data
	move.w	#$2700,sr		; put the image after the sprite table)
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
	move.w	(a7)+,sr
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
	move.w	d1,d0			; lifted with its cell (#297)
	lsr.w	#8,d0
	sub.w	d0,d3
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
.ik:
	ifd	SIZE2M
	cmpi.b	#2,d1			; occlusion overlay: only wholly inside
	bne.s	.ik2			; the hole (it is terrain)
	bsr.w	ti_ohole
	bne.s	.icond
.ik2:
	endif
	cmpi.w	#-32,d2
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
	bsr.s	td_vread		; y + 128
	move.w	d0,d3
	move.w	d2,d0
	addq.w	#2,d0
	bsr.s	td_vread		; size | link
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
	bsr.s	td_vread		; tile word
	tst.w	d0
	bmi.s	.nx
	ori.w	#$8000,d0
	move.w	d0,d3
	move.w	d4,d1
	add.w	d1,d1
	move.w	d3,(a2,d1.w)
	move.w	d2,d0
	addq.w	#4,d0
	bsr.s	td_vwrite
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
	bsr.s	td_vcmd			; (masked: an interrupt between command
	move.w	sr,-(a7)		; and read leaves the port in write
	ori.w	#$0700,sr		; mode; BlastEm freezes on that read)
	move.l	d0,VDP_CTRL
	move.w	VDP_DATA,d0
	move.w	(a7)+,sr
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
TD_CC		equ DECBUF+16*1152	; 2 KB cell cache: (y&31)*64 + (x&31)*2
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
	bsr.s	td_vcmd
	move.w	sr,-(a7)
	ori.w	#$0700,sr
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
	move.w	(a7)+,sr
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
	bgt.s	.all
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
	add.w	#TD_NROW+3,d7		; the cell cache's new south row
	bsr.w	td_ccrow
	subq.w	#4,d7			; the ring's new south row
	bsr.s	td_draw_row
	bra.s	.yd
.yu:	cmp.w	TD_CY0,d5
	bge.s	.out
	subq.w	#1,TD_CY0
	move.w	TD_CY0,d7
	bsr.w	td_ccrow
	bsr.s	td_draw_row
	bra.s	.yu
.all:	move.w	d4,TD_CX0
	move.w	d5,TD_CY0
	bsr.s	td_draw_all
.out:	movem.l	(a7)+,d2-d7
	rts

;=======================================================================
; Cell drawing with height (#297, Q14 revised: raised). Cell y of height
; h (cell bits 13-15) covers world tile rows 2y-h .. 2y+1: its top (the
; cell's 16x16 block) lifted h tile rows, then h rows of south face (the
; block's rows upside down, shadowed: no priority bit). A tile row shows
; the southmost cell covering it (painter order), so each plane tile is
; resolved from the cell cache TD_CC: the ring's rows cy0..cy0+15 plus
; the 4 rows south of it whose tops can reach up into the ring. A new
; ring row or column redraws only its own tiles; the rest stays valid.
; d6 = cell x, d7 = cell y, d4 = world tile row (kept across game calls:
; the game's C code saves d4-d7/a3-a4 when it uses them).
;=======================================================================
td_draw_all:
	movem.l	d4-d7,-(a7)
	move.w	TD_CX0,d6
	subq.w	#TD_SHL,d6
	moveq	#21+TD_SHL+TD_SHR-1,d4
.c:	bsr.w	td_cccol
	addq.w	#1,d6
	dbra	d4,.c
	move.w	TD_CY0,d7
	moveq	#TD_NROW-1,d4
.r:	bsr.s	td_draw_row
	addq.w	#1,d7
	dbra	d4,.r
	movem.l	(a7)+,d4-d7
	rts

td_draw_row:				; tile rows 2y, 2y+1 of cell row d7
	movem.l	d4-d6,-(a7)
	move.w	d7,d4
	add.w	d4,d4
	bsr.s	td_trow
	addq.w	#1,d4
	bsr.s	td_trow
	movem.l	(a7)+,d4-d6
	rts
td_trow:	; tile row d4, columns cx0-TD_SHL..cx0+20+TD_SHR (uses d5-d6)
	move.w	TD_CX0,d6
	subq.w	#TD_SHL,d6
	moveq	#21+TD_SHL+TD_SHR-1,d5
.c:	bsr.w	td_tput
	addq.w	#1,d6
	dbra	d5,.c
	rts

td_draw_col:				; column d6: cache, then its 32 tile rows
	movem.l	d4-d5,-(a7)
	bsr.s	td_cccol
	move.w	TD_CY0,d4
	add.w	d4,d4
	moveq	#2*TD_NROW-1,d5
.c:	bsr.w	td_tput
	addq.w	#1,d4
	dbra	d5,.c
	movem.l	(a7)+,d4-d5
	rts

td_ccrow:				; cache cell row d7 (the ring's columns)
	movem.l	d5-d6,-(a7)
	move.w	TD_CX0,d6
	subq.w	#TD_SHL,d6
	moveq	#21+TD_SHL+TD_SHR-1,d5
.c:	bsr.s	td_ccget
	addq.w	#1,d6
	dbra	d5,.c
	movem.l	(a7)+,d5-d6
	rts

td_cccol:				; cache column d6, rows cy0..cy0+TD_NROW+3
	movem.l	d5/d7,-(a7)
	move.w	TD_CY0,d7
	moveq	#TD_NROW+4-1,d5
.c:	bsr.s	td_ccget
	addq.w	#1,d7
	dbra	d5,.c
	movem.l	(a7)+,d5/d7
	rts

td_ccget:				; cache (d6, d7) <- cell word, 0 off the map
	moveq	#0,d0
	bsr.s	td_inmap
	bne.s	.put
	move.w	d7,-(a7)
	move.w	d6,-(a7)
	jsr	(CELLREAD).l
	addq.w	#4,a7
	movea.l	d0,a0
	move.w	(a0),d0
.put:	bsr.s	td_ccadr
	move.w	d0,(a0)
	rts

td_inmap:				; Z set if (d6, d7) is on the map
	tst.w	d6
	bmi.s	.no
	cmp.w	TD_W,d6
	bge.s	.no
	tst.w	d7
	bmi.s	.no
	cmp.w	TD_H,d7
	bge.s	.no
	cmp.w	d6,d6
	rts
.no:	andi	#$FB,ccr
	rts

td_ccadr:				; (d6, d7) -> a0 = its cache word (uses d1)
	move.w	d7,d1
	andi.w	#31,d1
	lsl.w	#6,d1
	lea	TD_CC,a0
	adda.w	d1,a0
	move.w	d6,d1
	andi.w	#31,d1
	add.w	d1,d1
	adda.w	d1,a0
	rts

td_tput:				; plane tiles of cell column d6, tile row d4
	movem.l	d2-d3/d7,-(a7)
	move.w	d4,d7
	addq.w	#7,d7
	asr.w	#1,d7			; southmost cell that can reach row t
	move.w	d4,d3
	asr.w	#1,d3			; the row's own cell (always covers it)
.c:	cmp.w	d3,d7
	beq.s	.hit
	bsr.s	td_ccadr
	move.w	(a0),d2
	rol.w	#3,d2
	andi.w	#7,d2			; h
	move.w	d7,d0
	add.w	d0,d0
	sub.w	d4,d0			; 2y - t
	cmp.w	d2,d0
	ble.s	.hit			; h >= 2y - t: its top or face is here
	subq.w	#1,d7
	bra.s	.c
.hit:	bsr.s	td_inmap
	bne.s	.void
	bsr.s	td_ccadr
	move.w	(a0),d2			; cell word
	move.w	d2,d3
	rol.w	#3,d3
	andi.w	#7,d3
	add.w	d4,d3
	sub.w	d7,d3
	sub.w	d7,d3			; p = t - 2y + h: 0, 1 top, then face
	move.w	d3,-(a7)
	bsr.w	td_cellq		; d0 = TL:TR, d1 = BL:BR
	move.w	(a7)+,d3
	subq.w	#1,d3
	bmi.s	.top
	beq.s	.bot
	subq.w	#1,d3			; face row f = p - 2: even BL:BR,
	btst	#0,d3			; odd TL:TR, upside down
	bne.s	.f1
	move.l	d1,d0
.f1:	eori.l	#$10001000,d0
	moveq	#0,d2			; face: shadowed
	bra.s	.put
.void:	move.w	TD_BASE,d0		; off the map: parchment void
	add.w	#256+$2000,d0		; (palette 1, never shadowed)
	move.w	d0,d1
	swap	d0
	move.w	d1,d0
	moveq	#1,d2
	bra.s	.put
.bot:	move.l	d1,d0
.top:	moveq	#1,d2			; top: not shadowed
.put:	; plane row r = t & 31. A top gets the priority bit (not
	; shadowed) except in rows inside the HUD band (td_band redraws a
	; row that enters or leaves it).
	move.w	d4,d3
	andi.w	#31,d3			; r
	tst.w	d2
	beq.s	.ad
	move.w	d3,d1
	sub.w	TD_BTOP,d1
	andi.w	#31,d1
	cmpi.w	#TD_NBAND,d1
	bcs.s	.ad
	ori.l	#$80008000,d0
.ad:	lsl.w	#7,d3			; VRAM (r * 64 + (2x & 63)) * 2
	move.w	d6,d2
	add.w	d2,d2
	andi.w	#63,d2
	add.w	d2,d2
	add.w	d2,d3
	moveq	#0,d2
	move.w	d3,d2
	swap	d2
	ori.l	#$40000000,d2
	move.w	sr,-(a7)		; no VBlank update between address
	ori.w	#$0700,sr		; and data
	move.l	d2,VDP_CTRL
	move.l	d0,VDP_DATA
	move.w	(a7)+,sr
	movem.l	(a7)+,d2-d3/d7
	rts

td_cellq:	; d2 = cell word -> d0 = TL:TR, d1 = BL:BR (uses d2-d3, a0)
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
	bsr.w	ta_barrow		; (the pre-drawn view's bars: ta_bar's)
	beq.w	.nr
	move.w	d6,d0			; read the 40 visible words of row d6
	lsl.w	#7,d0
	add.w	#$1000,d0
	move.w	d0,d5			; row address
	andi.l	#$3FFF,d0
	swap	d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.l	d0,VDP_CTRL
	lea	TD_WROW,a2
	moveq	#40-1,d1
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d1,.rd
	move.w	(a7)+,sr
	lea	TD_WROW,a2
	moveq	#0,d4			; column 0..39
	move.w	FONTBLK,d3		; the word most cells hold: nothing to do
	cmpi.w	#TD_WBROW,d6
	bcs.s	.col
	ori.w	#$8000,d3
.col:	move.w	(a2)+,d0
	cmp.w	d3,d0
	beq.w	.nx
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
	move.w	sr,-(a7)		; (a VBlank update between the address
	move.w	#$2700,sr		; and the word put it on the font blank's
	bsr.w	td_vwrite		; first row: the screen-wide dots, #307)
	move.w	d1,VDP_DATA
	move.w	(a7)+,sr
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
.nr:	addq.w	#1,d6
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
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
	lea	TD_ROW,a2
	move.w	d4,d0
	subq.w	#1,d0
.rd:	move.w	VDP_DATA,(a2)+
	dbra	d0,.rd
	move.w	(a7)+,sr
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
	ifd	SIZE8M
	bsr.w	ta_sync
	cmpi.w	#$5A71,TA_ON
	beq.w	ti_rts
	endif
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
	ifd	SIZE8M
	bsr.w	ta_ctl
	endif
	bsr.w	td_chars
	bsr.w	td_iso_cam
	bsr.w	td_layers
	bsr.s	td_iso_scroll		; vblank-critical first
	ifd	SIZE8M
	bsr.w	td_sprites
	cmpi.w	#$5A71,TA_ON		; (the game rewrites its pad sprites
	bne.s	.ni			; and its HUD words: off again in
	bsr.w	ta_hud			; this VBlank)
	bra.w	ta_spr
.ni:	rts
	else
	bra.w	td_sprites
	endif

td_ilayers:
	move.w	#1,TD_LAY
	clr.w	TD_GSPON
	clr.w	TD_BAND
	clr.w	TD_BOX
	move.w	#TI_CY+TI_HH,TD_YMAX
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn overworld: whole screen
	bne.s	.nl
	move.w	#224,TD_YMAX
.nl:
	endif
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
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON
	beq.w	ta_pcheck
	endif
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
.ns:
	ifd	SIZE8M
	move.w	d0,d2			; the step's direction (rubber band)
	sub.w	TD_CGX,d2
	bsr.w	ta_sgn
	move.w	d2,TA_LX
	move.w	d1,d2
	sub.w	TD_CGY,d2
	bsr.w	ta_sgn
	move.w	d2,TA_LY
	endif
	move.w	d0,TD_CGX
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
.e1:
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn view: rubber band
	bne.s	.nr
	bsr.w	ta_rub
	bra.s	.xy
.nr:
	endif
	move.w	TD_CGX,d0
	move.w	TD_ICX,d1
	move.w	TD_CFX,d5
	lea	TD_CMX,a0
	bsr.s	.ax
	move.w	TD_CGY,d0
	move.w	TD_ICY,d1
	move.w	TD_CFY,d5
	lea	TD_CMY,a0
	bsr.s	.ax
.xy:	moveq	#0,d0			; (unsigned: x past cell 292 is past
	move.w	TD_CMX,d0		; 32767 units; as a signed word the
	moveq	#0,d1			; east of the map jumped 585 cells
	move.w	TD_CMY,d1		; west, into nothing, #308)
	sub.l	d1,d0
	asr.l	#3,d0			; 14 (x - y) / 112
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
	ifd	SIZE8M
	bsr.w	ta_clamp
	endif
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

; td_ilift — lift (px) of the target cell of char d7 (slide record a4)
; -> TD_TLIFT, gliding over the slide. Iso: (height + desc bit 7) * 7 +
; desc bit 8 * 4, as map_chunk_pos passes it to hero_track; cached per
; char, read from the map only when game calls are allowed (TD_MAIN).
; Top-down (#297): 8 px per height level, from the cell cache.
td_ilift:
	movem.l	d0-d3/a0-a2,-(a7)
	ifd	SIZE8M
	bsr.w	ta_isldr		; the leader (controller): his cell's
	bne.s	.nl			; lift at once, read ahead by ta_lifts
	move.w	d5,d2			; the cell nearest his drawn place
	addq.w	#8,d2			; (d5/d6): the lift turns at half a
	asr.w	#4,d2			; step (a refused one stops at 1/8:
	move.w	d6,d3			; never a wall's lift)
	addq.w	#8,d3
	asr.w	#4,d3
	bsr.w	ta_ltget
	bmi.s	.nl
	move.w	d0,TD_TLIFT
	move.w	d7,d1			; (the slide state follows, so the
	add.w	d1,d1			; lift is right if the controller
	lea	TD_LFD,a0		; pauses)
	move.w	d0,(a0,d1.w)
	lea	TD_LF0,a0
	move.w	d0,(a0,d1.w)
	lea	TD_LFT,a0
	move.w	8(a4),(a0,d1.w)
	lea	TD_CLK,a1
	adda.w	d1,a1
	move.w	d2,(a1)
	move.w	d3,112(a1)
	move.w	d0,224(a1)
	movem.l	(a7)+,d0-d3/a0-a2
	rts
.nl:
	endif
	move.w	d7,d1
	add.w	d1,d1
	lea	TD_CLK,a1
	adda.w	d1,a1			; +0 cell x, +112 cell y, +224 lift
	tst.w	TD_ISO
	bne.s	.iso
	movem.l	d6-d7,-(a7)		; (a figure on screen is in the cache)
	move.w	(a4),d6
	move.w	2(a4),d7
	bsr.w	td_ccadr
	move.w	(a0),d2
	rol.w	#6,d2
	andi.w	#$38,d2			; height * 8
	movem.l	(a7)+,d6-d7
	move.w	d2,224(a1)
	move.w	#$8000,(a1)		; iso reads its own lift again
	bra.s	.have
.iso:	move.w	(a4),d2
	move.w	2(a4),d3
	cmp.w	(a1),d2
	bne.s	.new
	cmp.w	112(a1),d3
	beq.s	.have
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
	addq.w	#1,d2			; the game draws its figures 7 px higher
	mulu.w	#7,d2			; than this formula gave (#300)
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
	bra.w	.c
.t:	move.w	(a2),d0
	move.w	2(a2),d1
	cmpi.b	#3,7(a2)		; kind 3 (overlay): global x already
	bne.s	.t3
	sub.w	TD_IGX,d0
	move.w	d0,(a2)
	bra.w	.n
.t3:	move.w	d0,d2
	sub.w	d1,d2
	muls.w	#7,d2
	asr.l	#3,d2			; global x = 14 (x - y)
	add.w	d1,d0
	asr.w	#1,d0			; global y = 8 (x + y)
	move.w	d0,2(a2)
	sub.w	TD_IGX,d2
	move.w	d2,(a2)
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; the pre-drawn view: the whole screen
	bne.w	.hole			; (not the old view's hole: far
	cmpi.w	#-40,d2			; figures showed only close by, #308)
	blt.w	.off
	cmpi.w	#360,d2
	bgt.w	.off
	sub.w	TD_IGY,d0
	cmpi.w	#-64,d0
	blt.w	.off
	cmpi.w	#264,d0
	ble.w	.n
.off:	move.w	#$8000,(a2)
	bra.w	.n
.hole:
	endif
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
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn overworld: no render
	beq.w	ti_rts
	endif
	movem.l	d2-d7/a2-a6,-(a7)
	clr.w	TD_INOB
	tst.w	TD_VALID		; first picture: all at once
	bne.s	.go
	move.w	#1,TD_INOB
.go:	tst.w	TD_IRS
	bne.w	.cont
	ifd	SIZE2M
	tst.w	TD_IREQ			; idle, no picture waiting: an
	bne.s	.ob			; occlusion overlay (#278; built also
	bsr.w	ti_obuild		; with one waiting: twice the cases
.ob:					; covered, trail 98.1 -> 97.6 %, Q19)
	endif
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
	bne.w	.com
	bsr.w	ti_late			; no time left in this tick?
	bne.w	.out
	move.w	#1,TD_REND		; render rows TD_IROW.. (map_chunk_pos
	clr.w	TD_IBAIL		; stops between rows when the tick's
	ifd	SIZE2M			; time is up: ti_row)
	tst.w	TD_ILIN			; 2 MB: our own cell loop (#283)
	beq.w	.cpos
	ifd	GAMELOOP		; (debug: the game's loop instead)
	bra.s	.cpos
	endif
	ifd	VERIFY283
	move.w	TD_INOB,-(a7)		; debug: whole render both ways,
	move.w	#1,TD_INOB		; compare the bitmaps' sums
	clr.w	TD_IROW
	clr.w	TD_ICOLR
	endif
	bsr.w	ti_loop
	ifd	VERIFY283
	lea	TD_VROW,a1
	bsr.w	ti_vsum
	move.l	d0,TD_VSUM
	bsr.w	ti_clear
	clr.w	TD_IROW
	clr.w	TD_ICOLR
	ifd	VERIFYOWN		; (debug of the debug: ours twice)
	bsr.w	ti_loop
	else
	move.w	TD_IRY,-(a7)
	move.w	TD_IRX,-(a7)
	jsr	(CHUNKPOS).l
	addq.w	#4,a7
	endif
	lea	TD_VROW+92,a1		; (scratch: overwritten next)
	bsr.w	ti_vsum
	addq.w	#1,TD_VOK
	cmp.l	TD_VSUM,d0
	beq.s	.veq
	subq.w	#1,TD_VOK
	addq.w	#1,TD_VBAD
	bsr.w	ti_vdif
.veq:	move.w	(a7)+,TD_INOB
	clr.w	TD_IBAIL
	endif
	bra.s	.rdn
.cpos:
	endif
	move.w	TD_IRY,-(a7)
	move.w	TD_IRX,-(a7)
	jsr	(CHUNKPOS).l
	addq.w	#4,a7
.rdn:	clr.w	TD_REND
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
	ifd	SIZE2M
	lea	TD_OVK,a0		; occlusion decided again on it
	moveq	#56/2-1,d0
.ok:	clr.l	(a0)+
	dbra	d0,.ok
	clr.w	TD_OVPK
	endif
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
	blt.s	.out
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
	ifd	SIZE2M
;=======================================================================
; ti_loop — map_chunk_pos's 10 x 10 cell loop ($01BA4E) for our linear
; render, without its compiled-C overhead (#283): the same tile word
; (ti_tword = ti_ccr's lookup), props, phase step, height stack, top
; call and figure records (kinds 2/3 drawn by the game's routines,
; 0/1 skipped as ti_fig_ht / ti_fig_pr skip them, kind 1's grid move
; kept); no spell step. Starts at TD_IROW (TD_ICOL if TD_ICOLR), stops
; before a cell when the tick's time is up (TD_IBAIL). Terrain calls
; go straight to ti_fast.
;=======================================================================
TL_YCH		equ -48			; 10 words: chunk row * chunks per row
TL_YIN		equ -68			; 10 words: 2 E (y' mod E)
TL_FY		equ -88			; 10 words: figure grid (H + y + sy) mod H
TL_XCH		equ -90			; row: chunk column
TL_XIN		equ -92			; row: 2 (x' mod E)
TL_FX		equ -96			; row: figure grid 32 ((W + x + sx) mod W)
TL_CB		equ -98			; chunk number base (rooms: LOC + $4D)
ti_loop:
	link	a6,#-100		; -2 stream, -4 tile, -6 props, -8 x,
	movem.l	d4-d7/a3-a4,-(a7)	; -10 y, -12 L, -14 e, -16 d3, -18 h,
	pea	-24(a6)			; -20 rec1, -24/-22 scroll offset,
	jsr	($020D58).l		; -28 grid index (long)
	addq.w	#4,a7			; map_scroll_offset
	movea.l	GRIDPTR,a1		; per render: the 10 y values
	clr.w	TL_CB(a6)		; (ti_ccr's arithmetic, divu once per
	cmpi.w	#$FFFF,LOC		; column, not per cell)
	beq.s	.cb
	move.w	LOC,d0
	add.w	#$4D,d0
	move.w	d0,TL_CB(a6)
.cb:	moveq	#0,d5
.yt:	move.w	TD_IRY,d1
	add.w	d5,d1
	subq.w	#5,d1
	move.w	d1,d2
	add.w	2(a1),d1		; y' = y mod H (ti_ccr: + H, - H ...)
.ym:	cmp.w	2(a1),d1
	blt.s	.yd
	sub.w	2(a1),d1
	bra.s	.ym
.yd:	andi.l	#$FFFF,d1
	divu.w	4(a1),d1
	move.w	d5,d0
	add.w	d0,d0
	lea	TL_YCH(a6),a0
	move.w	d1,d3
	mulu.w	6(a1),d3
	move.w	d3,(a0,d0.w)
	swap	d1
	mulu.w	4(a1),d1
	add.w	d1,d1
	lea	TL_YIN(a6),a0
	move.w	d1,(a0,d0.w)
	add.w	2(a1),d2		; figure grid: (H + y + sy) mod H, divs
	add.w	-22(a6),d2		; as map_chunk_pos
	ext.l	d2
	divs.w	2(a1),d2
	swap	d2
	lea	TL_FY(a6),a0
	move.w	d2,(a0,d0.w)
	addq.w	#1,d5
	cmpi.w	#10,d5
	bcs.s	.yt
	move.w	TD_IROW,d4
.row:	bsr.w	.xr
	moveq	#0,d5
	tst.w	TD_ICOLR
	beq.s	.cell
	move.w	TD_ICOL,d5
	clr.w	TD_ICOLR
.cell:	bsr.w	ti_late
	beq.s	.go
	move.w	d4,TD_IROW
	move.w	d5,TD_ICOL
	move.w	#1,TD_ICOLR
	move.w	#1,TD_IBAIL
	bra.w	.x
.go:	move.w	TD_IRX,d7		; world cell x = cx + row - 5,
	add.w	d4,d7			; y = cy + col - 5
	subq.w	#5,d7
	move.w	TD_IRY,d0
	add.w	d5,d0
	subq.w	#5,d0
	movea.w	d0,a3
	move.w	d5,d0		; tile word: chunk YCH + XCH + base, at
	add.w	d0,d0		; YIN + XIN in it (ti_ccr's lookup)
	lea	TL_YCH(a6),a0
	move.w	(a0,d0.w),d1
	add.w	TL_XCH(a6),d1
	add.w	TL_CB(a6),d1
	lea	TL_YIN(a6),a0
	move.w	(a0,d0.w),d3
	add.w	TL_XIN(a6),d3
	moveq	#0,d2
	move.w	d1,d2
	lsl.l	#2,d2
	lea	($FFA896).l,a0		; chunk buffer pointers
	move.l	(a0,d2.l),d0
	bne.s	.hv
	movem.l	d1-d3,-(a7)
	move.w	d1,-(a7)
	jsr	($019692).l		; map_chunk_load
	addq.w	#2,a7
	movem.l	(a7)+,d1-d3
	lea	($FFA896).l,a0
	move.l	(a0,d2.l),d0
.hv:	movea.l	d0,a0
	move.w	(a0,d3.w),d0
	move.w	d0,($FF0248).l		; (as map_chunk_cache_read leaves it)
	move.w	d4,d1			; the window's words for the occlusion
	mulu.w	#20,d1			; overlays (TI_WIN)
	add.w	d5,d1
	add.w	d5,d1
	lea	TI_WIN,a0
	move.w	d0,(a0,d1.w)
	move.w	d0,-4(a6)
	andi.w	#$1FF,d0
	move.w	d0,-2(a6)
	add.w	d0,d0
	lea	($05EDC4).l,a0		; props
	move.w	(a0,d0.w),d2
	move.w	d2,-6(a6)
	move.w	d4,d0			; X / Y tables
	mulu.w	#20,d0
	add.w	d5,d0
	add.w	d5,d0
	lea	XTAB,a0
	move.w	(a0,d0.w),-8(a6)
	lea	XTAB+200,a0		; (the Y table follows it)
	move.w	(a0,d0.w),-10(a6)
	tst.w	$FF0092			; terrain phase: props bit 9 -> +1,
	beq.s	.ph			; bit 6 -> -1
	btst	#9,d2
	beq.s	.p1
	addq.w	#1,-2(a6)
.p1:	btst	#6,d2
	beq.s	.ph
	subq.w	#1,-2(a6)
.ph:	move.w	-4(a6),d0		; height (tile bits 13-15)
	rol.w	#3,d0
	andi.w	#7,d0
	move.w	d0,-18(a6)
	moveq	#0,d1			; L = -(7 (h + props bit 7) + 4 bit 8)
	btst	#7,d2
	beq.s	.l7
	moveq	#1,d1
.l7:	add.w	d0,d1
	mulu.w	#7,d1
	btst	#8,d2
	beq.s	.l8
	addq.w	#4,d1
.l8:	neg.w	d1
	move.w	d1,-12(a6)
	tst.w	d0
	beq.w	.top
	cmpi.w	#9,d4			; height stack: edge row / column, or
	beq.s	.stk			; tile bit 9
	cmpi.w	#9,d5
	beq.s	.stk
	move.w	-4(a6),d1
	btst	#9,d1
	beq.w	.top
.stk:	btst	#5,d2
	bne.s	.own
	andi.w	#$1F,d2			; filler stream $22F + props & $1F
	add.w	#$22F,d2
	movea.w	d2,a4
	add.w	d2,d2
	lea	($05EDC4).l,a0
	move.w	(a0,d2.w),d1		; its props
	move.w	d1,d2
	andi.w	#$1F,d2
	sub.w	d2,d0
	move.w	d0,-14(a6)
	moveq	#0,d2
	btst	#5,d1
	beq.s	.d0
	move.w	-4(a6),d2
	rol.w	#4,d2
	andi.w	#1,d2
.d0:	move.w	d2,-16(a6)
	bra.s	.lp
.own:	movea.w	-2(a6),a4		; the stream itself
	andi.w	#$1F,d2
	sub.w	d2,d0
	move.w	d0,-14(a6)
	move.w	-4(a6),d2
	rol.w	#4,d2
	andi.w	#1,d2
	move.w	d2,-16(a6)
.lp:	moveq	#0,d6
	bra.s	.lc
.l:	move.w	d6,d0
	muls.w	#7,d0
	move.w	-10(a6),d1
	sub.w	d0,d1
	cmp.w	-14(a6),d6
	blt.s	.f
	move.w	-16(a6),-(a7)
	move.w	d1,-(a7)
	move.w	-8(a6),-(a7)
	move.w	a4,-(a7)
	bra.s	.cf
.f:	clr.w	-(a7)			; below the top layers: filler $230
	move.w	d1,-(a7)
	move.w	-8(a6),-(a7)
	move.w	#$230,-(a7)
.cf:	bsr.w	ti_fast
	addq.w	#8,a7
	addq.w	#1,d6
.lc:	cmp.w	-18(a6),d6
	bcs.s	.l
.top:	move.w	-4(a6),d0		; top: stream, y - 7 h, tile bit 12
	rol.w	#4,d0
	andi.w	#1,d0
	move.w	d0,-(a7)
	move.w	-18(a6),d0
	mulu.w	#7,d0
	move.w	-10(a6),d1
	sub.w	d0,d1
	move.w	d1,-(a7)
	move.w	-8(a6),-(a7)
	move.w	-2(a6),-(a7)
	bsr.w	ti_fast
	addq.w	#8,a7
	move.w	d5,d0		; figure grids: index FX + FY
	add.w	d0,d0
	lea	TL_FY(a6),a0
	move.w	(a0,d0.w),d1
	ext.l	d1
	move.l	TL_FX(a6),d0
	add.l	d1,d0
	move.l	d0,-28(a6)
	lea	($FFB36C).l,a0
	moveq	#0,d1
	move.b	(a0,d0.l),d1
	move.w	d1,-20(a6)		; rec1 (first grid)
	lea	($FFB76C).l,a0
	moveq	#0,d6
	move.b	(a0,d0.l),d6		; rec2 (second grid), drawn first
	move.w	d4,d1			; (both kept for the overlays, TI_WREC)
	mulu.w	#20,d1
	add.w	d5,d1
	add.w	d5,d1
	lea	TI_WREC,a0
	move.b	d6,(a0,d1.w)
	move.b	-19(a6),1(a0,d1.w)
	cmpi.w	#$FF,d6
	beq.s	.r1
	move.w	d6,d0
	bsr.w	ti_frec
.r1:	move.w	-20(a6),d0
	cmpi.w	#$FF,d0
	beq.s	.nx
	bsr.w	ti_frec
	cmpi.w	#1,d1			; kind 1 in the first grid, nothing in
	bne.s	.nx			; the second: the record moves there
	cmpi.w	#$FF,d6
	bne.s	.nx
	move.l	-28(a6),d0
	lea	($FFB36C).l,a0
	move.b	#$FF,(a0,d0.l)
	lea	($FFB76C).l,a0
	move.b	-19(a6),(a0,d0.l)
.nx:	addq.w	#1,d5
	cmpi.w	#10,d5
	blt.w	.cell
	addq.w	#1,d4
	move.w	d4,TD_IROW
	cmpi.w	#10,d4
	blt.w	.row
.x:	movem.l	(a7)+,d4-d7/a3-a4
	unlk	a6
	rts
.xr:	movea.l	GRIDPTR,a1		; per row: x' = x mod W, its chunk
	move.w	TD_IRX,d1		; column and offset; figure grid
	add.w	d4,d1			; 32 ((W + x + sx) mod W)
	subq.w	#5,d1
	move.w	d1,d2
	add.w	(a1),d1
.xm:	cmp.w	(a1),d1
	blt.s	.xd
	sub.w	(a1),d1
	bra.s	.xm
.xd:	andi.l	#$FFFF,d1
	divu.w	4(a1),d1
	move.w	d1,TL_XCH(a6)
	swap	d1
	add.w	d1,d1
	move.w	d1,TL_XIN(a6)
	add.w	(a1),d2
	add.w	-24(a6),d2
	ext.l	d2
	divs.w	(a1),d2
	swap	d2
	ext.l	d2
	asl.l	#5,d2
	move.l	d2,TL_FX(a6)
	rts

;=======================================================================
; Occlusion overlays (#278). A figure is a sprite above the iso plane,
; but in the game's painter order the cells drawn after it (x > Fx, or
; x = Fx and y > Fy) cover it where they paint. For a figure whose
; target cell has such a cell close by that rises above its feet
; (ti_oneed, from the last picture's words, TI_WIN), those cells are
; drawn alone with the game's $E358 into the cleared figure corner of
; the decode buffer, positioned as the picture has them relative to the
; figure's image, and the 4x4 tiles go to a figure-cache slot (key
; $4000 | cell). The overlay is a sprite at the figure's resting place,
; just in front of it (depth + 4, lift + 4: same pixels). Drawn in the
; main loop's spare time while no render owns the buffer (ti_obuild).
; Candidates: every later cell of the picture with |dx - dy| <= 2 whose
; top is not wholly below the box (dx, dy up to 9; a tall cell far south
; still rises into it). All of them, so the overlay holds exactly what
; the picture shows of later cells there.
;=======================================================================
ti_occl:	; td_chars: d7 = char, a4 = its slide (target cell), a2 = list
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; (no picture of ours to cut)
	beq.w	ti_rts
	endif
	movem.l	d0-d6/a0-a1,-(a7)
	cmpi.w	#TD_NFIG,TD_NB
	bcc.w	.out
	move.w	(a4),d4
	move.w	2(a4),d5
	move.w	d4,d6			; cell key: $8000 | (x & 63) << 6 | y & 63
	andi.w	#63,d6
	lsl.w	#6,d6
	move.w	d5,d0
	andi.w	#63,d0
	or.w	d0,d6
	ori.w	#$8000,d6
	lea	TD_OVK,a1
	adda.w	d7,a1
	adda.w	d7,a1
	move.w	(a1),d2
	move.w	d2,d0
	andi.w	#$BFFF,d0
	cmp.w	d6,d0
	beq.s	.known
	tst.w	TD_IRS			; decide on a finished picture only,
	bne.w	.out			; one figure per update
	tst.w	TD_VALID
	beq.w	.out
	tst.w	TD_OVDN
	bne.w	.out
	move.w	#1,TD_OVDN
	bsr.w	ti_oneed
	move.w	d6,d2
	tst.w	d0
	beq.s	.st
	ori.w	#$4000,d2
.st:	move.w	d2,(a1)
.known:	btst	#14,d2
	beq.w	.out
	move.w	d6,d0			; overlay key: + terrain phase (its
	andi.w	#$0FFF,d0		; water animates; both phases stay
	ori.w	#$4000,d0		; cached while standing)
	tst.w	TD_IPH
	beq.s	.k0
	ori.w	#$1000,d0
.k0:
	move.w	d0,d3
	move.w	TD_CANX,-(a7)		; cached? (lookup only)
	clr.w	TD_CANX
	bsr.w	td_img
	move.w	(a7)+,TD_CANX
	move.w	d0,-(a7)		; the figure's lift at rest, from its
	move.w	d4,d0			; cell in the picture (TD_CLK's may
	move.w	d5,d1			; still be the last cell's)
	bsr.w	ti_wword
	move.w	d0,-(a7)
	bsr.w	ti_olift
	move.w	(a7)+,d1		; + 7 as td_ilift; props bit 8 moves the
					; figure 4 px but not the ground it is
					; placed by (measured against the original)
	andi.w	#$1FF,d1
	add.w	d1,d1
	lea	DESC2,a0
	btst	#0,(a0,d1.w)
	beq.s	.n8
	subq.w	#4,d0
.n8:	addq.w	#7,d0
	move.w	d0,d1
	move.w	(a7)+,d0
	tst.w	d0
	bpl.s	.add
	tst.w	TD_OVPK			; not yet: ask the main loop
	bne.s	.out
	move.w	d4,TD_OVPX
	move.w	d5,TD_OVPY
	move.w	d1,TD_OVPL
	move.w	d3,TD_OVPK
	bra.s	.out
.add:	lsl.w	#4,d4
	addq.w	#4,d4
	move.w	d4,(a2)+		; resting place, depth + 4
	lsl.w	#4,d5
	addq.w	#4,d5
	move.w	d5,(a2)+
	move.w	d0,(a2)+
	addq.w	#4,d1			; lift + 4: the same pixels
	lsl.w	#8,d1
	addq.w	#2,d1			; kind 2: overlay, 32x32
	move.w	d1,(a2)+
	addq.w	#1,TD_NB
.out:	movem.l	(a7)+,d0-d6/a0-a1
	rts

ti_ohole:	; d2/d3 = sprite top-left on screen -> Z set if its 32x32 box
	; lies inside the hole: |x - CX| HH + |y - CY| HW <= HW HH
	movem.l	d0-d1/d4-d5,-(a7)
	moveq	#3,d5			; corners
.c:	move.w	d2,d0
	btst	#0,d5
	beq.s	.x
	add.w	#31,d0
.x:	move.w	d3,d1
	btst	#1,d5
	beq.s	.y
	add.w	#31,d1
.y:	sub.w	#TI_CX,d0
	bpl.s	.a
	neg.w	d0
.a:	mulu.w	#TI_HH,d0
	sub.w	#TI_CY,d1
	bpl.s	.b
	neg.w	d1
.b:	mulu.w	#TI_HW,d1
	add.l	d1,d0
	cmpi.l	#TI_HW*TI_HH,d0
	bhi.s	.no
	dbra	d5,.c
	cmp.w	d0,d0
	bra.s	.o
.no:	andi	#$FB,ccr
.o:	movem.l	(a7)+,d0-d1/d4-d5
	rts

ti_wword:	; d0 = cell x, d1 = y -> d0 = its word in the last picture,
	; d1 = row*20 + col*2; carry set outside the window
	sub.w	TD_IRX,d0
	addq.w	#5,d0
	cmpi.w	#10,d0
	bcc.s	.no
	sub.w	TD_IRY,d1
	addq.w	#5,d1
	cmpi.w	#10,d1
	bcc.s	.no
	mulu.w	#20,d0
	add.w	d1,d1
	add.w	d0,d1
	lea	TI_WIN,a0
	move.w	(a0,d1.w),d0		; (move clears carry)
	rts
.no:	ori	#1,ccr
	rts

ti_oneed:	; d4/d5 = figure cell -> d0 = 1 if a later cell close by
	; rises above its feet: lift - lift f > 8 (dx + dy - 1), lift =
	; 7 (h + props bit 7) + 4 props bit 8 (ti_olift)
	movem.l	d1-d3/d6-d7/a0,-(a7)
	move.w	d4,d0
	move.w	d5,d1
	bsr.s	ti_wword
	bcs.s	.no
	bsr.s	ti_olift
	move.w	d0,d3			; lift f
	moveq	#0,d6			; dx
.dx:	moveq	#-2,d7			; dy
.dy:	bsr.s	ti_ocand
	bne.s	.nx
	move.w	d4,d0
	add.w	d6,d0
	move.w	d5,d1
	add.w	d7,d1
	bsr.s	ti_wword
	bcs.s	.nx
	bsr.s	ti_olift
	sub.w	d3,d0
	ble.s	.nx
	move.w	d6,d2
	add.w	d7,d2
	subq.w	#1,d2
	asl.w	#3,d2
	cmp.w	d2,d0
	bgt.s	.yes
.nx:	addq.w	#1,d7
	cmpi.w	#10,d7
	blt.s	.dy
	addq.w	#1,d6
	cmpi.w	#10,d6
	blt.s	.dx
.no:	moveq	#0,d0
	bra.s	.out
.yes:	moveq	#1,d0
.out:	movem.l	(a7)+,d1-d3/d6-d7/a0
	rts

ti_olift:	; d0 = cell word -> d0 = its lift (uses d1, a0)
	move.w	d0,d1
	andi.w	#$1FF,d1
	add.w	d1,d1
	lea	DESC2,a0
	move.w	(a0,d1.w),d1		; props
	rol.w	#3,d0
	andi.w	#7,d0
	btst	#7,d1
	beq.s	.a
	addq.w	#1,d0
.a:	mulu.w	#7,d0
	btst	#8,d1
	beq.s	.b
	addq.w	#4,d0
.b:	rts

ti_ocand:	; d6 = dx, d7 = dy: Z set if a candidate (drawn later, close)
	tst.w	d6
	bne.s	.a
	tst.w	d7
	ble.s	.n			; same x: only y > Fy is later
.a:	move.w	d6,d0
	sub.w	d7,d0
	bpl.s	.b
	neg.w	d0
.b:	cmpi.w	#2,d0
	bgt.s	.n
	cmp.w	d0,d0
	rts
.n:	andi	#$FB,ccr
	rts

ti_obuild:	; main loop, spare time: draw the requested overlay
	tst.w	TD_OVPK
	beq.w	.r
	tst.w	TD_IRS			; the buffer belongs to a render
	bne.w	.r
	tst.w	TD_VALID
	beq.w	.r
	movem.l	d0-d7/a0-a6,-(a7)
	move.w	LOC,d0			; new location: drop old overlays
	cmp.w	TD_OLOC,d0
	beq.s	.lru
	move.w	d0,TD_OLOC
	lea	TD_FC,a0
	moveq	#TD_NFC-1,d1
.fl:	move.w	(a0),d0
	andi.w	#$C000,d0
	cmpi.w	#$4000,d0
	bne.s	.fn
	move.w	#$FFFF,(a0)
.fn:	addq.l	#4,a0
	dbra	d1,.fl
.lru:	lea	TD_FC,a0		; overlays in the cache: at most 4,
	move.w	TD_NFCV,d1		; so figures keep their slots
	subq.w	#1,d1
	moveq	#0,d5
.n:	move.w	(a0),d0
	andi.w	#$C000,d0
	cmpi.w	#$4000,d0
	bne.s	.n1
	addq.w	#1,d5
.n1:	addq.l	#4,a0
	dbra	d1,.n
	lea	TD_FC,a0		; least recently used slot (td_img),
	move.w	TD_NFCV,d1		; an overlay's if 4 are there
	subq.w	#1,d1
	moveq	#0,d3
	moveq	#-1,d2
	moveq	#0,d4
.l:	cmpi.w	#4,d5
	bcs.s	.l0
	move.w	(a0),d0
	andi.w	#$C000,d0
	cmpi.w	#$4000,d0
	bne.s	.l1
.l0:	cmp.w	2(a0),d2
	bls.s	.l1
	move.w	2(a0),d2
	move.w	d3,d4
.l1:	addq.l	#4,a0
	addq.w	#1,d3
	dbra	d1,.l
	move.w	d4,-(a7)		; slot
	moveq	#5-1,d1			; clear the corner (td_extract)
	lea	DECBUF+(2*36+16)*32,a0
.cr:	moveq	#32-1,d0
	movea.l	a0,a1
.cl:	clr.l	(a1)+
	dbra	d0,.cl
	lea	36*32(a0),a0
	dbra	d1,.cr
	moveq	#0,d6			; candidates in painter order
.dx:	moveq	#-2,d7
.dy:	bsr.w	ti_ocand
	bne.s	.nx
	bsr.s	ti_odraw
.nx:	addq.w	#1,d7
	cmpi.w	#10,d7
	blt.s	.dy
	addq.w	#1,d6
	cmpi.w	#10,d6
	blt.s	.dx
	move.w	(a7)+,d2		; upload, as td_extract (no VBlank
	move.w	sr,-(a7)		; VDP writes in between)
	ori.w	#$0700,sr
	move.w	d2,d0
	bsr.w	td_slot
	lsl.w	#5,d0
	bsr.w	td_vwrite
	lea	DECBUF+(2*36+16)*32,a0
	moveq	#4-1,d1
.cc:	movea.l	a0,a1
	moveq	#4-1,d3
.cr2:	moveq	#8-1,d4
	movea.l	a1,a3
.cw:	move.l	(a3)+,VDP_DATA
	dbra	d4,.cw
	lea	36*32(a1),a1
	dbra	d3,.cr2
	lea	32(a0),a0
	dbra	d1,.cc
	move.w	(a7)+,sr
	lsl.w	#2,d2
	lea	TD_FC,a0
	adda.w	d2,a0
	move.w	TD_OVPK,(a0)
	move.w	TD_STAMP,2(a0)
	clr.w	TD_OVPK
	movem.l	(a7)+,d0-d7/a0-a6
.r:	rts

ti_odraw:	; d6/d7 = dx/dy from TD_OVPX/Y: its stack and top as ti_loop
	; draws them, at x = 192 + 14 (dx - dy), y = 24 + 8 (dx + dy) +
	; lift - 7 k (the figure's image is at 192, 16)
	movem.l	d6-d7,-(a7)
	move.w	TD_OVPX,d0
	add.w	d6,d0
	move.w	TD_OVPY,d1
	add.w	d7,d1
	bsr.w	ti_wword
	bcs.w	.out
	move.w	d1,d5			; window offset row*20 + col*2
	movea.w	d1,a2
	move.w	d0,d4			; word
	move.w	d6,d0
	sub.w	d7,d0
	mulu.w	#14,d0
	add.w	#192,d0
	movea.w	d0,a5			; X
	move.w	d6,d0
	add.w	d7,d0
	asl.w	#3,d0
	add.w	TD_OVPL,d0
	add.w	#24,d0
	movea.w	d0,a6			; Y of layer 0
	move.w	d4,d2
	andi.w	#$1FF,d2
	move.w	d2,d0
	add.w	d0,d0
	lea	DESC2,a0
	move.w	(a0,d0.w),d3		; props
	tst.w	TD_IPH			; terrain phase of the picture
	beq.s	.ph
	btst	#9,d3
	beq.s	.p1
	addq.w	#1,d2
.p1:	btst	#6,d3
	beq.s	.ph
	subq.w	#1,d2
.ph:	movea.w	d2,a4			; stream
	move.w	d4,d6
	rol.w	#3,d6
	andi.w	#7,d6			; h
	move.w	d6,d0			; top wholly below the box: nothing
	mulu.w	#7,d0
	move.w	a6,d1
	sub.w	d0,d1
	cmpi.w	#48,d1			; (its records may still rise into it)
	bge.w	.recs
	tst.w	d6
	beq.w	.top
	move.w	d5,d0			; stack: window edge row / column, or
	cmpi.w	#9*20,d0		; tile bit 9 (as ti_loop)
	bcc.s	.stk
	andi.l	#$FFFF,d0
	divu.w	#20,d0
	swap	d0
	cmpi.w	#18,d0
	beq.s	.stk
	btst	#9,d4
	beq.w	.top
.stk:	btst	#5,d3
	bne.s	.own
	andi.w	#$1F,d3			; filler $22F + props & $1F
	add.w	#$22F,d3
	movea.w	d3,a3
	add.w	d3,d3
	lea	DESC2,a0
	move.w	(a0,d3.w),d1
	move.w	d1,d2
	andi.w	#$1F,d2
	move.w	d6,d7
	sub.w	d2,d7			; e
	moveq	#0,d5
	btst	#5,d1
	beq.s	.lp
	move.w	d4,d5
	rol.w	#4,d5
	andi.w	#1,d5
	bra.s	.lp
.own:	movea.w	a4,a3
	andi.w	#$1F,d3
	move.w	d6,d7
	sub.w	d3,d7
	move.w	d4,d5
	rol.w	#4,d5
	andi.w	#1,d5
.lp:	moveq	#0,d3			; layer k
	bra.s	.lc
.l:	move.w	d3,d0
	mulu.w	#7,d0
	move.w	a6,d2
	sub.w	d0,d2			; y
	move.w	a5,d1			; x
	move.w	a3,d0
	movea.w	d5,a0
	cmp.w	d7,d3
	bge.s	.cf
	move.w	#$230,d0		; below the top layers: filler $230
	suba.l	a0,a0
.cf:	bsr.w	ti_e3
	addq.w	#1,d3
.lc:	cmp.w	d6,d3
	bcs.s	.l
.top:	move.w	d6,d0			; top: stream, y - 7 h, tile bit 12
	mulu.w	#7,d0
	move.w	a6,d2
	sub.w	d0,d2
	move.w	a5,d1
	rol.w	#4,d4
	andi.w	#1,d4
	movea.w	d4,a0
	move.w	a4,d0
	bsr.w	ti_e3
.recs:	move.w	TD_OVPX,d0		; its records (kinds 2 / 3: buildings,
	add.w	2(a7),d0		; objects), as ti_frec: L = -lift
	move.w	TD_OVPY,d1
	add.w	6(a7),d1
	bsr.w	ti_wword
	bsr.w	ti_olift
	neg.w	d0
	move.w	d0,d3
	lea	TI_WREC,a0
	moveq	#0,d0
	move.b	(a0,a2.w),d0		; second grid first
	bsr.s	ti_orec
	moveq	#0,d0
	move.b	1(a0,a2.w),d0
	bsr.s	ti_orec
.out:	movem.l	(a7)+,d6-d7
	rts

ti_orec:	; d0 = record ($FF none), a5 = X, a6 = Y, d3 = L; all kept
	cmpi.w	#$FF,d0
	beq.s	.r
	movem.l	d0-d7/a0-a6,-(a7)
	mulu.w	#12,d0
	add.l	#$FFB0CC,d0
	movea.l	d0,a0
	move.w	10(a0),d1
	cmpi.w	#2,d1
	beq.s	.k
	cmpi.w	#3,d1
	bne.s	.o
.k:	move.w	d1,-(a7)
	move.w	d3,-(a7)
	move.w	a6,-(a7)
	move.w	a5,-(a7)
	move.l	a0,-(a7)
	cmpi.w	#2,d1
	bne.s	.an
	jsr	($0232AC).l		; map_tile_at_offset
	bra.s	.p
.an:	jsr	($0232D2).l		; map_animated_tile
.p:	lea	12(a7),a7
.o:	movem.l	(a7)+,d0-d7/a0-a6
.r:	rts

ti_e3:	; $E358(stream d0, x d1, y d2, flag a0), all registers kept (the
	; game's code keeps only d4-d7/a3-a4 that it uses)
	movem.l	d0-d7/a0-a6,-(a7)
	move.w	a0,-(a7)
	move.w	d2,-(a7)
	move.w	d1,-(a7)
	move.w	d0,-(a7)
	jsr	($00E358).l
	addq.w	#8,a7
	movem.l	(a7)+,d0-d7/a0-a6
	rts

ti_frec:	; d0 = record number, a6 = ti_loop's frame -> d1 = its kind;
	; kinds 2 / 3 drawn (map_tile_at_offset / map_animated_tile)
	mulu.w	#12,d0
	add.l	#$FFB0CC,d0
	movea.l	d0,a0
	move.w	10(a0),d1
	cmpi.w	#2,d1
	beq.s	.k
	cmpi.w	#3,d1
	bne.s	.o
.k:	move.w	d1,-(a7)
	move.w	-12(a6),-(a7)		; (record, x, y, L) as the game
	move.w	-10(a6),-(a7)
	move.w	-8(a6),-(a7)
	move.l	a0,-(a7)
	cmpi.w	#2,d1
	bne.s	.an
	jsr	($0232AC).l		; map_tile_at_offset
	bra.s	.p
.an:	jsr	($0232D2).l		; map_animated_tile
.p:	lea	10(a7),a7
	move.w	(a7)+,d1
.o:	rts

	ifd	VERIFY283
ti_vsum:	; -> d0 = sum of the decode buffer's longs; per 8-line row
	; sums to (a1) (23 longs)
	movem.l	d2-d3,-(a7)
	lea	DECBUF,a0
	moveq	#0,d0
	moveq	#23-1,d3
.r:	moveq	#0,d2
	move.w	#8*144/4-1,d1
.s:	add.l	(a0)+,d2
	rol.l	#1,d2
	dbra	d1,.s
	move.l	d2,(a1)+
	add.l	d2,d0
	rol.l	#3,d0
	dbra	d3,.r
	movem.l	(a7)+,d2-d3
	rts
ti_vdif:	; rows whose sums differ (map_chunk_pos's just written after
	; ours: sums again) -> TD_VDIF mask, TD_VDIF+4/6 = IRX/IRY
	movem.l	d2-d3,-(a7)
	lea	DECBUF,a0
	lea	TD_VROW,a1
	moveq	#0,d3
	moveq	#0,d1
.r:	moveq	#0,d2
	move.w	#8*144/4-1,d0
.s:	add.l	(a0)+,d2
	rol.l	#1,d2
	dbra	d0,.s
	cmp.l	(a1)+,d2
	beq.s	.e
	bset	d1,d3
.e:	addq.w	#1,d1
	cmpi.w	#23,d1
	bcs.s	.r
	move.l	d3,TD_VDIF
	move.w	TD_IRX,TD_VDIF+4
	move.w	TD_IRY,TD_VDIF+6
	movem.l	(a7)+,d2-d3
	rts
	endif
	endif

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
	ifd	NOLIMIT			; (debug: CPU per picture)
	bra.s	.no
	endif
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
	movem.l	d2-d6/a2-a3,-(a7)
	ifd	SIZE2M
	bsr.w	ti_artchk
	endif
	move.w	#1,TD_INWF
	moveq	#0,d6			; row
.row:	tst.w	TD_UNFR
	bne.s	.r0
	bsr.w	td_poll_vb
.r0:	bsr.w	ta_barrow
	beq.s	.nr
	move.w	d6,d0
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
	bsr.w	ti_erow			; the row's frame words (TD_EROW)
	lea	TD_WROW,a2
	lea	TD_EROW,a3
	moveq	#0,d4
.col:	move.w	(a2)+,d0		; as it should be: next (most cells,
	move.w	(a3)+,d3		; one compare; per-cell table walks
	cmp.w	d3,d0			; made the scan 6-9 frames, #289)
	beq.s	.nx
	bsr.s	ti_blankish
	bne.s	.nx
	move.w	d4,d0
	add.w	d0,d0
	add.w	d5,d0
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	bsr.w	td_vwrite
	move.w	d3,VDP_DATA
	move.w	(a7)+,sr
.nx:	addq.w	#1,d4
	cmpi.w	#40,d4
	bcs.s	.col
.nr:	addq.w	#1,d6
	cmpi.w	#28,d6
	bcs.s	.row
	clr.w	TD_INWF
	movem.l	(a7)+,d2-d6/a2-a3
	rts
ti_wend:

ti_blankish:	; d0 = window word -> Z set if it is ours to (re)write
	movem.l	d0-d1,-(a7)
	move.w	d0,d1
	sub.w	FONTBLK,d1
	andi.w	#$7FF,d1
	beq.w	.y
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn: nothing of the game's own
	bne.s	.nt			; picture stays in the window, only
	move.w	d0,d1			; text (the font) and the portrait
	andi.w	#$7FF,d1		; (874-909)
	sub.w	FONTBLK,d1
	cmpi.w	#100,d1
	bcs.s	.kn
	move.w	d0,d1
	andi.w	#$7FF,d1
	sub.w	#874,d1
	cmpi.w	#36,d1
	bcs.s	.kn
	bra.w	.y
.kn:	moveq	#1,d1			; (keep)
	movem.l	(a7)+,d0-d1
	rts
.nt:
	endif
	move.w	d0,d1
	andi.w	#$F800,d1
	beq.w	.room
	ifd	SIZE2M
	cmpi.w	#$2000,d1		; frame art: palette 1, rec 6's tiles
	bcs.s	.na			; (any flips)
	cmpi.w	#$3800,d1
	bhi.s	.na
	move.w	d0,d1
	andi.w	#$7FF,d1
	sub.w	#TI_ARTB&$7FF,d1
	cmpi.w	#438,d1
	bcs.w	.y
.na:	move.w	d0,d1
	andi.w	#$F800,d1
	endif
	cmpi.w	#$2000,d1		; palette 1, no flags: a frame word?
	bne.s	.n
	andi.w	#$7FF,d0
	sub.w	TD_BASE,d0
	cmpi.w	#256,d0
	beq.w	.y
	sub.w	#TI_EDGE,d0
	cmpi.w	#TI_NEDGE,d0
	bcs.w	.y
	bra.s	.n
.room:
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON		; pre-drawn: a word on one of our
	bne.s	.rm			; slot tiles is the game's picture
	andi.w	#$7FF,d0		; (shows our tiles, not its own); on
	beq.w	.y			; tile 0 too (our plane table there)
	cmpi.w	#436,d0
	bcs.s	.rb
	cmpi.w	#874,d0
	bcs.w	.y
	cmpi.w	#1834,d0
	bcs.s	.rb
	cmpi.w	#1974,d0
	bcs.w	.y
.rb:	sub.w	TD_BASE,d0
	cmpi.w	#64,d0
	bcs.s	.rm0
	cmpi.w	#273,d0
	bcs.w	.y
	cmpi.w	#401,d0
	bcs.s	.rm0
	cmpi.w	#828,d0
	bcs.w	.y
.rm0:	move.l	(a7),d0
.rm:
	endif
	sub.w	BANKBASE,d0
	cmpi.w	#828,d0
	bcs.w	.y
.n:	moveq	#1,d1
	bra.s	.o
.y:	moveq	#0,d1
.o:	movem.l	(a7)+,d0-d1
	rts

ti_erow:	; d6 = window row -> TD_EROW = its 40 frame words (ti_frameword's
	; for every column; all transparent while the frame comes off)
	movem.l	d1-d3/a0-a1,-(a7)
	lea	TD_EROW,a1
	move.w	TD_BASE,d0		; parchment
	add.w	#256+$2000,d0
	tst.w	TD_UNFR
	beq.s	.f
	move.w	FONTBLK,d0
.f:	moveq	#40-1,d1
.p:	move.w	d0,(a1)+
	dbra	d1,.p
	tst.w	TD_UNFR
	bne.w	.o
	lea	-80(a1),a1
	ifd	SIZE2M
	tst.w	TD_ARTOK		; the original's frame art (rec 9)
	beq.s	.na			; where it is not its transparent land
	move.w	d6,d0
	mulu.w	#80,d0
	lea	ti_art(pc),a0
	adda.w	d0,a0
	moveq	#40-1,d1
.a:	move.w	(a0)+,d0
	move.w	d0,d2
	andi.w	#$7FF,d2
	cmpi.w	#TI_ARTT,d2
	beq.s	.a1
	add.w	#TI_ARTB,d0
	move.w	d0,(a1)
.a1:	addq.w	#2,a1
	dbra	d1,.a
	lea	-80(a1),a1
.na:
	endif
	lea	ti_rows(pc),a0		; the hole's fully inside columns
	move.w	d6,d0
	add.w	d0,d0
	moveq	#0,d1
	move.b	(a0,d0.w),d1
	moveq	#0,d2
	move.b	1(a0,d0.w),d2
	move.w	FONTBLK,d3
	bra.s	.hc
.h:	move.w	d1,d0
	add.w	d0,d0
	move.w	d3,(a1,d0.w)
	addq.w	#1,d1
.hc:	cmp.w	d2,d1
	bls.s	.h
	lea	ti_eoff(pc),a0		; its edge cells
	moveq	#0,d1
	move.b	(a0,d6.w),d1
	moveq	#0,d2
	move.b	1(a0,d6.w),d2
	sub.w	d1,d2
	lea	ti_ecel(pc),a0
	add.w	d1,d1
	adda.w	d1,a0
	move.w	TD_BASE,d3
	add.w	#TI_EDGE+$2000,d3
	bra.s	.ec
.e:	moveq	#0,d0
	move.b	(a0)+,d0
	moveq	#0,d1
	move.b	(a0)+,d1
	add.w	d3,d1
	add.w	d0,d0
	move.w	d1,(a1,d0.w)
.ec:	dbra	d2,.e
.o:	movem.l	(a7)+,d1-d3/a0-a1
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
	ifd	SIZE2M
	tst.w	TD_ARTOK		; outside: the original's frame art
	beq.s	.pp			; (rec 9), its transparent land as
	move.w	d2,d0			; parchment (#306)
	mulu.w	#80,d0
	add.w	d1,d0
	add.w	d1,d0
	lea	ti_art(pc),a0
	move.w	(a0,d0.w),d0
	move.w	d0,d3
	andi.w	#$7FF,d3
	cmpi.w	#TI_ARTT,d3
	beq.s	.pp
	add.w	#TI_ARTB,d0
	bra.s	.o
.pp:
	endif
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

	ifd	SIZE2M
ti_artchk:	; TD_ARTOK = rec 6's signature tile is in VRAM (rec 9's art
	movem.l	d0-d1/a0,-(a7)		; can be shown around the hole)
	move.w	#TI_ARTS*32,d0
	bsr.w	td_vcmd
	lea	ti_artsig(pc),a0
	clr.w	TD_ARTOK
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.l	d0,VDP_CTRL
	move.l	VDP_DATA,d0
	move.l	VDP_DATA,d1
	move.w	(a7)+,sr
	cmp.l	(a0)+,d0
	bne.s	.o
	cmp.l	(a0),d1
	bne.s	.o
	move.w	#1,TD_ARTOK
.o:	movem.l	(a7)+,d0-d1/a0
	rts
; ti_art data (tools/td_iso_art.py)
TI_ARTB		equ $2000+436	; rec 6's VRAM base, palette 1
TI_ARTT		equ 131		; parchment here (a tile with transparent pixels)
TI_ARTS		equ 436+31	; signature tile
ti_artsig:	; its first 8 bytes
	dc.b	$4E, $EE, $4E, $EE, $EE, $EE, $EE, $EE
ti_art:	; rec 9, 28 rows x 40 columns
	dc.w	$0000,$0001,$0002,$0003,$0004,$0005,$0006,$0007,$0008,$0009
	dc.w	$000A,$000B,$000C,$000D,$000E,$000F,$0010,$0011,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0013,$0014,$0015,$0016,$0017
	dc.w	$0018,$0019,$001A,$001B,$001C,$001D,$001E,$001F,$001F,$0800
	dc.w	$001C,$001D,$001E,$0020,$0021,$0022,$0023,$0024,$0025,$0026
	dc.w	$0027,$0028,$0029,$002A,$002B,$002C,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$002D,$002E,$002F
	dc.w	$0030,$0031,$0032,$0033,$0034,$0035,$0036,$001F,$0037,$0038
	dc.w	$0039,$003A,$003B,$001F,$0037,$0038,$003C,$003D,$003E,$003F
	dc.w	$0040,$0041,$0042,$0043,$0012,$0012,$0012,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0012,$0012,$0012,$0012,$0012,$0047,$0048
	dc.w	$0049,$004A,$004B,$004C,$004D,$004E,$004F,$0050,$0051,$0037
	dc.w	$0052,$0053,$0054,$0055,$0056,$0057,$0058,$0059,$005A,$005B
	dc.w	$005C,$005D,$005E,$0012,$0012,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0067,$0068,$0069,$0012,$0012
	dc.w	$006A,$006B,$006C,$006D,$006E,$006F,$0070,$0071,$0072,$0073
	dc.w	$0074,$0075,$0076,$0077,$0078,$0079,$007A,$007B,$007C,$007D
	dc.w	$007E,$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0089,$0012,$0012
	dc.w	$0012,$008A,$008B,$008C,$008D,$008E,$008F,$0090,$0091,$0092
	dc.w	$0093,$0094,$0095,$0096,$0097,$0098,$0099,$009A,$009B,$009C
	dc.w	$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0012,$00A6,$00A7,$00A8,$00A9,$00AA,$00AB,$00AC,$00AD
	dc.w	$00AE,$00AF,$00B0,$00B1,$00B2,$00B3,$00B4,$00B5,$00B6,$00B7
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0012,$0012,$00BD,$00BE,$00BF,$00C0,$00C1,$00C2,$00C3,$00C4
	dc.w	$00C5,$00C6,$00C7,$00C8,$00C9,$088A,$0012,$0012,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$00D0,$00D1,$00D2,$00D3,$00D4,$00D5,$00D6,$00D7
	dc.w	$00D8,$00D9,$00DA,$00DB,$0012,$0012,$0012,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$00E1,$00E2,$0012,$0012,$00E3,$00E4
	dc.w	$00E5,$00E6,$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0012,$0012,$0012,$0012
	dc.w	$005E,$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012,$0012,$0012
	dc.w	$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0120,$18E3,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0126,$0127,$0128,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0083,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$185E
	dc.w	$0130,$0131,$0132,$0133,$0134,$0012,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$0083,$0083,$0139,$013A,$013B,$013C,$013D
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$013E,$013F
	dc.w	$0140,$0141,$0142,$0143,$0144,$0145,$0146,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0083,$0083,$0083,$0083,$0083
	dc.w	$0083,$0083,$0083,$014B,$014C,$014D,$014E,$014F,$0150,$088A
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0151,$0152
	dc.w	$0153,$0154,$0155,$0156,$0157,$0158,$0159,$015A,$188A,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0083,$0083,$0083
	dc.w	$0083,$015E,$015F,$0160,$0161,$0162,$0163,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0164,$0165
	dc.w	$0166,$0167,$0168,$0169,$016A,$016B,$016C,$016D,$016E,$016F
	dc.w	$0012,$188A,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0012,$0170,$0171,$0172,$0173,$0012,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0174,$0175
	dc.w	$001C,$001D,$0176,$0177,$0178,$0179,$017A,$017B,$017C,$017D
	dc.w	$017E,$017F,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0180,$0181,$0182,$0183,$0184,$0185,$0012,$0012,$0012,$0012
	dc.w	$0012,$0186,$0012,$0012,$0012,$0012,$0012,$0012,$0187,$0188
	dc.w	$0039,$003A,$003B,$001F,$0189,$018A,$018B,$018C,$018D,$018E
	dc.w	$018F,$0190,$0191,$0192,$0012,$0012,$0012,$0012,$0012,$0012
	dc.w	$0193,$0194,$0012,$0012,$0012,$0012,$0012,$0012,$0012,$0195
	dc.w	$0196,$0197,$0198,$0199,$019A,$019B,$019C,$019D,$019E,$019F
	dc.w	$1000,$0053,$003A,$003B,$001F,$01A0,$01A1,$01A2,$01A3,$01A4
	dc.w	$01A5,$01A6,$01A7,$01A8,$01A9,$188A,$0012,$0012,$0012,$0012
	dc.w	$0012,$0012,$0012,$0012,$0012,$0012,$0012,$1811,$01AA,$01AB
	dc.w	$01AC,$01AD,$01AE,$01AF,$01B0,$01B1,$01B2,$01B3,$01B4,$01B5
; ti_art data end
	endif

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

;=======================================================================
; ta_sprw — sprite_write's y word ($011BF6, with its push and pop): in
; the pre-drawn overworld a sprite showing records 16-17 (pad picture,
; gauges) goes off screen, their tiles hold terrain there (#307).
;=======================================================================
;=======================================================================
; ta_dbuf — tile_record_load ($011AE8) and map_decode ($013840): the game
; decodes into DECBUF, where the pre-drawn view keeps its slot tables
; (a portrait with a message does it). Its `pea DECBUF`, and the tables
; are built again on the next frame.
;=======================================================================
ta_dbuf:				; tile_record_load: 36 tiles (1.2 KB)
	tst.w	TA_LOST			; reach the hash heads only
	bne.s	ta_dbuf0
	move.w	#1,TA_LOST
	bra.s	ta_dbuf0
ta_dbuf2:				; map_decode: a text record (small:
	bra.s	ta_dbuf			; the heads too)
ta_dbuf0:
	movea.l	(a7)+,a0
	pea	($FF1EC0).l
	jmp	(a0)

;=======================================================================
; ta_gread — the game's VRAM word read ($01111E): command and read with
; interrupts masked, so a VBlank picture update between them can not
; leave the port in write mode (BlastEm freezes the CPU on that read).
;=======================================================================
ta_gread:
	move.w	sr,-(a7)
	ori.w	#$0700,sr
	move.w	d0,VDP_CTRL
	move.w	#$20,VDP_CTRL
	moveq	#0,d0
	move.w	VDP_DATA,d0
	move.w	(a7)+,sr
	unlk	a6
	rts

ta_sprw:
	move.w	$C(a6),d0
	ifd	SIZE8M
	cmpi.w	#$5A71,TA_ON
	bne.s	.w
	move.w	$14(a6),d1
	andi.w	#$7FF,d1
	cmpi.w	#1834,d1
	bcs.s	.w
	cmpi.w	#2038,d1
	bcc.s	.w
	moveq	#0,d0
	endif
.w:	move.w	d0,VDP_DATA
	rts

;=======================================================================
; ta_ctl — the leader controller (pre-drawn view, outside menus and
; combat; once per frame from td_iframe). The figure leaves the game's
; cell as soon as a direction is held, at the walking pace (a cell per
; tick period), facing that way at once; at half a cell the step goes
; to the game (its pad pop gets the direction, its tick starts now); a
; refused step, or a release before half way, slides back; a release
; past half way finishes the step. A tap turns and nudges.
;=======================================================================
	ifd	SIZE8M
ta_ctl:
	cmpi.w	#$5A71,TA_ON
	bne.w	.off
	tst.w	$FF00AC			; a menu
	bne.w	.off
	cmpi.l	#$FFB0BC,GRIDPTR	; combat
	beq.w	.off
	move.w	FRAME,d0
	cmp.w	TA_CFR,d0
	beq.w	.o
	move.w	d0,TA_CFR
	movem.l	d2-d6/a0,-(a7)
	bsr.w	ta_who
	cmp.w	TA_WHO,d0		; another figure (a room): start over
	beq.s	.ws			; on its cell
	move.w	d0,TA_WHO
	clr.w	TA_CTL
.ws:	mulu.w	#$34,d0
	lea	CHARS,a0
	adda.l	d0,a0
	move.w	$C(a0),d2		; the game's cell
	move.w	$E(a0),d3
	tst.w	TA_CTL
	bne.s	.on
	move.w	d2,TA_G0X		; switching on: on the cell
	move.w	d3,TA_G0Y
	clr.w	TA_OX
	clr.w	TA_OY
	clr.w	TA_CMT
	clr.w	TA_CF
	clr.w	TA_BLK
	move.w	#-1,TA_LH
	move.w	#1,TA_CTL
.on:	move.w	d2,d0			; the cell changed: the offset follows
	sub.w	TA_G0X,d0
	move.w	d3,d1
	sub.w	TA_G0Y,d1
	move.w	d2,TA_G0X
	move.w	d3,TA_G0Y
	move.w	d0,d4
	or.w	d1,d4
	beq.s	.same
	clr.w	TA_CF			; a step (not refused)
	clr.w	TA_BLK
	move.w	d0,d4			; more than a cell: a jump
	bpl.s	.a1
	neg.w	d4
.a1:	cmpi.w	#1,d4
	bhi.s	.jump
	move.w	d1,d4
	bpl.s	.a2
	neg.w	d4
.a2:	cmpi.w	#1,d4
	bhi.s	.jump
	lsl.w	#8,d0
	sub.w	d0,TA_OX
	lsl.w	#8,d1
	sub.w	d1,TA_OY
	bra.s	.same
.jump:	clr.w	TA_OX
	clr.w	TA_OY
.same:	move.w	TA_CF,d0		; handed out > 3 frames ago, no step:
	beq.s	.nb			; refused
	move.w	FRAME,d1
	sub.w	d0,d1
	cmpi.w	#3,d1
	bcs.s	.nb
	clr.w	TA_CF
	move.w	#1,TA_BLK
.nb:	moveq	#0,d5			; the direction held now
	move.b	$FF0018,d5
	andi.w	#$F,d5
	bsr.w	ta_hdir			; -> d4 = 0-3 or -1
	tst.w	d4
	bmi.s	.rl
	move.w	d5,TA_LP
	cmp.w	TA_FACE,d4		; a new facing: the turn shows at once,
	beq.s	.hd			; the step if still held TA_TURN frames
	move.w	FRAME,TA_TRN		; on (its walk images get drawn)
	bra.s	.hd
.rl:	tst.w	TA_BLK			; released: a step under way goes on
	bne.s	.hd			; to the next cell, never back
	move.w	TA_FACE,d0
	add.w	d0,d0
	add.w	d0,d0
	lea	ta_dxy(pc),a0
	move.w	TA_OX,d1
	muls.w	(a0,d0.w),d1
	move.w	TA_OY,d2
	muls.w	2(a0,d0.w),d2
	add.l	d2,d1
	ble.s	.hd
	move.w	TA_FACE,d4
	move.w	TA_LP,d5
.hd:	tst.w	d4
	bmi.s	.nh
	move.w	d4,TA_FACE		; facing: at once (the game's draw
	move.w	TA_WHO,d0		; record too, so it stays when the
	mulu.w	#$34,d0			; controller pauses)
	lea	CHARS,a0
	adda.l	d0,a0
	move.w	4(a0),d0
	cmpi.w	#56,d0
	bcc.s	.nr
	mulu.w	#12,d0
	lea	RECS,a0
	move.w	d4,2(a0,d0.w)
.nr:	cmp.w	TA_LH,d4
	beq.s	.nh
	clr.w	TA_BLK			; another direction: try again
.nh:	move.w	d4,TA_LH
	moveq	#0,d2			; target offset: a cell that way, or 0
	moveq	#0,d3
	tst.w	TA_CMT			; a step handed out goes on whatever
	bne.s	.pd			; the pad does now (no turn back)
	tst.w	TA_CF
	beq.s	.np
.pd:	move.w	TA_CDIR,d4
	bra.s	.go
.np:	tst.w	d4
	bmi.s	.t
	tst.w	TA_BLK
	bne.s	.t
	move.w	FRAME,d0		; turning: not yet
	sub.w	TA_TRN,d0
	cmpi.w	#TA_TURN,d0
	bcs.s	.t
.go:	move.w	d4,d0
	add.w	d0,d0
	add.w	d0,d0
	lea	ta_dxy(pc),a0
	move.w	(a0,d0.w),d2
	move.w	2(a0,d0.w),d3
	lsl.w	#8,d2
	lsl.w	#8,d3
	tst.w	TA_CMT			; handed to the game, not taken yet:
	bne.s	.hw			; no further than TA_CAP (from rest
	tst.w	TA_CF			; 1/4: a step it refuses is a nudge;
					; walking on 1/2: the game is busy)
	beq.s	.t
.hw:	muls.w	TA_CAP,d2		; (past it already: stay there)
	asr.l	#8,d2
	muls.w	TA_CAP,d3
	asr.l	#8,d3
	move.w	TA_OX,d0
	muls.w	d2,d0
	move.w	TA_OY,d1
	muls.w	d3,d1
	add.l	d1,d0
	move.w	TA_CAP,d1
	mulu.w	d1,d1
	cmp.l	d1,d0
	blt.s	.t
	move.w	TA_OX,d2
	move.w	TA_OY,d3
.t:	move.w	TA_OX,TA_POX		; (where he was: the way he moves)
	move.w	TA_OY,TA_POY
	move.w	#256,d6			; speed: a cell per tick period
	ext.l	d6
	move.w	TD_RPER,d0		; (or per tick when the game's ticks
					; run longer)
	cmp.w	TD_PERIOD,d0
	bls.s	.sp
	divu.w	d0,d6
	bra.s	.sp1
.sp:	divu.w	TD_PERIOD,d6
	addq.w	#1,d6
.sp1:
	clr.w	TA_MOV
	tst.w	d2			; moving along x: y back to 0 first
	beq.s	.ny
	tst.w	TA_OY
	beq.s	.ny
	moveq	#0,d0
	lea	TA_OY,a0
	bsr.w	ta_toward
	bra.s	.cm
.ny:	tst.w	d3			; along y: x back to 0 first
	beq.s	.both
	tst.w	TA_OX
	beq.s	.both
	moveq	#0,d0
	lea	TA_OX,a0
	bsr.w	ta_toward
	bra.s	.cm
.both:	move.w	d2,d0
	lea	TA_OX,a0
	bsr.w	ta_toward
	move.w	d3,d0
	lea	TA_OY,a0
	bsr.w	ta_toward
.cm:	move.w	TA_FACE,d0		; the facing drawn: his motion's
	tst.w	TA_BLK			; (back from a refused step: facing)
	bne.s	.vt
	move.w	TA_OX,d1
	sub.w	TA_POX,d1
	beq.s	.vy
	moveq	#1,d0
	tst.w	d1
	bpl.s	.vf
	moveq	#3,d0
	bra.s	.vf
.vy:	move.w	TA_OY,d1
	sub.w	TA_POY,d1
	beq.s	.vf
	moveq	#2,d0
	tst.w	d1
	bpl.s	.vf
	moveq	#0,d0
.vf:	cmp.w	TA_DFACE,d0		; (a lone frame sideways, as a step
	beq.s	.vk			; is put right, keeps the facing)
	cmp.w	TA_DCAND,d0
	beq.s	.vt
	move.w	d0,TA_DCAND
	tst.w	TA_MOV			; (standing: at once)
	bne.s	.vk
.vt:	move.w	d0,TA_DFACE
.vk:	move.w	TA_DFACE,d0
	tst.w	TA_MOV
	bne.s	.mv
	move.w	FRAME,TA_LMF
.mv:
	tst.w	d4			; the step to the game
	bmi.s	.x
	tst.w	TA_BLK
	bne.s	.x
	tst.w	TA_CMT
	bne.s	.x
	tst.w	TA_CF
	bne.s	.x
	move.w	d4,d0			; progress = offset . direction
	add.w	d0,d0
	add.w	d0,d0
	lea	ta_dxy(pc),a0
	move.w	TA_OX,d1
	muls.w	(a0,d0.w),d1
	move.w	TA_OY,d2
	muls.w	2(a0,d0.w),d2
	add.l	d2,d1
	cmpi.l	#TA_CMTP,d1		; (at once: its answer comes before he
	blt.s	.x			; is far, so a wall stops him short)
	move.w	#96,TA_CAP
	move.w	FRAME,d0
	sub.w	TA_LMF,d0
	cmpi.w	#4,d0
	bls.s	.cp
	move.w	#192,TA_CAP
.cp:	move.w	d4,TA_CDIR
	move.w	d5,TA_CMT
	move.w	FRAME,d0		; and the game's tick now
	sub.w	TD_PERIOD,d0
	move.w	d0,TD_TICKFR
.x:	movem.l	(a7)+,d2-d6/a0
.o:	rts
.off:	clr.w	TA_CTL
	clr.w	TA_MOV
	rts

ta_toward:	; (a0) toward d0 by at most d6; TA_WPH, TA_MOV count it
	move.w	d0,d1
	sub.w	(a0),d1
	beq.s	.o
	bpl.s	.p
	neg.w	d1
	cmp.w	d6,d1
	bls.s	.n
	move.w	d6,d1
.n:	sub.w	d1,(a0)
	bra.s	.c
.p:	cmp.w	d6,d1
	bls.s	.q
	move.w	d6,d1
.q:	add.w	d1,(a0)
.c:	add.w	d1,TA_WPH
	move.w	#1,TA_MOV
.o:	rts

ta_dxy:	dc.w	0,-1, 1,0, 0,1, -1,0

;=======================================================================
; ta_ovl — td_chars: the overlay (ta_occ) as a list entry, kind 3: a
; 32x32 sprite of the terrain painted after the leader's cell, sorted
; just in front of him (depth + 4).
;=======================================================================
ta_ovl:
	tst.w	TA_OVOK
	beq.s	.o
	tst.w	TD_LEADOK
	beq.s	.o
	cmpi.w	#TD_NFIG,TD_NB
	bcc.s	.o
	movem.l	d0-d1/a0,-(a7)
	move.w	TD_NB,d0
	lsl.w	#3,d0
	lea	TD_LIST,a0
	adda.w	d0,a0
	move.w	TA_OVX,(a0)+		; global x
	move.w	TD_LEADX,d0		; depth y: the leader's + 4
	add.w	TD_LEADY,d0
	asr.w	#1,d0
	addq.w	#4,d0
	move.w	d0,(a0)+
	move.w	#TA_OVT,(a0)+
	subq.w	#8,d0			; "lift": top = depth - 8 - lift
	sub.w	TA_OVY,d0
	cmpi.w	#255,d0
	bhi.s	.x
	lsl.w	#8,d0
	addq.w	#3,d0
	move.w	d0,(a0)+
	addq.w	#1,TD_NB
.x:	movem.l	(a7)+,d0-d1/a0
.o:	rts

;=======================================================================
; ta_occ — main loop: the 4x4 plane tiles over the leader's figure, cut
; to what is painted after his cell (the game's order: deeper cells
; later). Per tile: its cell depth smin and the next one up (depth
; byte), and the pixels at that next depth (the tile's mask): wholly
; in front if S < smin, those pixels if smin <= S < sup. Redone when
; the tiles, his cell, the water phase or the area change.
;=======================================================================
ta_occ:
	tst.w	TA_CTL
	beq.w	.off
	tst.w	TD_LEADOK
	beq.w	.off
	movem.l	d2-d7/a2-a4,-(a7)
	move.w	TD_LEADX,d0
	move.w	TD_LEADY,d1
	move.w	d0,d2			; c0 = (left + 4) / 8
	sub.w	d1,d2
	muls.w	#7,d2
	asr.l	#3,d2
	addq.w	#4,d2
	asr.w	#3,d2
	add.w	d1,d0			; r0 = (top - 2) / 8 (rows from y 6)
	asr.w	#1,d0
	sub.w	TA_BLIFT,d0
	sub.w	#10,d0
	asr.w	#3,d0
	move.w	d0,d3
	move.w	TD_LEADX,d4		; S: his nearest cell's depth
	addq.w	#8,d4
	asr.w	#4,d4
	move.w	TD_LEADY,d0
	addq.w	#8,d0
	asr.w	#4,d0
	add.w	d0,d4
	lea	TA_OVK,a2
	cmp.w	(a2),d2
	bne.s	.new
	cmp.w	2(a2),d3
	bne.s	.new
	cmp.w	4(a2),d4
	bne.s	.new
	move.w	TA_PH,d0
	cmp.w	6(a2),d0
	bne.s	.new
	move.w	TA_AR,d0
	cmp.w	8(a2),d0
	beq.w	.same
.new:	clr.w	TA_OVOK			; (off while its tiles change: never
	move.w	d2,(a2)			; new place, old pixels)
	move.w	d3,2(a2)
	move.w	d4,4(a2)
	move.w	TA_PH,6(a2)
	move.w	TA_AR,8(a2)
	move.w	d4,d7			; S
	lea	OVBUF,a3
	moveq	#0,d6			; anything in front
	moveq	#0,d3			; i (column)
.ci:	moveq	#0,d2			; j (row)
.rj:	move.w	TA_OVK,d4
	add.w	d3,d4
	move.w	TA_OVK+2,d5
	add.w	d2,d5
	move.w	d2,-(a7)
	bsr.w	ta_look
	move.w	(a7)+,d2
	tst.l	d0
	bmi.w	.zero
	move.l	d0,a4			; tile id
	move.w	TA_LDB,d1
	cmpi.w	#$FF,d1			; (no cell painted it: the filler)
	beq.s	.zero
	move.w	d1,d0
	lsr.w	#3,d1
	sub.w	#16,d1
	add.w	TA_LROW,d1		; smin
	cmp.w	d1,d7
	blt.s	.all
	andi.w	#7,d0
	beq.s	.zero
	add.w	d0,d1			; sup
	cmp.w	d1,d7
	bge.s	.zero
	bsr.w	.copy			; the pixels at sup only
	move.l	a4,d0
	cmp.l	ATL+734,d0		; a composite: its overlay's mask
	bcs.s	.mt
	sub.l	ATL+734,d0
	lsr.l	#7,d0
	lsl.l	#3,d0
	add.l	ATL+742,d0
	bra.s	.mo
.mt:	lsl.l	#3,d0
	add.l	ATL+6+4*(1+175),d0	; the mask (via slot 6)
.mo:
	bsr.w	ta_map6
	lea	ta_nib(pc),a1
	moveq	#8-1,d1
.m:	moveq	#0,d0
	move.b	(a0)+,d0
	lsl.w	#2,d0
	move.l	(a1,d0.w),d0
	and.l	d0,-32(a3)
	addq.l	#4,a3
	dbra	d1,.m
	lea	-32(a3),a3
	moveq	#1,d6
	bra.s	.nx
.all:	bsr.w	.copy
	moveq	#1,d6
	bra.s	.nx
.zero:	moveq	#8-1,d1
.z:	clr.l	(a3)+
	dbra	d1,.z
.nx:	addq.w	#1,d2
	cmpi.w	#4,d2
	bcs.w	.rj
	addq.w	#1,d3
	cmpi.w	#4,d3
	bcs.w	.ci
	tst.w	d6
	beq.s	.done
	lea	OVBUF,a0		; up: 64 bytes at a time, masked
	move.w	#TA_OVT*32,d2
	moveq	#8-1,d3
.u:	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d2,d0
	bsr.w	td_vwrite
	lea	VDP_DATA,a1
	moveq	#16-1,d1
.uw:	move.l	(a0)+,(a1)
	dbra	d1,.uw
	move.w	(a7)+,sr
	add.w	#64,d2
	dbra	d3,.u
	move.w	TA_OVK,d0
	lsl.w	#3,d0
	move.w	d0,TA_OVX
	move.w	TA_OVK+2,d0
	lsl.w	#3,d0
	addq.w	#6,d0
	move.w	d0,TA_OVY
	move.w	#1,TA_OVOK
.done:
.same:	movem.l	(a7)+,d2-d7/a2-a4
	rts
.off:	clr.w	TA_OVOK
	move.w	#$8000,TA_OVK
	rts

.copy:	; tile a4 -> a3 (32 bytes, a3 past it)
	movem.l	d2/a2,-(a7)
	move.l	a4,d1
	lea	TD_HB2,a2
	bsr.w	ta_tget
	movem.l	(a7)+,d2/a2
	moveq	#8-1,d1
.cl:	move.l	(a0)+,(a3)+
	dbra	d1,.cl
	rts

ta_nib:	; mask byte -> 8 nibbles ($F where the bit is set)
	dc.l	$00000000,$0000000F,$000000F0,$000000FF,$00000F00,$00000F0F,$00000FF0,$00000FFF
	dc.l	$0000F000,$0000F00F,$0000F0F0,$0000F0FF,$0000FF00,$0000FF0F,$0000FFF0,$0000FFFF
	dc.l	$000F0000,$000F000F,$000F00F0,$000F00FF,$000F0F00,$000F0F0F,$000F0FF0,$000F0FFF
	dc.l	$000FF000,$000FF00F,$000FF0F0,$000FF0FF,$000FFF00,$000FFF0F,$000FFFF0,$000FFFFF
	dc.l	$00F00000,$00F0000F,$00F000F0,$00F000FF,$00F00F00,$00F00F0F,$00F00FF0,$00F00FFF
	dc.l	$00F0F000,$00F0F00F,$00F0F0F0,$00F0F0FF,$00F0FF00,$00F0FF0F,$00F0FFF0,$00F0FFFF
	dc.l	$00FF0000,$00FF000F,$00FF00F0,$00FF00FF,$00FF0F00,$00FF0F0F,$00FF0FF0,$00FF0FFF
	dc.l	$00FFF000,$00FFF00F,$00FFF0F0,$00FFF0FF,$00FFFF00,$00FFFF0F,$00FFFFF0,$00FFFFFF
	dc.l	$0F000000,$0F00000F,$0F0000F0,$0F0000FF,$0F000F00,$0F000F0F,$0F000FF0,$0F000FFF
	dc.l	$0F00F000,$0F00F00F,$0F00F0F0,$0F00F0FF,$0F00FF00,$0F00FF0F,$0F00FFF0,$0F00FFFF
	dc.l	$0F0F0000,$0F0F000F,$0F0F00F0,$0F0F00FF,$0F0F0F00,$0F0F0F0F,$0F0F0FF0,$0F0F0FFF
	dc.l	$0F0FF000,$0F0FF00F,$0F0FF0F0,$0F0FF0FF,$0F0FFF00,$0F0FFF0F,$0F0FFFF0,$0F0FFFFF
	dc.l	$0FF00000,$0FF0000F,$0FF000F0,$0FF000FF,$0FF00F00,$0FF00F0F,$0FF00FF0,$0FF00FFF
	dc.l	$0FF0F000,$0FF0F00F,$0FF0F0F0,$0FF0F0FF,$0FF0FF00,$0FF0FF0F,$0FF0FFF0,$0FF0FFFF
	dc.l	$0FFF0000,$0FFF000F,$0FFF00F0,$0FFF00FF,$0FFF0F00,$0FFF0F0F,$0FFF0FF0,$0FFF0FFF
	dc.l	$0FFFF000,$0FFFF00F,$0FFFF0F0,$0FFFF0FF,$0FFFFF00,$0FFFFF0F,$0FFFFFF0,$0FFFFFFF
	dc.l	$F0000000,$F000000F,$F00000F0,$F00000FF,$F0000F00,$F0000F0F,$F0000FF0,$F0000FFF
	dc.l	$F000F000,$F000F00F,$F000F0F0,$F000F0FF,$F000FF00,$F000FF0F,$F000FFF0,$F000FFFF
	dc.l	$F00F0000,$F00F000F,$F00F00F0,$F00F00FF,$F00F0F00,$F00F0F0F,$F00F0FF0,$F00F0FFF
	dc.l	$F00FF000,$F00FF00F,$F00FF0F0,$F00FF0FF,$F00FFF00,$F00FFF0F,$F00FFFF0,$F00FFFFF
	dc.l	$F0F00000,$F0F0000F,$F0F000F0,$F0F000FF,$F0F00F00,$F0F00F0F,$F0F00FF0,$F0F00FFF
	dc.l	$F0F0F000,$F0F0F00F,$F0F0F0F0,$F0F0F0FF,$F0F0FF00,$F0F0FF0F,$F0F0FFF0,$F0F0FFFF
	dc.l	$F0FF0000,$F0FF000F,$F0FF00F0,$F0FF00FF,$F0FF0F00,$F0FF0F0F,$F0FF0FF0,$F0FF0FFF
	dc.l	$F0FFF000,$F0FFF00F,$F0FFF0F0,$F0FFF0FF,$F0FFFF00,$F0FFFF0F,$F0FFFFF0,$F0FFFFFF
	dc.l	$FF000000,$FF00000F,$FF0000F0,$FF0000FF,$FF000F00,$FF000F0F,$FF000FF0,$FF000FFF
	dc.l	$FF00F000,$FF00F00F,$FF00F0F0,$FF00F0FF,$FF00FF00,$FF00FF0F,$FF00FFF0,$FF00FFFF
	dc.l	$FF0F0000,$FF0F000F,$FF0F00F0,$FF0F00FF,$FF0F0F00,$FF0F0F0F,$FF0F0FF0,$FF0F0FFF
	dc.l	$FF0FF000,$FF0FF00F,$FF0FF0F0,$FF0FF0FF,$FF0FFF00,$FF0FFF0F,$FF0FFFF0,$FF0FFFFF
	dc.l	$FFF00000,$FFF0000F,$FFF000F0,$FFF000FF,$FFF00F00,$FFF00F0F,$FFF00FF0,$FFF00FFF
	dc.l	$FFF0F000,$FFF0F00F,$FFF0F0F0,$FFF0F0FF,$FFF0FF00,$FFF0FF0F,$FFF0FFF0,$FFF0FFFF
	dc.l	$FFFF0000,$FFFF000F,$FFFF00F0,$FFFF00FF,$FFFF0F00,$FFFF0F0F,$FFFF0FF0,$FFFF0FFF
	dc.l	$FFFFF000,$FFFFF00F,$FFFFF0F0,$FFFFF0FF,$FFFFFF00,$FFFFFF0F,$FFFFFFF0,$FFFFFFFF

ta_who:	; -> d0 = the char the pad moves: the party leader, or in a room
	; (his cell off this map: the party splits) the first party member
	movem.l	a0-a1,-(a7)
	move.w	LEADER,d0
	mulu.w	#$34,d0
	lea	CHARS,a0
	adda.l	d0,a0
	movea.l	GRIDPTR,a1
	move.w	$C(a0),d0
	cmp.w	(a1),d0
	bcc.s	.r
	move.w	$E(a0),d0
	cmp.w	2(a1),d0
	bcc.s	.r
	move.w	LEADER,d0
	bra.s	.o
.r:	move.w	($FF0E82).l,d0
.o:	movem.l	(a7)+,a0-a1
	rts

ta_hdir:	; d5 = pad nibble (U D L R) -> d4 = direction 0-3, -1 none, as
	; menu_verb_input maps it ($0116: turned layout, $0134: diagonals)
	moveq	#-1,d4
	lea	ta_pad0(pc),a0
	tst.w	$FF0116
	beq.s	.t
	lea	ta_pad1(pc),a0
.t:	move.b	(a0,d5.w),d4
	ext.w	d4
	cmpi.w	#4,d4			; a diagonal: only with $0134
	blt.s	.o
	moveq	#-1,d4
	tst.w	$FF0134
	beq.s	.o
	move.b	(a0,d5.w),d4
	ext.w	d4
	subq.w	#4,d4
	cmpi.w	#4,d4
	blt.s	.o
	moveq	#-1,d4
.o:	rts
ta_pad0:	; nibble 0-15 -> 0-3, 4 + d for a diagonal, 8 none
	dc.b	8,0,2,8, 3,7,6,8, 1,4,5,8, 8,8,8,8
ta_pad1:
	dc.b	8,3,1,8, 2,7,6,8, 0,4,5,8, 8,8,8,8

ta_padf:	; td_pad: d0 = the popped pad byte. With the controller on, the
	; game sees no direction but the step it is handed (once)
	tst.w	TA_CTL
	beq.s	.o
	cmpi.w	#$5A71,TA_ON		; only the walk's own pop (main_loop's
	bne.s	.o			; menu_verb_input, $012FF2), in the
	tst.w	$FF00AC			; pre-drawn view, no menu, no combat:
	bne.s	.o			; menus, talk and the arena keep their
	cmpi.l	#$FFB0BC,GRIDPTR	; arrows
	beq.s	.o
	cmpi.l	#$012FF8,4(a7)
	bne.s	.o
	andi.b	#$F0,d0
	tst.w	TA_CMT
	beq.s	.o
	or.b	TA_CMT+1,d0
	clr.w	TA_CMT
	movem.l	d1-d2,-(a7)		; the frames between the steps the game
	move.w	FRAME,d1		; takes pace the walk too: one taken
	sub.w	TA_CF,d1		; later than the walk expected raises it
	move.w	TD_PERIOD,d2		; at once (no stop and go in a busy
	add.w	d2,d2			; room, #308); a pause (2 periods or
	cmp.w	d2,d1			; more) does not count
	bcc.s	.nr
	cmp.w	TD_RPER,d1
	bls.s	.nr
	move.w	d1,TD_RPER
.nr:	movem.l	(a7)+,d1-d2
	move.w	FRAME,TA_CF
	bne.s	.o
	move.w	#1,TA_CF		; (frame 0)
.o:	rts

ta_ltget:	; d2/d3 = cell -> d0 = its lift from TA_LT (N set: not there)
	lea	TA_LT,a0
	moveq	#5-1,d0
.l:	cmp.w	(a0),d2
	bne.s	.n
	cmp.w	2(a0),d3
	bne.s	.n
	move.w	4(a0),d0
	rts
.n:	addq.l	#6,a0
	dbra	d0,.l
	moveq	#-1,d0
	rts

ta_lifts:	; main loop: TA_LT <- the leader's cell and its 4 neighbours
	; (only cells not there yet are read: CELLREAD is a game call)
	movem.l	d2-d6/a2,-(a7)
	move.w	TA_WHO,d0
	mulu.w	#$34,d0
	lea	CHARS,a2
	adda.l	d0,a2
	move.w	$C(a2),d4
	move.w	$E(a2),d5
	moveq	#5-1,d6
.c:	move.w	d6,d0			; cell k: 4 = here, 0-3 = ta_dxy
	move.w	d4,d2
	move.w	d5,d3
	cmpi.w	#4,d0
	beq.s	.h
	add.w	d0,d0
	add.w	d0,d0
	lea	ta_dxy(pc),a0
	add.w	(a0,d0.w),d2
	add.w	2(a0,d0.w),d3
.h:	bsr.s	ta_ltget
	bpl.s	.k
	bsr.s	ta_cellift
.k:	move.w	d0,-(a7)
	move.w	d3,-(a7)
	move.w	d2,-(a7)
	dbra	d6,.c
	lea	TA_LT,a0		; (all 5 read first, then stored)
	moveq	#15-1,d0
.s:	move.w	(a7)+,(a0)+
	dbra	d0,.s
	movem.l	(a7)+,d2-d6/a2
	rts

ta_cellift:	; d2/d3 = cell -> d0 = the figure lift there (as td_ilift)
	movem.l	d1-d3/a0-a1,-(a7)
	move.w	d3,-(a7)
	move.w	d2,-(a7)
	jsr	(CELLREAD).l
	addq.w	#4,a7
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
	addq.w	#1,d2
	mulu.w	#7,d2
	lsr.w	#8,d1
	andi.w	#1,d1
	lsl.w	#2,d1
	add.w	d1,d2
	move.w	d2,d0
	movem.l	(a7)+,d1-d3/a0-a1
	rts

ta_pref:	; main loop (ta_stream): the leader's images for his facing
	; (standing + 4 walk frames) kept in the figure cache: missing ones
	; drawn now (2 a frame), all of them touched so the cache keeps them
	; (the turn shows at once, no other direction's pose while walking)
	tst.w	TA_CTL
	beq.s	.o
	movem.l	d2-d7/a2-a3,-(a7)
	move.w	TA_WHO,d0
	mulu.w	#$34,d0
	lea	CHARS,a3
	adda.l	d0,a3
	move.w	4(a3),d0		; its record
	cmpi.w	#56,d0
	bcc.s	.x
	mulu.w	#12,d0
	lea	RECS,a2
	adda.w	d0,a2
	moveq	#5,d7			; drawings left this frame
	move.w	TA_DFACE,d5		; (d5: the facing ta_lkey uses)
	moveq	#-1,d6			; the image shown now first:
	tst.w	TA_MOV			; walk frame or standing
	beq.s	.f
	move.w	TA_WPH,d6
	lsr.w	#6,d6
	andi.w	#3,d6
.f:	bsr.s	.one
	moveq	#-1,d6			; then all five
.k:	bsr.s	.one
	addq.w	#1,d6
	cmpi.w	#4,d6
	blt.s	.k
	moveq	#3,d5			; and every facing's standing image
.fl:	moveq	#-1,d6			; (a turn shows at once)
	bsr.s	.one
	dbra	d5,.fl
.x:	clr.w	TD_CANX
	movem.l	(a7)+,d2-d7/a2-a3
.o:	rts
.one:	bsr.s	ta_lkey
	tst.w	d1
	bne.s	.n
	move.w	d7,TD_CANX
	bsr.w	td_img			; (a hit only touches it)
	tst.w	TD_CANX
	bne.s	.n
	tst.w	d7
	beq.s	.n
	subq.w	#1,d7
.n:	rts

ta_lkey:	; a2 = record, d5 = facing, d6 = walk frame (-1 standing) -> d0 =
	; the image key td_figure would use, d1 = 0 (d1 != 0: none). Uses
	; d2-d3/a0.
	move.w	d5,d0
	add.w	4(a2),d0
	cmpi.w	#56,d0
	bcc.s	.none
	mulu.w	#36,d0
	movea.l	GRIDPTR,a0
	move.w	$A(a0),d1
	andi.w	#3,d1
	lsl.w	#3,d1
	add.w	d1,d0
	lea	($0197B0).l,a0
	adda.w	d0,a0
	move.w	(a0),d2
	move.w	2(a0),d3
	tst.w	d6
	bmi.s	.key
	move.w	d2,d0
	andi.w	#6,d0
	beq.s	.w
	cmpi.w	#6,d0
	bne.s	.key
.w:	andi.w	#8,d2
	lea	td_walk(pc),a0
	add.b	(a0,d6.w),d2
.key:	add.w	(a2),d2
	tst.w	d3
	beq.s	.k1
	ori.w	#$8000,d2
.k1:	move.w	d2,d0
	moveq	#0,d1
	rts
.none:	moveq	#-1,d1
	rts

ta_isldr:	; d7 = char index, a3 = char -> Z if it is the leader's figure
	; and the controller is on (keeps all registers)
	movem.l	d0,-(a7)
	tst.w	TA_CTL
	beq.s	.n
	cmp.w	TA_WHO,d7
	beq.s	.y
	move.w	(a3),d0
	andi.w	#$F,d0
	cmpi.w	#4,d0
	bne.s	.n
	moveq	#0,d0
	move.b	$27(a3),d0
	cmp.w	TA_WHO,d0
	beq.s	.y
.n:	movem.l	(a7)+,d0
	andi	#$FB,ccr
	rts
.y:	movem.l	(a7)+,d0
	ori	#4,ccr
	rts
	endif

;=======================================================================
; ta_pathc — combat_move_unit's step test ($024B6A, 14 bytes: pea,
; jsr move_cost_calc, addq, move d0,d4). In the pre-drawn view, the
; party leader stepping into a wall slides around it: a side step that
; is free and from where the wanted step is free too is taken instead
; (the remaster's path correction, rebuilt, #307). Outside combat.
;=======================================================================
ta_pathc:
	pea	-$22(a6)
	jsr	($01C892).l		; move_cost_calc
	addq.w	#4,a7
	move.w	d0,d4
	ifd	SIZE8M
	bne.w	.o
	cmpi.w	#$5A71,TA_ON
	bne.w	.o
	cmpi.w	#1,d7			; a plain step
	bgt.w	.o
	cmpi.w	#4,d6
	bcc.w	.o
	tst.w	$8(a6)
	bmi.w	.o
	move.w	-$34(a6),d0		; the party leader
	cmp.w	TA_WHO,d0
	bne.w	.o
	cmpi.l	#$FFB0BC,GRIDPTR	; not in a combat arena
	beq.w	.o
	cmpi.w	#$FF,-$A(a6)		; plain ground only: a building, door or
	bne.w	.o			; person is bumped (entered, talked to)
	move.w	($FF0E92).l,d0		; (a location's key: the game names
	andi.w	#$3FF,d0		; it, then enters)
	cmpi.w	#$3FF,d0
	bne.w	.o
	move.l	-$22(a6),TA_SXY
	move.w	-$A(a6),TA_SFL
	move.w	TA_LS,d0		; (no ping-pong along a wall)
	cmpi.w	#3,d0
	beq.s	.ls
	moveq	#1,d0
.ls:	move.w	d0,TA_TRY
	move.w	d0,TA_LS
.t:	move.w	d6,d1			; side: direction + 1, then + 3
	add.w	TA_TRY,d1
	andi.w	#3,d1
	move.w	d1,TA_PD
	bsr.w	.free			; the side step free?
	beq.s	.no
	move.w	TA_PD,d1		; from there, the wanted step?
	bsr.w	.dxy
	add.w	d0,-$22(a6)
	add.w	d1,-$20(a6)
	move.w	d6,d1
	bsr.w	.free
	move.l	TA_SXY,-$22(a6)
	beq.s	.no
	move.w	TA_TRY,TA_LS
	move.w	TA_PD,d6		; yes: the side step it is
	move.w	d6,d1
	bsr.w	.dxy
	move.w	d0,-$26(a6)
	move.w	d1,-$24(a6)
	move.w	d6,d1
	bsr.w	.free
	move.w	d0,d4
	bra.s	.o
.no:	move.l	TA_SXY,-$22(a6)
	move.w	TA_TRY,d0
	cmp.w	TA_LS,d0		; tried both?
	bne.s	.fail
	move.w	#4,d0
	sub.w	TA_TRY,d0
	move.w	d0,TA_TRY
	bra.w	.t
.fail:	move.w	d6,d1			; neither: the record as the game left it
	bsr.w	.free
	moveq	#0,d4
	endif
.o:	rts
	ifd	SIZE8M
.free:	; d1 = direction: record deltas and blocked flag, then the test
	; -> d0 = steps (Z if none)
	bsr.s	.dxy
	move.w	d0,-$18(a6)
	move.w	d1,-$16(a6)
	move.w	TA_SFL,-$A(a6)
	pea	-$22(a6)
	jsr	($01C892).l
	addq.w	#4,a7
	tst.w	d0
	rts
.dxy:	; d1 = direction -> d0 = dx, d1 = dy (as world_get_step_delta)
	add.w	d1,d1
	add.w	d1,d1
	lea	.tab(pc),a0
	move.w	(a0,d1.w),d0
	move.w	2(a0,d1.w),d1
	rts
.tab:	dc.w	0,-1, 1,0, 0,1, -1,0
	endif

;=======================================================================
; td_hud_glyph / td_hud_gauge — the game's HUD draw (case 7, $29128)
; writes its words with text_glyph_draw / text_draw_gauge at the
; original cells (rows 20-25). LITERAL DISABLE (Dayset's named method
; for #307 task #3): in the pre-drawn view td_hud_map drops EVERY
; call, so gold / time / food-water are never drawn anywhere — not
; at the original cells, and not in the HUD box either. That also
; starves td_hud: it copies from the source cells, finds them blank
; and moves nothing, so the box stays empty (TD_HASBOX never set by
; it). Not the pre-drawn view: the calls go through unchanged. The
; row/col are the caller's stack args (12(a7) / 10(a7) at entry: ret,
; plane, $40, col, row, str, attr).
;
; These must resolve in every build (hooks.csv), so they live outside
; the SIZE8M block and gate on TA_ON's address directly: TA_ON is
; defined only under SIZE8M (line 229) as TD_ARTOK+2 ($FF7D4E). In
; the 1m/2m builds that word is never $5A71, so nothing remaps there.
;=======================================================================
TD_HUDON	equ	TD_ARTOK+2	; = TA_ON (pre-drawn view on, $5A71)

td_hud_glyph:
	move.w	12(a7),d2		; row
	move.w	10(a7),d3		; col
	bsr.w	td_hud_map
	tst.w	d0
	beq.s	.orig			; 0: as-is
	cmpi.w	#2,d0
	beq.s	.skip			; 2: a label: drop the draw
	move.w	d2,12(a7)		; 1: remapped row
	move.w	d3,10(a7)		;    remapped col
.orig:
	; TAIL CALL: jmp so text_glyph_draw returns straight to the arm.
	; A jsr here would leave a second return address on the stack and
	; shift every a6-relative arg text_glyph_draw reads (plane/row/col/str).
	jmp	($01113C).l		; text_glyph_draw
.skip:
	rts

td_hud_gauge:
	move.w	12(a7),d2		; row
	move.w	10(a7),d3		; col
	bsr.w	td_hud_map
	tst.w	d0
	beq.s	.orig			; 0: as-is
	cmpi.w	#2,d0
	beq.s	.skip			; 2: a label: drop the draw
	move.w	d2,12(a7)		; 1: remapped row
	move.w	d3,10(a7)		;    remapped col
.orig:
	; TAIL CALL: see td_hud_glyph.
	jmp	($011416).l		; text_draw_gauge
.skip:
	rts

td_hud_map:
	; d2 = row, d3 = col -> d0 = 0 as-is, 1 remapped (d2/d3 new,
	; unused under the literal disable), 2 skip. Only when the
	; pre-drawn view is on. td_hseg's rows are all distinct, so the
	; row alone picks the segment; the column must still fall inside
	; it. LITERAL DISABLE: any call matching a HUD segment is
	; dropped outright — no remap to the box, no draw at all.
	cmpi.w	#$5A71,TD_HUDON
	bne.s	.asis
	movem.l	d4-d6,-(a7)
	lea	td_hseg(pc),a0
.seg:
	moveq	#0,d0
	move.b	(a0)+,d0		; src row (0 = end)
	beq.s	.done0
	moveq	#0,d1
	move.b	(a0)+,d1		; src col
	moveq	#0,d4
	move.b	(a0)+,d4		; len
	moveq	#0,d5
	move.b	(a0)+,d5		; dest row
	moveq	#0,d6
	move.b	(a0)+,d6		; dest col
	addq.w	#1,a0			; pad
	cmp.w	d0,d2
	bne.s	.seg
	cmp.w	d1,d3
	bcs.s	.seg
	add.w	d1,d4			; src col + len
	cmp.w	d4,d3
	bcc.s	.seg
	bra.s	.skip			; disable: drop the draw entirely
.skip:
	moveq	#2,d0
	bra.s	.done
.done0:
	moveq	#0,d0
.done:
	movem.l	(a7)+,d4-d6
	rts
.asis:
	moveq	#0,d0
	rts

;=======================================================================
; Pre-drawn overworld (#307, 8 MB): the overworld's tiles come from the
; atlas at ATL (tools/ow_atlas.py) instead of the game's render. A
; 42x30-tile window around the camera is kept on Plane B at its global
; place; a column or row is streamed as the camera crosses a tile, tiles
; go to VRAM through a slot cache (hash by tile id, a slot is free when
; no cell of the window uses it). The atlas is read through the Sega
; mapper: records in slot 6 ($300000), tiles in slot 7 ($380000).
;=======================================================================
	ifd	SIZE8M
	even
ta_want:	; -> d0 = 1 + the area to show (0 none), a0 = its header
	cmpi.l	#$4F574138,ATL		; 'OWA8'
	bne.s	.n
	cmpi.l	#$FFB0BC,GRIDPTR	; a combat arena: none (its own art
	beq.s	.n			; goes where our slots are)
	moveq	#0,d0			; area 0: the overworld,
	move.w	LOC,d1			; 1 + n: location n
	cmpi.w	#$FFFF,d1
	beq.s	.a
	cmpi.w	#175,d1
	bcc.s	.n
	move.w	d1,d0
	addq.w	#1,d0
.a:	move.w	d0,d1
	lsl.w	#2,d1
	lea	ATL+6,a0
	move.l	(a0,d1.w),d1
	beq.s	.n
	movea.l	d1,a0
	addq.w	#1,d0
	rts
.n:	moveq	#0,d0
	rts

ta_sync:	; td_isync, once per tick: enter, change area or leave
	bsr.s	ta_want
	cmpi.w	#$5A71,TA_ON
	bne.s	.off
	cmp.w	TA_AR,d0
	beq.w	.same
	tst.w	d0
	beq.w	.leave
	move.l	a0,TA_A			; another area: all of it again
	move.w	d0,TA_AR
	move.w	#1,TD_VALID		; (a new map cleared it)
	bsr.w	ta_reset
	bsr.w	ta_pblank		; (no old area at the new scroll)
	move.w	#120,TA_WFF		; (the game draws its room into the
	move.w	#4,TA_WFQ		; window for a while; its old picture:
	bsr.s	.snap			; off it now, and the next 4 ticks)
	subq.w	#1,TD_BUSY
	bsr.w	td_winfix
	move.w	#1,TD_UNFR
	bsr.w	td_iso_winfix
	clr.w	TD_UNFR
	addq.w	#1,TD_BUSY
	rts
.off:	tst.w	d0
	beq.w	.o
	move.l	a0,TA_A
	move.w	d0,TA_AR
	bsr.w	td_iso_cancel
	move.w	#TI_NFC+4,TD_NFCV	; 12 figure images: 8 + 4 in
	move.w	#1974,d1		; VRAM 1974-2037
	sub.w	TD_BASE,d1
	move.w	d1,TD_PEND
	bsr.w	.unfr
	bsr.w	ta_reset
	bsr.w	ta_pblank		; (the game's arena / view words off)
	lea	TD_FC,a0		; figure images: the game wrote over
	moveq	#TD_NFC-1,d1		; them meanwhile (combat): all again
.fc:	move.l	#$FFFF0000,(a0)+
	dbra	d1,.fc
	move.w	#120,TA_WFF		; (and its window words, a while)
	move.w	#$5A71,TA_ON
	move.w	#1,TD_VALID
.snap:	move.w	$FF0E8E,TD_ICX		; camera on the game camera's cell
	move.w	$FF0E90,TD_ICY
	bsr.w	td_iso_snap
	bra.w	td_iso_cam
.leave:	bra.w	ta_out
.same:	move.w	#1,TD_VALID
	bsr.w	ta_fblk			; (writes that miss the sprite table
	tst.w	d0			; land on it: keep it blank)
	tst.w	d0			; on: room-bitmap and frame words the
	beq.w	.o			; game put in the window go blank (they
	bsr.w	ta_hud			; would show our tiles), every 4th tick
	move.w	TD_MSG,d0		; each; the HUD words every tick. A
	cmp.w	TA_MSG0,d0		; message gone or a new area: both
	beq.s	.mq			; every tick for a while (the game puts
	move.w	d0,TA_MSG0		; its old picture back under the box)
	tst.w	d0
	bne.s	.mq
	move.w	#3,TA_WFQ
	move.w	#60,TA_WFF
.mq:	tst.w	TA_WFQ
	beq.s	.nq
	subq.w	#1,TA_WFQ
	subq.w	#1,TD_BUSY
	bsr.w	td_winfix
	move.w	#1,TD_UNFR
	bsr.w	td_iso_winfix
	clr.w	TD_UNFR
	addq.w	#1,TD_BUSY
	rts
.nq:	addq.w	#1,TD_WFC
	move.w	TD_WFC,d0
	andi.w	#3,d0
	beq.s	.unfr
	cmpi.w	#2,d0
	bne.s	.o
	subq.w	#1,TD_BUSY
	bsr.w	td_winfix		; (also: is a message showing)
	addq.w	#1,TD_BUSY
	rts
.unfr:	move.w	#1,TD_UNFR		; the frame off the window
	subq.w	#1,TD_BUSY
	bsr.w	td_iso_winfix
	addq.w	#1,TD_BUSY
	clr.w	TD_UNFR
.o:	rts

ta_out:	; the pre-drawn view off: records 16-17 and 6 back
	move.l	d2,-(a7)
	clr.w	TA_ON			; the iso picture's tiles, pool and
	clr.w	TD_VALID		; plane come back (td_iso_load)
	clr.w	TD_TILES
	move.w	#TA_HUD>>19,d0		; records 16-17 back from their copy
	move.w	d0,TA_B7
	move.b	d0,$A130FF
	lea	$380000+(TA_HUD&$7FFFF),a0
	move.w	#1834*32,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	bsr.w	td_vwrite
	move.w	#204*8-1,d1
.hr:	move.l	(a0)+,VDP_DATA
	dbra	d1,.hr
	move.w	(a7)+,sr
	move.w	#436*32,d0		; record 6 (frame art) right after it,
	moveq	#7-1,d2			; 64 tiles a go
.r6:	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d0,-(a7)
	bsr.w	td_vwrite
	move.w	#64*8-1,d1
	tst.w	d2
	bne.s	.r7
	move.w	#(438-6*64)*8-1,d1
.r7:	move.l	(a0)+,VDP_DATA
	dbra	d1,.r7
	move.w	(a7)+,d0
	move.w	(a7)+,sr
	add.w	#64*32,d0
	dbra	d2,.r6
	move.w	TD_BASE,d0		; the room bitmap's tiles we used: clear
	add.w	#64,d0			; (the game redraws only its window
	moveq	#209-1,d1		; there; the rest showed our tiles)
	bsr.s	.clr
	move.w	TD_BASE,d0
	add.w	#401,d0
	move.w	#427-1,d1
	bsr.s	.clr
	move.l	(a7)+,d2
	rts
.clr:	; tiles d0.. (d1 + 1 of them) <- 0, 16 a go
	lsl.w	#5,d0
.c0:	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d0,-(a7)
	bsr.w	td_vwrite
	moveq	#16-1,d2
.c1:	moveq	#8-1,d0
.c2:	move.l	#0,VDP_DATA
	dbra	d0,.c2
	subq.w	#1,d1
	bmi.s	.c3
	dbra	d2,.c1
.c3:	move.w	(a7)+,d0
	move.w	(a7)+,sr
	add.w	#16*32,d0
	tst.w	d1
	bpl.s	.c0
	rts

ta_hud:	; no gold, time, food / water words: td_hsrc's cells blank
	tst.w	TD_MSG			; (unless a message is in those rows)
	bne.w	.o
	movem.l	d2-d3/a2,-(a7)
	move.w	#$1000+20*128+3*2,d2	; a message shows on row 20 where no
.m:	move.w	d2,d0			; HUD word goes (portrait cols 3-5,
	bsr.w	td_vread		; text from col 10): leave it be
	andi.w	#$7FF,d0
	cmp.w	FONTBLK,d0
	bne.s	.x
	addq.w	#2,d2
	cmpi.w	#$1000+20*128+6*2,d2
	bne.s	.m1
	move.w	#$1000+20*128+10*2,d2
.m1:	cmpi.w	#$1000+20*128+22*2,d2
	bcs.s	.m
	lea	td_hsrc(pc),a2
	moveq	#20,d2			; row
.r:	moveq	#0,d3
	move.b	(a2)+,d3		; first column
	move.w	d2,d0
	lsl.w	#7,d0
	add.w	d3,d0
	add.w	d3,d0
	add.w	#$1000,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	bsr.w	td_vwrite
	moveq	#0,d1
	move.b	(a2)+,d1
	sub.w	d3,d1
.c:	move.w	FONTBLK,VDP_DATA
	dbra	d1,.c
	move.w	(a7)+,sr
	addq.w	#1,d2
	cmpi.w	#26,d2
	bcs.s	.r
.x:	movem.l	(a7)+,d2-d3/a2
.o:	rts

ta_spr:	; the game's sprites showing records 16-17 (pad, gauges): off
	; screen (their tiles are ours here)
	movem.l	d2-d4,-(a7)
	move.w	TD_GHEAD,d2
	moveq	#80-1,d3
.l:	tst.w	d2
	beq.s	.o
	move.w	d2,d4
	lsl.w	#3,d4
	add.w	SPRBASE,d4
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d4,d0			; link and tile in one read
	addq.w	#2,d0
	bsr.w	td_vcmd
	move.l	d0,VDP_CTRL
	move.w	VDP_DATA,d2
	move.w	VDP_DATA,d0
	andi.w	#$7FF,d0
	cmpi.w	#1834,d0
	bcs.s	.k
	cmpi.w	#2038,d0
	bcc.s	.k
	move.w	d4,d0
	bsr.w	td_vwrite
	move.w	#0,VDP_DATA
.k:	move.w	(a7)+,sr
	andi.w	#$7F,d2
	dbra	d3,.l
.o:	movem.l	(a7)+,d2-d4
	rts

ta_sgn:	; d2 = sign(d2), a jump of more than one cell -> 0
	cmpi.w	#1,d2
	bgt.s	.z
	cmpi.w	#-1,d2
	bge.s	.o
.z:	moveq	#0,d2
.o:	rts

ta_rub:	; rubber-band camera (td_iso_cam): still while the leader's cell
	; is within TA_DZ of it, then a spring toward the cell plus a lead
	; of TA_LEAD in the walking direction (while walking)
	moveq	#0,d4
	move.w	FRAME,d0
	sub.w	TD_CT0,d0
	move.w	TD_PERIOD,d1
	add.w	d1,d1
	cmp.w	d1,d0
	bcc.s	.nl
	moveq	#1,d4
.nl:	move.w	TD_CGX,d0
	mulu.w	#TI_CU,d0
	tst.w	TA_CTL			; (the controller: the leader's figure)
	beq.s	.gx
	tst.w	TD_LEADOK
	beq.s	.gx
	move.w	TD_LEADX,d0		; 1/16 cell -> 112/16
	mulu.w	#TI_CU/16,d0
.gx:	move.w	TA_LX,d1
	lea	TD_CMX,a0
	bsr.s	.ax
	move.w	TD_CGY,d0
	mulu.w	#TI_CU,d0
	tst.w	TA_CTL
	beq.s	.gy
	tst.w	TD_LEADOK
	beq.s	.gy
	move.w	TD_LEADY,d0
	mulu.w	#TI_CU/16,d0
.gy:	move.w	TA_LY,d1
	lea	TD_CMY,a0
.ax:	move.w	d0,(a0)			; the camera is the leader: no dead
	rts				; zone, lead or spring (a reversed walk
					; made it hold, then race at 2 px a
					; frame: the zigzag). The easing in
					; ta_clamp makes the glide (#308)
	tst.w	d4
	beq.s	.w
	muls.w	#TA_LEAD,d1
	add.w	d1,d0
.w:	sub.w	(a0),d0			; d0 = want - camera
	move.w	d0,d2
	bpl.s	.p
	neg.w	d2
.p:	cmpi.w	#8*TI_CU,d2		; far (door, scene): snap (a turned
					; walk lead is a glide, not a jump)
	bls.s	.s
	add.w	d0,(a0)
	rts
.s:	sub.w	#TA_DZ,d2
	bls.s	.o
	tst.w	d4			; stopped: no glide back against the
	bne.s	.sw			; last walk (the lead stays)
	move.w	d1,d3
	eor.w	d0,d3
	bpl.s	.sw
	tst.w	d1
	beq.s	.sw
	sub.w	#TA_LEAD,d2
	bls.s	.o
.sw:
	lsr.w	#4,d2			; 1/16 of the way out of the zone
	addq.w	#1,d2
	cmpi.w	#TA_VMAX,d2
	bls.s	.v
	moveq	#TA_VMAX,d2
.v:	tst.w	d0
	bpl.s	.a
	neg.w	d2
.a:	add.w	d2,(a0)
.o:	rts

ta_pcheck:	; td_frame_go: one cell of the window still ours? (-> d0 = 0;
	; if not, the window is filled again)
	cmpi.w	#$8000,TA_L
	beq.s	.o
	movem.l	d4-d5,-(a7)
	move.w	TA_T,d5
	add.w	#14,d5
	move.w	TA_L,d4
	add.w	#20,d4
	bsr.w	ta_cell
	lea	TA_SH,a0
	move.w	(a0,d0.w),d1
	movem.l	(a7)+,d4-d5
	beq.s	.o			; (not written yet)
	move.w	d1,-(a7)
	bsr.w	td_vread		; d0 = the plane word there
	andi.w	#$7FF,d0
	move.w	(a7)+,d1
	move.w	d0,-(a7)
	move.w	FONTBLK,d0
	cmpi.w	#$FFFF,d1
	beq.s	.c
	move.w	d1,d0
	subq.w	#1,d0
	bsr.w	ta_vt
.c:	andi.w	#$7FF,d0
	cmp.w	(a7)+,d0
	beq.s	.o
	move.w	#1,TA_BAD
.o:	moveq	#0,d0
	rts

ta_fblk:	; the font blank tile (every blank window cell) blank again, if
	; anything wrote over it; keeps d0
	movem.l	d0-d1,-(a7)
	move.w	FONTBLK,d0
	lsl.w	#5,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d0,-(a7)
	bsr.w	td_vread
	move.w	d0,d1
	move.w	(a7)+,d0
	addq.w	#2,d0
	move.w	d0,-(a7)
	bsr.w	td_vread
	or.w	d0,d1
	move.w	(a7)+,d0
	subq.w	#2,d0
	tst.w	d1
	beq.s	.ok
	bsr.w	td_vwrite
	moveq	#8-1,d1
.c:	move.l	#0,VDP_DATA		; (not clr: it reads the port first)
	dbra	d1,.c
.ok:	move.w	(a7)+,sr
	movem.l	(a7)+,d0-d1
	rts

ta_pblank:	; the plane all blank at once (256 cells a go)
	movem.l	d2-d4,-(a7)
	moveq	#0,d4			; once (all blank, 256 cells a go):
	moveq	#8-1,d2			; no old area at the new scroll
.pb:	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.w	d4,d0
	bsr.w	td_vwrite
	move.w	FONTBLK,d1
	swap	d1
	move.w	FONTBLK,d1
	moveq	#128-1,d3
.pw:	move.l	d1,VDP_DATA
	dbra	d3,.pw
	move.w	(a7)+,sr
	add.w	#512,d4
	dbra	d2,.pb
	movem.l	(a7)+,d2-d4
	rts

ta_rehash:	; TA_HEAD / TA_NX again from TA_ID
	movem.l	d2-d4/a2,-(a7)
	lea	TA_HEAD,a0
	move.w	#512/2-1,d0
.h:	clr.l	(a0)+
	dbra	d0,.h
	lea	TA_HEAD,a0
	lea	TA_ID,a1
	lea	TA_NX,a2
	moveq	#0,d3			; slot
.s:	move.l	(a1)+,d4
	bmi.s	.n
	bsr.w	ta_hash			; d2 = bucket * 2
	move.w	d3,d0
	add.w	d0,d0
	move.w	(a0,d2.w),(a2,d0.w)
	move.w	d3,d0
	addq.w	#1,d0
	move.w	d0,(a0,d2.w)
.n:	addq.w	#1,d3
	cmpi.w	#TA_N,d3
	bcs.s	.s
	movem.l	(a7)+,d2-d4/a2
	rts

ta_reset:
	bsr.w	ta_glyphs		; (records 16-17 came back meanwhile)
	lea	TA_HEAD,a0
	move.w	#512/2-1,d0
.h:	clr.l	(a0)+
	dbra	d0,.h
	lea	TA_SH,a0
	move.w	#2048/2-1,d0
.s:	clr.l	(a0)+
	dbra	d0,.s
	lea	TA_ID,a0
	move.w	#TA_N-1,d0
.i:	move.l	#-1,(a0)+
	dbra	d0,.i
	bsr.w	ta_norc
	clr.w	TA_HAND
	clr.w	TA_BAD
	move.w	FONTBLK,d0		; the font blank blank again
	lsl.w	#5,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	bsr.w	td_vwrite
	moveq	#8-1,d1
.fb:	move.l	#0,VDP_DATA		; (not clr: it reads the port first)
	dbra	d1,.fb
	move.w	(a7)+,sr
	move.w	#-1,TA_PR
	bsr.w	ta_phnow
	move.w	d0,TA_PH
	move.w	#$8000,TA_L
	move.w	#-1,TA_B6
	move.w	#-1,TA_B7
	rts

ta_norc:	; no cell uses any slot
	lea	TA_RC,a0
	move.w	#TA_N-1,d0
.r:	clr.w	(a0)+
	dbra	d0,.r
	rts

ta_clamp:	; td_iso_cam: the camera stays inside the loaded window
	cmpi.w	#$5A71,TA_ON
	bne.w	.o
	move.w	TD_IGX,TA_RGX
	move.w	TD_IGY,TA_RGY
	movem.l	a0-a1/d2,-(a7)
	lea	TD_IGX,a0		; a target 64 px or more away: a snap
	lea	TA_CX,a1		; only when seen twice running (a
	bsr.w	.far			; single wild one, (0,1) while the game
	bne.s	.f1			; is busy, shook the scroll, #308)
	lea	TD_IGY,a0
	lea	TA_CY,a1
	bsr.w	.far
	bne.s	.f1
	clr.w	TA_FARN
	bra.s	.f2
.f1:	tst.w	TA_FARN
	bne.s	.f3
	move.w	#1,TA_FARN		; the first: keep the last view
	move.l	TA_CX,d0
	addq.l	#8,d0
	asr.l	#4,d0
	move.w	d0,TD_IGX
	move.l	TA_CY,d0
	addq.l	#8,d0
	asr.l	#4,d0
	move.w	d0,TD_IGY
	bra.s	.f4
.f3:	clr.w	TA_FARN
.f2:
	lea	TD_IGX,a0		; shown: eased toward the target, a
	lea	TA_CX,a1		; 16th of the way a frame in 1/16 px
	bsr.w	.lim			; (a zigzag of the leader's diagonal
	lea	TD_IGY,a0		; steps comes out a straight glide; the
	lea	TA_CY,a1		; rounding even both ways, #308), at
	bsr.w	.lim			; most 3 px a frame; 64 px or more: a
.f4:	movem.l	(a7)+,a0-a1/d2		; snap. The window follows it
	move.w	TD_IGX,TA_GX
	move.w	TD_IGY,TA_GY
	move.w	TA_L,d0
	cmpi.w	#$8000,d0
	beq.w	.o
	lsl.w	#3,d0			; columns L .. L+41 hold x 8L .. 8L+16
	cmp.w	TD_IGX,d0
	ble.s	.k1
	move.w	d0,TD_IGX
.k1:	add.w	#16+8*(TA_W-42),d0
	cmp.w	TD_IGX,d0
	bge.s	.k2
	move.w	d0,TD_IGX
.k2:	move.w	TA_T,d0			; rows T .. T+27: screen line 8 at
	lsl.w	#3,d0			; plane line IGY + 2
	subq.w	#2,d0
	cmp.w	TD_IGY,d0
	ble.s	.k3
	move.w	d0,TD_IGY
.k3:	add.w	#16,d0
	cmp.w	TD_IGY,d0
	bge.s	.sm
	move.w	d0,TD_IGY
.sm:	clr.w	TA_HELD
	lea	TD_IGX,a0		; held at the window's edge: the
	lea	TA_CX,a1		; easing goes on from there
	bsr.s	.rs
	lea	TD_IGY,a0
	lea	TA_CY,a1
.rs:	move.l	(a1),d0
	addq.l	#8,d0
	asr.l	#4,d0
	cmp.w	(a0),d0
	beq.s	.rs1
	move.w	(a0),d0
	ext.l	d0
	asl.l	#4,d0
	move.l	d0,(a1)
	move.w	#1,TA_HELD
.rs1:	rts
.far:	move.w	(a0),d0			; Z clear: (a0) 64 px or more from
	ext.l	d0			; the eased view (a1)
	asl.l	#4,d0
	sub.l	(a1),d0
	bpl.s	.fa
	neg.l	d0
.fa:	cmpi.w	#TD_TF,TD_PERIOD	; (the dragon: 4-6 cells a step
	beq.s	.fd			; glide too, #308)
	cmpi.l	#64*16,d0
	bra.s	.fe
.fd:	cmpi.l	#192*16,d0
.fe:	scc	d0
	tst.b	d0
	rts
.lim:	move.w	(a0),d0
	ext.l	d0
	asl.l	#4,d0			; target, 1/16 px
	move.l	d0,d1
	sub.l	(a1),d1			; how far
	move.l	d1,d2
	bpl.s	.l1
	neg.l	d2
.l1:	move.l	d3,-(a7)
	moveq	#3*16,d3		; at most 3 px a frame, 64 px: a snap
	cmpi.w	#TD_TF,TD_PERIOD	; (the dragon: 8, 192)
	bne.s	.ld
	cmpi.l	#192*16,d2
	bcc.s	.sx
	moveq	#8*16,d3
	bra.s	.le
.ld:	cmpi.l	#64*16,d2
	bcc.s	.sx
.le:	addq.l	#8,d2			; a 16th, rounded, the sign put back
	lsr.l	#4,d2
	cmp.l	d3,d2
	bls.s	.l2
	move.l	d3,d2
.l2:	move.l	(a7)+,d3
	tst.l	d1
	bpl.s	.l3
	neg.l	d2
.l3:	add.l	(a1),d2
	move.l	d2,d0
	bra.s	.sn
.sx:	move.l	(a7)+,d3
.sn:	move.l	d0,(a1)
	addq.l	#8,d0			; shown: the nearest pixel
	asr.l	#4,d0
	move.w	d0,(a0)
.o:	rts

ta_start:
ta_stream:	; main loop, every frame: the window follows the camera
	cmpi.w	#$5A71,TA_ON
	bne.w	.x
	movem.l	d2-d7/a2-a6,-(a7)
	tst.w	TA_LOST			; the game decoded into DECBUF: a short
	beq.s	.nlo			; decode (a portrait) only hit the hash
	cmpi.w	#1,TA_LOST		; heads (TA_LOST 1): them again from the
	bne.s	.lo			; slots; else all from scratch
	clr.w	TA_LOST
	bsr.w	ta_rehash
	bra.s	.g
.lo:	clr.w	TA_LOST
	bsr.w	ta_reset
	move.w	#$8000,TA_L
	bra.s	.g
.nlo:	tst.w	TA_BAD
	beq.s	.g
	clr.w	TA_BAD
	move.w	#$8000,TA_L
	lea	TA_SH,a0		; (nothing on the plane is known)
	move.w	#2048/2-1,d0
.z:	clr.l	(a0)+
	dbra	d0,.z
.g:
	move.w	$FF0E8E,TD_ICX		; the glide: no picture to stay near
	bsr.w	ta_spr
	move.w	$FF0E90,TD_ICY
	move.w	TA_GX,d6
	asr.w	#3,d6			; d6/d7 = wanted left column, top row
	sub.w	#(TA_W-42)/2,d6
	move.w	TA_GY,d7		; (rows 1-26 show the picture, 0 and
	addq.w	#2,d7			; 27 are the bars: ta_bar)
	asr.w	#3,d7
	cmpi.w	#$8000,TA_L
	beq.w	.full
	moveq	#8,d1			; (in VBlank: one line at most)
	tst.w	TA_INV
	beq.s	.mx
	moveq	#1,d1
.mx:	move.w	d6,d0
	sub.w	TA_L,d0
	bpl.s	.a
	neg.w	d0
.a:	cmp.w	d1,d0			; a jump: all of it again
	bhi.w	.full
	move.w	d7,d0
	sub.w	TA_T,d0
	bpl.s	.b
	neg.w	d0
.b:	cmp.w	d1,d0
	bhi.w	.full
.lp:	move.w	TA_L,d0
	cmp.w	d6,d0
	blt.s	.right
	bgt.s	.left
	move.w	TA_T,d0
	cmp.w	d7,d0
	blt.s	.down
	bgt.s	.up
	bra.w	.done
.right:	move.w	TA_L,d4
	bsr.w	ta_dcol
	add.w	#TA_W,d4
	bsr.w	ta_fcol
	addq.w	#1,TA_L
	bra.s	.lp
.left:	move.w	TA_L,d4
	add.w	#TA_W-1,d4
	bsr.w	ta_dcol
	sub.w	#TA_W,d4
	bsr.w	ta_fcol
	subq.w	#1,TA_L
	bra.s	.lp
.down:	move.w	TA_T,d5
	bsr.w	ta_drow
	add.w	#TA_H,d5
	bsr.w	ta_frow
	addq.w	#1,TA_T
	bra.s	.lp
.up:	move.w	TA_T,d5
	add.w	#TA_H-1,d5
	bsr.w	ta_drow
	sub.w	#TA_H,d5
	bsr.w	ta_frow
	subq.w	#1,TA_T
	bra.w	.lp
.full:
	tst.w	TA_INV			; not from VBlank: the main thread's
	bne.w	.vx			; job
	ifd	HELDPC
	move.w	FRAME,($FF7E30).l
	endif
	bsr.w	ta_norc
	move.w	d6,TA_L
	move.w	d7,TA_T
	addq.w	#1,TD_BUSY		; (no picture updates meanwhile: all
	move.w	#$8134,VDP_CTRL		; (the screen off meanwhile: a jump
	moveq	#TA_H-1,d3		; of it at once is quicker), from the
.fr:	moveq	#0,d5			; middle out: the leader's surroundings
	lea	ta_mid(pc),a0		; first (#308)
	move.b	(a0,d3.w),d5
	add.w	TA_T,d5
	bsr.w	ta_frow
	cmpi.w	#10,d3			; the game's picture in the window
	beq.s	.fw			; (drawn meanwhile): off, twice
	cmpi.w	#20,d3
	bne.s	.fn
.fw:	move.w	#1,TD_UNFR
	bsr.w	td_iso_winfix
	clr.w	TD_UNFR
.fn:	dbra	d3,.fr
	move.w	#$8174,VDP_CTRL		; showed old and new mixed, #308)
	subq.w	#1,TD_BUSY
	ifd	HELDPC
	move.w	FRAME,($FF7E32).l
	endif
.done:	tst.w	TA_INV			; from VBlank: the line, nothing else
	bne.w	.vx			; (ta_want / ta_lifts call the game,
	bsr.w	ta_want			; which the main thread is inside;
					; the scans take a frame; #308)
	cmp.w	TA_AR,d0
	bne.s	.end
	tst.w	TA_PR			; terrain phase (water): a changed
	bpl.s	.sw			; phase is swept in, 3 rows a frame
	bra.s	.end			; no tile animation in the pre-drawn
	bsr.w	ta_phnow		; view: the row sweep showed (#308)
	cmp.w	TA_PH,d0
	beq.s	.end
	move.w	d0,TA_PH
	clr.w	TA_PR
.sw:	moveq	#3-1,d3
.sr:	move.w	TA_T,d5
	add.w	TA_PR,d5
	bsr.w	ta_rerow
	addq.w	#1,TA_PR
	cmpi.w	#TA_H,TA_PR
	bcs.s	.sn
	move.w	#-1,TA_PR
	bra.s	.end
.sn:	dbra	d3,.sr
.end:	bsr.w	ta_pref			; the leader's images ready
	tst.w	TA_CTL			; his neighbours' lifts
	beq.s	.nl
	bsr.w	ta_lifts
.nl:	bsr.w	ta_hud			; no HUD words, every frame
	bsr.w	ta_bar			; the bars and their numbers
	bsr.w	ta_occ			; terrain in front of the leader
	tst.w	TA_WFF			; the window, often after a change
	beq.s	.nw
	subq.w	#1,TA_WFF
	move.w	TA_WFF,d0
	andi.w	#7,d0			; (every 8th frame: a scan is ~1 frame)
	bne.s	.nw
	bsr.w	td_winfix
	move.w	#1,TD_UNFR
	bsr.w	td_iso_winfix
	clr.w	TD_UNFR
.vx:
.nw:	movem.l	(a7)+,d2-d7/a2-a6
.x:	rts

ta_vstream:	; VBlank, the main thread busy in game logic (a long tick
	; in a big room) and the camera held at the window's edge: the
	; window catches up here, not when the tick ends (the stop and go
	; of the scroll, #308). Only in routines that leave DECBUF alone.
	cmpi.w	#$5A71,TA_ON
	bne.s	.x
	tst.w	TA_HELD
	beq.s	.x
	move.l	66+4(a7),d0		; interrupted PC (our caller's frame)
	lea	ta_vsl(pc),a0
.l:	move.l	(a0)+,d1
	beq.s	.x
	move.l	(a0)+,d2
	cmp.l	d1,d0
	bcs.s	.l
	cmp.l	d2,d0
	bcc.s	.l
	tst.w	TA_LOST			; only a line or so here: a refill
	bne.s	.x			; from VBlank took frames, and the
	tst.w	TA_BAD			; next VBlank did it again: the game
	bne.s	.x			; never ran (the freeze in the academy
	move.w	#1,TA_INV		; cutscene, #308)
	bsr.w	ta_stream
	clr.w	TA_INV
.x:	rts
ta_vsl:	dc.l	$02155E,$021FE6		; world_tick
	dc.l	$0226BC,$0231D8		; combat_turn_run
	dc.l	$024676,$024916		; map_grid_place_chars
	dc.l	$01C83E,$01D9BA		; location_divide, move_cost_calc
	dc.l	$00DE8E,$00DF58		; mul32 .. math_udiv32
	dc.l	mg_find,mg_fend		; the grid search
	dc.l	0

ta_pfetch:	; idle frames: the 3 lines of tiles past the window ahead of
	; the camera into the slot cache (no plane words): a column or row
	; the walk brings in then needs no uploads that frame (#308)
	cmpi.w	#$5A71,TA_ON
	bne.w	.x
	cmpi.w	#$8000,TA_L
	beq.w	.x
	movem.l	d2-d7,-(a7)
	move.w	TA_GX,d0		; the camera's way (the larger axis)
	sub.w	TA_PFGX,d0
	move.w	TA_GX,TA_PFGX
	move.w	TA_GY,d1
	sub.w	TA_PFGY,d1
	move.w	TA_GY,TA_PFGY
	move.w	d0,d2
	bpl.w	.a0
	neg.w	d2
.a0:	move.w	d1,d3
	bpl.w	.a1
	neg.w	d3
.a1:	move.w	TA_PFD,d4
	cmpi.w	#64,d2			; (a jump: not a way)
	bcc.w	.kd
	cmpi.w	#64,d3
	bcc.w	.kd
	cmp.w	d3,d2
	bcs.w	.vy
	tst.w	d0
	beq.w	.kd
	moveq	#1,d4
	tst.w	d0
	bpl.w	.kd
	moveq	#2,d4
	bra.w	.kd
.vy:	moveq	#3,d4
	tst.w	d1
	bpl.w	.kd
	moveq	#4,d4
.kd:	cmp.w	TA_PFD,d4		; a new way or window: from the start
	bne.w	.rs
	move.w	TA_L,d0
	cmp.w	TA_PFL,d0
	bne.w	.rs
	move.w	TA_T,d0
	cmp.w	TA_PFT,d0
	beq.w	.go
.rs:	move.w	d4,TA_PFD
	move.w	TA_L,TA_PFL
	move.w	TA_T,TA_PFT
	clr.w	TA_PFP
.go:	tst.w	d4
	beq.w	.o
	moveq	#TA_H,d6		; line length: a column TA_H, a row TA_W
	cmpi.w	#3,d4
	bcs.w	.ll
	moveq	#TA_W,d6
.ll:	moveq	#6-1,d7			; 6 tiles a frame
.l:	move.w	TA_PFP,d0
	move.w	d6,d1
	mulu.w	#3,d1
	cmp.w	d1,d0
	bcc.w	.o
	addq.w	#1,TA_PFP
	ext.l	d0
	divu.w	d6,d0			; d0 = line, high word = place
	move.l	d0,d1
	swap	d1
	move.w	TA_PFD,d2
	cmpi.w	#2,d2
	bhi.w	.row
	move.w	TA_T,d5			; columns: row = top + place
	add.w	d1,d5
	move.w	TA_L,d4
	cmpi.w	#1,d2
	bne.w	.lf
	add.w	#TA_W,d4		; right: past the last column
	add.w	d0,d4
	bra.w	.f
.lf:	subq.w	#1,d4			; left: before the first
	sub.w	d0,d4
	bra.w	.f
.row:	move.w	TA_L,d4			; rows: column = left + place
	add.w	d1,d4
	move.w	TA_T,d5
	cmpi.w	#3,d2
	bne.w	.up
	add.w	#TA_H,d5
	add.w	d0,d5
	bra.w	.f
.up:	subq.w	#1,d5
	sub.w	d0,d5
.f:	bsr.w	ta_look
	tst.l	d0
	bmi.w	.n
	bsr.w	ta_get
.n:	dbra	d7,.l
.o:	movem.l	(a7)+,d2-d7
.x:	rts

ta_phnow:	; -> d0 = the game's terrain phase (0/1)
	moveq	#0,d0
	tst.w	$FF0092
	beq.s	.o
	moveq	#1,d0
.o:	rts

ta_rerow:	; d5 = row: its cells again (the phase changed)
	movem.l	d3-d4,-(a7)
	move.w	TA_L,d4
	moveq	#TA_W-1,d3
.l:	bsr.w	ta_drop
	bsr.w	ta_fill
	addq.w	#1,d4
	dbra	d3,.l
	movem.l	(a7)+,d3-d4
	rts

ta_mid:	; .full row order (indexed by the count down): the middle out
	dc.b	0,27,1,26,2,25,3,24,4,23,5,22,6,21,7,20,8,19,9,18,10,17,11,16,12,15,13,14
	even

ta_frow:	; d5 = row: its 42 cells from TA_L
	movem.l	d3-d4,-(a7)
	move.w	TA_L,d4
	moveq	#TA_W-1,d3
.l:	bsr.w	ta_fill
	addq.w	#1,d4
	dbra	d3,.l
	movem.l	(a7)+,d3-d4
	rts

ta_fcol:	; d4 = column: its TA_H cells from TA_T
	movem.l	d3/d5,-(a7)
	move.w	TA_T,d5
	moveq	#TA_H-1,d3
.l:	bsr.w	ta_fill
	addq.w	#1,d5
	dbra	d3,.l
	movem.l	(a7)+,d3/d5
	rts

ta_drow:	; d5 = row leaves the window
	movem.l	d3-d4,-(a7)
	move.w	TA_L,d4
	moveq	#TA_W-1,d3
.l:	bsr.s	ta_drop
	addq.w	#1,d4
	dbra	d3,.l
	movem.l	(a7)+,d3-d4
	rts

ta_dcol:	; d4 = column leaves the window
	movem.l	d3/d5,-(a7)
	move.w	TA_T,d5
	moveq	#TA_H-1,d3
.l:	bsr.s	ta_drop
	addq.w	#1,d5
	dbra	d3,.l
	movem.l	(a7)+,d3/d5
	rts

ta_cell:	; d5 = row, d4 = column -> d0 = plane cell * 2
	move.w	d5,d0
	andi.w	#31,d0
	lsl.w	#6,d0
	move.w	d4,d1
	andi.w	#63,d1
	or.w	d1,d0
	add.w	d0,d0
	rts

ta_drop:	; the cell (d5, d4) stops using its slot
	bsr.s	ta_cell
	lea	TA_SH,a0
	move.w	(a0,d0.w),d0
	beq.s	.o
	cmpi.w	#$FFFF,d0
	beq.s	.o
	subq.w	#1,d0
	add.w	d0,d0
	lea	TA_RC,a0
	subq.w	#1,(a0,d0.w)
.o:	rts

ta_fill:	; the cell (d5, d4) <- its atlas tile (keeps d2-d7)
	movem.l	d2-d3/a2,-(a7)
	bsr.w	ta_look
	tst.l	d0
	bmi.s	.blank
	bsr.w	ta_get
	tst.w	d0
	bmi.s	.blank
	lea	TA_RC,a0
	add.w	d0,d0
	addq.w	#1,(a0,d0.w)
	lsr.w	#1,d0
	addq.w	#1,d0
	bra.s	.put
.blank:	move.w	#$FFFF,d0
.put:	move.w	d0,d3
	bsr.s	ta_cell
	lea	TA_SH,a2
	cmp.w	(a2,d0.w),d3
	beq.s	.o
	move.w	d3,(a2,d0.w)
	move.w	d0,d2			; plane B address (table $0000)
	move.w	FONTBLK,d1
	cmpi.w	#$FFFF,d3
	beq.s	.w
	move.w	d3,d0
	subq.w	#1,d0
	bsr.w	ta_vt
	move.w	d0,d1
.w:	move.w	d2,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	bsr.w	td_vwrite
	move.w	d1,VDP_DATA
	move.w	(a7)+,sr
.o:	movem.l	(a7)+,d2-d3/a2
	rts

ta_vt:	; d0 = slot -> d0 = its VRAM tile: bank 64-272 (0-63: the game
	; writes its message there), 401-827, rec 6's 436-873
	cmpi.w	#209,d0
	bcs.s	.b
	cmpi.w	#636,d0
	bcs.s	.c
	cmpi.w	#1074,d0
	bcs.s	.r6
	add.w	#1834-1074,d0
	rts
.r6:	add.w	#436-636,d0
	rts
.c:	add.w	#401-209-64,d0
.b:	add.w	#64,d0
	add.w	TD_BASE,d0
	rts

ta_look:	; d5 = row, d4 = column -> d0.l = tile id, -1 blank
	; (uses d1-d2/a0-a1; TA_LDB = depth byte, TA_LROW = atlas row)
	movea.l	TA_A,a1
	move.w	d5,d1
	add.w	8(a1),d1		; atlas row
	move.w	d1,TA_LROW
	bmi.w	.out
	cmp.w	(a1),d1
	bcc.w	.out
	move.w	d4,d2
	add.w	10(a1),d2		; atlas column
	bmi.w	.out
	cmp.w	2(a1),d2
	bcc.w	.out
.in:	move.w	d1,d0			; block (row / 16) * BC + column / 16
	lsr.w	#4,d0
	mulu.w	6(a1),d0
	move.w	d2,-(a7)
	lsr.w	#4,d2
	add.w	d2,d0
	move.w	(a7)+,d2
	lsl.w	#2,d0
	lea	20(a1),a0
	move.l	(a0,d0.w),d0
	beq.w	.bl
	move.w	d1,-(a7)
	bsr.w	ta_map6
	move.w	(a7)+,d1		; its pair: u8 at (r & 15) 16 + c & 15
	andi.w	#15,d1
	lsl.w	#4,d1
	andi.w	#15,d2
	or.w	d2,d1
	moveq	#0,d0
	move.b	(a0,d1.w),d0		; pair k
	move.w	d0,-(a7)
	lea	256(a0),a0
	move.b	(a0,d1.w),d0		; its depth byte
	move.w	d0,TA_LDB
	move.w	(a7)+,d0
	lea	256(a0),a0
	move.w	(a0)+,d2		; m: pairs 0..m-1 differ by phase
	move.w	d0,d1			; 3 k
	add.w	d0,d0
	add.w	d1,d0
	cmp.w	d2,d1
	bcc.s	.p0			; k >= m: the same in both phases
	tst.w	TA_PH
	bne.s	.rd			; phase 1: the k-th u24 of m
.p0:	add.w	d2,d0			; phase 0: past the m phase-1 ids
	add.w	d2,d0
	add.w	d2,d0
.rd:	adda.w	d0,a0			; (u24 at any address: by bytes)
	moveq	#0,d0
	move.b	(a0)+,d0
	swap	d0
	move.b	(a0)+,d1
	lsl.w	#8,d1
	move.b	(a0),d1
	move.w	d1,d0
.o:	rts
.out:	; past the canvas of a zone that repeats (#308): its picture at
	; atlas row % period rows, column % period columns
	movea.l	16(a1),a0
	tst.w	112(a0)
	beq.s	.bl
	ext.l	d1
	divs.w	112(a0),d1
	swap	d1
	tst.w	d1
	bpl.s	.r1
	add.w	112(a0),d1
.r1:	move.w	d4,d2
	add.w	10(a1),d2
	ext.l	d2
	divs.w	114(a0),d2
	swap	d2
	tst.w	d2
	bpl.s	.c1
	add.w	114(a0),d2
.c1:	bsr.w	.in
	move.w	#$FF,TA_LDB		; (nothing in front of anyone)
	rts
.bl:	; past the canvas, or a block not stored: the filler pattern (no
	; pink void), tile (row % 2) 7 + column % 7 of the area's 2 x 14
	move.w	d5,d1
	add.w	8(a1),d1		; atlas row, column (either sign)
	move.w	d4,d2
	add.w	10(a1),d2
	add.w	#7*2000,d2
	andi.l	#$FFFF,d2
	divu.w	#7,d2
	swap	d2
	andi.w	#1,d1
	mulu.w	#7,d1
	add.w	d2,d1
	tst.w	TA_PH
	beq.s	.b0
	add.w	#14,d1
.b0:	lsl.w	#2,d1
	movea.l	16(a1),a0
	move.l	(a0,d1.w),d0
	move.w	#$FF,TA_LDB		; (nothing in front of anyone)
	rts

ta_map6:	; d0 = ROM address -> a0 = where the CPU sees it (slot 6)
	cmpi.l	#$300000,d0
	bcs.s	.d
	move.l	d0,d1
	swap	d1
	lsr.w	#3,d1			; 512 KB bank
	cmp.w	TA_B6,d1
	beq.s	.s
	move.w	d1,TA_B6
	move.b	d1,$A130FD
.s:	andi.l	#$7FFFF,d0
	addi.l	#$300000,d0
.d:	movea.l	d0,a0
	rts

ta_get:	; d0.l = tile id -> d0.w = its slot (uploaded), -1 none free
	movem.l	d2-d4/a2,-(a7)
	move.l	d0,d4
	bsr.w	ta_hash			; d2 = bucket * 2
	lea	TA_HEAD,a0
	move.w	(a0,d2.w),d0
	lea	TA_ID,a1
	lea	TA_NX,a2
.f:	tst.w	d0
	beq.s	.miss
	subq.w	#1,d0
	move.w	d0,d1
	lsl.w	#2,d1
	cmp.l	(a1,d1.w),d4
	beq.w	.o
	add.w	d0,d0
	move.w	(a2,d0.w),d0
	bra.s	.f
.miss:	lea	TA_RC,a2		; a free slot from the hand on (a tight
	move.w	TA_HAND,d0		; scan: with the window full it walked
	move.w	d0,d1			; most of the slots, a quarter of a big
	add.w	d1,d1			; room's time, #308)
	lea	(a2,d1.w),a0
	move.w	#TA_N-1,d3
	sub.w	d0,d3
.s:	tst.w	(a0)+
	dbeq	d3,.s
	beq.s	.fnd
	movea.l	a2,a0			; then from the start to the hand
	move.w	d0,d3
	subq.w	#1,d3
	bmi.s	.none
.s2:	tst.w	(a0)+
	dbeq	d3,.s2
	beq.s	.fnd
.none:	moveq	#-1,d0
	bra.s	.o
.fnd:	move.l	a0,d0
	sub.l	a2,d0
	lsr.w	#1,d0
	subq.w	#1,d0
.got:	move.w	d0,d1
	addq.w	#1,d1
	cmpi.w	#TA_N,d1
	bcs.s	.g1
	moveq	#0,d1
.g1:	move.w	d1,TA_HAND
	bsr.s	ta_unlink
	lea	TA_ID,a1		; the slot: id, first in its bucket
	move.w	d0,d1
	lsl.w	#2,d1
	move.l	d4,(a1,d1.w)
	lea	TA_HEAD,a0
	lea	TA_NX,a2
	move.w	d0,d1
	add.w	d1,d1
	move.w	(a0,d2.w),(a2,d1.w)
	move.w	d0,d1
	addq.w	#1,d1
	move.w	d1,(a0,d2.w)
	bsr.w	ta_up
.o:	movem.l	(a7)+,d2-d4/a2
	rts

ta_hash:	; d4.l = id -> d2 = bucket * 2 (uses d1)
	move.l	d4,d1
	lsr.l	#8,d1
	lsr.l	#1,d1
	move.w	d4,d2
	eor.w	d1,d2
	andi.w	#511,d2
	add.w	d2,d2
	rts

ta_unlink:	; d0 = slot: out of its bucket (keeps d0, d2, d4)
	movem.l	d0/d2/d4,-(a7)
	move.w	d0,d3
	lsl.w	#2,d0
	lea	TA_ID,a1
	move.l	(a1,d0.w),d4
	bmi.s	.o			; free
	bsr.s	ta_hash
	lea	TA_HEAD,a0
	adda.w	d2,a0			; a0 -> the link holding slot + 1
	lea	TA_NX,a2
	move.w	d3,d1
	addq.w	#1,d1
.w:	move.w	(a0),d0
	beq.s	.o
	cmp.w	d1,d0
	beq.s	.cut
	subq.w	#1,d0
	add.w	d0,d0
	lea	(a2,d0.w),a0
	bra.s	.w
.cut:	add.w	d3,d3
	move.w	(a2,d3.w),(a0)
.o:	movem.l	(a7)+,d0/d2/d4
	rts

ta_tget:	; d1.l = tile id, a2 = 32-byte buffer -> a0 = its 32 bytes
	; (uses d1-d2): ids from ATL+714 on are half-width, 16 bytes at
	; ATL+718 on, each pixel doubled here; from ATL+722 on: material
	; noise, made here from the one field all materials share (#308)
	cmp.l	ATL+734,d1		; a composite: ground + overlay
	bcc.w	ta_comp
	cmp.l	ATL+722,d1
	bcc.s	.g
	cmp.l	ATL+714,d1
	bcc.s	.h
	lsl.l	#5,d1
	movea.l	TA_A,a0
	add.l	12(a0),d1		; ROM address, in slot 7's window
	bra.w	ta_t7
.h:	sub.l	ATL+714,d1
	lsl.l	#4,d1
	add.l	ATL+718,d1
	bsr.w	ta_t7
	move.l	a1,-(a7)
	move.l	a2,-(a7)
	move.l	a3,-(a7)
	lea	ta_dbl(pc),a1		; even rows p p q q, odd rows p q p q
	lea	512(a1),a3		; (a dither where the half pixels
	moveq	#4-1,d2			; change: detail back, #308)
.e:	moveq	#0,d1
	move.b	(a0)+,d1
	add.w	d1,d1
	move.w	(a1,d1.w),(a2)+
	moveq	#0,d1
	move.b	(a0)+,d1
	add.w	d1,d1
	move.w	(a1,d1.w),(a2)+
	moveq	#0,d1
	move.b	(a0)+,d1
	add.w	d1,d1
	move.w	(a3,d1.w),(a2)+
	moveq	#0,d1
	move.b	(a0)+,d1
	add.w	d1,d1
	move.w	(a3,d1.w),(a2)+
	dbra	d2,.e
	movea.l	(a7)+,a3
	movea.l	(a7)+,a0
	movea.l	(a7)+,a1
	rts
.g:	sub.l	ATL+722,d1		; material 8 + variant
ta_gen:	; d1 = material 8 + variant, a2 = buffer -> a0 = a2, its noise
	movem.l	d0/d3-d6/a1-a3,-(a7)
	moveq	#7,d2
	and.w	d1,d2
	lsr.l	#3,d1
	lsl.l	#3,d1
	movea.l	ATL+726,a1
	adda.l	d1,a1			; c0 c1 c2 c3 t1 t2 t3 shift
	sub.b	7(a1),d2		; field row (variant - shift) & 7
	andi.w	#7,d2
	lsl.w	#6,d2
	movea.l	ATL+730,a0
	adda.w	d2,a0
	movea.l	a2,a3
	move.b	4(a1),d3
	move.b	5(a1),d4
	move.b	6(a1),d5
	moveq	#32-1,d6
.gp:	bsr.s	.px			; left pixel
	lsl.b	#4,d1
	move.b	d1,d2
	bsr.s	.px
	or.b	d1,d2
	move.b	d2,(a3)+
	dbra	d6,.gp
	movea.l	a2,a0
	movem.l	(a7)+,d0/d3-d6/a1-a3
	rts
.px:	moveq	#0,d1			; colour of the next field byte
	move.b	(a0)+,d0
	cmp.b	d3,d0
	bcs.s	.p
	addq.w	#1,d1
	cmp.b	d4,d0
	bcs.s	.p
	addq.w	#1,d1
	cmp.b	d5,d0
	bcs.s	.p
	addq.w	#1,d1
.p:	move.b	(a1,d1.w),d1
	rts
ta_comp:	; d1 = composite id: material noise, the object overlay over it
	sub.l	ATL+734,d1		; overlay 128 + material
	movem.l	d0/d3-d6/a1/a3,-(a7)
	move.l	d1,d6
	lsr.l	#7,d6			; d6 = overlay
	andi.l	#127,d1
	lsl.w	#3,d1
	moveq	#7,d0			; variant: the overlay's low bits
	and.w	d6,d0
	or.w	d0,d1
	bsr.w	ta_gen			; the ground into (a2)
	move.l	d6,d0			; its group of 8: address
	lsr.l	#3,d0
	lsl.l	#2,d0
	add.l	ATL+738,d0
	bsr.w	ta_map6
	move.l	(a0),d1
	bsr.w	ta_t7			; a0 = the group (one bank)
	lea	ta_pop(pc),a1
	moveq	#7,d5
	and.w	d6,d5
	bra.s	.sk1
.sk:	moveq	#0,d3			; skip one: 8 mask bytes + pixels
	moveq	#8-1,d4
.sc:	moveq	#0,d0
	move.b	(a0)+,d0
	add.b	(a1,d0.w),d3
	dbra	d4,.sc
	addq.w	#1,d3
	lsr.w	#1,d3
	adda.w	d3,a0
.sk1:	dbra	d5,.sk
	lea	8(a0),a1		; a1 = its pixels, 2 a byte
	movea.l	a2,a3
	moveq	#0,d5			; nibble: 0 high next
	moveq	#8-1,d6
.mb:	move.b	(a0)+,d3
	moveq	#4-1,d4
.pb:	add.b	d3,d3
	bcc.s	.h0
	bsr.s	.nib
	lsl.b	#4,d0
	andi.b	#$0F,(a3)
	or.b	d0,(a3)
.h0:	add.b	d3,d3
	bcc.s	.l0
	bsr.s	.nib
	andi.b	#$F0,(a3)
	or.b	d0,(a3)
.l0:	addq.l	#1,a3
	dbra	d4,.pb
	dbra	d6,.mb
	movea.l	a2,a0
	movem.l	(a7)+,d0/d3-d6/a1/a3
	rts
.nib:	move.b	(a1),d0
	not.b	d5
	beq.s	.lo
	lsr.b	#4,d0
	rts
.lo:	andi.b	#$0F,d0
	addq.l	#1,a1
	rts

ta_t7:	move.l	d1,d2			; d1 = ROM address -> a0 (slot 7)
	swap	d2
	lsr.w	#3,d2
	cmp.w	TA_B7,d2
	beq.s	.s
	move.w	d2,TA_B7
	move.b	d2,$A130FF
.s:	andi.l	#$7FFFF,d1
	addi.l	#$380000,d1
	movea.l	d1,a0
	rts

ta_up:	; slot d0 <- the 32 bytes of tile d4 (keeps d0)
	movem.l	d0/d2/a2,-(a7)
	move.l	d4,d1
	lea	TD_HB1,a2
	bsr.w	ta_tget
	bsr.w	ta_vt
	lsl.w	#5,d0
	move.w	sr,-(a7)
	move.w	#$2700,sr
	bsr.w	td_vwrite
	lea	VDP_DATA,a1
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.l	(a0)+,(a1)
	move.w	(a7)+,sr
	movem.l	(a7)+,d0/d2/a2
	rts

ta_pop:	; bits set per byte
	dc.b	0,1,1,2,1,2,2,3,1,2,2,3,2,3,3,4
	dc.b	1,2,2,3,2,3,3,4,2,3,3,4,3,4,4,5
	dc.b	1,2,2,3,2,3,3,4,2,3,3,4,3,4,4,5
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	1,2,2,3,2,3,3,4,2,3,3,4,3,4,4,5
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	3,4,4,5,4,5,5,6,4,5,5,6,5,6,6,7
	dc.b	1,2,2,3,2,3,3,4,2,3,3,4,3,4,4,5
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	3,4,4,5,4,5,5,6,4,5,5,6,5,6,6,7
	dc.b	2,3,3,4,3,4,4,5,3,4,4,5,4,5,5,6
	dc.b	3,4,4,5,4,5,5,6,4,5,5,6,5,6,6,7
	dc.b	3,4,4,5,4,5,5,6,4,5,5,6,5,6,6,7
	dc.b	4,5,5,6,5,6,6,7,5,6,6,7,6,7,7,8

ta_dbl:	; byte -> word, each pixel doubled
	dc.w	$0000,$0011,$0022,$0033,$0044,$0055,$0066,$0077,$0088,$0099,$00AA,$00BB,$00CC,$00DD,$00EE,$00FF
	dc.w	$1100,$1111,$1122,$1133,$1144,$1155,$1166,$1177,$1188,$1199,$11AA,$11BB,$11CC,$11DD,$11EE,$11FF
	dc.w	$2200,$2211,$2222,$2233,$2244,$2255,$2266,$2277,$2288,$2299,$22AA,$22BB,$22CC,$22DD,$22EE,$22FF
	dc.w	$3300,$3311,$3322,$3333,$3344,$3355,$3366,$3377,$3388,$3399,$33AA,$33BB,$33CC,$33DD,$33EE,$33FF
	dc.w	$4400,$4411,$4422,$4433,$4444,$4455,$4466,$4477,$4488,$4499,$44AA,$44BB,$44CC,$44DD,$44EE,$44FF
	dc.w	$5500,$5511,$5522,$5533,$5544,$5555,$5566,$5577,$5588,$5599,$55AA,$55BB,$55CC,$55DD,$55EE,$55FF
	dc.w	$6600,$6611,$6622,$6633,$6644,$6655,$6666,$6677,$6688,$6699,$66AA,$66BB,$66CC,$66DD,$66EE,$66FF
	dc.w	$7700,$7711,$7722,$7733,$7744,$7755,$7766,$7777,$7788,$7799,$77AA,$77BB,$77CC,$77DD,$77EE,$77FF
	dc.w	$8800,$8811,$8822,$8833,$8844,$8855,$8866,$8877,$8888,$8899,$88AA,$88BB,$88CC,$88DD,$88EE,$88FF
	dc.w	$9900,$9911,$9922,$9933,$9944,$9955,$9966,$9977,$9988,$9999,$99AA,$99BB,$99CC,$99DD,$99EE,$99FF
	dc.w	$AA00,$AA11,$AA22,$AA33,$AA44,$AA55,$AA66,$AA77,$AA88,$AA99,$AAAA,$AABB,$AACC,$AADD,$AAEE,$AAFF
	dc.w	$BB00,$BB11,$BB22,$BB33,$BB44,$BB55,$BB66,$BB77,$BB88,$BB99,$BBAA,$BBBB,$BBCC,$BBDD,$BBEE,$BBFF
	dc.w	$CC00,$CC11,$CC22,$CC33,$CC44,$CC55,$CC66,$CC77,$CC88,$CC99,$CCAA,$CCBB,$CCCC,$CCDD,$CCEE,$CCFF
	dc.w	$DD00,$DD11,$DD22,$DD33,$DD44,$DD55,$DD66,$DD77,$DD88,$DD99,$DDAA,$DDBB,$DDCC,$DDDD,$DDEE,$DDFF
	dc.w	$EE00,$EE11,$EE22,$EE33,$EE44,$EE55,$EE66,$EE77,$EE88,$EE99,$EEAA,$EEBB,$EECC,$EEDD,$EEEE,$EEFF
	dc.w	$FF00,$FF11,$FF22,$FF33,$FF44,$FF55,$FF66,$FF77,$FF88,$FF99,$FFAA,$FFBB,$FFCC,$FFDD,$FFEE,$FFFF
ta_dbl2:	; odd rows: p q p q
	dc.w	$0000,$0101,$0202,$0303,$0404,$0505,$0606,$0707,$0808,$0909,$0A0A,$0B0B,$0C0C,$0D0D,$0E0E,$0F0F
	dc.w	$1010,$1111,$1212,$1313,$1414,$1515,$1616,$1717,$1818,$1919,$1A1A,$1B1B,$1C1C,$1D1D,$1E1E,$1F1F
	dc.w	$2020,$2121,$2222,$2323,$2424,$2525,$2626,$2727,$2828,$2929,$2A2A,$2B2B,$2C2C,$2D2D,$2E2E,$2F2F
	dc.w	$3030,$3131,$3232,$3333,$3434,$3535,$3636,$3737,$3838,$3939,$3A3A,$3B3B,$3C3C,$3D3D,$3E3E,$3F3F
	dc.w	$4040,$4141,$4242,$4343,$4444,$4545,$4646,$4747,$4848,$4949,$4A4A,$4B4B,$4C4C,$4D4D,$4E4E,$4F4F
	dc.w	$5050,$5151,$5252,$5353,$5454,$5555,$5656,$5757,$5858,$5959,$5A5A,$5B5B,$5C5C,$5D5D,$5E5E,$5F5F
	dc.w	$6060,$6161,$6262,$6363,$6464,$6565,$6666,$6767,$6868,$6969,$6A6A,$6B6B,$6C6C,$6D6D,$6E6E,$6F6F
	dc.w	$7070,$7171,$7272,$7373,$7474,$7575,$7676,$7777,$7878,$7979,$7A7A,$7B7B,$7C7C,$7D7D,$7E7E,$7F7F
	dc.w	$8080,$8181,$8282,$8383,$8484,$8585,$8686,$8787,$8888,$8989,$8A8A,$8B8B,$8C8C,$8D8D,$8E8E,$8F8F
	dc.w	$9090,$9191,$9292,$9393,$9494,$9595,$9696,$9797,$9898,$9999,$9A9A,$9B9B,$9C9C,$9D9D,$9E9E,$9F9F
	dc.w	$A0A0,$A1A1,$A2A2,$A3A3,$A4A4,$A5A5,$A6A6,$A7A7,$A8A8,$A9A9,$AAAA,$ABAB,$ACAC,$ADAD,$AEAE,$AFAF
	dc.w	$B0B0,$B1B1,$B2B2,$B3B3,$B4B4,$B5B5,$B6B6,$B7B7,$B8B8,$B9B9,$BABA,$BBBB,$BCBC,$BDBD,$BEBE,$BFBF
	dc.w	$C0C0,$C1C1,$C2C2,$C3C3,$C4C4,$C5C5,$C6C6,$C7C7,$C8C8,$C9C9,$CACA,$CBCB,$CCCC,$CDCD,$CECE,$CFCF
	dc.w	$D0D0,$D1D1,$D2D2,$D3D3,$D4D4,$D5D5,$D6D6,$D7D7,$D8D8,$D9D9,$DADA,$DBDB,$DCDC,$DDDD,$DEDE,$DFDF
	dc.w	$E0E0,$E1E1,$E2E2,$E3E3,$E4E4,$E5E5,$E6E6,$E7E7,$E8E8,$E9E9,$EAEA,$EBEB,$ECEC,$EDED,$EEEE,$EFEF
	dc.w	$F0F0,$F1F1,$F2F2,$F3F3,$F4F4,$F5F5,$F6F6,$F7F7,$F8F8,$F9F9,$FAFA,$FBFB,$FCFC,$FDFD,$FEFE,$FFFF
ta_end:
	endif
