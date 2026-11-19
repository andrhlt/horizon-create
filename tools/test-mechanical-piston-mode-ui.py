#!/usr/bin/env python3
"""Exercise the piston movement-mode board as host and LAN guest offscreen."""
import argparse
import re
from pathlib import Path
from runpy import run_path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

POS=(8,201,42)
LABELS=['Always Place when Stopped','Place only in Starting Position','Place only when Anchor Destroyed']
def mode(host):
    value=host.command('/data get block 8 201 42 ScrollValue')
    match=re.search(r'block data: (\d+)$',value)
    return int(match.group(1)) if match else 0

def choose(control,value):
    control.call('look-at',8.375,201.5,42.985)
    control.call('wait',2)
    control.call('mouse','right','down')
    control.call('wait',7)
    screen=control.call('screen')
    assert control.call('state')['screen']=='mod',screen
    buttons=screen['buttons']
    assert [b['label'] for b in buttons]==LABELS,buttons
    cells=[(b['x']+b['w']/2,b['y']+b['h']/2) for b in buttons]
    assert [cells[i+1][0]-cells[i][0] for i in range(2)]==[10,10],cells
    control.call('click-at',*cells[value],'right')
    control.call('wait',3)
    assert control.call('state')['screen']=='playing'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ctl','client','resources'):p.add_argument(name,type=lambda x:Path(x).resolve(strict=True))
    a=p.parse_args();mp=run_path(str(ROOT/'tools/test-multiplayer.py'));until=mp['until']
    with fixture_world(a,'PistonModeUI',render=True,env={'HORIZON_NO_AUDIO':'1'}) as host:
        host.commands(['/fill 6 200 40 11 200 47 minecraft:smooth_stone','/setblock 8 201 42 create:mechanical_piston[facing=east,axis_along_first=true]','/tp @s 8.375 201 45.5 180 24','/gamemode survival'])
        host.step_to(host.clock()+1)
        for option in (1,2,0):
            choose(host,option)
            assert mode(host)==option,(option,mode(host))
        host.command('/tp @s 6.5 201 45.5')
        network=host.call('lan','open','0','commands','force')
        with TemporaryDirectory(prefix='piston-ui-') as temp, mp['joined_client'](a,Path(temp),f"127.0.0.1:{network['port']}",'PistonGuest',render=True,scenario='piston-ui') as guest:
            until('guest to join',lambda:any(p['name']=='PistonGuest' and p['placed'] for p in host.call('lan','status')['guests']))
            host.commands(['/gamemode survival PistonGuest','/tp PistonGuest 8.375 201 45.5 180 24'])
            host.step_to(host.clock()+1)
            until('guest to see piston',lambda:guest.call('block',*POS)['block']=='create:mechanical_piston')
            choose(guest,2)
            until('guest mode on server',lambda:mode(host)==2)
    print('Host selected modes 1, 2, 0; LAN guest selected 2 using the offscreen movement-mode board.')
if __name__=='__main__':main()
