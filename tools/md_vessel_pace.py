#!/usr/bin/env python3
"""Frames per world tick for a travel mode over open sea (#262): from the
overworld start, fly (mode 4, poked into the leader char +6 via the save
state) to the sea at (132,76), poke MODE, sail a square, print the median.
  md_vessel_pace.py MODE [ROM]
"""
import sys,numpy as np; sys.path.insert(0,'tools'); import md_run as m
mode=int(sys.argv[1])
seq=[]
for n,p in m.parse_route('tools/playtest_route_orig.txt'): seq+=[p]*n
md=m.MD(sys.argv[2] if len(sys.argv)>2 else 'rop-original.gen')
for i in range(3700): md.step(seq[i])
def setmode(v):
    r=md.ram(); a=0xFF02B4+0x34*m.w(r,0xFF02B2)+6-0xFF0000
    st=bytearray(md.em.get_state()); st[16+a]=v&0xff; st[16+a+1]=v>>8; md.em.set_state(bytes(st))
def pos(): r=md.ram(); return (m.w(r,0xFF0E8E),m.w(r,0xFF0E90))
setmode(4)
n=0
while pos()[1]>78 and n<3000: md.step('U'); n+=1
while pos()[0]<132 and n<6000: md.step('R'); n+=1
for k in range(60): md.step('')
setmode(mode); print('at',pos(),'after',n)
ev=[];p0=pos()
pat=(['R']*150+['D']*150+['L']*150+['U']*150)*4
for i,d in enumerate(pat):
    md.step(d); p=pos()
    if p!=p0 and (not ev or i-ev[-1]>3): ev.append(i)
    p0=p
d=np.diff(ev)
print('mode',mode,'moves',len(ev),'frames/tick median',np.median(d) if len(d) else None,'mean %.1f'%(d.mean() if len(d) else 0), 'end',pos())
