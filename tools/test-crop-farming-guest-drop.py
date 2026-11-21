#!/usr/bin/env python3
"""Verify LAN guest convergence by collecting the harvester's dropped output."""
import argparse, re, tempfile
from contextlib import ExitStack
from pathlib import Path
from fixture_world import fixture_world
import importlib
mp = importlib.import_module("test-multiplayer")
TEMPLATE=Path("gametest/contraptions/crop_farming.nbt")
COUNT=re.compile(r"(?:Count|count): (\d+)")
POS=re.compile(r"\[([-0-9.]+)d, ([-0-9.]+)d, ([-0-9.]+)d\]")
def total(c): return sum(c.call("inventory")["counts"].values())
def run(a):
  with tempfile.TemporaryDirectory(prefix="hc-crop-drop-") as raw, ExitStack() as s:
    h=s.enter_context(fixture_world(a,"crop_drop",TEMPLATE)); h.call("lan","open","0","commands","force")
    g=s.enter_context(mp.joined_client(a,Path(raw),f"127.0.0.1:{h.call('lan','status')['port']}","CropGuest",scenario="crop-drop"))
    h.command("/gamerule random_tick_speed 0")
    while h.clock()%20!=2: h.step_to(h.clock()+1)
    h.command("/place template create:gametest/contraptions/crop_farming 3 96 -12"); h.command("/tp @s 7.5 99 -8.5"); h.call("interact",7,98,-11,"up")
    for _ in range(72): h.step_to(h.clock()+1)
    dump=h.command("/data get entity @e[type=minecraft:chest_minecart,limit=1] Items"); expected=sum(map(int,COUNT.findall(dump)))
    if expected<1: raise RuntimeError(f"no authoritative output: {dump}")
    before=total(g); h.command("/kill @e[type=minecraft:chest_minecart]"); g.call("tp",7.5,97,-2.5)
    for _ in range(4): h.step_to(h.clock()+1)
    after=total(g)
    if after-before!=expected: raise RuntimeError(f"guest got {after-before}, expected {expected}; {dump}")
  print(f"guest collected dropped harvester output count {expected}; authoritative and guest counts converged")
if __name__=='__main__':
  p=argparse.ArgumentParser()
  for n in ('ctl','client','resources'): p.add_argument(n,type=lambda x:Path(x).resolve())
  run(p.parse_args())
