#!/usr/bin/env python3
"""Bounded station status, controls prompts and mounted arrival audio checks."""
import argparse
from contextlib import ExitStack
from importlib import import_module
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

train = import_module('test-simple-train')
trip = import_module('test-scheduled-station-approach')
conductor = trip.conductor
mp = conductor.multiplayer


def step(world, ticks=1):
    for _ in range(ticks):
        world.step_to(world.clock()+1)


def source(world):
    x,y,z = train.STATION
    world.commands((f'/setblock {x+1} {y} {z} create:display_link[facing=east]{{TargetOffset:[I;2,0,0]}}',
                    f'/setblock {x+3} {y} {z} create:nixie_tube'))
    return x+1,y,z


def text(world):
    x,y,z=train.STATION
    return world.command(f'/data get block {x+3} {y} {z} CustomText')


def configure(world, actor, who, pos):
    x,y,z=pos
    world.commands((f'/tp {who} {x+0.5} {y} {z+2.5}',f'/clear {who}'))
    actor.call('wait',4)
    actor.call('interact',*pos,'up')
    mp.until('station train status source',lambda:any(b.get('label')=='Train Schedule Status' for b in actor.call('screen').get('buttons',[])))
    actor.call('click-button','Train Schedule Status')
    actor.call('key','escape','tap')
    step(world)


def join(sessions,args,world,env):
    port=world.call('lan','open','0','commands','force')['port']
    scratch=Path(sessions.enter_context(TemporaryDirectory(prefix='hc-train-feedback-')))
    guest=sessions.enter_context(mp.joined_client(args,scratch,f'127.0.0.1:{port}','FeedbackGuest',render=True,scenario='train-feedback',pack=args.pack,env=env))
    mp.until('feedback guest placed',lambda:any(g['name']=='FeedbackGuest' and g['placed'] for g in world.call('lan','status')['guests']))
    world.command('/op FeedbackGuest')
    return guest


def status_cases(args):
    with ExitStack() as sessions:
        world=sessions.enter_context(fixture_world(args,'TrainFeedbackStatus',train.STRUCTURE,render=True,pack=args.pack,env={'HORIZON_NO_AUDIO':'1'}))
        train.setup(world,after_station=trip.place_stations,take_controls=False)
        pos=source(world)
        step(world)
        actor=join(sessions,args,world,{'HORIZON_NO_AUDIO':'1'}) if args.lan else world
        who='FeedbackGuest' if args.lan else '@s'
        configure(world,actor,who,pos)
        assert 'Departs' not in text(world),text(world)
        program=trip.PROGRAM.replace('Value:3','Value:2400')
        trip.give_fixture_schedule(world,actor,who,program)
        conductor.click(world,actor,who,0)
        step(world,3)
        assert 'Departs in 1 Minute' in text(world),text(world)
        # Noncyclic last stop, paused and transit status are blank in Java.
        for patch in ('{SchedulePaused:1b}','{SchedulePaused:0b,ScheduleRuntime:{Stage:1}}'):
            world.command(f'/data merge entity {train.ENTITY} {{CreateTrain:{patch}}}')
            step(world)
            assert 'Departs' not in text(world),text(world)
        world.command(f'/data merge entity {train.ENTITY} {{CreateTrain:{{SchedulePaused:0b,ScheduleRuntime:{{Stage:2,Entry:0,Wait:[I;0,2301]}}}}}}')
        step(world)
        assert 'Departs in 5 Seconds' in text(world),text(world)
        if args.lan:
            x,y,z=train.STATION
            mp.until('guest sees station display',lambda:actor.call('block',x+3,y,z)['block']=='create:nixie_tube')
        else:
            world.call('save');world.restart();step(world)
            assert 'Departs in 5 Seconds' in text(world),text(world)
            x,y,z=pos
            assert 'create:train_status' in world.command(f'/data get block {x} {y} {z} Source')
        reference=json.loads((ROOT/'fixtures/train-feedback-java.json').read_text())
        for row in reference[:6]:
            elapsed=int(row['case'])
            world.command(f'/data merge entity {train.ENTITY} {{CreateTrain:{{ScheduleRuntime:{{Stage:2,Entry:0,Cooldown:10,Wait:[I;0,{elapsed}]}}}}}}')
            step(world)
            assert row['text'] in text(world),(row,text(world))
        world.command(f'/data merge entity {train.ENTITY} {{CreateTrain:{{ScheduleRuntime:{{Stage:2,Entry:1,Wait:[I;0,0]}}}}}}')
        step(world)
        assert 'Departs' not in text(world),text(world)
    print('Station train status: selectable source, absent/paused/transit/final negatives, minute/second countdown, guest configuration or idle reopen passed.',flush=True)


