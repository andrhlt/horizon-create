#!/usr/bin/env python3
"""Select a train station and place a bound Postbox in survival."""
import argparse
import gzip
from contextlib import ExitStack
from importlib import import_module
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import fixture_world

mp = import_module("test-multiplayer")
train = import_module("test-simple-train")
STATION = train.STATION
POSTBOX = (11, 112, -5)
BOX = "create:white_postbox"
PACKAGE = "create:cardboard_package_12x12"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=lambda value: Path(value).resolve())
    parser.add_argument("--pack", type=lambda value: Path(value).resolve())
    parser.add_argument("--lan", action="store_true")
    parser.add_argument("--registry", action="store_true", help="check persisted station registry and explicit removal")
    parser.add_argument("--primed", action="store_true", help="simulate an offline buffer change and check restoration")
    args = parser.parse_args()
    if args.primed and not args.registry:
        parser.error("--primed requires --registry")
    if args.registry and args.lan:
        parser.error("--registry currently requires the solo actor across world restarts")
    with TemporaryDirectory(prefix="hc-postbox-", dir="/private/tmp") as scratch, ExitStack() as sessions:
        env = {"HORIZON_NO_AUDIO": "1"}
        world = sessions.enter_context(fixture_world(args, "TrainPostboxTarget", render=not args.lan,
                                                     pack=args.pack, env=env))
        actor, player = world, "@s"
        if args.lan:
            player = "PostboxGuest"
            port = world.call("lan", "open", "0", "commands", "force")["port"]
            actor = sessions.enter_context(mp.joined_client(
                args, Path(scratch), f"127.0.0.1:{port}", player, render=True,
                scenario="postbox-target", pack=args.pack, env=env))
            mp.until("the guest to join", lambda: any(
                guest["name"] == player and guest["placed"]
                for guest in world.call("lan", "status")["guests"]))
        x, y, z = train.X, train.Y, train.Z
        world.commands((f"/fill {x-6} {y-1} {z-5} {x+12} {y-1} {z+8} minecraft:smooth_stone",
                        f"/fill {x-5} {y} {z} {x+10} {y} {z} create:track[shape=xo]",
                        f"/gamemode survival {player}", f"/tp {player} {x+2.5} {y} {z+0.5} 90 20",
                        f"/item replace entity {player} hotbar.0 with create:track_station"))
        actor.call("wait", 4)
        actor.call("select", "create:track_station")
        train.click_track(actor, x)
        sx, sy, sz = STATION
        world.command(f"/tp {player} {sx+0.5} {sy} {sz+2.5} 180 20")
        actor.call("wait", 4)
        actor.call("interact", sx, sy-1, sz, "up")
        mp.until("the selected station to be placed", lambda:
                 world.call("block", *STATION)["block"] == "create:track_station")
        actor.call("wait", 4)
        world.command(f"/item replace entity {player} hotbar.0 with {BOX}")
        mp.until("the actor to hold a Postbox", lambda: mp.count(actor, BOX) == 1)
        actor.call("select", BOX)
        actor.call("look-at", sx+0.5, sy+0.4, sz+0.5)
        mp.until("the station to be targeted", lambda:
                 (actor.call("looking-at").get("block") or {}).get("pos") == list(STATION))
        actor.call("mouse", "right", "click")
        actor.call("wait", 4)
        assert actor.call("state")["screen"] == "playing", "Selecting a station opened its menu"
        px, py, pz = POSTBOX
        world.command(f"/tp {player} {px+0.5} {py} {pz+2.5}")
        actor.call("wait", 4)
        actor.call("interact", px, py-1, pz, "up")
        mp.until("the selected Postbox to be placed", lambda: world.call("block", *POSTBOX)["block"] == BOX)
        mp.until("the bound Postbox configuration to open", lambda:
                 actor.call("state")["screen"] == "container"
                 and "Frogport Address" in str(actor.call("screen")))
        if args.registry:
            actor.call("click-button", "Frogport Address")
            actor.call("type", "Depot")
            actor.call("click-button", "Confirm")
            mp.until("the configuration to close", lambda: actor.call("state")["screen"] == "playing")
        else:
            actor.call("key", "escape", "tap")
        def binding():
            value = world.command(f"/data get block {px} {py} {pz} Target")
            return value if "train_station" in value and "-2, 0, -1" in value else None
        target = mp.until("the Postbox to retain its selected station", binding)
        print(f"A Postbox was bound to the selected station: {target}")
        if args.registry:
            mp.until("the address to save", lambda:
                     '"Depot"' in world.command(f"/data get block {px} {py} {pz} AddressFilter"))
            world.step_to(world.clock() + 1)
            world.command("/setblock 14 112 -4 minecraft:barrel")
            world.command(f'/data merge block 14 112 -4 {{Items:[{{Slot:0b,id:"{PACKAGE}",count:1,components:{{"create:package_address":"Parcel Depot"}}}}]}}')
            world.command("/item replace entity @s hotbar.0 from block 14 112 -4 container.0")
            mp.until("the addressed package to reach the hotbar", lambda: mp.count(world, PACKAGE) == 1)
            world.call("interact", px, py, pz, "south")
            menu = import_module("test-frogport-menu")
            mp.until("the Postbox inventory to open", lambda: world.call("state")["screen"] == "container")
            world.call("click-slot", 0)
            world.call("click-slot", 317)
            mp.until("the package to enter the last Postbox slot", lambda: menu.stack_item(world, 317) == PACKAGE)
            world.call("key", "escape", "tap")
            world.step_to(world.clock() + 1)
            game_dir = Path(world._launch[world._launch.index("--game-dir") + 1])
            path = game_dir / "saves/TrainPostboxTarget/dimensions/minecraft/overworld/data/horizon/attachments.dat"
            read_nbt = import_module("test-schematic-capture").read_nbt
            def ports():
                return read_nbt(path)["data"]["create"]["train_postbox_ports"]["value"]["Ports"]
            world.stop()
            saved = ports()
            assert len(saved) == 1 and saved[0]["Station"] == list(STATION) and saved[0]["Pos"] == list(POSTBOX), saved
            assert saved[0]["Address"] == "Depot" and saved[0]["Primed"] == 0, saved
            buffer = saved[0]["OfflineBuffer"]
            assert buffer["Size"] == 18 and len(buffer["Items"]) == 1, saved
            item = buffer["Items"][0]
            assert item["Slot"] == 17 and item["id"] == PACKAGE and item["count"] == 1, item
            assert item["components"]["create:package_address"] == "Parcel Depot", item
            world.open()
            world.command("/attribute @s minecraft:gravity base set 0")
            world.command("/tp @s 512 120 512")
            def unloaded():
                world.call("wait", 4)
                world.step_to(world.clock() + 1)
                return all(world.command(f"/execute if loaded {x} {y} {z}") == "Test failed"
                           and "has the following block data" not in world.command(f"/data get block {x} {y} {z}")
                           for x, y, z in (STATION, POSTBOX))
            mp.until("both station and Postbox chunks to unload", unloaded, seconds=40)
            world.stop()
            assert ports() == saved, ports()
            if args.primed:
                # Simulate a train changing its persisted buffer while the
                # Postbox is unloaded; no train transfer is implemented here.
                raw = gzip.decompress(path.read_bytes())
                primed = b"\x01\x00\x06Primed\x00"
                old_address, new_address = b"Parcel Depot", b"Remote Depot"
                assert raw.count(primed) == 1 and raw.count(old_address) == 1
                raw = raw.replace(primed, primed[:-1] + b"\x01").replace(old_address, new_address)
                path.write_bytes(gzip.compress(raw))
                offline = ports()
                assert offline[0]["Primed"] == 1
                assert offline[0]["OfflineBuffer"]["Items"][0]["components"]["create:package_address"] == "Remote Depot"
                saved[0]["OfflineBuffer"]["Items"][0]["components"]["create:package_address"] = "Remote Depot"
            world.open()
            world.command(f"/tp @s {px+0.5} {py} {pz+2.5}")
            def loaded():
                world.call("wait", 4)
                return all(world.command(f"/execute if loaded {x} {y} {z}") == "Test passed"
                           for x, y, z in (STATION, POSTBOX))
            mp.until("both station and Postbox to reload", loaded, seconds=40)
            world.step_to(world.clock() + 1)
            contents = world.command(f"/data get block {px} {py} {pz} Items")
            expected_address = "Remote Depot" if args.primed else "Parcel Depot"
            assert PACKAGE in contents and expected_address in contents, contents
            world.stop()
            assert ports() == saved, ports()
            world.open()
            world.call("interact", px, py, pz, "south")
            mp.until("the retained package to appear in slot 17", lambda: menu.stack_item(world, 317) == PACKAGE)
            world.call("click-slot", 317)
            world.call("click-slot", 0)
            mp.until("the package to leave the Postbox", lambda: menu.stack_item(world, 317) is None)
            world.call("key", "escape", "tap")
            world.step_to(world.clock() + 1)
            world.stop()
            cleared = ports()
            assert len(cleared) == 1 and cleared[0]["OfflineBuffer"]["Items"] == [], cleared
            world.open()
            world.command("/gamemode creative")
            world.command(f"/tp @s {px+0.5} {py} {pz+2.5}")
            world.call("wait", 4)
            world.call("break", px, py, pz, "--timeout", 20)
            world.stop()
            assert ports() == [], ports()
            world.open()
            world.command(f"/setblock {px} {py} {pz} {BOX}")
            world.command(f'/data merge block {px} {py} {pz} {{Target:{{type:"create:train_station",relative_pos:[I;-2,0,-1]}},AddressFilter:"Depot"}}')
            world.step_to(world.clock() + 1)
            world.stop()
            recreated = ports()
            assert len(recreated) == 1 and recreated[0]["Pos"] == list(POSTBOX), recreated
            assert recreated[0]["OfflineBuffer"]["Items"] == [], recreated
            world.open()
            world.command(f"/setblock {px} {py} {pz} minecraft:air")
            world.stop()
            assert ports() == [], ports()
            print("The addressed package and station buffer survived chunk unload/reload and restart; both removal paths cleared the registry.")
            if args.primed:
                print("A synthetic offline buffer update restored its package and cleared Primed on reload.")


if __name__ == "__main__":
    main()
