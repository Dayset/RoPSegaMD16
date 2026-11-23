#!/usr/bin/env python3
"""Render the per-location NPC list from Rings of Power ROM bytes.

Implements world_enter_location ($03090A) placement matching EXACTLY as coded:
  for anchor d4 = $FF0E92 & 0x3FF, for each template i in 0..461:
    key = template word at +20 ($CF1C0 + 24*i)
    branch 1: (key & 0x3FF) == d4
    branch 2: (key & 0x3FF) == byte at $D1CFC + 10*d4   [literal lea $D1CFC,
              verified from raw ROM bytes 41 F9 00 0D 1C FC at $030A96/$030B30/$02BA58;
              = previous anchor record's +6 byte; see REPORT.md for intent discussion]
    AND (key >> 12) == ($FF0E92 >> 12)   [variant/floor nibble]
  then gates: kind-0 event-bit gate (sys_copy_stride6_2d284) OR seen-ring
  (world_seen_check), then sys_struct24_read gate (template +14 hi byte:
  0xFF -> spawn iff $FF0E16 <= 557; 0xFE -> iff $FF0E16 >= 558; else always).

Name resolution (verified): template spawn word -> spawn record ($CECF0) ->
name_idx word -> name table ($CD430).  NOT names[spawn index]: that misreading
is in docs/architecture.md + docs/maps.md (see REPORT.md §5).

Also renders: world_enter_location 3rd-loop event effects (kind 1 -> tile
0x112+bit, kind 2 -> tile 0x107+bit, kind 3 -> mode-5 entity spawn if bit set),
and the world_tick random pools (placement low10 == 2 / == 4; anchors 2 and 4
are (999,999) placeholders, so these never spawn on entry).

Outputs: npc-by-location.md, npc-by-location.csv in this directory.
Run: python3 render_npc_by_location.py  (needs rop-original.gen beside it)
"""
import struct, collections, csv, sys

ROM_PATH = 'rop-original.gen'
rom = open(ROM_PATH, 'rb').read()
assert len(rom) == 1048576, len(rom)
import hashlib
assert hashlib.md5(rom).hexdigest() == '30c18fdbe2183f64702ae9f1a45d63f9'

def w(a): return struct.unpack('>H', rom[a:a+2])[0]
def b(a): return rom[a]

names = []
for i in range(396):
    a = 0xCD430 + 16*i
    names.append((rom[a], rom[a+1:a+16].split(b'\x00')[0].decode('ascii', 'replace')))
def name_of(idx):
    return names[idx][1] if 0 <= idx < 396 else f'<name-idx {idx} OUT OF TABLE>'

spawns = []
for i in range(202):
    a = 0xCECF0 + 6*i
    spawns.append(dict(idx=i, name_idx=w(a), portrait=b(a+2), b3=b(a+3),
                       b4=b(a+4), b5=b(a+5), name=name_of(w(a))))

tmpls = []
for i in range(462):
    a = 0xCF1AC + 24*i
    words = [w(a+2*j) for j in range(12)]
    key = words[10]
    tmpls.append(dict(idx=i, spawns=words[:6], w12=words[6], w14=words[7],
                      home=words[8], b18=rom[a+18], b19=rom[a+19], key=key,
                      anchor=key & 0x3FF, nibble=key >> 12,
                      direction=(key >> 10) & 3, x=rom[a+22], y=rom[a+23],
                      raw=rom[a:a+24].hex(' ')))
def tname(t): return name_of(spawns[t['spawns'][0]]['name_idx'])
def spawn_names(t): return '+'.join(name_of(spawns[s]['name_idx']) for s in t['spawns'] if s != 0) or '—'

anchors = []
for i in range(455):
    a = 0xD1D00 + 10*i
    anchors.append(dict(idx=i, keyx=w(a), keyy=w(a+2), dest=b(a+4), msg=b(a+5),
                        b6=b(a+6), b7=b(a+7)))

