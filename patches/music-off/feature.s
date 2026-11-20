; music-off feature.s — "Quiet" actually stops the music (issue #239).
;
; Port of patches/music-off (README.md there documents the bug and the
; design in full). Two trampolines in free space; the hooks are in
; hooks.csv. This file never hardcodes where it lands: it starts with
; `org ORGVAL`, and tools/build_rom.py supplies ORGVAL as the
; allocator-chosen address. All in-blob branches are PC-relative
; (labels); the absolute-long references are fixed game addresses.
;
; Trampoline A (music_off_gate, 32 bytes): hooked at $173C0, replacing
; `move.w $FF012E,d0` in $173BC (request-song). While Quiet (song index
; 18, $12) is active, any request for a different song (i.e. every
; location change) returns without playing and without overwriting
; $FF012E. The displaced instruction is re-executed first; the return
; address is rewritten to $173BC's exit ($173D6) to skip the request.
;
; Trampoline B (music_off_stop, 72 bytes): hooked at $173F4, replacing
; `ext.l d0; bra.w $17570` in $173EC (dispatch). The jsr pushed a
; return address ($173FA); every exit discards it with `addq.w #4,sp`
; and jumps to a $173EC-internal address, so the stack is exactly as
; $173EC left it after `link a6,#0`. Quiet requested -> STOP (mark
; Quiet active, stop the music via the dead $EB7C8 routine, but only
; if $EB9C4 says music is actually playing, so an SFX is never
; truncated). Quiet active -> BLOCK (return, no play). Otherwise ->
; normal dispatch through the jump table at $17570.
;
; Layout (byte-identical to the original hand-built patch, so
; `make rom FEATURES=music-off` reproduces the existing IPS):
;   gate 32 bytes, 4 bytes of $FF gap, stop 72 bytes = 108 bytes.
; The $FF bytes inside the absolute-long addresses ($FF012E) are
; emitted by the assembler; the original IPS does not record them
; because they were already $FF in the padding.

	org ORGVAL

music_off_gate:
	move.w $FF012E,d0		; replicate replaced instruction
	cmpi.w #$12,d0			; Quiet active? ($FF012E == 18)
	bne.w music_off_gate_ret	; no  -> normal return to $173C6
	cmpi.w #$12,8(a6)		; requested == 18?
	beq.w music_off_gate_ret	; yes -> normal (re-pick Quiet)
	move.l #$173D6,(a7)		; no  -> return to $173BC's exit instead
music_off_gate_ret:
	rts				; (unlk a6; rts) — song request skipped

	dc.l $FFFFFFFF			; gap between the trampolines

music_off_stop:
	ext.l d0			; replicate replaced instruction
	cmpi.w #$12,d0			; Quiet requested?
	beq.w music_off_stop_do		; yes -> STOP
	cmpi.w #$12,$FF012E		; Quiet active?
	beq.w music_off_stop_block	; yes -> BLOCK (return, no play)
	addq.w #4,sp
	jmp $17570.l			; normal dispatch (jump table)
music_off_stop_block:
	addq.w #4,sp			; BLOCK
	jmp $17582.l			; unlk a6; rts
music_off_stop_do:
	move.w #$12,$FF012E		; STOP: mark Quiet active first
	jsr $EB9C4.l			; is music actually playing?
	tst.w d0
	beq.w music_off_stop_block	; no  -> just return (no Z80 reset)
	jsr $EB7C8.l			; yes -> stop it (the dead routine)
	addq.w #4,sp
	jmp $17582.l			; unlk a6; rts
