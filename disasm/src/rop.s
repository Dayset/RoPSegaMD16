; Rings of Power (Mega Drive, USA/Europe) — rebuild root (issues #012, #009).
; Every byte is an incbin slice of rop-original.gen; nothing is hand-typed.
; Assembled by tools/build.sh with vasmm68k_mot from the repository root.
; Slices so far (start, length):
;   $000000 +$400    68000 vector table (verified in ROM header/vectors)
;   $000400 +$100    unlabelled, data until proven code
;   $000500 +$FFB00  remainder of ROM, to be sliced per region in #012 follow-ups
	section rom,data
	xdef rom_start
rom_start:
	incbin "rop-original.gen",$000000,$400
	incbin "rop-original.gen",$000400,$100
	incbin "rop-original.gen",$000500,$FFB00