songs = []
for i in range(175):
    a = 0xD63E4 + 4*i
    songs.append(dict(idx=i, x=rom[a], y=rom[a+1], direction=rom[a+2], song=rom[a+3] & 0xF))

events = []
for i in range(161):
    a = 0xD601E + 6*i
    w0 = w(a)
    kind = ((((w0 << 5) | (w0 >> 11)) & 0xFFFF) & 0xF)
    events.append(dict(idx=i, w0=w0, kind=kind, code=w0 & 0x7FF,
                       plus2=w(a+2), loc=w(a+2) & 0x3FF,
                       nibble=(w(a+2) >> 12) & 0xF, b4=b(a+4), b5=b(a+5)))

# kind-0 placement gates: event idx by template
k0 = {}
for e in events:
    if e['kind'] == 0:
        k0.setdefault(e['plus2'], []).append(e['idx'])

# Initial event-bit state, from shop_merchant_scan ($02B5F4): bit i = top bit of
# event i's w0 for i < 161, 0 for 161..183. Called at $01B75A (new game) and
# $02F904 (world_seen_reset). Save/load restores $FFC326 from the save buffer
# ($030060 loop, 184 bits). Dialog/script/shop writers mutate it during play.
init_bit = {e['idx']: ((e['w0'] >> 15) & 1) for e in events}
# Setters for the initially-CLEAR gating events (verified: whole-ROM op-11 scan
# + full $D3102 first/second dispatch enumeration + shop-dispatch writers).
SETTER = {6: 'Buc intro script op-11 $1A1E8 (b3=1)',
          32: 'dialog ev231 (2nd dispatch key 12)',
          33: 'dialog ev226 (1st dispatch key 12)',
          73: 'dialog ev372 (2nd dispatch key 12)',
          80: 'Tutu script op-11 $1A420 (b3=1)',
          100: 'Fezzik script op-11 $1A508 (b3=1) [mode-5 gate, not a template gate]',
          131: 'dialog ev568 (2nd dispatch key 12)',
          132: 'dialog ev149 (1st dispatch key 12)',
          139: 'dialog ev465 (1st dispatch key 12)'}
# bit-clearing writers that matter for placement gates:
CLEARER = {0: 'Buc intro script op-11 $1A1D8 (b3=0)',
           1: 'Buc intro script op-11 $1A1E0 (b3=0)',
           2: 'Buc intro script op-11 $1A1F0 (b3=0)',
           3: 'Buc intro script op-11 $1A1F8 (b3=0)',
           4: 'Buc intro script op-11 $1A200 (b3=0)',
           5: 'Buc intro script op-11 $1A208 (b3=0)',
           79: 'Tutu script op-11 $1A418 (b3=0)',
           62: 'shop action $02DFDC (clears 62,63)',
           143: 'shop action $02DE46 sets 143 (kind-1 tile at anchor 392 nib 3)'}

def gate14(t):
    hb = t['w14'] >> 8
    if hb == 0xFF: return 'FF:only-if-$FF0E16<=557'
    if hb == 0xFE: return 'FE:only-if-$FF0E16>=558'
    return 'always'

# ---------------- self-checks against known pins ----------------
fails = []
def check(cond, label):
    print(('PASS ' if cond else 'FAIL ') + label)
    if not cond: fails.append(label)

check(tmpls[8]['anchor'] == 34 and tmpls[8]['nibble'] == 3 and (tmpls[8]['x'], tmpls[8]['y']) == (2, 9) and tname(tmpls[8]) == 'Darius',
      'Darius tmpl 8 @ anchor 34 nib 3 (2,9)')
check(tmpls[342]['anchor'] == 405 and tmpls[342]['nibble'] == 2 and (tmpls[342]['x'], tmpls[342]['y']) == (3, 8) and tname(tmpls[342]) == 'Fezzik',
      'Fezzik tmpl 342 @ anchor 405 nib 2 (3,8)')