def mounted(world):
    x,y,z=train.X+2,train.Y+3,train.Z
    world.commands((f'/setblock {x} {y} {z} minecraft:bell',
                    f'/setblock {x+1} {y} {z} minecraft:note_block[note=12,instrument=harp]',
                    f'/setblock {x+2} {y} {z} create:steam_whistle[facing=north,size=small]{{Pitch:0}}'))


def read_hud(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def manual_cases(args):
    with ExitStack() as sessions:
        scratch=Path(sessions.enter_context(TemporaryDirectory(prefix='hc-train-hud-')))
        host_trace=scratch/'host.jsonl'; guest_trace=scratch/'guest.jsonl'
        env={'HORIZON_NO_AUDIO':'1','CREATE_TRAIN_HUD_TRACE':str(host_trace)}
        world=sessions.enter_context(fixture_world(args,'TrainFeedbackManual',train.STRUCTURE,render=True,pack=args.pack,env=env))
        def stations(w):
            trip.approach.place_stations(w)
            for pos,name in ((train.STATION,'Origin'),(trip.approach.DESTINATION,'Terminal')):
                w.command(f'/data merge block {trip.coordinates(pos)} {{Name:"{name}"}}')
        train.setup(world,after_station=stations,before_glue=mounted,take_controls=not args.lan)
        world.command(f'/data merge entity {train.ENTITY} {{CreateTrain:{{Name:"Feedback Express"}}}}')
        actor=join(sessions,args,world,{'HORIZON_NO_AUDIO':'1','CREATE_TRAIN_HUD_TRACE':str(guest_trace)}) if args.lan else world
        trace=guest_trace if args.lan else host_trace
        who='FeedbackGuest' if args.lan else '@s'
        if args.lan:
            world.commands((f'/tp @s {train.X+8} {train.Y} {train.Z-4}',f'/attribute {who} minecraft:movement_speed base set 0',f'/tp {who} {train.X+0.5} {train.Y} {train.Z-1.3}'))
            actor.call('wait',5);actor.call('look-at',train.X+1.5,train.Y+3.45,train.Z+0.5);actor.call('mouse','right','click');actor.call('wait',5)
            uuid=world.command('/data get entity FeedbackGuest UUID').partition('data: ')[2]
            mp.until('guest owns train controls',lambda:world.command(f'/data get entity {train.ENTITY} CreateTrain.Driver').endswith(uuid))
        world.command(f'/attribute {who} minecraft:gravity base set 0')
        step(world,2);actor.call('wait',3)
        mp.until('named train HUD',lambda:any(v['name']=='Feedback Express' for v in read_hud(trace)))
        actor.call('key','space','down');actor.call('wait',3);step(world);actor.call('wait',3)
        mp.until('arrival station prompt',lambda:any(v['prompt']=='Arrived at Origin' for v in read_hud(trace)))
        actor.call('screenshot',ROOT / f'.local/train-feedback-hud-{"lan" if args.lan else "solo"}.png')
        actor.call('key','space','up');actor.call('key','w','down');actor.call('wait',3)
        heard=actor.call('status')['heard']
        for tick in range(65):
            step(world)
            if tick==17:
                actor.call('key','w','up');actor.call('key','space','down');actor.call('wait',3)
            speed,*wheels,_=train.sample(world)
            if tick%3==2:
                world.command(f'/tp {who} {train.X+(wheels[0]+wheels[1])/2} {train.Y+4} {train.Z+1.5}')
                actor.call('wait',3)
        actor.call('key','space','up');actor.call('wait',4)
        views=read_hud(trace)
        assert any(v['prompt']=='Departing from Origin' for v in views),views[-3:]
        assert any(v['speed']>0 for v in views),views[-3:]
        after=actor.call('status')['heard']
        for sound in ('minecraft:block.bell.use','minecraft:block.note_block.harp','create:whistle_train'):
            assert after.get(sound,0)-heard.get(sound,0)==1,(sound,heard,after)
        if not args.lan:
            before=train.sample(world)
            world.call('save');world.restart();step(world)
            after_reload=train.sample(world)
            assert abs(after_reload[0]) > 0 and after_reload[1:3] != before[1:3],(before,after_reload)
            assert 'Feedback Express' in world.command(f'/data get entity {train.ENTITY} CreateTrain.Name')
        print('Named controls HUD, arrival/departure prompts, speed and one mounted bell/note/whistle arrival sequence passed.',flush=True)


def run(args):
    status_cases(args)
    manual_cases(args)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('ctl','client','resources'):p.add_argument(arg,type=lambda v:Path(v).resolve(strict=True))
    p.add_argument('--pack',type=Path,default=ROOT/'.local/create.hmod')
    p.add_argument('--lan',action='store_true')
    run(p.parse_args())
