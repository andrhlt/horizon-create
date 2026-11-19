#!/usr/bin/env python3
"""Replay every original Gearbox face's animation and transmitted RPM."""

import argparse
import csv
from importlib.util import module_from_spec, spec_from_file_location
from math import fmod, isclose
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import re
from time import monotonic, sleep

from fixture_world import ROOT, fixture_world

TRACE='CREATE_GEARBOX_FRAME '
DIRECTIONS={
    'down':(0,-1,0),'up':(0,1,0),'north':(0,0,-1),
    'south':(0,0,1),'west':(-1,0,0),'east':(1,0,0),
}
OPPOSITE=dict(zip(DIRECTIONS,('up','down','south','north','east','west'),strict=True))


def position(case):
    return (8+4*(case%4),104+4*(case//4),-10)


def neighbor(case,direction):
    return tuple(a+b for a,b in zip(position(case),DIRECTIONS[direction],strict=True))


def xyz(values):
    return ' '.join(map(str,values))


def rpm(snbt):
    speed=re.search(r'\bSpeed: (-?\d+(?:\.\d+)?)',snbt)
    return float(speed[1]) if speed else 0.0


def reference():
    result = {}
    with (ROOT / "fixtures/gearbox-render-java.csv").open(newline="") as source:
        for row in csv.DictReader(source):
            case, tick = int(row["case"]), int(row["tick"])
            result.setdefault(tick, {})[case, row["face"]] = (
                row["casing_axis"], row["input_face"], float(row["render_rpm"]), float(row["shaft_rpm"]),
            )
    assert len(result) == 12 and all(len(rows) == 48 for rows in result.values())
    return result


def setup(control,rows):
    commands=[
        '/fill 10 106 -3 18 106 -1 minecraft:smooth_stone',
        '/tp @s 14.5 107 -1.5',
    ]
    for case in range(12):
        box,input_side,*_=next(values for (number,_),values in rows.items() if number==case)
        commands.append(f'/setblock {xyz(position(case))} create:gearbox[axis={box}]')
        for (number,face),_ in rows.items():
            if number!=case:
                continue
            pos=xyz(neighbor(case,face))
            if face==input_side:
                commands.append(f'/setblock {pos} create:creative_motor[facing={OPPOSITE[input_side]}]')
                commands.append(f'/data merge block {pos} {{ScrollValue:32}}')
            else:
                axis='xyz'[next(i for i,value in enumerate(DIRECTIONS[face]) if value)]
                commands.append(f'/setblock {pos} create:shaft[axis={axis}]')
    control.commands(commands)
    control.call('look-at',14.5,108.5,-9.5)
    for _ in range(4):
        control.step_to(control.clock()+1)


def frames(log,clock,rows):
    expected={(position(case),DIRECTIONS[face]):(box,DIRECTIONS[source],speed)
              for (case,face),(box,source,speed,_) in rows.items()}
    found={}
    deadline=monotonic()+5
    while len(found)<len(expected) and monotonic()<deadline:
        for line in reversed(log.read_text().splitlines()):
            if not line.startswith(TRACE):
                continue
            row=line[len(TRACE):].split(',')
            if len(row)!=15:
                continue
            x,y,z,box,axis,sign,sx,sy,sz,ticks,partial,phase,rate,angle,vertices=row
            if int(ticks)!=clock:
                continue
            pos=(int(x),int(y),int(z))
            axis=int(axis)
            side=tuple(int(sign) if index==axis else 0 for index in range(3))
            key=(pos,side)
            if key in found or key not in expected:
                continue
            want_box,want_source,want_rate=expected[key]
            if tuple(map(int,(sx,sy,sz)))!=want_source or float(rate)!=want_rate:
                continue
            assert 'xyz'[int(box)]==want_box and int(vertices)>0,row
            phase=float(phase)
            expected_phase=22.5 if (pos[(axis+1)%3]+pos[(axis+2)%3])%2==0 else 0.0
            assert phase==expected_phase,row
            expected_angle=fmod((clock+float(partial))*want_rate*3/10,360)+phase
            error=(float(angle)-expected_angle+180)%360-180
            assert isclose(error,0.0,abs_tol=0.0002),row
            found[key]=float(partial)
        if len(found)<len(expected):
            sleep(.06)
    if len(found)!=len(expected):
        missing={key:expected[key] for key in expected.keys()-found.keys()}
        raise RuntimeError(f'Missing original Gearbox frames at game tick {clock}: {missing}.')
    return list(found.values())


def change(control,rows,speed):
    sources={case:source for (case,_),(_,source,_,_) in rows.items()}
    control.commands(f'/data merge block {xyz(neighbor(case,source))} {{ScrollValue:{speed}}}'
                     for case,source in sources.items())


def verify(args):
    refs=reference()
    partials=set()
    with fixture_world(args,'GearboxRender',render=True,pack=args.pack,
                       env={'CREATE_GEARBOX_RENDER':'1'}) as control:
        setup(control,refs[0])
        start=control.clock()
        for tick,rows in refs.items():
            if tick:
                control.step_to(start+tick)
            partials.update(frames(control.socket.parent/'ctl.log',start+tick,rows))
            speeds=control.commands(f'/data get block {xyz(neighbor(case,face))}' for case,face in rows)
            for ((case,face),(*_,expected)),actual in zip(rows.items(),speeds,strict=True):
                assert rpm(actual)==expected,(tick,case,face,expected,actual)
            if tick in (3,7):
                change(control,rows,-48 if tick==3 else 16)
    assert len(partials)>1,partials
    print(f'All 576 Java Gearbox shaft speeds and rendered sides match, covering twelve rigs and {len(partials)} rendered fractions.')


def load(name):
    spec=spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_frames(peer,rpm,after):
    expect={DIRECTIONS['north']:rpm,DIRECTIONS['south']:-rpm,
            DIRECTIONS['west']:-rpm,DIRECTIONS['east']:rpm}
    log=peer.socket.parent/'ctl.log'
    found=set()
    boundary=monotonic()+5
    peer.call('look-at',8.5,101.5,-8.5)
    while monotonic()<boundary:
        for line in reversed(log.read_bytes()[after:].decode(errors='replace').splitlines()):
            if not line.startswith(TRACE):
                continue
            row=line[len(TRACE):].split(',')
            if len(row)!=15:
                continue
            x,y,z,axis,shaft,sign,sx,sy,sz,tick,partial,phase,speed,angle,vertices=row
            if tuple(map(int,(x,y,z)))!=(8, 101, -9):
                continue
            shaft=int(shaft)
            side=tuple(int(sign) if index==shaft else 0 for index in range(3))
            if side not in expect or float(speed)!=expect[side]:
                continue
            assert axis=='1' and (sx,sy,sz)==('0','0','-1') and int(vertices)>0,row
            phase=float(phase)
            angle_expected=fmod((int(tick)+float(partial))*expect[side]*3/10,360)+phase
            assert isclose((float(angle)-angle_expected+180)%360-180,0.,abs_tol=.0002),row
            found.add(side)
        if found==set(expect):
            return
        sleep(.07)
    raise RuntimeError(f'Missing fresh original Gearbox frames at speed {rpm}: {set(expect)-found}')


def verify_lan(args, scratch):
    guest_name = "GearboxView"
    motor=load('test-creative-motor')
    multiplayer=load('test-multiplayer')
    os.environ['CREATE_GEARBOX_RENDER']='1'
    with fixture_world(args,'GearboxRenderLAN',render=True,pack=args.pack) as host:
        motor.setup(host)
        host.commands((
            '/setblock 8 101 -9 create:gearbox[axis=y]',
            '/setblock 8 101 -8 create:shaft[axis=z]',
            '/setblock 9 101 -9 create:shaft[axis=x]',
            '/setblock 7 101 -9 create:shaft[axis=x]',
            '/setblock 6 100 -10 minecraft:stone',
        ))
        host.step_to(host.clock()+1)
        motor.configure(host,motor.HORIZONTAL,1,64)
        host.step_to(host.clock()+1)
        host.command('/tp @s 12.5 101 -7.5')
        address=f"127.0.0.1:{host.call('lan','open','0','commands','force')['port']}"
        with multiplayer.joined_client(args,scratch,address,guest_name,render=True,scenario='gearbox-render',pack=args.pack) as guest:
            multiplayer.until('guest to enter the driven world',lambda:any(
                user['name']==guest_name and user['placed'] for user in host.call('lan','status')['guests']
            ))
            host.commands((f'/gamemode survival {guest_name}',f'/tp {guest_name} 6.0 101.0 -9.5'))
            multiplayer.until('guest to see the driveshaft and reach the motor',lambda:(
                guest.call('state')['player']['position']==[6.0,101.0,-9.5]
                and guest.call('block',*(8, 101, -9))['state']=='create:gearbox[axis=y]'
            ))
            peers=(host,guest)
            offsets=[(peer.socket.parent/'ctl.log').stat().st_size for peer in peers]
            for peer,offset in zip(peers,offsets,strict=True):
                verify_frames(peer,64,offset)
            motor.configure(guest,motor.HORIZONTAL,0,24,teleport=False)
            offsets=[(peer.socket.parent/'ctl.log').stat().st_size for peer in peers]
            host.step_to(host.clock()+1)
            for peer,offset in zip(peers,offsets,strict=True):
                verify_frames(peer,-24,offset)
    print('Host and guest rendered all four original Gearbox half-shafts at +64 and reversed −24 RPM after their real motor settings.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda path: Path(path).resolve(strict=True))
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--lan", action="store_true")
    args = parser.parse_args()
    if args.lan:
        with TemporaryDirectory(prefix="hc-gbl-") as scratch:
            verify_lan(args, Path(scratch))
    else:
        verify(args)


if __name__ == "__main__":
    main()