check(not any(t['anchor'] == 60 for t in tmpls), 'no template spawns at anchor 60 (Fezzik home)')
check(tmpls[389]['anchor'] == 391 and tmpls[389]['nibble'] == 6 and (tmpls[389]['x'], tmpls[389]['y']) == (5, 3) and tname(tmpls[389]) == 'Tutu',
      'Tutu tmpl 389 @ anchor 391 nib 6 (5,3) [script op-3 position]')
check(tmpls[390]['anchor'] == 391 and tmpls[390]['nibble'] == 5 and (tmpls[390]['x'], tmpls[390]['y']) == (5, 4) and tname(tmpls[390]) == 'Tutu',
      'Tutu tmpl 390 @ anchor 391 nib 5 (5,4)')
check(not any(t['anchor'] == 389 and tname(t) == 'Tutu' for t in tmpls), 'no Tutu template at anchor 389')
check(sum(1 for t in tmpls if t['anchor'] == 389) == 8, 'anchor 389 holds 8 templates (all Man)')
check(tmpls[218]['anchor'] == 249 and tmpls[218]['nibble'] == 3 and (tmpls[218]['x'], tmpls[218]['y']) == (2, 9) and tname(tmpls[218]) == 'Fiver',
      'Fiver tmpl 218 @ anchor 249 nib 3 (2,9)')
check(tmpls[28]['anchor'] == 170 and (tmpls[28]['x'], tmpls[28]['y']) == (5, 3) and tname(tmpls[28]) == 'Rashiid',
      'tmpl 28 = Rashiid @ anchor 170 (5,3) [brief pin corrected: not Woman]')
check(tmpls[443]['anchor'] == 11 and (tmpls[443]['x'], tmpls[443]['y']) == (5, 9) and spawns[28]['name'] == 'Woman' and tmpls[443]['spawns'][0] == 28,
      'spawn 28 = Woman is tmpl 443 @ placeholder anchor 11 (5,9)')
check(anchors[11]['keyx'] == 999, 'anchor 11 is a (999,999) placeholder')
check(tmpls[1]['anchor'] == 30 and (tmpls[1]['x'], tmpls[1]['y']) == (9, 17) and tname(tmpls[1]) == 'Thalmus',
      'Thalmus tmpl 1 @ anchor 30 (9,17) [== Buc script op-3 position]')
check(anchors[30]['dest'] == 156 and 77 + 156 == 233, 'anchor 30 dest 156 chunk 233 (Buc doc)')
check(tmpls[5]['anchor'] == 30 and tname(tmpls[5]) == 'Imino', 'Imino tmpl 5 @ anchor 30')
check(tmpls[6]['anchor'] == 43 and tname(tmpls[6]) == 'Yoppa', 'Yoppa tmpl 6 @ anchor 43')
check(tmpls[424]['anchor'] == 392 and tname(tmpls[424]) == 'Darius', 'Darius-110 tmpl 424 @ anchor 392 (dest 170)')
e100 = events[100]
check(e100['kind'] == 3 and e100['loc'] == 405 and e100['nibble'] == 2 and e100['code'] == 650,
      'ev100 kind 3 decodes to anchor 405 nib 2 code 650 (Ring of Perfctin)')
