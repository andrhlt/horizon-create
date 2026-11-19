#!/usr/bin/env python3
"""Compare the translated Sticker core and real Horizon adapters with Java."""
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from fixture_world import ROOT,fixture_world

DIRECTIONS={'down':(0,-1,0),'up':(0,1,0),'north':(0,0,-1),'south':(0,0,1),'west':(-1,0,0),'east':(1,0,0)}
OUT=ROOT/'.local/sticker-benchmark'
def coord(p):return ' '.join(map(str,p))
def add(a,b):return [x+y for x,y in zip(a,b)]
def call(world,op,pos,**kw):return world.call('create-test-sticker',json.dumps({'op':op,'pos':pos,**kw},separators=(',',':')))
def equal(actual,expected,label):
    assert len(actual)==len(expected),(label,len(actual),len(expected))
    for i,(a,e) in enumerate(zip(actual,expected)):
        assert a==e,(label,i,a,e)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ['ctl','client','resources']:p.add_argument(key,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
    p.add_argument('--visual-only',action='store_true')
    a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    if not a.visual_only:
        metadata=json.loads((ROOT/'fixtures/sticker-source-java.metadata.json').read_text())
        assert metadata['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-source.patch').read_bytes()).hexdigest()
        expected=[json.loads(x) for x in (ROOT/'fixtures/sticker-source-java.jsonl').read_text().splitlines()]
        rust=ROOT/'.local/patched-launcher/rust/1.99.1-aarch64-apple-darwin/bin/rustc'
        subprocess.run([str(rust),'--edition=2024','-O',str(ROOT/'tools/sticker-replay.rs'),'-o',str(OUT/'replay')],check=True)
        core=subprocess.run([str(OUT/'replay')],text=True,capture_output=True,check=True)
        actual_core=[json.loads(x) for x in core.stdout.splitlines()]
        equal(actual_core,[x for x in expected if x['kind']=='animation'],'animation')
        (OUT/'core.jsonl').write_text(core.stdout)
        observed=[];origin=[9,170,20]
        with fixture_world(a,'StickerSource',render=False,pack=a.pack,env={'CREATE_STICKER_TEST':'1','HORIZON_NO_AUDIO':'1'}) as world:
            for rig,(face,normal) in enumerate(DIRECTIONS.items()):
                pos=add(origin,[rig*4,0,0]);front=add(pos,normal);back=add(pos,[-v for v in normal])
                world.call('command',f'/setblock {coord(pos)} create:sticker[facing={face}]')
                world.call('command',f'/setblock {coord(front)} minecraft:stone')
                for stage in range(6):
                    powered=stage in [1,2,4]
                    world.call('command',f'/setblock {coord(back)} minecraft:'+('redstone_block' if powered else 'air'))
                    observed.append({'kind':'world','facing':face,'stage':stage,**call(world,'world',pos)})
            pos=add(origin,[0,5,0]);controller=add(pos,[0,-1,0])
            for face,normal in DIRECTIONS.items():
                for variant in range(3):
                    for delta in DIRECTIONS.values():world.call('command',f'/setblock {coord(add(pos,delta))} minecraft:air')
                    world.call('command',f'/setblock {coord(controller)} create:mechanical_bearing[facing=up]')
                    world.call('command',f'/setblock {coord(pos)} create:sticker[facing={face},extended={str(variant!=0).lower()}]')
                    target=f'create:mechanical_drill[facing={next(k for k,v in DIRECTIONS.items() if v==tuple(-n for n in normal))}]' if variant==2 else 'minecraft:stone'
                    world.call('command',f'/setblock {coord(add(pos,normal))} {target}')
                    captured=call(world,'capture',pos,controller=controller)['positions']
                    observed.append({'kind':'capture','facing':face,'variant':variant,'positions':sorted(','.join(map(str,x)) for x in captured)})
        (OUT/'world.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in observed))
        equal(observed,[x for x in expected if x['kind']!='animation'],'world/attachment')
        print('192 animation ticks / 960 partial-frame offsets and 54 world/assembly records match Java.',flush=True)
    with fixture_world(a,'StickerClient',render=True,pack=a.pack,env={'CREATE_STICKER_TRACE':'1','HORIZON_NO_AUDIO':'1'}) as world:
        pos=[9,170,20]
        world.commands(['/fill 7 169 22 12 169 27 minecraft:stone','/setblock 9 170 20 create:sticker[facing=up]','/setblock 9 171 20 minecraft:stone','/tp @s 9.5 170 24.5'])
        world.call('look-at',9.5,170.5,20.5);world.step_to(world.clock()+1);world.call('wait',10)
        world.command('/setblock 9 170 19 minecraft:redstone_block');world.step_to(world.clock()+1);world.call('wait',15)
        world.command('/setblock 9 170 19 minecraft:air');world.step_to(world.clock()+1);world.call('wait',3)
        world.command('/setblock 9 170 19 minecraft:redstone_block');world.step_to(world.clock()+1);world.call('wait',15)
        world.command('/setblock 9 170 19 minecraft:air');world.step_to(world.clock()+1);world.call('wait',3)
        text=(world.socket.parent/'ctl.log').read_text(errors='replace')
        (OUT/'client.log').write_text(text)
        frames=re.findall(r'CREATE_STICKER_FRAME (-?\d+) \[9, 170, 20\] ([\deE.+-]+) ([\deE.+-]+) (\d+) (\w+)',text)
        assert frames,'No original Sticker head render calls'
        offsets=[float(x[2]) for x in frames]
        with zipfile.ZipFile(a.pack) as pack:model=json.loads(pack.read('assets/create/models/block/sticker/head.json'))
        vertices=sum(len(x['faces'])*4 for x in model['elements'])
        assert all(int(x[3])==vertices for x in frames),(vertices,frames[:3])
        assert min(offsets)==0 and max(offsets)==.25 and any(0<x<.25 for x in offsets),(min(offsets),max(offsets))
        ticks=re.findall(r'CREATE_STICKER_TICK -?\d+ \[9, 170, 20\] (\d+) (\d+) (\d+) (\d+) (true|false) (true|false)',text)
        java=[json.loads(line) for line in (ROOT/'fixtures/sticker-source-java.jsonl').read_text().splitlines()]
        signatures={tuple(row[key] for key in ('previous','value','target','events')) for row in java if row['kind']=='animation'}
        assert ticks,'No production client animation ticks'
        assert all(tuple(map(int,row[:4])) in signatures for row in ticks),'Client transition missing from Java trace'
        events=[int(row[3]) for row in ticks]
        assert any(event&1 for event in events) and any(event&2 for event in events),'Missing attachment/detachment events'
        (OUT/'client-summary.json').write_text(json.dumps({'frames':len(frames),'client_ticks':len(ticks),'vertices':vertices,'min_offset':min(offsets),'max_offset':max(offsets),'attachment_events':sum(bool(event&1) for event in events),'detachment_events':sum(bool(event&2) for event in events)},indent=2)+'\n')
    print('Original head model renders, interpolates 0→0.25→0 in a real offscreen client.',flush=True)
if __name__=='__main__':main()
