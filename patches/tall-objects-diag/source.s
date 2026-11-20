; tall-objects-diag source.s -- the fix, as data.
; Base: rop-tall-objects.rom (MD5 9846c168f559bb8acf4a14aca46623b7).
; Diagnosis (probe-verified): .blocked IS taken (43 tall calls per
; render in the Academy room, loc 156 / chunk 233) and the tall
; patterns ARE written and survive in the buffer (129 tall-top +
; 31 tall-base tiles in a complete render). The tall objects were
; invisible because the tall TOP blended with the land: its average
; luminance (idx 11 lum 182 / idx 9 lum 109 -> 145.5) sits squarely
; inside land's range (127-173), so the 129 surviving bright tiles
; read as ground, not as objects. The dark base (idx 7/0, avg 36)
; is the only distinctive part, but only 24% of base writes survive
; (31/129) -- the rest are overwritten by later-drawn cells -- and
; the survivors are scattered single tiles, not a coherent band.
;
; Fix: make the tall TOP solid white (palette idx 15), the brightest
; index in both palettes (day pal 10: lum 255; night pal 19: lum 117)
; and an index land/water never use. The tall object becomes an
; unmistakable solid highlight. The dark base is unchanged.
;
; Change: noise_tbl[8] (tall top-even) and noise_tbl[9] (tall top-odd),
; loaded by .blocked at $FD4AA / $FD4AE (offsets 32 / 36 from noise_tbl
; $FD5B6, i.e. ROM $FD5D6 / $FD5DA).
;   BEFORE: $BBBBBBBB (idx 11) / $99999999 (idx 9)
;   AFTER:  $FFFFFFFF (idx 15) / $FFFFFFFF (idx 15)
; Only these two longwords change (plus the two checksums).

        org $FD5D6
        dc.l $FFFFFFFF          ; noise_tbl[8] tall top-even: solid idx 15
        dc.l $FFFFFFFF          ; noise_tbl[9] tall top-odd:  solid idx 15