check(all(e['plus2'] >= 462 for e in events if e['kind'] == 3), 'all 16 kind-3 events have +2 >= 462 (dead in event_apply)')
check(max(s for t in tmpls for s in t['spawns']) <= 201, 'template spawn indices all <= 201')
check(max(s['name_idx'] for s in spawns) == 145, 'spawn name indices all <= 145')
check(spawns[1]['name_idx'] == 57 and name_of(57) == 'Buc', 'spawn 1 -> Buc (architecture.md leader puzzle is a misreading)')
check(not any(s['name_idx'] in (40, 20, 185) for s in spawns), 'no spawn record is named Annulka/Ayzz/Cleave')
check([t['idx'] for t in tmpls if t['anchor'] == 2] == [30, 31, 32, 33, 34, 35], 'low10==2 pool = templates 30-35')
check(len([t for t in tmpls if t['anchor'] == 4]) == 38, 'low10==4 pool = 38 templates')
# event-bit initial state (shop_merchant_scan: bit i = top bit of ev_i.w0)
check(all(init_bit[e] == 1 for e in (0, 1, 2, 3, 4, 5, 79, 99, 144)), 'scan sets bits 0-5,79,99,144 (Buc cast, Tutu-389, Fezzik, Darius-110 spawn from start)')
check(all(init_bit[e] == 0 for e in (6, 80, 100)), 'scan clears bits 6,80,100 (Roakus-4, Tutu-390, Ring mode-5 appear only after their setters)')
check(all(e in SETTER for e in (6, 32, 33, 73, 80, 131, 132, 139)
          if e in [ev for t in tmpls for ev in k0.get(t['idx'], [])]),
      'every initially-CLEAR gating event has a known setter')
check(SETTER[100].startswith('Fezzik'), 'ev100 setter is the Fezzik script (mode-5 Ring gate)')
if fails:
    print('SELF-CHECKS FAILED:', fails); sys.exit(1)
print('all self-checks passed')

# ---------------- build per-anchor render ----------------
def b2byte(d4): return rom[0xD1CFC + 10*d4]

rows = []  # csv rows
md = []
md.append('# NPCs by location — rendered from the ROM\n')
md.append('Generated by `render_npc_by_location.py` from `rop-original.gen` '
          '(MD5 `30c18fdbe2183f64702ae9f1a45d63f9`).\n')
md.append('Method: `world_enter_location` ($03090A) placement matching, implemented exactly as coded. '
          'A template spawns on entry to anchor A (=$FF0E92 & 0x3FF) iff its placement key '
          '(template word +20, low 10 bits) equals A (branch 1) or equals the byte at $D1CFC+10*A '
          '(branch 2, literal code behavior), AND its key bits 12–15 equal the $FF0E92 variant/floor '
          'nibble. Then the kind-0 event-bit gate / seen-ring gate and the +14 time gate apply '
          '(see REPORT.md). Names resolve spawn record → name_idx → name table (verified).\n')
md.append('Anchor A below is the $D1D00 record index. `dest` is the record\'s +4 byte '
          '($FF0E98, the room/song-table index); `chunk` = 77+dest; the song record gives the '
          'party\'s entry position. "loc 156" in cutscene docs = dest 156 = anchor 30, NOT anchor 156.\n')

covered_b1 = collections.Counter(t['anchor'] for t in tmpls)
b2pairs = collections.defaultdict(list)
for d4 in range(455):
    bv = b2byte(d4)
    for t in tmpls:
        if t['anchor'] == bv and t['anchor'] != d4:
            b2pairs[d4].append(t)

# event effects per (anchor, nibble): kinds 1,2,3
ev_by_an = collections.defaultdict(list)
for e in events:
    if e['kind'] in (1, 2, 3):
        ev_by_an[(e['loc'], e['nibble'])].append(e)

def fmt_tmpl(t, gate_note=''):
    ev = k0.get(t['idx'], [])
    if ev:
        e = ev[0]
        note = f"init:{'SET' if init_bit[e] else 'CLEAR'}"
        if not init_bit[e] and e in SETTER:
            note += f" setter={SETTER[e]}"
        elif init_bit[e] and e in CLEARER:
            note += f" clearer={CLEARER[e]}"
        gate = f"gate:ev{e}({note})"
    else:
        gate = 'gate:seen-ring'
    return (f"tmpl {t['idx']:3d} {tname(t):10s} nib {t['nibble']} dir {t['direction']} "
            f"({t['x']:2d},{t['y']:2d}) home {t['home']:3d} w12 {t['w12']:2d} "
            f"time:{gate14(t)[:6]} {gate} spawnlist[{','.join(str(s) for s in t['spawns'] if s)}]={spawn_names(t)} "
            f"b18 {t['b18']} b19 {t['b19']}{gate_note}")

