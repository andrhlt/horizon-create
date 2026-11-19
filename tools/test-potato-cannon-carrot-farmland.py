#!/usr/bin/env python3
"""Compare carrot projectile impacts on farmland to pinned Java."""
import argparse
import csv
import math
from importlib import import_module
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from fixture_world import ROOT, fixture_world

carrot = import_module("test-potato-cannon-carrot")
multiplayer = import_module("test-multiplayer")
SOIL = (8,101,3)
ABOVE = (8,102,3)
SHOT = "@e[type=create:potato_projectile,limit=1]"


def run(args):
    with (ROOT / "fixtures/potato-cannon-carrot-farmland-java.csv").open() as f:
        rows = list(csv.DictReader(f))
    with (ROOT / "fixtures/potato-cannon-carrot-farmland-launch-java.csv").open() as f:
        launch = next(csv.DictReader(f))
    with TemporaryDirectory(prefix="hc-carrot-farm-") as tmp:
        with fixture_world(args, "CarrotFarmland", render=False, pack=args.pack) as host:
            host.commands(("/fill 6 101 1 11 106 6 minecraft:air", "/setblock 8 101 3 minecraft:farmland",
                           "/setblock 9 102 3 minecraft:stone"))
            with carrot.actor_for(host, args, Path(tmp)) as (actor, name):
                host.commands((f"/gamemode survival {name}", f"/clear {name}",
                    f"/tp {name} 9.25 103 3.65 0 90", f"/item replace entity {name} hotbar.0 with create:potato_cannon",
                    f"/item replace entity {name} hotbar.1 with minecraft:carrot 3"))
                multiplayer.until("cannon and carrots", lambda: actor.call("inventory")["counts"].get("minecraft:carrot") == 3
                                  and actor.call("inventory")["counts"].get("create:potato_cannon") == 1)
                actor.call("select", "create:potato_cannon")
                actor.call("use-item")
                multiplayer.until("carrot shot", lambda: actor.call("inventory")["counts"].get("minecraft:carrot") == 2)
                assert (actor.call("inventory")["held"] or {}).get("damage", 0) == 1
                shot = carrot.data(host, SHOT)
                assert shot is not None
                position = tuple(a-b for a,b in zip(carrot.vector(shot,"Pos"), SOIL, strict=True))
                actual = (*position, *carrot.vector(shot,"Motion"))
                expected = tuple(float(launch[k]) for k in ("x","y","z","vx","vy","vz"))
                assert all(math.isclose(a,b,abs_tol=1e-6) for a,b in zip(actual,expected,strict=True)), (actual, expected)
                start = host.clock()
                for row in rows:
                    host.step_to(start + int(row["tick"]))
                    soil = host.call("block", *SOIL)
                    above = host.call("block", *ABOVE)
                    assert soil["block"] == "minecraft:" + row["soil"], (row, soil)
                    assert "moisture=" + row["moisture"] in soil["state"], (row, soil)
                    assert above["block"] == "minecraft:" + row["above"], (row, above)
                    assert (carrot.data(host, SHOT) is not None) == (int(row["projectiles"]) > 0), row
    print("Carrot farmland impact and no planting matched pinned Java.")


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__)
    for key in ("ctl","client","resources"):
        p.add_argument(key,type=lambda path:Path(path).resolve(strict=True))
    p.add_argument("--pack",type=Path,default=ROOT/".local/create.hmod")
    p.add_argument("--lan",action="store_true")
    os.environ["HORIZON_NO_AUDIO"]="1"
    run(p.parse_args())
