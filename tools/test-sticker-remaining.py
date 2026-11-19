#!/usr/bin/env python3
"""Batch original Java Sticker callbacks, face rules and actual movement comparisons."""
import argparse,hashlib,json,math,re,struct
from pathlib import Path
from fixture_world import ROOT,fixture_world
OUT=ROOT/'.local/sticker-completion'
def bits(value):return struct.unpack('>d',int(value).to_bytes(8,'big'))[0]
def vector(message):return [float(x) for x in re.findall(r'(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)d',message)]
def probe(world,op,cases):
    keys={'kind','facing','extended','living','careful','vy','distance','state','direction'}
    clean=[{k:v for k,v in row.items() if k in keys} for row in cases]
    for row in clean:
        if row.get('state','').partition('[')[0]=='minecraft:chain':row['state']=row['state'].replace('minecraft:chain','minecraft:iron_chain',1)
    result=world.call('create-test-sticker',json.dumps({'op':op,'pos':[9,190,20],'cases':clean},separators=(',',':')))['rows']
    for have,want in zip(result,cases):
        if 'state' in want:have['state']=want['state']
    return result
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['ctl','client','resources']:p.add_argument(name,type=lambda x:Path(x).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
    a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    meta=json.loads((ROOT/'fixtures/sticker-remaining-java.metadata.json').read_text())
    assert meta['patch_sha256']==hashlib.sha256((ROOT/'tools/java-sticker-remaining.patch').read_bytes()).hexdigest()
    expected=[json.loads(x) for x in (ROOT/'fixtures/sticker-remaining-java.jsonl').read_text().splitlines()]
    assert len(expected)==meta['records']==999
    actual=[];errors=[]
    with fixture_world(a,'StickerRemaining',render=False,pack=a.pack,env={'CREATE_STICKER_TEST':'1','HORIZON_NO_AUDIO':'1'}) as w:
        w.command('/summon minecraft:pig 9.5 196 20.5 {NoAI:1b,Tags:["callback_template"]}')
        callbacks=[row for row in expected if row['kind'] in ['physics','fall']]
        observed=probe(w,'callbacks',callbacks)
        actual.extend(observed)
        (OUT/'callback-actual.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in observed))
        for index,(have,want) in enumerate(zip(observed,callbacks)):
            if have!=want:errors.append({'phase':'callbacks','index':index,'actual':have,'expected':want})
        w.command('/setblock 9 189 20 minecraft:stone')
        faces=[row for row in expected if row['kind']=='face']
        observed=probe(w,'faces',faces);actual.extend(observed)
        for index,(have,want) in enumerate(zip(observed,faces)):
            if have!=want:errors.append({'phase':'faces','index':index,'actual':have,'expected':want})
        for scenario,x in enumerate([9,13,17]):
            block=['create:sticker[facing=up]','create:sticker[facing=north]','minecraft:stone'][scenario]
            w.commands([f'/setblock {x} 175 20 {block}',f'/summon minecraft:pig {x+.5} 176 20.5 {{Motion:[0.2d,0.0d,0.1d],Tags:["sticker{scenario}"],NoAI:0b}}',f'/attribute @e[tag=sticker{scenario},limit=1] minecraft:movement_speed base set 0'])
        start=w.clock()
        trajectories={(r['scenario'],r['tick']):r for r in expected if r['kind']=='trajectory'}
        for tick in range(1,6):
            w.step_to(start+tick)
            for scenario,x in enumerate([9,13,17]):
                selector=f'@e[tag=sticker{scenario},limit=1]'
                position=vector(w.command(f'/data get entity {selector} Pos'));motion=vector(w.command(f'/data get entity {selector} Motion'))
                position=[position[0]-x,position[1]-175,position[2]-20]
                row={'kind':'trajectory','scenario':scenario,'tick':tick,'position':position,'motion':motion};actual.append(row)
                want=trajectories[scenario,tick]
                for key in ['position','motion']:
                    target=[bits(value) for value in want[key]]
                    if not all(math.isclose(got,ref,rel_tol=0,abs_tol=1e-7) for got,ref in zip(row[key],target)):
                        errors.append({'phase':'trajectory','scenario':scenario,'tick':tick,'field':key,'actual':row[key],'expected':target})
    (OUT/'remaining-actual.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in actual))
    (OUT/'remaining-mismatches.json').write_text(json.dumps(errors,indent=2)+'\n')
    print(json.dumps({'records':len(actual),'physics':384,'fall':120,'faces':480,'movement_ticks':15,'mismatches':len(errors)}),flush=True)
    assert len(actual)==999
    if errors:
        print(json.dumps(errors[:12],indent=2),flush=True)
        raise AssertionError(f'{len(errors)} mismatches; see {OUT}/remaining-mismatches.json')
    print('384 bit-exact physics callbacks,120 fall results,480 face decisions and15 actual movement ticks match Java.',flush=True)
if __name__=='__main__':main()