n_anchors_with = 0
for d4 in range(455):
    a = anchors[d4]
    b1 = [t for t in tmpls if t['anchor'] == d4]
    b2 = b2pairs.get(d4, [])
    evs = [e for (an, ni), es in ev_by_an.items() if an == d4 for e in es]
    if not b1 and not b2 and not evs:
        continue
    n_anchors_with += 1
    s = songs[a['dest']] if a['dest'] < 175 else None
    chunk = 77 + a['dest']
    room = '11x11' if a['dest'] < 153 else '32x32'
    md.append(f"## Anchor {d4} — key ({a['keyx']},{a['keyy']}) dest {a['dest']} msg {a['msg']} "
              f"chunk {chunk} ({room})" +
              (f" | party enters at song rec {a['dest']}: ({s['x']},{s['y']}) dir {s['direction']} song {s['song']}" if s else ' | dest >= 175: no song record') +
              ('\n**Placeholder (999,999) — unreachable as $FF0E92 in normal play. Templates listed here '
               'spawn only via branch 2 at other anchors, or via the world_tick pools (low10 2/4).**' if a['keyx'] == 999 else '') + '\n')
    if b2byte(d4) != 5:
        md.append(f'Branch-2 byte ($D1CFC+10*{d4}) = {b2byte(d4)} (5 = matches nothing).\n')
    for nib in sorted(set(t['nibble'] for t in b1)):
        md.append(f'### Branch 1, floor nibble {nib}\n')
        for t in sorted([x for x in b1 if x['nibble'] == nib], key=lambda x: x['idx']):
            md.append('- ' + fmt_tmpl(t) + '\n')
            rows.append([d4, a['keyx'], a['keyy'], a['dest'], a['msg'], chunk, s['x'] if s else '', s['y'] if s else '',
                         s['direction'] if s else '', s['song'] if s else '', 1, nib, t['idx'], tname(t),
                         ';'.join(str(x) for x in t['spawns']), t['x'], t['y'], t['direction'], t['home'],
                         t['w12'], gate14(t), ';'.join('ev%d' % e for e in k0.get(t['idx'], [])), t['b18'], t['b19']])
    if b2:
        md.append(f"### Branch 2 (key == {b2byte(d4)}, literal $D1CFC read)\n")
        for t in sorted(b2, key=lambda x: (x['nibble'], x['idx'])):
            md.append('- ' + fmt_tmpl(t) + '\n')
            rows.append([d4, a['keyx'], a['keyy'], a['dest'], a['msg'], chunk, s['x'] if s else '', s['y'] if s else '',
                         s['direction'] if s else '', s['song'] if s else '', 2, t['nibble'], t['idx'], tname(t),
                         ';'.join(str(x) for x in t['spawns']), t['x'], t['y'], t['direction'], t['home'],
                         t['w12'], gate14(t), ';'.join('ev%d' % e for e in k0.get(t['idx'], [])), t['b18'], t['b19']])
    if evs:
        md.append('### Location events (world_enter_location 3rd loop; only the nibble-matching one fires)\n')
        for e in sorted(evs, key=lambda e: (e['nibble'], e['idx'])):
            if e['kind'] == 1:
                eff = f"tile 0x112+bit at offset ({e['b4']},{e['b5']})"
            elif e['kind'] == 2:
                eff = f"tile 0x107+bit at offset ({e['b4']},{e['b5']})"
            else:
                eff = f"MODE-5 SPAWN if bit {e['idx']} set: code {e['code']} (cat {e['code']//64}) at offset ({e['b4']},{e['b5']})"
            md.append(f"- ev{e['idx']} kind {e['kind']} nibble {e['nibble']}: {eff}\n")

# anchors with nothing
nothing = [d4 for d4 in range(455)
           if not any(t['anchor'] == d4 for t in tmpls) and d4 not in b2pairs
           and not any(an == d4 for (an, ni) in ev_by_an)]
