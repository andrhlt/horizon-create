#!/usr/bin/env python3
"""Compare original Sticker wrench rotations and exercise weak-power isolation."""
import argparse,hashlib,json
from pathlib import Path
from fixture_world import ROOT,fixture_world
DIRECTIONS={'down':(0,-1,0),'up':(0,1,0),'north':(0,0,-1),'south':(0,0,1),'west':(-1,0,0),'east':(1,0,0)}
def coords(p):return ' '.join(map(str,p))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['ctl','client','resources']:p.add_argument(name,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=Path);a=p.parse_args()
    meta=json.loads((ROOT/'fixtures/sticker-interactions-java.metadata.json').read_text())
    assert meta['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-interactions.patch').read_bytes()).hexdigest()
    expected=[json.loads(line) for line in (ROOT/'fixtures/sticker-interactions-java.jsonl').read_text().splitlines()]
    inputs=[{k:v for k,v in row.items() if k in ['kind','facing','target','direction']} for row in expected]
    with fixture_world(a,'StickerInteractions',render=False,pack=a.pack,env={'CREATE_STICKER_TEST':'1','HORIZON_NO_AUDIO':'1'}) as w:
        default_meta=json.loads((ROOT/'fixtures/sticker-defaults-java.metadata.json').read_text())
        assert default_meta['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-defaults.patch').read_bytes()).hexdigest()
        expected_default=json.loads((ROOT/'fixtures/sticker-defaults-java.jsonl').read_text().strip())
        w.command('/setblock 9 190 20 create:sticker')
        actual_default=w.call('create-test-sticker',json.dumps({'op':'defaults','pos':[9,190,20]}))
        for key,value in expected_default.items():
            if isinstance(value,float):assert abs(actual_default[key]-value)<1e-7,(key,actual_default[key],value)
            else:assert actual_default[key]==value,(key,actual_default[key],value)
        w.command('/setblock 9 189 20 minecraft:redstone_block')
        actual=w.call('create-test-sticker',json.dumps({'op':'interactions','pos':[9,190,20],'cases':inputs},separators=(',',':')))['rows']
        assert len(actual)==len(expected)==42
        for have,want in zip(actual,expected):assert have==want,(have,want)
        isolation=[]
        for index,(face,normal) in enumerate(DIRECTIONS.items()):
            center=[9+index*4,178,20];source=[x-d for x,d in zip(center,normal)];target=[x+d for x,d in zip(center,normal)]
            w.commands([f'/setblock {coords(center)} create:sticker[facing=up]',f'/setblock {coords(target)} create:sticker[facing=up]',f'/setblock {coords(source)} minecraft:redstone_block'])
            get=lambda pos:w.call('create-test-sticker',json.dumps({'op':'world','pos':pos}))
            assert get(center)['powered'],(face,'source did not power center')
            assert not get(target)['powered'],(face,'Sticker conducted weak power')
            isolation.append(face)
    out=ROOT/'.local/sticker-completion';out.mkdir(parents=True,exist_ok=True)
    (out/'interaction-summary.json').write_text(json.dumps({'java_records':43,'physical_defaults':actual_default,'weak_isolation_directions':isolation,'result':'pass'},indent=2)+'\n')
    print('Original physical defaults,36 wrench rotations and6 weak-power decisions match Java; indirect power is blocked in6 real-world directions.')
if __name__=='__main__':main()
