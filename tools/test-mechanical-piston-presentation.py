#!/usr/bin/env python3
"""Check that the moving extended Sticker renders its original head."""
import argparse,json,re
from pathlib import Path
from fixture_world import ROOT,fixture_world
TEMPLATE=Path('gametest/contraptions/ploughing.nbt');OUT=ROOT/'.local/mechanical-piston'
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['ctl','client','resources']:p.add_argument(k,type=lambda x:Path(x).resolve(strict=True))
 a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 with fixture_world(a,'PistonPresentation',TEMPLATE,render=True,env={'HORIZON_NO_AUDIO':'1','CREATE_STICKER_TRACE':'1'}) as w:
  while w.clock()%20!=2:w.step_to(w.clock()+1)
  w.commands(['/place template create:gametest/contraptions/ploughing 25 96 -12','/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]','/setblock 29 98 -11 minecraft:stone','/setblock 28 98 -11 create:sticker[facing=east,extended=true,powered=false]','/data merge block 27 98 -11 {ScrollValue:1}','/fill 26 97 -9 31 97 -5 minecraft:stone','/tp @s 28.5 98 -7.5'])
  w.call('look-at',28.5,98.5,-11);w.step_to(w.clock()+1);w.step_to(w.clock()+1)
  check=w.command('/execute if entity @e[type=minecraft:block_display]');match=re.search(r'Count: (\d+)',check)
  assert match and int(match.group(1))>=4,check
  log=w.socket.parent/'ctl.log';start=len(log.read_bytes());w.call('wait',15)
  trace=log.read_bytes()[start:].decode(errors='replace');(OUT/'moving-presentation.log').write_text(trace)
  frames=re.findall(r'CREATE_STICKER_FRAME .*? ([\deE.+-]+) ([\deE.+-]+) (\d+) east',trace)
  passed=any(float(offset)==.25 and int(count)==40 for _,offset,count in frames)
  print(json.dumps({'moving_displays':int(match.group(1)),'sticker_head_frames':len(frames),'extended_head_observed':passed}),flush=True)
  assert passed,'Moving extended Sticker has no rendered head in the offscreen client'
if __name__=='__main__':main()