md.append('\n## Anchors with no placement NPC and no location event\n\n')
md.append(f'{len(nothing)} anchors: ' + ', '.join(str(x) for x in nothing) + '\n')
md.append('\n(Anchors 0–29 are (999,999) placeholders and are unreachable as $FF0E92 in normal play.)\n')

# world_tick pools
md.append('\n## world_tick random-spawn pools (NOT entry spawns)\n\n')
md.append('Anchors 2 and 4 are (999,999) placeholders, so these templates never spawn via '
          '`world_enter_location`. `world_tick` ($021BC4) randomly spawns one template with placement '
          'key low10 == 2 per tick-window, and ($021D80) one with low10 == 4 (with extra conditions: '
          'x-byte vs cell, +14 byte vs threshold, sys_condition_test on the y-byte).\n')
for pool in (2, 4):
    md.append(f'### Pool low10 == {pool}\n')
    for t in [x for x in tmpls if x['anchor'] == pool]:
        md.append('- ' + fmt_tmpl(t) + '\n')

# kind-3 event table (all dead in event_apply, live as mode-5 spawns on entry)
md.append('\n## Appendix: kind-3 events decoded (anchor/nibble for the world_enter_location mode-5 path)\n\n')
md.append('In `npc_attitude_event_apply` the kind-3 path indexes $CF1C0 by +2×24 — all 16 records are '
          'out of ROM there (dead). In `world_enter_location` the SAME records are decoded as '
          'anchor=(+2 & 0x3FF), nibble=(+2>>12): on entry to that (anchor, nibble) with the event bit '
          'set, a mode-5 entity with the record\'s code spawns.\n')
for e in sorted([x for x in events if x['kind'] == 3], key=lambda x: x['idx']):
    md.append(f"- ev{e['idx']}: +2={e['plus2']} anchor {e['loc']} nibble {e['nibble']} code {e['code']} "
              f"(cat {e['code']//64}) offset ({e['b4']},{e['b5']})\n")

# event-bit lifecycle (why the gated NPCs appear/disappear)
md.append('\n## Event-bit lifecycle ($FFC326) — how the gates move\n\n')
md.append('Initial state: `shop_merchant_scan` ($02B5F4, called at $01B75A new-game and '
          '$02F904 reset) sets bit *i* = top bit of event *i*\'s w0 (i < 161) and clears '
          'bits 161–183. Save/load restores the bitmap from the save buffer ($030060 loop, '
          '184 bits). During play the bits move only via: dialog events (first dispatch on '
          'rec+10: keys 12 SET / 13 CLEAR / 5 TOGGLE; second dispatch on rec+8: keys 12 SET / '
          '13 CLEAR), script op-11 (`sys_event_run` $02DB06), and shop actions (bit 143 SET at '
          '$02DE46; bits 62/63 CLEAR at $02DFDC; bit 180 SET at $02E0C4). Whole-ROM op-11 scan '
          'finds 12 real sites ($1A1D8–$1A208 intro, $1A418/$1A420/$1A438/$1A480 Tutu, $1A508 '
          'Fezzik); full $D3102 dispatch enumeration finds NO dialog event that sets bits '
          '0–8, 79, or 80.\n\n')
md.append('Initially-CLEAR gating events and their setters:\n')
for e in sorted(SETTER):
    if e == 100:
        md.append(f'- bit {e}: {SETTER[e]}\n')
        continue
    tmpl = [t for t in tmpls if e in k0.get(t['idx'], [])]
    who = ', '.join(f"tmpl {t['idx']} {tname(t)} @ anchor {t['anchor']} nib {t['nibble']}" for t in tmpl)
    md.append(f'- bit {e}: {SETTER[e]} — gates {who}\n')
