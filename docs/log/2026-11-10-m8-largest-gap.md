# M8 largest unclassified block: 0x05F7E4-0x09611F (223,549 bytes)

- Card: M8 (all bytes accounted). Current state: block classed `unknown` in disasm/regions.csv; docs/graphics.md:884 says ~172 KB unknown (#017).
- Measured: entropy 4.7-6.2 bits/byte per 4 KB chunk; zero bytes 1-23%. Not raw 4bpp tile data by this profile.
- Tried: documented LZSS format (disasm/text/README.md section 2). Scanning every even offset for a 4-byte length header that decodes gives 468 candidates, but LZSS back-references never fail, so a clean decode is not evidence.
- Chain test: following candidate headers end to end from 0x05F802 covers only one stream (ends 0x05FAF5). No contiguous LZSS tiling of the block.
- Conclusion: the block is not one LZSS run. Its streams are probably referenced individually (the $96120 table has 62 records). Not classified; stays `unknown`.
- Next: decode each $96120 record and check whether its stream lies inside this block; then class those spans `lzss-stream` with the record id.
- Per-record check (done): all 62 $96120 records decode with the documented LZSS format to exactly their declared length (decoder validated). Stream starts span 0x09638C-0x0B83A1; zero of them fall inside 0x05F7E4-0x09611F. So the $96120 table does not reference this block.
- Remaining candidate owners: the terrain streams at $603E4+ (maps.md:371, ends ~$6823B) and the unknown data #017 (graphics.md:884). Next: check whether any $5F524 offset or other pointer table reaches 0x05F7E4-0x09611F before classing it.
- CORRECTION: the earlier "62/62 decode to declared length" result was vacuous. The decoder always stops at the declared length, so that check could not fail. Ignore it.
- Valid test (can fail): each stream must end exactly where the next record's stream starts. $96120 with base 0x9638C: 61/61 consecutive, last ends at 0xB86AE. $B86AE with base 0xB8A32: 89/89, last ends at 0xCC9D8.
- Result: 0x0B86AE-0x0CC9D7 is a 90-record table (0x0B86AE-0x0B8A31) plus its LZSS streams (0x0B8A32-0x0CC9D7). Classed in disasm/doc_regions.csv. Unknown/high-entropy 446,171 -> 363,442.
