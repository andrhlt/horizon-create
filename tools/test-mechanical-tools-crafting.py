#!/usr/bin/env python3
"""Run the original Wand and Potato Cannon recipes through powered crafters."""

import argparse
from pathlib import Path

from fixture_world import fixture_world

RECIPES = {
    "wand_of_symmetry": (
        (" G ", "GEG", " P ", " B ", " O "),
        (" v ", ">v<", " v ", " v ", " v "),
        {"G": "minecraft:glass", "E": "minecraft:ender_pearl",
         "P": "create:precision_mechanism", "B": "create:brass_ingot",
         "O": "minecraft:obsidian"},
    ),
    "potato_cannon": (
        ("LRSSS", "CC   "),
        ("v<<<<", "v<   "),
        {"L": "create:andesite_alloy", "R": "create:precision_mechanism",
         "S": "create:fluid_pipe", "C": "minecraft:copper_ingot"},
    ),
}
POINTING = {"v": "down", ">": "right", "<": "left"}
TOP, Z = 106, -9


def setup(world, recipe, arrows, ingredients):
    inlet = next(i for i, value in enumerate(recipe[0]) if value != " ")
    outlet = arrows[-1].index("v")
    output = f"{5 + outlet} {TOP - len(recipe)} {Z}"
    commands = [f"/setblock {output} minecraft:barrel"]
    commands.append(f"/setblock {5 + inlet} {TOP} {Z - 1} create:creative_motor[facing=south]{{ScrollValue:128}}")
    for row, (recipe_row, arrow_row) in enumerate(zip(recipe, arrows, strict=True)):
        for col, (item, arrow) in enumerate(zip(recipe_row, arrow_row, strict=True)):
            if item == " ":
                continue
            at = f"{5 + col} {TOP - row} {Z}"
            commands.append(f"/setblock {at} create:mechanical_crafter[facing=south,pointing={POINTING[arrow]}]")
            if (row, col) != (0, inlet):
                commands.append(f"/item replace block {at} container.0 with {ingredients[item]}")
    chute = f"{5 + inlet} {TOP + 1} {Z}"
    commands.extend((
        f"/setblock {chute} create:chute",
        f"/item replace block {chute} container.0 with {ingredients[recipe[0][inlet]]}",
        f"/data merge block {chute} {{ItemPosition:0.0f}}",
    ))
    world.commands(commands)
    return output


def run(args, result):
    with fixture_world(args, f"Crafting-{result}", pack=args.pack) as world:
        output = setup(world, *RECIPES[result])
        start = world.clock()
        for tick in range(1, 181):
            world.step_to(start + tick)
            if tick % 5 == 0:
                stored = world.command(f"/data get block {output} Items")
                if f'id: "create:{result}"' in stored:
                    print(f"{result} reached the output barrel by tick {tick}.", flush=True)
                    return
        raise RuntimeError(f"No {result} in output barrel: {stored}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("ctl", "client", "resources"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--pack", type=Path)
    parser.add_argument("--recipe", choices=tuple(RECIPES))
    args = parser.parse_args()
    for result in (args.recipe,) if args.recipe else RECIPES:
        run(args, result)


if __name__ == "__main__":
    main()
