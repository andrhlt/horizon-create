#!/usr/bin/env python3
"""Compare player effect ticks after summoned golden-apple projectile hits.

The command harness has one real player; it summons an ownerless projectile.
"""
import argparse,csv,re
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT,install_pack,last_command_message,run_command_harness
EFFECTS=('regeneration','absorption','resistance','fire_resistance')

def run(args):
 with (ROOT/'fixtures/potato-cannon-gapple-player-ticks-java.csv').open() as f: all_rows=list(csv.DictReader(f))
 for case in ('golden','enchanted'):
  rows=[r for r in all_rows if r['case']==case]
  ammo='minecraft:golden_apple' if case=='golden' else 'minecraft:enchanted_golden_apple'
  commands=('/gamemode survival @s','/gamerule naturalRegeneration false','/fill 0 99 -5 16 106 10 minecraft:air','/fill 0 100 -5 16 100 10 minecraft:stone','/tp @s 8.5 101 4.5 0 0',f'/summon create:potato_projectile 8.5 102.4 2.0 {{Motion:[0.0d,0.0d,1.0d],Item:{{id:"{ammo}",count:1}}}}')
  ops=[{'op':'settle'},*({'op':'cmd','cmd':c,'record':False} for c in commands)]
  for tick in range(5):
   ops.append({'op':'tick','n':1})
   ops.extend({'op':'cmd','cmd':c} for c in ('/data get entity @s Health','/data get entity @s AbsorptionAmount','/data get entity @s active_effects'))
  with TemporaryDirectory(prefix='hc-gapple-player-ticks-') as tmp:
   game=Path(tmp)/'game';install_pack(game,args.pack)
   records=run_command_harness(args,game,'gapple-player-ticks-'+case,ops)
  assert len(records)==15,len(records)
  samples=[tuple(last_command_message(r) for r in records[i:i+3]) for i in range(0,len(records),3)]
  assert '20.0f' in samples[0][0] and 'minecraft:regeneration' not in samples[0][2],samples[0]
  for row,(health,absorption,effects) in zip(rows,samples[1:],strict=True):
   hp=re.search(r'entity data: ([\d.]+)f$',health);ab=re.search(r'entity data: ([\d.]+)f$',absorption)
   assert hp and ab and float(hp[1])==float(row['health']) and float(ab[1])==float(row['absorption']),(case,row,health,absorption)
   actual={}
   for entry in re.findall(r'\{[^{}]*\}',effects):
    name=re.search(r'id:\s*"minecraft:([a-z_]+)"',entry);duration=re.search(r'duration:\s*(\d+)',entry);amp=re.search(r'amplifier:\s*(\d+)',entry)
    if name and duration:actual[name[1]]=(int(duration[1]),int(amp[1]) if amp else 0)
   expected={name:(int(row[name+'_duration']),int(row[name+'_amplifier'])) for name in EFFECTS if int(row[name+'_duration'])>=0}
   assert actual==expected,(case,row,actual,expected)
  print(f'{case}: health, absorption, and effects matched Java on four player ticks.',flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for key in ('ctl','client','resources'):p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
 p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
 run(p.parse_args())
