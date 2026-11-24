; sram-save — the 128-byte save in header-declared SRAM instead of the
; serial EEPROM (#284). Added by tools/build_rom.py to every ROM larger
; than 1 MB, so BlastEm, Genesis Plus GX, other emulators, flash carts
; and SRAM repro boards all map the save from the header alone: no
; rom.db entry or EEPROM database match is needed (header.py gives the
; ROM its own product ID so the T-50176 entries no longer apply).
;
; The game's save code ($17706/$177B4) is unchanged: it still calls the
; EEPROM block read ($43012) and byte write ($430F4) and checks their
; error count $FF014E. Both are replaced here; the bit-bang delay
; ($42FD8, reached from eeprom_init) returns at once, so nothing is
; written to $200000 any more (a word write there would land in SRAM).
; SRAM byte n is at $200001 + 2n (odd bytes, 128 of them, header
; $1B0). $A130F1 = 1 maps SRAM over ROM on boards larger than 2 MB
; (Sega mapper); on a 2 MB board it is mapped anyway and the write is
; ignored. Interrupts are held while SRAM is mapped in.
	org	ORGVAL

SRAM	equ	$200001
SRBANK	equ	$A130F1
ERRCNT	equ	$FF014E

sr_read:	; d0 = save address, d1.w = count, a0 = buffer
	movem.l	d0-d2/a0-a1,-(a7)
	bsr.s	sr_on
	subq.w	#1,d1
.byte:	moveq	#$7F,d2
	and.w	d0,d2
	add.w	d2,d2
	move.b	(a1,d2.w),(a0)+
	addq.w	#1,d0
	dbra	d1,.byte
	bra.s	sr_off

sr_write:	; d0 = save address, a0 = the byte
	movem.l	d0-d2/a0-a1,-(a7)
	bsr.s	sr_on
	moveq	#$7F,d2
	and.w	d0,d2
	add.w	d2,d2
	move.b	(a0),(a1,d2.w)
sr_off:	move.b	#0,SRBANK
	move.w	(a7)+,sr
	clr.w	ERRCNT
	movem.l	(a7)+,d0-d2/a0-a1
	rts

sr_on:	move.l	(a7)+,a1		; return address
	move.w	sr,-(a7)
	move.w	#$2700,sr
	move.b	#1,SRBANK
	move.l	a1,-(a7)
	lea	SRAM,a1
sr_none:	rts
