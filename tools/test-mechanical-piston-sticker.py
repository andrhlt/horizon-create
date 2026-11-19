#!/usr/bin/env python3
"""Compare the Java mechanical piston carrying an extended Sticker and stone."""
import argparse,hashlib,json,re,tempfile,time
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from fixture_world import ROOT,fixture_world
mp=import_module('test-multiplayer')
OUT=ROOT/'.local/mechanical-piston';TEMPLATE=Path('gametest/contraptions/ploughing.nbt')
PISTON=(27,98,-11);ORIGIN=(25,96,-12)
def pos(distance):return [PISTON[0]+distance,PISTON[1],PISTON[2]]
def xyz(p):return ' '.join(map(str,p))
def field(text,name):
 m=re.search(r'\b'+re.escape(name)+r':\s*(-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?)[fd]?',text)
 return float(m.group(1)) if m else 0.0
def ids_from_payload(text):return sorted(re.findall(r'\bName:\s*"([^\"]+)"',text))
def read_state(control,tick,actors=False):
 data=control.command(f'/data get block {xyz(PISTON)}')
 cells=[control.call('block',*pos(i)) for i in range(-2,6)];ids=[cell['block'] for cell in cells]
 sticker_states=[]
 for distance,cell in zip(range(-2,6),cells):
  if cell['block']=='create:sticker':
   properties=dict(re.findall(r'(\w+)=(\w+)',cell['state']))
   sticker_states.append({'distance':distance,'extended':properties.get('extended')=='true','powered':properties.get('powered')=='true'})
 state=control.call('block',*PISTON)['state'];mode=re.search(r'\bstate=(\w+)',state)
 payload=[];captured_extended=False;dump=''
 if mode and mode.group(1)=='moving':
  dump=control.command(f'/data get block {xyz(PISTON)} Blocks');payload=ids_from_payload(dump)
  states=re.findall(r'BlockState:\s*\{(.*?)\},\s*Pos:',dump)
  sticker=next((state for state in states if re.search(r'Name:\s*"create:sticker"',state)),None)
  captured_extended=bool(sticker and re.search(r'extended:\s*"?true"?',sticker))
 row={'tick':tick,'offset':field(data,'Offset'),'speed':field(data,'Speed'),'state':mode.group(1) if mode else '?','cells':ids,'payload':payload,'captured_extended':captured_extended,'sticker_states':sticker_states,'payload_dump':dump}
 if actors:row['actor_cells']=[control.call('block',PISTON[0]+i,PISTON[1]+1,PISTON[2])['block'] for i in range(5)]
 return row
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for key in ['ctl','client','resources']:p.add_argument(key,type=lambda x:Path(x).resolve(strict=True))
 p.add_argument('--lan',action='store_true');p.add_argument('--visual-guest',action='store_true');p.add_argument('--reload',action='store_true');p.add_argument('--mode',type=int,choices=range(3),default=1);p.add_argument('--extra',choices=['normal','blocked','actors']);a=p.parse_args();OUT.mkdir(parents=True,exist_ok=True)
 if a.visual_guest:a.lan=True
 assert not (a.reload and (a.lan or a.extra or a.mode!=1)), 'reload scenario uses mode 1 without a guest'
 case={'normal':3,'blocked':4,'actors':5}.get(a.extra,a.mode);kind='actors' if a.extra=='actors' else ('extra' if a.extra else 'modes')
 meta=json.loads((ROOT/f'fixtures/mechanical-piston-{kind}-java.metadata.json').read_text())
 assert meta['patch_sha256']==hashlib.sha256((ROOT/f'tools/java-mechanical-piston-{kind}.patch').read_bytes()).hexdigest()
 reference=[r for x in (ROOT/f'fixtures/mechanical-piston-{kind}-java.jsonl').read_text().splitlines() if (r:=json.loads(x))['case']==case]
 assert len(reference)==24
 if a.extra=='blocked':assert all(not r['running'] for r in reference)
 else:assert any(r['running'] and r['captured_extended'] and 'minecraft:stone' in r['payload'] for r in reference)
 errors=[];rows=[];guest_rows=[]
 with tempfile.TemporaryDirectory(prefix='mp-') as tmp,ExitStack() as stack:
  host=stack.enter_context(fixture_world(a,'PistonSticker',TEMPLATE,render=False,env={'HORIZON_NO_AUDIO':'1'}))
  guest=None
  if a.lan:
   address=f"127.0.0.1:{host.call('lan','open','0','commands','force')['port']}"
   guest=stack.enter_context(mp.joined_client(a,Path(tmp),address,'PistonGuest',render=a.visual_guest,scenario='piston-sticker',env={'HORIZON_NO_AUDIO':'1','CREATE_STICKER_TRACE':'1'}))
   mp.until('guest to join',lambda:any(g['name']=='PistonGuest' and g['placed'] for g in host.call('lan','status')['guests']))
   host.command('/tp PistonGuest 28.5 100 -8.5')
   mp.until('guest to load piston area',lambda:guest.call('block',*PISTON).get('loaded'))
  host.command('/gamerule random_tick_speed 0')
  while host.clock()%20!=2:host.step_to(host.clock()+1)
  setup=host.commands(['/place template create:gametest/contraptions/ploughing 25 96 -12','/setblock 28 98 -10 minecraft:lever[face=floor,facing=west,powered=false]','/setblock 29 98 -11 minecraft:stone','/setblock 31 98 -11 minecraft:air','/setblock 28 98 -11 create:sticker[facing=east,extended=true,powered=false]'])
  assert all('Changed the block' in reply or 'Could not set the block' in reply or 'Loaded template' in reply for reply in setup),setup
  if a.extra=='normal':
   axis='true' if host.command('/execute if block 27 98 -11 create:sticky_mechanical_piston[axis_along_first=true]').startswith('Test passed') else 'false'
   host.command(f'/setblock 27 98 -11 create:mechanical_piston[facing=east,axis_along_first={axis}]')
  if a.extra=='blocked':host.command('/setblock 30 98 -11 minecraft:bedrock')
  if a.extra=='actors':
   host.commands(['/setblock 28 99 -11 create:mechanical_plough[facing=east]','/setblock 29 99 -11 create:mechanical_harvester[facing=east]','/setblock 31 99 -11 minecraft:barrier','/summon minecraft:marker 28 98 -11 {CreateSuperGlue:1b,From:[0d,0d,0d],To:[2d,2d,1d]}'])
  if a.visual_guest:
   host.commands(['/fill 26 97 -9 31 97 -5 minecraft:stone','/tp PistonGuest 28.5 98 -7.5'])
   mp.until('guest camera location',lambda:guest.call('state')['player']['position']==[28.5,98.0,-7.5])
   guest.call('look-at',28.5,98.5,-11)
  initial=host.command('/execute if block 28 98 -11 create:sticker[facing=east,extended=true]');assert initial.startswith('Test passed'),initial
  setting=0 if a.extra else a.mode
  host.command(f'/data merge block 27 98 -11 {{ScrollValue:{setting}}}')
  host.step_to(host.clock()+1);host.step_to(host.clock()+1)
  guest_frame_fail=False;guest_frame_ticks=[]
  for tick,want in enumerate(reference):
   cursor=(guest.socket.parent/'ctl.log').stat().st_size if a.visual_guest else 0
   if tick:host.step_to(host.clock()+1)
   if tick==10:host.command('/data merge block 29 97 -10 {ScrollValue:-64}')
   actual=read_state(host,tick,a.extra=='actors');rows.append(actual)
   keys=['offset','speed','state','cells','payload','captured_extended','sticker_states']+(['actor_cells'] if a.extra=='actors' else [])
   for key in keys:
    if actual[key]!=want[key]:errors.append({'tick':tick,'field':key,'java':want[key],'horizon':actual[key]})
   if guest:
    # Wait for each paused authoritative step to replicate; this checks state
    # convergence per server step, not Java packet-arrival latency.
    expected_cells=actual['cells']
    try:mp.until(f'guest step {tick}',lambda:[guest.call('block',*pos(i)).get('block') for i in range(-2,6)]==expected_cells,seconds=5)
    except RuntimeError as e:errors.append({'tick':tick,'field':'guest_cells','error':str(e)})
    remote=[guest.call('block',*pos(i)) for i in range(-2,6)]
    remote_stickers=[]
    for distance,cell in zip(range(-2,6),remote):
     if cell.get('block')=='create:sticker':
      props=dict(re.findall(r'(\w+)=(\w+)',cell['state']))
      remote_stickers.append({'distance':distance,'extended':props.get('extended')=='true','powered':props.get('powered')=='true'})
    if remote_stickers!=want['sticker_states']:errors.append({'tick':tick,'field':'guest_sticker_states','java':want['sticker_states'],'guest':remote_stickers})
    remote_actors=[]
    if a.extra=='actors':
     try:mp.until(f'guest actor cells at step {tick}',lambda:[guest.call('block',PISTON[0]+i,PISTON[1]+1,PISTON[2]).get('block') for i in range(5)]==actual['actor_cells'],seconds=5)
     except RuntimeError as e:errors.append({'tick':tick,'field':'guest_actor_cells','error':str(e)})
     remote_actors=[guest.call('block',PISTON[0]+i,PISTON[1]+1,PISTON[2]).get('block') for i in range(5)]
     if remote_actors!=want['actor_cells']:errors.append({'tick':tick,'field':'guest_java_actor_cells','java':want['actor_cells'],'guest':remote_actors})
    guest_rows.append({'tick':tick,'cells':[cell.get('block') for cell in remote],'sticker_states':remote_stickers,'actor_cells':remote_actors})
    if a.visual_guest and want['captured_extended'] and not guest_frame_fail:
     def head_visible():
      trace=(guest.socket.parent/'ctl.log').read_bytes()[cursor:].decode(errors='replace')
      frames=re.findall(r'CREATE_STICKER_FRAME .*? ([\deE.+-]+) ([\deE.+-]+) (\d+) east',trace)
      return any(float(offset)==.25 and int(count)==40 for _,offset,count in frames)
     try:
      mp.until(f'guest extended Sticker head at step {tick}',head_visible,seconds=4);guest_frame_ticks.append(tick)
     except RuntimeError as e:
      guest_frame_fail=True;errors.append({'tick':tick,'field':'guest_sticker_head','error':str(e)})
   if a.reload and tick==8:
    host.restart()
    mp.until('reloaded piston block',lambda:host.call('block',*PISTON).get('block')=='create:sticky_mechanical_piston')
    restored=read_state(host,tick)
    for key in ['offset','speed','state','cells','payload','captured_extended','sticker_states']:
     if restored[key]!=want[key]:errors.append({'tick':tick,'field':'reload_'+key,'java_uninterrupted':want[key],'horizon_reloaded':restored[key]})
  (OUT/(f'sticker-case{case}-reload' if a.reload else (f'sticker-case{case}-visual-lan' if a.visual_guest else (f'sticker-case{case}-lan' if a.lan else f'sticker-case{case}-solo')))).with_suffix('.json').write_text(json.dumps({'rows':rows,'guest':guest_rows,'guest_frame_ticks':guest_frame_ticks,'mismatches':errors},indent=2)+'\n')
 print(json.dumps({'ticks':len(rows),'case':case,'lan':a.lan,'visual_guest':a.visual_guest,'guest_head_ticks':len(guest_frame_ticks),'reload':a.reload,'mismatches':len(errors),'first':errors[:6]}),flush=True)
 assert not errors,f'{len(errors)} mismatches; see {OUT}'
if __name__=='__main__':main()
