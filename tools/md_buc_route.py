#!/usr/bin/env python3
"""Closed-loop Buc cutscene check: walk the leader to Buc by position
(not by frame), play the cutscene, print the end state (MODE, LOC, ...,
Buc x, y). Robust to timing changes that break fixed-input routes.
  md_buc_route.py ROM OUT_ROUTE.txt
"""
import sys; sys.path.insert(0,'tools'); import md_run as m
rom=sys.argv[1]; out=sys.argv[2]
md=m.MD(rom)
route=list(m.parse_route('tools/playtest_route_orig.txt'))
pref=[]; tot=0
for n,p in route:
    if tot+n>=3290: pref.append((3290-tot,p)); break
    pref.append((n,p)); tot+=n
for n,p in pref:
    for k in range(n): md.step(p)
steps=list(pref)
def pos():
    r=md.ram(); 
    lead=m.w(r,0xFF02B2)
    # figure: leader or type-4 redirect with record
    return (m.w(r,0xFF00AE), m.w(r,0xFF0E98), m.w(r,0xFF02C0), m.w(r,0xFF02C2), m.w(r,0xFF02F4), m.w(r,0xFF02F6))
def fig(p):
    return p[2:4] if p[0]==1 else p[4:6]
def go(d, cells=None, frames=None):
    # hold d until the leader figure moved `cells` cells (or frames elapsed)
    n=0; moved=0; last=fig(pos())
    while True:
        md.step('' if d=='.' else d); n+=1
        p=fig(pos())
        if p!=last: moved+=1; last=p
        if cells is not None and moved>=cells: break
        if frames is not None and n>=frames: break
        if n>3000: break
    steps.append((n,d))
    for k in range(8): md.step('')
    steps.append((8,'.'))
    print(d,cells,frames,'->',pos(),n)
def to(d, axis, val):
    # hold d until the leader figure's coordinate reaches val
    n=0
    while fig(pos())[axis]!=val and n<3000:
        md.step(d); n+=1
    steps.append((n,d))
    for k in range(8): md.step('')
    steps.append((8,'.'))
    print('to',d,axis,val,'->',pos(),n)
to('U',1,117); to('R',0,117); to('U',1,113)
go('L',frames=40); go('B',frames=30); go('.',frames=500)
to('L',0,25); to('U',1,6); to('L',0,8); to('D',1,7)
go('.',frames=60)
go('C',frames=30); go('.',frames=200); go('A',frames=30); go('.',frames=400); go('A',frames=30); go('.',frames=3000)
with open(out,'w') as f:
    for n,p in steps: f.write(f'{n} {p if p else "."}\n')
