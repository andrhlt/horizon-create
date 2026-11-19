#!/usr/bin/env python3
"""Verify original Sticker assets and six-facing head transforms in a hidden renderer."""
import argparse,hashlib,itertools,json,math,re,zipfile
from pathlib import Path
from fixture_world import ROOT,fixture_world
OUT=ROOT/'.local/sticker-completion'
FACES=['down','up','north','south','west','east']
def bounds(model,face,offset):
    yaw={'west':90,'north':180,'east':270}.get(face,0)
    pitch={'up':0,'down':180}.get(face,90)
    cy,sy=round(math.cos(math.radians(yaw))),round(math.sin(math.radians(yaw)))
    cx,sx=round(math.cos(math.radians(pitch))),round(math.sin(math.radians(pitch)))
    points=[]
    for element in model['elements']:
        assert element.get('rotation',{}).get('angle',0)==0
        for v in itertools.product(*zip(element['from'],element['to'])):
            x,y,z=[value/16-.5 for value in v];y+=offset
            y,z=cx*y-sx*z,sx*y+cx*z;x,z=cy*x+sy*z,-sy*x+cy*z
            points.append([x+.5,y+.5,z+.5])
    return [min(v[i] for v in points) for i in range(3)]+[max(v[i] for v in points) for i in range(3)]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['ctl','client','resources']:p.add_argument(key,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod');a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    hashes={}
    with zipfile.ZipFile(a.pack) as pack:
        for file in ['assets/create/models/block/sticker/head.json','assets/create/models/block/sticker/block.json','assets/create/models/block/sticker/block_powered.json','assets/create/textures/block/sticker.png','assets/create/textures/block/sticker_side.png','assets/create/textures/block/sticker_side_powered.png']:
            raw=pack.read(file);assert raw==(ROOT/'.local/java-reference/src/main/resources'/file).read_bytes(),file
            hashes[file]=hashlib.sha256(raw).hexdigest()
        model=json.loads(pack.read('assets/create/models/block/sticker/head.json'))
        sound=json.loads(pack.read('assets/create/sounds.json'))['slime_added'];assert sound['sounds']==[{'type':'event','name':'minecraft:block.slime_block.place'}]
    with fixture_world(a,'StickerGeometry',render=True,pack=a.pack,env={'CREATE_STICKER_TRACE':'1','HORIZON_NO_AUDIO':'1'}) as w:
        commands=['/fill 7 170 25 12 170 29 minecraft:stone','/tp @s 9.5 171 27.5']
        for extended,y in [(False,170),(True,172)]:
            for x,face in enumerate(FACES,6):commands.append(f'/setblock {x} {y} 20 create:sticker[facing={face},extended={str(extended).lower()}]')
        w.commands(commands);w.call('look-at',9.5,171.5,20.5);w.step_to(w.clock()+1);w.call('wait',12)
        text=(w.socket.parent/'ctl.log').read_text(errors='replace');(OUT/'presentation-client.log').write_text(text)
    observed={}
    for x,y,z,face,offset,box in re.findall(r'CREATE_STICKER_GEOMETRY \[(-?\d+), (-?\d+), (-?\d+)\] (\w+) ([\deE.+-]+) (\[[^\n]+\])\n',text):
        if int(z)!=20 or int(y) not in [170,172] or int(x) not in range(6,12):continue
        offset=float(offset);expected=.25 if int(y)==172 else 0
        assert offset==expected,(face,offset,expected)
        actual=json.loads(box);target=bounds(model,face,offset)
        assert all(abs(a-b)<1e-4 for a,b in zip(actual,target)),(face,offset,actual,target)
        observed[face,offset]=actual
    assert len(observed)==12,sorted(observed)
    receipt={'asset_sha256':hashes,'sound_event':sound,'transforms':[{'facing':face,'offset':offset,'bounds':box} for (face,offset),box in sorted(observed.items())],'geometry_tolerance_blocks':1e-4,'comparison':'Original model data plus source-derived Java renderer transform; actual offscreen Horizon vertices, not Java GPU pixels'}
    (OUT/'presentation-summary.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('Six original model/texture assets match byte-for-byte; all12 facing/endpoint transforms match source-derived geometry in an offscreen client.')
if __name__=='__main__':main()