md.append('\nThe three scene swaps this explains:\n')
md.append('- **Buc classroom**: bits 0–5 SET at scan, so Thalmus/Roakus-3/Imino/Yoppa/Fezzik-7/'
          'Darius-8 spawn on first entry to anchors 30/43/34. The intro script ($1A1B0+, '
          'op-11s $1A1D8–$1A208) then CLEARs bits 0–5 and SETs bit 6 — after the scene the '
          'classroom cast no longer respawns via placement, and Roakus-4 appears at anchor 47.\n')
md.append('- **Tutu tower**: bit 79 SET at scan, so Tutu-389 is standing at anchor 391 nibble 6 '
          '(5,3) on first entry — the first meeting works. The Tutu script CLEARs bit 79 '
          '($1A418) and SETs bit 80 ($1A420): on re-entry Tutu-389 is gone and Tutu-390 spawns '
          'at nibble 5 (5,4). Bit 81 is cleared then set by the same script ($1A438/$1A480) '
          'for its kind-1 tile writes.\n')
md.append('- **Fezzik chamber**: bit 99 SET at scan, so Fezzik-342 is standing at anchor 405 '
          'nibble 2 (3,8) from the start. The Fezzik script SETs bit 100 ($1A508): on re-entry '
          'to 405/nib 2 the kind-3 mode-5 entity (code 650, Ring of Perfctin) spawns.\n')

# summary
multi = [(an, sorted(set(t['nibble'] for t in tmpls if t['anchor'] == an)))
         for an in range(455) if len(set(t['nibble'] for t in tmpls if t['anchor'] == an)) > 1]
md.append('\n## Summary counts\n\n')
md.append(f'- Templates: 462. Branch-1 (anchor,template) pairs: 462 (one anchor per template).\n')
md.append(f'- Anchors with >=1 branch-1 template: {len([a for a in range(455) if covered_b1[a]])}; '
          f'with none: {455 - len([a for a in range(455) if covered_b1[a]])}.\n')
md.append(f'- Branch-2 extra pairs (literal $D1CFC read): {sum(len(v) for v in b2pairs.values())} across '
          f'{len(b2pairs)} anchors.\n')
md.append(f'- Anchors with a placement NPC or location event: {n_anchors_with}; with nothing: {len(nothing)}.\n')
md.append(f'- Multi-floor anchors (>1 nibble): {len(multi)}: ' +
          ', '.join(f'{a}{v}' for a, v in multi) + '\n')
md.append(f'- Floor-nibble distribution over templates: {dict(sorted(collections.Counter(t["nibble"] for t in tmpls).items()))}\n')
md.append(f'- Time-gated templates: +14 hi 0xFF (day-side, $FF0E16<=557): '
          f'{sum(1 for t in tmpls if (t["w14"] >> 8) == 0xFF)}; 0xFE (night-side, >=558): '
          f'{sum(1 for t in tmpls if (t["w14"] >> 8) == 0xFE)}.\n')
md.append(f'- Bit-gated templates (kind-0 event): {len(k0)} (one kind-0 event each).\n')
md.append(f'- Distinct spawn records used: {len(set(s for t in tmpls for s in t["spawns"]))} of 202; '
          f'distinct names used: {len(set(tname(t) for t in tmpls))}.\n')

open('npc-by-location.md', 'w').write(''.join(md))
with open('npc-by-location.csv', 'w', newline='') as f:
    wr = csv.writer(f)
    wr.writerow(['anchor', 'key_x', 'key_y', 'dest', 'msg', 'chunk', 'song_x', 'song_y', 'song_dir', 'song',
                 'branch', 'nibble', 'tmpl', 'name', 'spawn_list', 'x', 'y', 'dir', 'home', 'w12',
                 'time_gate', 'kind0_event', 'b18', 'b19'])
    wr.writerows(rows)
print(f'wrote npc-by-location.md ({len(md)} lines) and npc-by-location.csv ({len(rows)} rows)')
print('anchors with placement/event:', n_anchors_with, '| anchors with nothing:', len(nothing))
